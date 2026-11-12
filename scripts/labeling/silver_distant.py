"""Silver source 1: distant supervision.

Take values we already know for a listing (its parsed deadline dates and fee
amounts) and find where they are written in the page text. The position becomes
a free label. It only works when the value is actually on the page, so coverage
is partial, and an unmatched field is left unlabeled, never treated as "absent".

  python scripts/labeling/silver_distant.py     # prints coverage on train and val
"""
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from silver_common import load_listings, silver_ids

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
SUFFIX = r"(?:st|nd|rd|th)?"
CURRENCY = {"$": r"\$", "€": "€", "£": "£"}


def month_pattern(month):
    name = MONTHS[month - 1]
    short = name[:3]
    # "Sept" is common for September, "May" has no short form to add
    forms = {name, short} | ({"Sept"} if month == 9 else set())
    return r"(?:" + "|".join(sorted(forms, key=len, reverse=True)) + r")\.?"


def date_patterns(iso):
    """Regexes for one ISO date written several ways. Each match keeps an attached year."""
    y, m, d = (int(p) for p in iso.split("-"))
    try:
        date(y, m, d)
    except ValueError:
        return []
    mo, day, year = month_pattern(m), rf"0?{d}{SUFFIX}", rf"(?:{y}|{y % 100:02d})"
    return [
        # March 3, 2026   March 3rd   Mar. 3
        rf"(?<!\w){mo}\s+{day}(?!\d)(?:,?\s+{y}(?!\d))?",
        # 3 March 2026   3rd of March
        rf"(?<!\d){day}\s+(?:of\s+)?{mo}(?:,?\s+{y}(?!\d))?",
        # 3/3/2026   03/03/26   2026-03-03
        rf"(?<!\d)0?{m}/0?{d}/{year}(?!\d)",
        rf"(?<!\d){y}-{m:02d}-{d:02d}(?!\d)",
    ]


def amount_pattern(amount, symbol):
    cents = r"(?:\.00)?"
    whole = int(amount)
    plain = str(whole)
    grouped = f"{whole:,}"
    digits = plain if plain == grouped else f"(?:{plain}|{re.escape(grouped)})"
    return rf"{CURRENCY[symbol]}\s?{digits}{cents}(?![\d,]*\d)"


def spans_for(patterns, text):
    found = set()
    for pat in patterns:
        for m in re.finditer(pat, text, re.I):
            found.add((m.start(), m.end()))
    return sorted(found)


def distant_spans(listing):
    """Return {"deadline": [(s, e)], "fee": [(s, e)]} for one listing."""
    text = listing["page_text"]
    dates = set(listing.get("deadline_dates") or []) | set(listing.get("all_deadlines") or [])
    patterns = [p for iso in dates for p in date_patterns(iso)]
    out = {"deadline": spans_for(patterns, text), "fee": []}

    symbol = listing.get("fee_currency")
    if listing.get("fee_mentioned") and symbol in CURRENCY:
        amounts = {a for a in (listing.get("fee_min"), listing.get("fee_max")) if a}
        out["fee"] = spans_for([amount_pattern(a, symbol) for a in amounts], text)
    return out


def main():
    ids = silver_ids()
    rows = load_listings(ids["train"] + ids["val"])
    for split in ("train", "val"):
        known = {"deadline": 0, "fee": 0}
        hit = {"deadline": 0, "fee": 0}
        for lid in ids[split]:
            row = rows[lid]
            spans = distant_spans(row)
            if row.get("deadline_dates"):
                known["deadline"] += 1
                hit["deadline"] += bool(spans["deadline"])
            if row.get("fee_mentioned") and row.get("fee_min"):
                known["fee"] += 1
                hit["fee"] += bool(spans["fee"])
        print(split, {k: f"{hit[k]}/{known[k]} listings matched" for k in known})


if __name__ == "__main__":
    main()
