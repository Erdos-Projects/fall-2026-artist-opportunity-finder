"""Silver source 2: regex rules.

Finds deadline dates that sit next to a deadline word, and money amounts that
sit next to a fee word. Unlike distant supervision it does not need to know the
value in advance, so it also works on pages whose date differs from the listing's.

This is a separate module from the Oct 15 to 22 baseline on purpose: the
baseline is scored on gold only, and silver labels must not be measured against
themselves.

  python scripts/labeling/silver_regex.py     # prints span counts on train and val
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from silver_common import load_listings, silver_ids

MONTH = (r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|"
         r"Sept?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?")
DATE = (rf"(?:{MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?(?!\d)"
        rf"|\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?{MONTH}(?:,?\s+\d{{4}})?"
        rf"|\d{{1,2}}/\d{{1,2}}/\d{{2,4}}|\d{{4}}-\d{{2}}-\d{{2}})")
DEADLINE_WORD = (r"(?:deadline|due|apply by|applications? (?:close|closes|must be received)|"
                 r"submissions? (?:close|closes|due)|closes?|no later than|postmarked by|received by)")
DEADLINE_RE = re.compile(rf"{DEADLINE_WORD}[^.\n]{{0,60}}?(?P<date>{DATE})", re.I)

MONEY = re.compile(r"[$€£]\s?\d[\d,]*(?:\.\d\d)?(?![\d,]*\d)")
FEE_WORD = re.compile(r"\b(?:fee|fees|cost|costs|charge|charged|entry|submission|application|admission|"
                      r"to apply|to submit|per submission|per application)\b", re.I)
AWARD_WORD = re.compile(r"\b(?:award|awards|awarded|grant|grants|stipend|prize|prizes|honorarium|"
                        r"receive|receives|funding|worth|up to|scholarship|salary|budget|reimburse\w*)\b", re.I)
WINDOW = 50


def nearest(pattern, text, start, end):
    """Distance in characters from the span to the closest match of pattern, or None."""
    best = None
    for m in pattern.finditer(text, max(0, start - WINDOW), min(len(text), end + WINDOW)):
        dist = max(m.start() - end, start - m.end(), 0)
        best = dist if best is None else min(best, dist)
    return best


def regex_spans(listing):
    """Return {"deadline": [(s, e)], "fee": [(s, e)]} for one listing."""
    text = listing["page_text"]
    deadlines = sorted({m.span("date") for m in DEADLINE_RE.finditer(text)})
    fees = []
    for m in MONEY.finditer(text):
        fee_dist = nearest(FEE_WORD, text, m.start(), m.end())
        if fee_dist is None:
            continue
        award_dist = nearest(AWARD_WORD, text, m.start(), m.end())
        if award_dist is None or fee_dist < award_dist:
            fees.append(m.span())
    return {"deadline": deadlines, "fee": fees}


def main():
    ids = silver_ids()
    rows = load_listings(ids["train"] + ids["val"])
    for split in ("train", "val"):
        counts = {"deadline": 0, "fee": 0}
        listings = {"deadline": 0, "fee": 0}
        for lid in ids[split]:
            for field, spans in regex_spans(rows[lid]).items():
                counts[field] += len(spans)
                listings[field] += bool(spans)
        print(split, {k: f"{counts[k]} spans in {listings[k]} listings" for k in counts})


if __name__ == "__main__":
    main()
