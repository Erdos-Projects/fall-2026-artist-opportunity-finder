"""Cleaning functions for the raw listings in data/raw.

Each function takes plain values and returns plain values, so it can be tried on
one string in a notebook and tested without loading any files. Raw files are
never edited: cleaned values are written to new columns or to data/clean.
"""

import bisect
import difflib
import re
import sys
import unicodedata
from itertools import accumulate
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


# ---------------------------------------------------------------------------
# Text normalization for the model, with an offset map back to the raw text
# ---------------------------------------------------------------------------

_QUOTES = {ord(c): "'" for c in "‘’‚‛′"} | {ord(c): '"' for c in "“”„‟″"}


def normalize_for_model(text):
    """Full text normalization used for everything the model will read.

    Builds on normalize_text. Order matters: ftfy first (it repairs mojibake,
    which later steps would make permanent), then NFKC (ligatures, full-width
    forms, unusual spaces), then removal of the soft hyphen and word joiner,
    then curly quotes to straight quotes, then a last whitespace tidy. En and
    em dashes are kept. Use build_offset_map to keep character positions
    traceable back to the raw text.
    """
    text = normalize_text(text)
    text = unicodedata.normalize("NFKC", text)
    text = re.sub("[­⁠]", "", text)
    text = text.translate(_QUOTES)
    return normalize_text(re.sub(r"[ \t]+", " ", text))


def _char_segments(raw, clean, raw_off, clean_off):
    """Character-level diff of two short strings, as [clean_start, raw_start, length] stretches."""
    sm = difflib.SequenceMatcher(None, raw, clean, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if j2 > j1 and (op == "equal" or (op == "replace" and i2 - i1 == j2 - j1)):
            yield [clean_off + j1, raw_off + i1, j2 - j1]


def build_offset_map(raw, clean):
    """Describe which stretches of `clean` come from which stretch of `raw`.

    Returns a list of [clean_start, raw_start, length]. Equal stretches and
    1-for-1 swaps (a curly quote becoming a straight one) are kept; deletions
    and rewrites are gaps.

    A character-level diff of a whole page is slow (it grows with the square of
    the length), so it diffs line by line first, which pins down the unchanged
    lines at once, and only runs the character-level diff inside the few lines
    that changed.
    """
    rl, cl = raw.split("\n"), clean.split("\n")
    r_off = [0] + list(accumulate(len(x) + 1 for x in rl))   # start of each line in raw
    c_off = [0] + list(accumulate(len(x) + 1 for x in cl))   # start of each line in clean
    found = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, rl, cl, autojunk=False).get_opcodes():
        rb, cb = "\n".join(rl[i1:i2]), "\n".join(cl[j1:j2])
        if op == "equal":
            found.append([c_off[j1], r_off[i1], len(cb)])
        elif rb and cb:
            found += _char_segments(rb, cb, r_off[i1], c_off[j1])
    segs = []
    for s in found:                                           # glue stretches that touch
        if segs and segs[-1][0] + segs[-1][2] == s[0] and segs[-1][1] + segs[-1][2] == s[1]:
            segs[-1][2] += s[2]
        else:
            segs.append(s)
    return segs


def clean_to_raw_span(segs, start, end, raw_len):
    """Turn a [start, end) span on the clean text into a [start, end) span on the raw text.

    A position inside a kept stretch converts exactly. One inside deleted or
    rewritten text snaps to the nearest kept character.
    """
    starts = [s[0] for s in segs]

    def locate(pos):                                          # the stretch holding clean position `pos`
        i = bisect.bisect_right(starts, pos) - 1
        return i, (i >= 0 and pos < segs[i][0] + segs[i][2])

    i, inside = locate(start)
    if inside:
        raw_start = segs[i][1] + start - segs[i][0]
    else:                                                     # in a gap: use the next kept character
        raw_start = segs[i + 1][1] if i + 1 < len(segs) else raw_len
    i, inside = locate(end - 1)
    if inside:
        raw_end = segs[i][1] + (end - 1) - segs[i][0] + 1
    else:                                                     # in a gap: use the end of the last kept stretch
        raw_end = segs[i][1] + segs[i][2] if i >= 0 else 0
    return raw_start, max(raw_end, raw_start)


# ---------------------------------------------------------------------------
# Page cleaning
# ---------------------------------------------------------------------------

_BOILER = re.compile(
    r"cookie|accept (?:all|cookies)|privacy (?:policy|settings|notice)|terms (?:of|&|and) (?:use|service)|"
    r"all rights reserved|skip to (?:main )?content|subscribe|newsletter|follow us|back to top|"
    r"toggle (?:navigation|menu)|©|\bcopyright\b|powered by|website by|site by", re.I)
_NAV_WORDS = {"menu", "home", "about", "contact", "search", "close", "login", "log in", "donate", "shop",
              "cart", "news", "events", "press", "support us", "skip to content"}


def strip_boilerplate(text):
    """Remove short nav, cookie and footer lines. Returns (text, number_of_lines_removed).

    A line is removed only if it is short (100 characters or fewer) and matches
    a boilerplate pattern or is a bare navigation word, so a real sentence that
    mentions "newsletter" is kept.
    """
    kept, removed = [], 0
    for line in text.split("\n"):
        s = line.strip()
        if s and len(s) <= 100 and (_BOILER.search(s) or s.lower() in _NAV_WORDS):
            removed += 1
            continue
        kept.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip(), removed


# ---------------------------------------------------------------------------
# Listing fields: opportunity type, and title parts for deduplication
# ---------------------------------------------------------------------------

def project_type(raw_type, title, description):
    """Map the scraper's type to the three project types.

    "Grant" becomes Grant/Fellowship and "Open Call" stays. The combined
    "Residency/Fellowship" is split by keyword: text that says fellowship but
    not residency is Grant/Fellowship, everything else is Residency. Text that
    mentions both words, or neither, therefore lands in Residency, so check
    those by hand.
    """
    if raw_type == "Grant":
        return "Grant/Fellowship"
    if raw_type == "Open Call":
        return "Open Call"
    text = f"{title or ''} {description or ''}"
    if re.search(r"fellowship", text, re.I) and not re.search(r"residen", text, re.I):
        return "Grant/Fellowship"
    return "Residency"


_DASH = re.compile(r"\s[–—-]\s")                                          # "Organizer - Program"
_YEAR = re.compile(r"\b(?:19|20)\d{2}(?:\s*[–—/-]\s*(?:19|20)?\d{2})?\b")  # 2025, 2026-27, 2025/2026


def split_title(title):
    """Return (organizer, program) from "Organizer - Program".

    Lower-cased, with years, punctuation and a leading "The" removed, so the
    same program in different years compares equal. A title with no dash has an
    empty organizer. Used by the deduplication step, which compares programs
    rather than whole titles.
    """
    t = _YEAR.sub(" ", (title or "").lower())
    parts = _DASH.split(t, maxsplit=1)
    org, prog = (parts[0], parts[1]) if len(parts) == 2 else ("", parts[0])

    def tidy(s):
        s = re.sub(r"^the\s+", "", s.strip())
        return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s)).strip()

    return tidy(org), tidy(prog)
