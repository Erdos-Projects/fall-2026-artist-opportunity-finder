"""Scoring for field extraction. Model agnostic: the regex baseline, DeBERTa, and
the LLM all produce the same span format and are scored by this file.

Span format, everywhere: (label, start, end), character offsets on the full
cleaned page (page_text), end exclusive.

What is measured, per field and micro averaged:
  - exact span P/R/F1: start and end must both match the gold span
  - overlap span P/R/F1: any shared character with an unmatched gold span of the
    same label counts (one gold span can be matched once)
  - value match for deadline and fee: the parsed value (a date, an amount), so
    "June 1" and "June 1, 2026" can be compared fairly, per listing
  - hallucination rate: predicted spans whose text is not on the page

Gold sources:
  silver   data/labeled/silver.jsonl (a development check only, never the final number)
  ls       a Label Studio JSON export of the gold tasks
"""
import json
import re
from collections import defaultdict
from pathlib import Path

FIELDS = ["deadline", "fee", "career_stage", "location", "medium"]
MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


# ---------- loading gold ----------

def load_silver(path, split="val"):
    """{listing_id: [(label, start, end)]} from silver.jsonl, for one split."""
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["split"] == split:
                out[r["listing_id"]] = [(s["label"], s["start"], s["end"]) for s in r["spans"]]
    return out


def load_label_studio(path):
    """{listing_id: [(label, start, end)]} from a Label Studio JSON export.

    Tasks with no finished annotation are skipped (reported by the caller)."""
    tasks = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {}
    for t in tasks:
        anns = [a for a in t.get("annotations", []) if not a.get("was_cancelled")]
        if not anns:
            continue
        spans = []
        for r in anns[0]["result"]:
            v = r.get("value", {})
            if r.get("type") == "labels" and v.get("labels"):
                spans.append((v["labels"][0], v["start"], v["end"]))
        out[t["data"]["listing_id"]] = spans
    return out


# ---------- value parsing (for exact match on dates and fees) ----------

def parse_date(text):
    """(year or None, month, day) from a date string, or None."""
    t = text.lower().replace(",", " ")
    if m := re.search(r"(\d{4})-(\d{2})-(\d{2})", t):
        return int(m[1]), int(m[2]), int(m[3])
    if m := re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b", t):
        y = int(m[3]); y = y + 2000 if y < 100 else y
        return y, int(m[1]), int(m[2])
    mon = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", t)
    day = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\b", t)
    year = re.search(r"\b(20\d{2})\b", t)
    if mon and day:
        return (int(year[1]) if year else None), MONTHS[mon[1]], int(day[1])
    return None


def parse_fee(text):
    m = re.search(r"\d[\d,]*(?:\.\d+)?", text)
    return float(m[0].replace(",", "")) if m else None


def parse_value(label, text):
    if label == "deadline":
        return parse_date(text)
    if label == "fee":
        return parse_fee(text)
    return None


def values_equal(label, a, b):
    if a is None or b is None:
        return False
    if label == "deadline":  # year only has to agree when both sides wrote one
        return a[1:] == b[1:] and (a[0] is None or b[0] is None or a[0] == b[0])
    return a == b


# ---------- span scoring ----------

def prf(tp, n_pred, n_gold):
    p = tp / n_pred if n_pred else 0.0
    r = tp / n_gold if n_gold else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": p, "recall": r, "f1": f, "tp": tp, "n_pred": n_pred, "n_gold": n_gold}


def match_spans(pred, gold, exact):
    """One-to-one greedy match. Returns the number of predicted spans that matched."""
    used, tp = set(), 0
    for p in pred:
        for i, g in enumerate(gold):
            if i in used:
                continue
            hit = (p[0] == g[0]) if exact else (p[0] < g[1] and g[0] < p[1])
            if hit:
                used.add(i)
                tp += 1
                break
    return tp


def score(gold, pred, texts):
    """gold, pred: {listing_id: [(label, start, end)]}; texts: {listing_id: page_text}.

    Only listings present in gold are scored. A listing with no prediction counts
    as predicting nothing."""
    counts = {m: {f: [0, 0, 0] for f in FIELDS} for m in ("exact", "overlap")}  # tp, n_pred, n_gold
    value = {f: [0, 0, 0] for f in ("deadline", "fee")}
    listing_value_match = {f: [0, 0] for f in ("deadline", "fee")}  # listings with gold value: all found
    n_pred_total, n_bad = 0, 0

    for lid, g_spans in gold.items():
        p_spans = pred.get(lid, [])
        text = texts[lid]
        n_pred_total += len(p_spans)
        n_bad += sum(1 for (_, s, e) in p_spans if not (0 <= s < e <= len(text)) or not text[s:e].strip())
        for f in FIELDS:
            g = [(s, e) for (l, s, e) in g_spans if l == f]
            p = [(s, e) for (l, s, e) in p_spans if l == f]
            for mode in ("exact", "overlap"):
                c = counts[mode][f]
                c[0] += match_spans(p, g, mode == "exact"); c[1] += len(p); c[2] += len(g)
            if f in value:
                gv = [parse_value(f, text[s:e]) for s, e in g]
                pv = [parse_value(f, text[s:e]) for s, e in p]
                gv, pv = [v for v in gv if v is not None], [v for v in pv if v is not None]
                used, tp = set(), 0
                for v in pv:
                    for i, w in enumerate(gv):
                        if i not in used and values_equal(f, v, w):
                            used.add(i); tp += 1; break
                value[f][0] += tp; value[f][1] += len(pv); value[f][2] += len(gv)
                if gv:
                    listing_value_match[f][1] += 1
                    listing_value_match[f][0] += tp == len(gv)

    result = {"n_listings": len(gold), "span": {}, "value": {}, "listing_value_recall_all": {}}
    for mode in ("exact", "overlap"):
        per = {f: prf(*counts[mode][f]) for f in FIELDS}
        tot = [sum(counts[mode][f][i] for f in FIELDS) for i in range(3)]
        per["micro"] = prf(*tot)
        result["span"][mode] = per
    for f, (tp, npred, ngold) in value.items():
        result["value"][f] = prf(tp, npred, ngold)
        hit, total = listing_value_match[f]
        result["listing_value_recall_all"][f] = {"listings": total, "all_values_found": hit,
                                                  "rate": hit / total if total else 0.0}
    result["hallucination"] = {"predicted_spans": n_pred_total, "invalid_spans": n_bad,
                               "rate": n_bad / n_pred_total if n_pred_total else 0.0}
    return result


def to_markdown(res, title):
    lines = [f"## {title}", "", f"Listings scored: {res['n_listings']}", "",
             "| Field | Exact P | Exact R | Exact F1 | Overlap P | Overlap R | Overlap F1 | Gold | Pred |",
             "|---|---|---|---|---|---|---|---|---|"]
    for f in FIELDS + ["micro"]:
        e, o = res["span"]["exact"][f], res["span"]["overlap"][f]
        lines.append(f"| {f} | {e['precision']:.2f} | {e['recall']:.2f} | {e['f1']:.2f} | "
                     f"{o['precision']:.2f} | {o['recall']:.2f} | {o['f1']:.2f} | {e['n_gold']} | {e['n_pred']} |")
    lines += ["", "Value match (parsed date or amount):", "",
              "| Field | P | R | F1 | Listings with gold | All gold values found |", "|---|---|---|---|---|---|"]
    for f, v in res["value"].items():
        a = res["listing_value_recall_all"][f]
        lines.append(f"| {f} | {v['precision']:.2f} | {v['recall']:.2f} | {v['f1']:.2f} | "
                     f"{a['listings']} | {a['all_values_found']} ({a['rate']:.0%}) |")
    h = res["hallucination"]
    lines += ["", f"Invalid or unsupported spans: {h['invalid_spans']} of {h['predicted_spans']} ({h['rate']:.1%})"]
    return "\n".join(lines)
