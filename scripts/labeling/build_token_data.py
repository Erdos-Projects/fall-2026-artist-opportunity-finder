"""Turn silver labels into token-level training data for DeBERTa.

Why this does not use data/labeled/chunks.jsonl: those chunks are cut by word
count, and 43 percent of them are over 512 real DeBERTa tokens (long image URLs
and markdown split into thousands of pieces). Here each page is tokenized once,
labels are placed on the tokens of the whole page, and windows are cut from the
tokens. Labels and tokens come from the same tokenization, so they cannot drift
apart at chunk edges.

Steps per page:
  1. Collect the silver spans of every listing on the page (a few pages are shared).
     Overlapping spans keep the longer one.
  2. Tokenize the full page_text with character offsets.
  3. A token inside a span gets B-<label> (first) or I-<label>. Others get O.
  4. Cut windows of WINDOW tokens with OVERLAP tokens shared, add [CLS] and [SEP].
     Special tokens get label -100, which the loss ignores.

Writes data/labeled/tokens_<split>.jsonl, label_map.json and token_report.md.

  python scripts/labeling/build_token_data.py
  python scripts/labeling/build_token_data.py --show 3     # print 3 windows to check by eye
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from silver_common import CLEAN, FIELDS, LABELED  # noqa: E402

MODEL = "microsoft/deberta-v3-base"
WINDOW, OVERLAP = 400, 80  # content tokens per window; leaves room for [CLS] and [SEP]
LABELS = ["O"] + [f"{p}-{f}" for f in FIELDS for p in ("B", "I")]
LABEL2ID = {l: i for i, l in enumerate(LABELS)}


def load_pages(split_of):
    """{page_key: {text, split, spans, listing_ids}} for the listings in split_of."""
    silver = {}
    with open(LABELED / "silver.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            silver[r["listing_id"]] = r
    pages = {}
    with open(CLEAN / "listings.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            lid = r["listing_id"]
            if lid not in silver or silver[lid]["split"] not in split_of:
                continue
            p = pages.setdefault(r["key"], {"text": r["page_text"], "split": silver[lid]["split"],
                                            "spans": set(), "listing_ids": []})
            if p["text"] != r["page_text"]:
                raise SystemExit(f"listings sharing {r['key']} have different page text")
            p["listing_ids"].append(lid)
            p.setdefault("by_listing", {})[lid] = [(s["label"], s["start"], s["end"]) for s in silver[lid]["spans"]]
            for s in silver[lid]["spans"]:
                p["spans"].add((s["start"], s["end"], s["label"]))
    for p in pages.values():
        # drop overlaps, longer span first (tags cannot overlap)
        keep = []
        for sp in sorted(p["spans"], key=lambda x: (-(x[1] - x[0]), x[0])):
            if all(sp[1] <= k[0] or k[1] <= sp[0] for k in keep):
                keep.append(sp)
        p["spans"] = sorted(keep)
    return pages


def tag_tokens(text, offsets, spans):
    """Return (tags, stats). tags[i] is a label string for token i; offsets are (start, end)."""
    tags = ["O"] * len(offsets)
    stats = Counter()
    for start, end, label in spans:
        inside = [i for i, (s, e) in enumerate(offsets) if s < end and e > start]
        if not inside:
            stats["span_no_token"] += 1
            continue
        for i in inside:
            s, e = offsets[i]
            if s < start or e > end:
                stats["straddling_token"] += 1  # token reaches outside the span
        for k, i in enumerate(inside):
            tags[i] = f"{'B' if k == 0 else 'I'}-{label}"
        stats["spans_placed"] += 1
    return tags, stats


def windows(n_tokens):
    """Yield (first, last_exclusive) token windows over n_tokens."""
    step = WINDOW - OVERLAP
    i = 0
    while True:
        j = min(i + WINDOW, n_tokens)
        yield i, j
        if j == n_tokens:
            break
        i += step


def clean_offsets(text, offsets):
    """Move a token's start past leading spaces (sentencepiece offsets can include them)."""
    out = []
    for s, e in offsets:
        while s < e and text[s].isspace():
            s += 1
        out.append((s, e))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", type=int, default=0, help="print N windows with tokens and tags")
    ap.add_argument("--model", default=MODEL, help="Hugging Face model whose tokenizer is used")
    ap.add_argument("--tag", default="", help="file name tag for a second model, for example roberta")
    args = ap.parse_args()
    t = f"{args.tag}_" if args.tag else ""   # files: tokens_<tag>_<split>.jsonl, label_map_<tag>.json

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(args.model)
    cls_id, sep_id = tok.cls_token_id, tok.sep_token_id

    pages = load_pages({"train", "val"})
    rows = {"train": [], "val": []}
    stats, label_tokens = Counter(), Counter()
    spans_total = Counter()
    mismatch = []
    shown = 0

    for key, p in sorted(pages.items()):
        text = p["text"]
        enc = tok(text, add_special_tokens=False, return_offsets_mapping=True, truncation=False)
        ids = enc["input_ids"]
        offsets = clean_offsets(text, enc["offset_mapping"])
        tags, st = tag_tokens(text, offsets, p["spans"])
        stats.update(st)
        spans_total[p["split"]] += len(p["spans"])
        # does the labeled token range give the span text back?
        for start, end, label in p["spans"]:
            toks = [i for i, t in enumerate(tags) if t.endswith(f"-{label}") and offsets[i][0] >= start - 1 and offsets[i][1] <= end + 1]
            if toks:
                got = text[offsets[toks[0]][0]:offsets[toks[-1]][1]]
                if got.strip() != text[start:end].strip():
                    mismatch.append((key, label, text[start:end], got))
        for w_first, w_last in windows(len(ids)):
            w_ids = [cls_id] + ids[w_first:w_last] + [sep_id]
            w_tags = tags[w_first:w_last]
            labels = [-100] + [LABEL2ID[t] for t in w_tags] + [-100]
            w_off = offsets[w_first:w_last]
            rows[p["split"]].append({
                "page_key": key, "listing_ids": p["listing_ids"], "split": p["split"],
                "char_start": w_off[0][0], "char_end": w_off[-1][1],
                "input_ids": w_ids, "labels": labels,
                "offsets": [[-1, -1]] + [list(o) for o in w_off] + [[-1, -1]],
            })
            label_tokens.update(w_tags)
            if shown < args.show and any(t != "O" for t in w_tags):
                shown += 1
                print(f"\n=== example {shown}: page {key[:60]}  split={p['split']}  tokens {w_first}-{w_last} ===")
                for i in range(w_first, w_last):
                    if tags[i] != "O":
                        lo, hi = max(w_first, i - 3), min(w_last, i + 4)
                        print(f"  {tags[i]:<16} token={tok.convert_ids_to_tokens(ids[i])!r:<18} "
                              f"chars={offsets[i]} text={text[offsets[i][0]:offsets[i][1]]!r:<16} "
                              f"around: {' '.join(tok.convert_ids_to_tokens(ids[lo:hi]))}")
                print("  silver spans in this window:", [(s, e, l, text[s:e]) for s, e, l in p["spans"]
                                                          if s >= w_off[0][0] and e <= w_off[-1][1]])

    for split, data in rows.items():
        path = LABELED / f"tokens_{t}{split}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for r in data:
                f.write(json.dumps(r) + "\n")
    # val listings with their page text and silver spans, for scoring predictions with evaluate.py
    eval_val = {lid: {"page_key": key, "text": p["text"], "spans": [list(s) for s in spans]}
                for key, p in pages.items() if p["split"] == "val"
                for lid, spans in p["by_listing"].items()}
    (LABELED / "eval_val.json").write_text(json.dumps(eval_val, ensure_ascii=False), encoding="utf-8")
    (LABELED / f"label_map{'_' + args.tag if args.tag else ''}.json").write_text(
        json.dumps({"labels": LABELS, "label2id": LABEL2ID, "model": args.model,
                    "window": WINDOW, "overlap": OVERLAP}, indent=1), encoding="utf-8")

    lines = ["# Token data report", "", "Generated by `scripts/labeling/build_token_data.py`.", "",
             f"Tokenizer: `{args.model}`. Window {WINDOW} tokens, overlap {OVERLAP}, plus [CLS] and [SEP].", ""]
    lines += ["| Split | Pages | Windows | Tokens (with specials) | Windows with a label | Silver spans on pages |", "|---|---|---|---|---|---|"]
    for split, data in rows.items():
        n_pages = len({r["page_key"] for r in data})
        n_tok = sum(len(r["input_ids"]) for r in data)
        n_lab = sum(any(l > 0 for l in r["labels"]) for r in data)
        lines.append(f"| {split} | {n_pages} | {len(data)} | {n_tok} | {n_lab} | {spans_total[split]} |")
    longest = max((len(r["input_ids"]) for d in rows.values() for r in d), default=0)
    lines += ["", f"Longest window: {longest} tokens (limit 512).", "",
              "## Alignment checks", "",
              f"- Spans placed on tokens: {stats['spans_placed']}",
              f"- Spans that covered no token: {stats['span_no_token']}",
              f"- Tokens that reach outside their span (kept as part of the span): {stats['straddling_token']}",
              f"- Spans whose labeled tokens do not give back the span text: {len(mismatch)}", "",
              "## Tokens per tag (content tokens)", ""]
    lines += [f"- {l}: {label_tokens[l]}" for l in LABELS]
    if mismatch:
        lines += ["", "## Text mismatches (first 10)", ""]
        lines += [f"- {k[:40]} {lab}: span {a!r} vs tokens {b!r}" for k, lab, a, b in mismatch[:10]]
    (LABELED / f"token_report{'_' + args.tag if args.tag else ''}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines).encode("ascii", "replace").decode())


if __name__ == "__main__":
    main()
