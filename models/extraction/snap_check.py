"""Score the saved val predictions before and after word snapping (no GPU, no model).

  python models/extraction/snap_check.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate as ev  # noqa: E402
from decode import snap_to_words  # noqa: E402

LABELED = ROOT / "data" / "labeled"
ev_val = json.loads((LABELED / "eval_val.json").read_text(encoding="utf-8"))
gold = {lid: [tuple(s) for s in v["spans"]] for lid, v in ev_val.items()}
texts = {lid: v["text"] for lid, v in ev_val.items()}

print("| run | spans changed | micro exact P / R / F1 before | after | micro overlap F1 before / after |")
print("|---|---|---|---|---|")
for run in ("deberta", "roberta", "roberta_neg3"):
    pred = {k: [tuple(x) for x in v] for k, v in json.loads(
        (LABELED / f"predictions_val_{run}.json").read_text(encoding="utf-8")).items()}
    snapped = {lid: snap_to_words(pred.get(lid, []), texts[lid]) for lid in gold}
    changed = sum(len(set(snapped[l]) - set(pred.get(l, []))) for l in gold)
    a, b = ev.score(gold, pred, texts), ev.score(gold, snapped, texts)
    ea, eb = a["span"]["exact"]["micro"], b["span"]["exact"]["micro"]
    print(f"| {run} | {changed} | {ea['precision']:.3f} / {ea['recall']:.3f} / {ea['f1']:.3f} | "
          f"{eb['precision']:.3f} / {eb['recall']:.3f} / {eb['f1']:.3f} | "
          f"{a['span']['overlap']['micro']['f1']:.3f} / {b['span']['overlap']['micro']['f1']:.3f} |")
    if run == "roberta_neg3":
        print("\nPer field exact F1, roberta_neg3, before -> after:")
        for f in ev.FIELDS:
            print(f"  {f}: {a['span']['exact'][f]['f1']:.2f} -> {b['span']['exact'][f]['f1']:.2f}")
        print()
