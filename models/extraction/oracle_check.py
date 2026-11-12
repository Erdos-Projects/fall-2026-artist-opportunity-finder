"""Round trip test for the whole token pipeline, with no model.

Feed the true labels in as if they were perfect predictions, decode them back to
page spans, and score them against the silver val spans with evaluate.py. If the
alignment, the window overlap handling, the decoder, and the scorer are right, the
score is close to 1.0. It cannot be exactly 1.0 only where two silver spans overlap
and one was dropped (tags cannot overlap).

  python models/extraction/oracle_check.py
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate as ev  # noqa: E402
from decode import decode_all  # noqa: E402

LABELED = ROOT / "data" / "labeled"


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else ""   # e.g. "roberta" for the RoBERTa token files
    lm = json.loads((LABELED / (f"label_map_{tag}.json" if tag else "label_map.json")).read_text(encoding="utf-8"))
    id2label = {i: l for i, l in enumerate(lm["labels"])}
    windows = [json.loads(l) for l in open(LABELED / (f"tokens_{tag}_val.jsonl" if tag else "tokens_val.jsonl"),
                                           encoding="utf-8")]
    probs = []
    for w in windows:
        p = np.zeros((len(w["labels"]), len(id2label)))
        for i, lab in enumerate(w["labels"]):
            p[i, lab if lab >= 0 else 0] = 1.0
        probs.append(p)
    by_page = decode_all(windows, probs, id2label)

    ev_val = json.loads((LABELED / "eval_val.json").read_text(encoding="utf-8"))
    gold = {lid: [tuple(s) for s in v["spans"]] for lid, v in ev_val.items()}
    texts = {lid: v["text"] for lid, v in ev_val.items()}
    pred = {lid: by_page.get(v["page_key"], []) for lid, v in ev_val.items()}
    res = ev.score(gold, pred, texts)
    print(ev.to_markdown(res, "Oracle round trip on silver val (should be about 1.0)"))


if __name__ == "__main__":
    main()
