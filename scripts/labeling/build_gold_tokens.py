"""Prepare the gold set for scoring: drop excluded listings, make token windows for a model.

Reads data/labeled/gold_export.json (Label Studio export of the 40 gold tasks) and writes
  gold_scored.json            the export without the excluded listings (Label Studio format),
                              for regex_baseline.py --gold
  eval_gold.json              {listing_id: {page_key, text, spans}} like eval_val.json, for scoring
  tokens_<tag>_gold.jsonl     token windows with no labels (all -100) for the model to predict on

The excluded listings (dead pages, a festival, a winners announcement, a past programs page, a degree
program) are not open calls. The decision is recorded in Plans/Progress.md and was made before any gold score.

  python scripts/labeling/build_gold_tokens.py --model roberta-base --tag roberta
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_token_data import WINDOW, OVERLAP, clean_offsets, windows  # noqa: E402
from silver_common import LABELED  # noqa: E402

EXCLUDED = {
    "Lc2fa6fc730": "page not found (Field of Vision)",
    "L295c71a36a": "page not found (San Bruno call, 404)",
    "L5185bf8fda": "page not found (Smack Mellon)",
    "Ldb8dfc161e": "festival, not an open call",
    "Lf10a98f567": "winners announcement, call is over",
    "L11145d6827": "past programs page, no open call",
    "L301e92c4fb": "degree program page, not a grant, residency or open call",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="roberta-base")
    ap.add_argument("--tag", default="roberta")
    args = ap.parse_args()

    tasks = json.loads((LABELED / "gold_export.json").read_text(encoding="utf-8"))
    kept = [t for t in tasks if t["data"]["listing_id"] not in EXCLUDED]
    unknown = set(EXCLUDED) - {t["data"]["listing_id"] for t in tasks}
    if unknown:
        raise SystemExit(f"excluded ids not in the export: {unknown}")
    (LABELED / "gold_scored.json").write_text(json.dumps(kept, ensure_ascii=False), encoding="utf-8")

    eval_gold = {}
    for t in kept:
        lid, text = t["data"]["listing_id"], t["data"]["text"]
        anns = [a for a in t.get("annotations", []) if not a.get("was_cancelled")]
        spans = []
        for r in (anns[0]["result"] if anns else []):
            v = r.get("value", {})
            if r.get("type") == "labels" and v.get("labels"):
                if text[v["start"]:v["end"]] != v["text"]:
                    raise SystemExit(f"offset mismatch in {lid}: {v['text']!r}")
                spans.append([v["labels"][0], v["start"], v["end"]])
        eval_gold[lid] = {"page_key": lid, "text": text, "spans": spans}
    (LABELED / "eval_gold.json").write_text(json.dumps(eval_gold, ensure_ascii=False), encoding="utf-8")

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(args.model)
    rows = []
    for lid, v in sorted(eval_gold.items()):
        text = v["text"]
        enc = tok(text, add_special_tokens=False, return_offsets_mapping=True, truncation=False)
        ids = enc["input_ids"]
        offsets = clean_offsets(text, enc["offset_mapping"])
        for first, last in windows(len(ids)):
            w_off = offsets[first:last]
            rows.append({"page_key": lid, "listing_ids": [lid], "split": "gold",
                         "char_start": w_off[0][0], "char_end": w_off[-1][1],
                         "input_ids": [tok.cls_token_id] + ids[first:last] + [tok.sep_token_id],
                         "labels": [-100] * (last - first + 2),
                         "offsets": [[-1, -1]] + [list(o) for o in w_off] + [[-1, -1]]})
    out = LABELED / f"tokens_{args.tag}_gold.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    n_spans = sum(len(v["spans"]) for v in eval_gold.values())
    print(f"gold listings kept: {len(eval_gold)} of {len(tasks)} (excluded {len(EXCLUDED)})")
    print(f"gold spans: {n_spans}; windows: {len(rows)}; longest window: {max(len(r['input_ids']) for r in rows)} tokens")
    print(f"written: gold_scored.json, eval_gold.json, {out.name}")


if __name__ == "__main__":
    main()
