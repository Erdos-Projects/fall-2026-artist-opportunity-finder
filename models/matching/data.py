"""Load cleaned listings and build the text that gets matched against a profile.

Each listing becomes one short "match text": title + description + the start of
the organizer page. Page text is long and starts with navigation menus, so we cap
it. Both BM25 (Step 2) and the sentence-transformer (Step 3) read this same text,
so the comparison between them is fair.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LISTINGS_PATH = ROOT / "data" / "clean" / "listings.jsonl"

PAGE_WORD_CAP = 250  # words of organizer page text to include

_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")  # [text](url) -> text
_URL = re.compile(r"https?://\S+")


def load_listings(path: Path = LISTINGS_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _strip_markup(text: str) -> str:
    text = _MD_LINK.sub(r"\1", text)
    text = _URL.sub(" ", text)
    return re.sub(r"[\s\-\*#|]+", " ", text).strip()


def match_text(listing: dict, page_word_cap: int = PAGE_WORD_CAP) -> str:
    """The text we compare against an artist profile."""
    parts = [listing.get("title") or "", listing.get("description") or ""]
    page = listing.get("page_text") or ""
    if page:
        parts.append(" ".join(_strip_markup(page).split()[:page_word_cap]))
    return " ".join(p for p in parts if p)
