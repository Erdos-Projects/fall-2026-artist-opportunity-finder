"""Cut cleaned organizer pages into overlapping windows for the model.

Run this after labeling, once the notebook has written data/clean/listings.jsonl
and data/clean/splits.json. It reads those two files and writes
data/labeled/chunks.jsonl.

Each chunk is one window of a cleaned page (page_text). Pages are cut once,
not once per listing. A chunk records where that window sits on the page, so a
label made on the full page can be moved onto the window later by subtracting
char_start. This script does not read or slice labels.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from preprocess.clean import clean_to_raw_span

CLEAN = ROOT / "data" / "clean"
LABELED = ROOT / "data" / "labeled"

WINDOW, STRIDE, MIN_TAIL = 300, 240, 40  # words; about 400 tokens, 60-word overlap


def chunk_page(text):
    """Yield (char_start, char_end) windows over text, cut on word boundaries."""
    words = [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]
    n, i = len(words), 0
    if n == 0:
        return
    while True:
        j = min(i + WINDOW, n)
        if n - j < MIN_TAIL:  # absorb a short tail into this last window
            j = n
        yield words[i][0], words[j - 1][1]
        if j == n:
            break
        i += STRIDE


def load_listings(path):
    pages = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if not row.get("has_page") or not row.get("page_text"):
                continue
            key = row["key"]
            page = pages.get(key)
            if page is None:
                pages[key] = {
                    "page_text": row["page_text"],
                    "page_text_raw": row.get("page_text_raw") or "",
                    "page_offsets": row.get("page_offsets") or [],
                    "listing_ids": [row["listing_id"]],
                }
                continue
            if page["page_text"] != row["page_text"]:
                raise SystemExit(f"listings that share {key} have different page text")
            page["listing_ids"].append(row["listing_id"])
    return pages


def load_split_of(path):
    splits = json.loads(path.read_text(encoding="utf-8"))
    split_of = {}
    for name in ("train", "val", "test"):
        for listing_id in splits[name]["listing_ids"]:
            split_of[listing_id] = name
    return split_of


def build_chunks(pages, split_of):
    rows = []
    for key in sorted(pages):
        page = pages[key]
        listing_ids = sorted(set(page["listing_ids"]))
        splits = {split_of[i] for i in listing_ids}
        if len(splits) != 1:
            raise SystemExit(f"{key} is shared by listings in different splits: {sorted(splits)}")
        split = splits.pop()
        text = page["page_text"]
        spans = list(chunk_page(text))
        pid = hashlib.sha1(key.encode()).hexdigest()[:8]
        raw = page["page_text_raw"]
        for k, (start, end) in enumerate(spans):
            raw_start, raw_end = clean_to_raw_span(page["page_offsets"], start, end, len(raw))
            chunk = text[start:end]
            rows.append({
                "chunk_id": f"{pid}-{k:03d}",
                "page_key": key,
                "listing_ids": listing_ids,
                "split": split,
                "chunk_index": k,
                "n_chunks": len(spans),
                "char_start": start,
                "char_end": end,
                "raw_start": raw_start,
                "raw_end": raw_end,
                "n_words": len(chunk.split()),
                "est_tokens": round(len(chunk.split()) * 1.3),
                "text": chunk,
            })
    too_long = [r["chunk_id"] for r in rows if r["est_tokens"] >= 512]
    if too_long:
        raise SystemExit(f"{len(too_long)} chunks are at or over 512 estimated tokens, first: {too_long[0]}")
    return rows


def main():
    listings_path = CLEAN / "listings.jsonl"
    splits_path = CLEAN / "splits.json"
    if not listings_path.exists() or not splits_path.exists():
        raise SystemExit(
            "Missing data/clean/listings.jsonl or data/clean/splits.json. "
            "Run notebooks/EDA+Preprocessing.ipynb first."
        )
    pages = load_listings(listings_path)
    rows = build_chunks(pages, load_split_of(splits_path))
    LABELED.mkdir(parents=True, exist_ok=True)
    out = LABELED / "chunks.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"{len(rows)} chunks from {len(pages)} pages written to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
