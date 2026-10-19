"""Build the Label Studio import file for the gold set.

Reads data/labeled/sets.json and data/clean/listings.jsonl, and writes
data/labeled/gold_tasks.json: one task per gold listing, with the fields the
label config uses ($title and $text) plus the listing_id.

The text is page_text exactly as stored, never cut or changed. Labels are
character positions in this text.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "data" / "clean"
LABELED = ROOT / "data" / "labeled"


def main():
    gold_ids = json.loads((LABELED / "sets.json").read_text(encoding="utf-8"))["gold"]
    listings = {}
    with open(CLEAN / "listings.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["listing_id"] in gold_ids:
                listings[r["listing_id"]] = r

    tasks = [
        {"data": {"listing_id": lid,
                  "title": listings[lid]["title"],
                  "text": listings[lid]["page_text"]}}
        for lid in gold_ids
    ]
    (LABELED / "gold_tasks.json").write_text(
        json.dumps(tasks, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(tasks)} tasks written")


if __name__ == "__main__":
    main()
