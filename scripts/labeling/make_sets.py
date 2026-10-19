"""Step 4: pick the train, val, and gold sets.

Reads data/clean/splits.json and data/clean/listings.jsonl, keeps only the
listings that have a usable page (has_page), and writes the listing ids to
data/labeled/sets.json. Ids only, no text, so nothing can go out of date.

  gold  = test split  (labeled by hand, used for the final score only)
  train = train split (silver labels, the model learns from these)
  val   = val split   (silver labels, used to pick the best epoch)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "data" / "clean"
OUT = ROOT / "data" / "labeled"


def main():
    splits = json.loads((CLEAN / "splits.json").read_text(encoding="utf-8"))
    has_page = {}
    with open(CLEAN / "listings.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            has_page[r["listing_id"]] = r["has_page"]

    def with_page(split):
        return sorted(i for i in splits[split]["listing_ids"] if has_page[i])

    sets = {"train": with_page("train"), "val": with_page("val"), "gold": with_page("test")}
    all_ids = [i for ids in sets.values() for i in ids]
    assert len(all_ids) == len(set(all_ids)), "a listing is in more than one set"

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sets.json").write_text(json.dumps(sets, indent=2), encoding="utf-8")
    print({k: len(v) for k, v in sets.items()})


if __name__ == "__main__":
    main()
