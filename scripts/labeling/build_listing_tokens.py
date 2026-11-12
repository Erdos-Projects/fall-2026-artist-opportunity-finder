"""Token windows for EVERY cleaned listing, so the final model can extract fields for matching.

Reads data/clean/listings.jsonl, tokenizes each listing's page_text with the RoBERTa tokenizer
(windows of 400 tokens, overlap 80, same as training), and writes data/labeled/tokens_roberta_all.jsonl.
The windows have no labels (all -100). Predict on them in Colab (probabilities per window), then
models/extraction/extract_all.py decodes them into fields.

  python scripts/labeling/build_listing_tokens.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_token_data import clean_offsets, windows  # noqa: E402
from silver_common import CLEAN, LABELED  # noqa: E402


def main():
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained("roberta-base")
    rows, n_listings, empty = [], 0, 0
    with open(CLEAN / "listings.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            text = r.get("page_text") or ""
            n_listings += 1
            if not text.strip():
                empty += 1
                continue
            enc = tok(text, add_special_tokens=False, return_offsets_mapping=True, truncation=False)
            ids = enc["input_ids"]
            if not ids:
                empty += 1
                continue
            offsets = clean_offsets(text, enc["offset_mapping"])
            for first, last in windows(len(ids)):
                w_off = offsets[first:last]
                rows.append({"page_key": r["listing_id"], "listing_ids": [r["listing_id"]], "split": "all",
                             "char_start": w_off[0][0], "char_end": w_off[-1][1],
                             "input_ids": [tok.cls_token_id] + ids[first:last] + [tok.sep_token_id],
                             "labels": [-100] * (last - first + 2),
                             "offsets": [[-1, -1]] + [list(o) for o in w_off] + [[-1, -1]]})
    out = LABELED / "tokens_roberta_all.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for w in rows:
            f.write(json.dumps(w) + "\n")
    print(f"listings: {n_listings} (no page text: {empty}); windows: {len(rows)}; written: {out.name}")


if __name__ == "__main__":
    main()
