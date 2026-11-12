"""Shared helpers for the silver labeling scripts.

Silver labels are character spans on page_text (the full cleaned page), the same
coordinates the gold labels in Label Studio use. Chunking happens later and
carries these spans into chunks.

Only train and val listings are ever labeled here. silver_ids() refuses to run
if a gold listing sits in either set.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "data" / "clean"
LABELED = ROOT / "data" / "labeled"

FIELDS = ["deadline", "fee", "career_stage", "location", "medium"]


def silver_ids():
    """Return {"train": [...], "val": [...]}. Raises if any gold id is in them."""
    sets = json.loads((LABELED / "sets.json").read_text(encoding="utf-8"))
    gold = set(sets["gold"])
    out = {"train": sets["train"], "val": sets["val"]}
    clash = gold & (set(out["train"]) | set(out["val"]))
    if clash:
        raise SystemExit(f"gold listings found in silver sets: {sorted(clash)[:5]}")
    return out


def load_listings(ids):
    """Return {listing_id: row} for the given ids, read from data/clean/listings.jsonl."""
    wanted = set(ids)
    rows = {}
    with open(CLEAN / "listings.jsonl", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row["listing_id"] in wanted:
                rows[row["listing_id"]] = row
    return rows


def overlaps(a, b):
    """True if two (start, end) spans share at least one character."""
    return a[0] < b[1] and b[0] < a[1]


def flexible_pattern(quote):
    """Regex for a quote that tolerates different whitespace and avoids partial words."""
    words = quote.split()
    if not words:
        return None
    body = r"\s+".join(re.escape(w) for w in words)
    left = r"(?<!\w)" if re.match(r"\w", words[0][0]) else ""
    right = r"(?!\w)" if re.match(r"\w", words[-1][-1]) else ""
    return re.compile(left + body + right)


def find_all(text, quote, start=0, end=None):
    """All (start, end) spans of quote in text[start:end], whitespace tolerant."""
    pattern = flexible_pattern(quote)
    if pattern is None:
        return []
    end = len(text) if end is None else end
    return [(m.start(), m.end()) for m in pattern.finditer(text, start, end)]
