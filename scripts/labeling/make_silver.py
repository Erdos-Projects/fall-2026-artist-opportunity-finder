"""Combine the three silver sources into data/labeled/silver.jsonl.

Sources: distant supervision, regex, and the LLM (cached by silver_llm.py).
Spans from different sources that overlap are one candidate. For deadline and
fee, which have three sources, a candidate is:

  agreed     two or more sources found it. Kept.
  llm_only   only the LLM found it. Kept by default, listed for review.
  rule_only  only distant supervision or regex found it. Dropped by default,
             listed for review.

Career stage, location and medium only have the LLM, so every span is "single"
and kept. Their quality is checked on a random sample instead.

Review: open data/labeled/silver_review.csv, put y or n in the keep column for
any row you want to force, and rerun. Decisions survive reruns.

  python scripts/labeling/make_silver.py
  python scripts/labeling/make_silver.py --resample    # draw a new precision sample
"""
import argparse
import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from silver_common import FIELDS, LABELED, ROOT, load_listings, silver_ids
from silver_distant import distant_spans
from silver_llm import cache_path, llm_spans, PROMPT_VERSION
from silver_regex import regex_spans

RULE_FIELDS = ("deadline", "fee")
PRIORITY = {"llm": 0, "regex": 1, "distant": 2}
SAMPLE_SIZE = 50
SEED = 42
REVIEW = LABELED / "silver_review.csv"
SAMPLE = LABELED / "silver_precision_sample.csv"
OUT = LABELED / "silver.jsonl"
REPORT = LABELED / "silver_report.md"


def cluster(candidates):
    """Group overlapping (start, end, source) spans. Returns a list of clusters."""
    groups = []
    for start, end, source in sorted(candidates):
        if groups and start < groups[-1]["end"]:
            groups[-1]["end"] = max(groups[-1]["end"], end)
            groups[-1]["spans"].append((start, end, source))
        else:
            groups.append({"end": end, "spans": [(start, end, source)]})
    return groups


def candidates_for(listing, record):
    """Return ({field: [(s, e, source)]}, llm_stats) for one listing."""
    by_field = {f: [] for f in FIELDS}
    llm, stats = llm_spans(listing, record)
    for field, spans in llm.items():
        by_field[field] += [(s, e, "llm") for s, e in spans]
    for source, found in (("regex", regex_spans(listing)), ("distant", distant_spans(listing))):
        for field, spans in found.items():
            by_field[field] += [(s, e, source) for s, e in spans]
    return by_field, stats


def decide(field, sources):
    """Return (status, keep_by_default) for a candidate."""
    if field not in RULE_FIELDS:
        return "single", True
    if len(sources) >= 2:
        return "agreed", True
    if sources == {"llm"}:
        return "llm_only", True
    return "rule_only", False


def followed_links():
    """{url_key of an organizer page: the deeper page that was followed, if any}."""
    sys.path.insert(0, str(ROOT / "scripts" / "scrapers"))
    from common import url_key

    links = {}
    with open(ROOT / "data" / "raw" / "opportunity_pages.jsonl", encoding="utf-8") as f:
        for line in f:
            page = json.loads(line)
            if page.get("linked_url"):
                links[url_key(page["source_url"])] = page["linked_url"]
    return links


def link_columns(listing, links):
    """Where a person can check a span: the organizer page, and the deeper page if one was used."""
    return {"title": listing["title"], "page_url": listing.get("website") or "",
            "followed_url": links.get(listing.get("key"), "")}


def read_decisions():
    if not REVIEW.exists():
        return {}
    with open(REVIEW, encoding="utf-8", newline="") as f:
        return {row["key"]: row["keep"].strip().lower() for row in csv.DictReader(f)}


def context(text, start, end, pad=70):
    return text[max(0, start - pad): end + pad].replace("\n", " ")


def build(split_of, rows, decisions, links):
    """Return (silver records, review rows, llm stats, overlap drops, missing ids)."""
    records, review, llm_stats, missing = [], [], Counter(), []
    overlap_drops = 0
    for lid, split in split_of.items():
        path = cache_path(lid)
        if not path.exists():
            missing.append(lid)
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("prompt_version") != PROMPT_VERSION:
            missing.append(lid)
            continue
        listing = rows[lid]
        text = listing["page_text"]
        by_field, stats = candidates_for(listing, record)
        llm_stats.update(stats)

        kept = []
        for field in FIELDS:
            for group in cluster(by_field[field]):
                sources = {src for _, _, src in group["spans"]}
                s, e, _ = min(group["spans"], key=lambda sp: (PRIORITY[sp[2]], sp[0]))
                status, keep = decide(field, sources)
                key = f"{lid}|{field}|{s}|{e}"
                if status in ("llm_only", "rule_only"):
                    review.append({
                        "key": key, "listing_id": lid, "split": split, "label": field,
                        "status": status, "sources": "+".join(sorted(sources)),
                        "text": text[s:e], "context": context(text, s, e),
                        **link_columns(listing, links),
                        "default": "y" if keep else "n", "keep": decisions.get(key, ""),
                    })
                    keep = {"y": True, "n": False}.get(decisions.get(key, ""), keep)
                if keep:
                    kept.append({"label": field, "start": s, "end": e, "text": text[s:e],
                                 "sources": sorted(sources), "status": status})

        # BIO tags cannot overlap, so a span that overlaps a longer kept span is dropped
        kept.sort(key=lambda sp: (sp["start"], -(sp["end"] - sp["start"])))
        final = []
        for sp in kept:
            if final and sp["start"] < final[-1]["end"]:
                overlap_drops += 1
                continue
            final.append(sp)
        records.append({"listing_id": lid, "split": split, "spans": final})
    return records, review, llm_stats, overlap_drops, missing


def write_csv(path, fieldnames, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_report(records, review, llm_stats, overlap_drops, missing):
    items = llm_stats["items"] or 1
    lines = ["# Silver label report", "", "Generated by `scripts/labeling/make_silver.py`.", ""]
    lines += [f"Listings labeled: {len(records)} (missing LLM output: {len(missing)})", ""]
    lines += ["## Spans kept, by field and split", "", "| Field | train | val |", "|---|---|---|"]
    for field in FIELDS:
        counts = {s: sum(sp["label"] == field for r in records if r["split"] == s for sp in r["spans"])
                  for s in ("train", "val")}
        lines.append(f"| {field} | {counts['train']} | {counts['val']} |")
    lines += ["", "## Status of kept spans", ""]
    status = Counter(sp["status"] for r in records for sp in r["spans"])
    lines += [f"- {k}: {v}" for k, v in sorted(status.items())]
    lines += ["", "## LLM quote check (hallucination rate)", ""]
    lines += [f"- Mentions returned: {llm_stats['items']}",
              f"- Found verbatim with context: {llm_stats['ok']}",
              f"- Found verbatim, context not matched: {llm_stats['no_context']}",
              f"- Text not found on the page (dropped): {llm_stats['text_not_found']} "
              f"({llm_stats['text_not_found'] / items:.1%})",
              f"- Text found several times, no context to pick one (dropped): {llm_stats['ambiguous']}"]
    lines += ["", "## Review queue", ""]
    queue = Counter((r["label"], r["status"]) for r in review)
    lines += [f"- {k[0]} {k[1]}: {v}" for k, v in sorted(queue.items())]
    decided = sum(bool(r["keep"]) for r in review)
    lines += [f"- decided so far: {decided} of {len(review)}",
              "", f"Spans dropped for overlapping another kept span: {overlap_drops}"]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resample", action="store_true", help="draw a new precision sample")
    args = parser.parse_args()

    ids = silver_ids()
    split_of = {lid: s for s in ("train", "val") for lid in ids[s]}
    rows = load_listings(split_of)
    links = followed_links()
    records, review, llm_stats, overlap_drops, missing = build(split_of, rows, read_decisions(), links)

    OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")
    review.sort(key=lambda r: (r["listing_id"], r["label"]))
    write_csv(REVIEW, ["key", "listing_id", "split", "label", "status", "sources",
                       "text", "context", "title", "page_url", "followed_url",
                       "default", "keep"], review)

    if args.resample or not SAMPLE.exists():
        flat = [(r["listing_id"], sp) for r in records for sp in r["spans"]]
        picked = random.Random(SEED).sample(flat, min(SAMPLE_SIZE, len(flat)))
        write_csv(SAMPLE, ["listing_id", "label", "text", "context", "title", "page_url",
                           "followed_url", "correct"], [
            {"listing_id": lid, "label": sp["label"], "text": sp["text"],
             "context": context(rows[lid]["page_text"], sp["start"], sp["end"]),
             **link_columns(rows[lid], links), "correct": ""}
            for lid, sp in picked])
    write_report(records, review, llm_stats, overlap_drops, missing)
    if missing:
        print(f"\nNo LLM output for {len(missing)} listings. Rerun silver_llm.py: {missing[:5]}")


if __name__ == "__main__":
    main()
