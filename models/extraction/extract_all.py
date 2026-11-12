"""Turn the final model's predictions on every cleaned listing into extracted fields.

Input: data/labeled/all_probs_roberta_neg3.npz (made in Colab from tokens_roberta_all.jsonl).
Decodes windows into page spans (o_scale 1.0), snaps spans to whole words, and writes
data/labeled/extracted_all.json:  {listing_id: {"deadline": [text, ...], "fee": [...], "career_stage": [...],
                                             "location": [...], "medium": [...], "has_text": bool}}
Listings with no page text get empty lists and has_text false ("not listed" for every field).

  python models/extraction/extract_all.py
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from decode import decode_all, snap_to_words  # noqa: E402

LABELED = ROOT / "data" / "labeled"
FIELDS = ["deadline", "fee", "career_stage", "location", "medium"]


def main():
    z = np.load(LABELED / "all_probs_roberta_neg3.npz")
    probs = [z[f"arr_{i}"].astype(float) for i in range(len(z.files))]
    wins = [json.loads(l) for l in open(LABELED / "tokens_roberta_all.jsonl", encoding="utf-8")]
    assert len(probs) == len(wins), (len(probs), len(wins))
    for w, p in zip(wins, probs):
        assert p.shape[0] == len(w["input_ids"])
    lm = json.loads((LABELED / "label_map_roberta.json").read_text(encoding="utf-8"))
    id2label = {i: l for i, l in enumerate(lm["labels"])}
    by_page = decode_all(wins, probs, id2label, o_scale=1.0)

    out, n_spans = {}, {f: 0 for f in FIELDS}
    with open(ROOT / "data" / "clean" / "listings.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            lid, text = r["listing_id"], r.get("page_text") or ""
            spans = snap_to_words(by_page.get(lid, []), text) if text else []
            rec = {fld: [] for fld in FIELDS}
            for label, s, e in spans:
                rec[label].append(text[s:e].strip())
                n_spans[label] += 1
            rec["has_text"] = bool(text.strip()) and lid in by_page
            out[lid] = rec
    (LABELED / "extracted_all.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    n = len(out)
    print(f"listings: {n}; with extracted text: {sum(v['has_text'] for v in out.values())}")
    for fld in FIELDS:
        have = sum(bool(v[fld]) for v in out.values())
        print(f"  {fld}: {n_spans[fld]} spans, {have} listings have at least one")


if __name__ == "__main__":
    main()
