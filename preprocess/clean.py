"""Cleaning functions for the raw listings in data/raw.

Each function takes plain values and returns plain values, so it can be tried on
one string in a notebook and tested without loading any files. Raw files are
never edited: cleaned values are written to new columns or to data/clean.
"""

import re
import sys
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import ftfy

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scrapers"))
from common import url_key  # noqa: E402

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sept?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
_DATE = re.compile(
    rf"(?P<m>{_MONTH})\.?\s+(?P<d>\d{{1,2}})(?:st|nd|rd|th)?"
    rf"(?:\s*[-–—]\s*(?:(?P<m2>{_MONTH})\.?\s+)?(?P<d2>\d{{1,2}}))?"
    r"(?:,?\s+(?P<y>\d{4}))?",
    re.I,
)
_ROLLING = re.compile(r"\b(rolling|ongoing|open until filled|continuous(?:ly)?)\b", re.I)
_AMOUNT = re.compile(
    r"(?P<cur>[$£€])\s?(?P<lo>\d[\d,]*(?:\.\d+)?)"
    r"(?:\s*[-–—]\s*[$£€]?\s?(?P<hi>\d[\d,]*(?:\.\d+)?))?"
)
_APPLICATION_FEE = re.compile(r"\b(application|apply|entry|submission|submit)\b", re.I)
_OPPORTUNITY_WORDS = re.compile(
    r"\b(deadline|appl(?:y|ying|ication)|eligib|grant|residenc|fellowship|open call|submission|artist)", re.I
)
_NOT_FOUND = re.compile(
    r"page not found|(?:couldn.t|can.t|could not) find (?:the|that) page|no longer (?:available|exists)|\b404\b", re.I
)


def normalize_text(text):
    """Make whitespace and invisible characters consistent.

    Fixes broken encodings, turns non-breaking spaces into plain spaces, drops
    zero-width characters, and collapses runs of spaces and blank lines. Curly
    quotes and en dashes are kept, because labels will be made on this text
    and should match what the organizer wrote. Run this once, before labeling:
    character positions change if it is run afterwards.
    """
    if not isinstance(text, str):
        return ""
    text = ftfy.fix_text(text)
    text = unicodedata.normalize("NFC", text)
    text = text.replace(" ", " ")
    text = re.sub(r"[​‌‍﻿]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _iso(year, month, day):
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def parse_deadline(text, default_year=None):
    """Read a deadline string such as "February 1-March 1, 2025 (5pm EST)".

    Returns a dict with every date found (`dates`, ISO strings), the last one as
    `deadline` (for a range this is the end), and `is_rolling`. A date with no
    year takes the year of the next date that has one, or default_year (for
    example the year the listing was published). `deadline` is None when
    nothing could be read, and "TBD" style text gives no dates.
    """
    out = {"dates": [], "deadline": None, "is_rolling": False}
    if not isinstance(text, str) or not text.strip():
        return out
    out["is_rolling"] = bool(_ROLLING.search(text))
    found = []  # (month, day, year or None), in reading order
    for m in _DATE.finditer(text):
        y = int(m["y"]) if m["y"] else None
        m1 = MONTHS[m["m"][:3].lower()]
        if m["d2"]:
            m2 = MONTHS[m["m2"][:3].lower()] if m["m2"] else m1
            found += [(m1, int(m["d"]), None if y is None else y), (m2, int(m["d2"]), y)]
        else:
            found.append((m1, int(m["d"]), y))
    # a date without a year borrows from the next one that has a year
    next_year = default_year
    for i in range(len(found) - 1, -1, -1):
        mo, d, y = found[i]
        if y is None:
            y = next_year
        else:
            next_year = y
        found[i] = (mo, d, y)
    out["dates"] = [iso for mo, d, y in found if y and (iso := _iso(y, mo, d))]
    out["deadline"] = out["dates"][-1] if out["dates"] else None
    return out


def parse_fees(text):
    """Read a fee sentence such as "Application fees are $35-40."

    `fee_mentioned` is False for an empty value, which means the listing did
    not say, not that it is free. Amounts are the smallest and largest numbers
    found. `fee_is_application` separates application fees from other costs
    such as workshop or program fees.
    """
    out = {"fee_mentioned": False, "fee_min": None, "fee_max": None, "fee_currency": None, "fee_is_application": None}
    if not isinstance(text, str) or not text.strip():
        return out
    out["fee_mentioned"] = True
    amounts, currency = [], None
    for m in _AMOUNT.finditer(text):
        currency = currency or m["cur"]
        for g in ("lo", "hi"):
            if m[g]:
                amounts.append(float(m[g].replace(",", "")))
    if amounts:
        out["fee_min"], out["fee_max"], out["fee_currency"] = min(amounts), max(amounts), currency
    out["fee_is_application"] = bool(_APPLICATION_FEE.search(text))
    return out


def month_from_source_url(url):
    """The month of a Hyperallergic post, such as "2025-04", from its address."""
    m = re.search(r"opportunities-(?:in-)?([a-z]+)-(\d{4})", url or "")
    if not m or m[1][:3] not in MONTHS:
        return None
    return f"{m[2]}-{MONTHS[m[1][:3]]:02d}"


def domain(url):
    """The site of a link, without "www.". Used to keep an organizer out of both train and test."""
    host = urlparse(url or "").netloc.lower()
    return host[4:] if host.startswith("www.") else host


def page_problem(text):
    """Say why an organizer page is not usable text, or None if it looks fine.

    "empty" is almost no text. "not_found" is an error page (the start of the
    text says the page is missing). "no_signal" is a page with no words a
    listing would use, such as a login wall or a cookie banner.
    """
    text = normalize_text(text)
    if len(text) < 200:
        return "empty"
    if _NOT_FOUND.search(text[:400]):
        return "not_found"
    if not _OPPORTUNITY_WORDS.search(text):
        return "no_signal"
    return None
