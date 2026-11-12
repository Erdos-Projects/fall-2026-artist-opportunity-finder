"""Regex + rules baseline for field extraction.

This is the number the fine-tuned DeBERTa has to beat. It reads a cleaned page
and returns character spans for five fields: deadline, fee, career_stage,
location, medium. Every span is a slice of the page, so it cannot invent text.

Independence from silver labels: the rules here are written separately from
scripts/labeling/silver_regex.py on purpose. Silver labels train the model, and
this baseline is scored on gold, so neither may be graded against the other's
rules. The rule sets were built by reading text, not by fitting gold.

Usage (from the repo root):
  # development check on silver val (a proxy, NOT the reported baseline number)
  python models/extraction/regex_baseline.py

  # the real baseline number, on a Label Studio export of the gold tasks
  python models/extraction/regex_baseline.py --gold path/to/gold_export.json
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate as ev  # noqa: E402

CLEAN = ROOT / "data" / "clean"
LABELED = ROOT / "data" / "labeled"
RESULTS = ROOT / "docs" / "results"

# ---------- deadline ----------
MONTH = (r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|"
         r"Sept?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?")
DATE = (rf"(?:{MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?(?!\d)"
        rf"|\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?{MONTH}(?:,?\s+\d{{4}})?"
        rf"|\d{{1,2}}/\d{{1,2}}/\d{{2,4}}|\d{{4}}-\d{{2}}-\d{{2}})")
# a deadline cue, then up to 80 characters (not crossing a paragraph), then a date
CUE = (r"(?:deadlines?|due(?: date)?|apply by|apply before|submit by|submissions? by|"
       r"applications? (?:are )?(?:due|close[sd]?|must be (?:received|submitted|postmarked))|"
       r"submissions? (?:are )?(?:due|close[sd]?)|closes?|closed on|closed:|closing|no later than|postmarked by|"
       r"received by|open until|until|through|by)")
DEADLINE_RE = re.compile(rf"\b{CUE}\b[^\n]{{0,80}}?(?P<date>{DATE})", re.I)
# a heading such as "Application Deadline" with the date on the next line or after markup
HEADING_RE = re.compile(rf"\b(?:application |submission |final )?deadlines?\b[\s:*#|\\–—-]{{0,12}}(?P<date>{DATE})", re.I)
# the date first, then the cue: "May 22, 2026: DEADLINE to apply"
AFTER_RE = re.compile(rf"(?P<date>{DATE})[ \t:*|\\]{{0,6}}(?:(?:application|submission|final)[ \t]+)?"
                      rf"(?:deadline|due\b|applications?[ \t]+clos\w+|submissions?[ \t]+clos\w+)(?![ \t]*:)", re.I)
# the end of a date range after an application word: "accepted from Feb 18 to June 15, 2026"
RANGE_RE = re.compile(rf"\b(?:applications?|submissions?|entries|proposals?|open call|accepted|accepting|"
                      rf"apply|submit|nominations?)\b[^\n]{{0,60}}?{DATE}\s*(?:to|through|until|thru|[-–—])\s*"
                      rf"(?P<date>{DATE})", re.I)
# weak cues need an application word nearby and no sign that the date is something else
WEAK_CUE = re.compile(r"(?:by|until|through|no later than|open until)\b", re.I)
APPLY_CTX = re.compile(r"appl|submi|entr(?:y|ies)|proposal|nominat|materials|regist|received|postmarked|"
                       r"send|sent|return|enter|upload", re.I)
BAD_CTX = re.compile(r"notif|notify|decision|communicat|inform|announc|complet|RSVP|deposit|install|"
                     r"payment|balance|final report|draft|edits?\b|arriv|shipping|pick-?up|invoice|"
                     r"tuition|housing|orientation|review (?:begins|starts)", re.I)
# words that mean the date is something other than the application deadline
NOT_DEADLINE = re.compile(r"\b(?:notif\w*|announced?|announcement|begins?|starts?|runs?|"
                          r"residency (?:dates|period)|program dates|exhibition|opening|"
                          r"workshop|event|arrive\w*|term)\b", re.I)

# ---------- fee ----------
MONEY = re.compile(r"[$€£]\s?\d[\d,]*(?:\.\d\d)?(?![\d,]*\d)")
FEE_CUE = re.compile(r"\b(?:(?:application|submission|entry|entrance|registration|reading|jury|processing|review|filing) "
                     r"(?:fees?|charges?)|fees?[\s*]*:|to apply|to submit|"
                     r"per (?:submission|application|entry|work|image|piece)|"
                     r"fees?\b[^.\n]{0,40}\b(?:apply|applying|submit|submission|entry|entries)|"
                     r"(?:apply|applying|submit|submission)\b[^.\n]{0,40}\bfees?)\b", re.I)
AWARD_CUE = re.compile(r"\b(?:awards?|awarded|grants?|stipends?|prizes?|honorarium|receives?|"
                       r"funding|worth|up to|scholarships?|salary|budget|reimburse\w*|"
                       r"housing|travel|prize money|will be paid|compensation|"
                       r"artist fees?|performer|booth|expenses?|projected|income|tickets?|VIP|"
                       r"ride|shipping|range|resources)\b", re.I)
WINDOW = 50

# ---------- career stage ----------
CAREER = re.compile(
    r"\b(?:(?:emerging|early[- ]career|mid[- ]career|mid[- ]level|established|professional|"
    r"amateur|student|graduate|undergraduate|senior|new|young|advanced|beginning)"
    r"(?:\s*(?:,|and|or|/|to)\s*(?:emerging|early[- ]career|mid[- ]career|established|professional|amateur|advanced))*"
    r"(?:\s+(?:visual\s+)?(?:artists?|writers?|curators?|critics?|photographers?|students?|practitioners?|"
    r"artisans?|filmmakers?|designers?|scholars?|poets?|musicians?|makers?|creatives?))?"
    r"|any (?:career )?stage|all (?:career )?(?:stages|levels)(?: of (?:their )?(?:careers?|experience))?"
    r"|(?:at )?(?:any|all) stages? of (?:their |your )?careers?"
    r"|(?:early )?stages? of (?:their |your )?careers?"
    r"|pre-?doctoral|post-?doctoral|MFA|BFA|PhD|doctoral (?:program|students?|candidates?))\b", re.I)
# bare "new", "senior", "young", "advanced", "graduate" are only ok with a following noun; checked below
CAREER_NEEDS_NOUN = re.compile(r"^(?:new|senior|young|advanced|beginning|graduate|undergraduate|professional)$", re.I)

# ---------- location (eligibility, not the place of the program) ----------
PLACE = (r"(?:the\s+)?(?:[A-Z][\w.'-]*|U\.S\.A?\.?|US|USA|NYC|LA|DC)"
         r"(?:\s+(?:and|or|of|the|[A-Z][\w.'-]*)){0,6}")
LOCATION = re.compile(
    rf"(?:\b(?:based|living|residing|reside|resides|live|lives|residents?|resident of|citizens?|"
    rf"working|work|from|located)\s+(?:in|of|within|from|outside(?: of)?)\s+{PLACE}"
    rf"|\b(?:U\.S\.|US|NYC|[A-Z][a-z]+)[- ]based\b(?: artists?)?"
    rf"|\bU\.?S\.?\s+(?:citizens?|residents?|permanent residents?)"
    rf"|\bcitizens?\s+(?:or\s+permanent\s+residents?\s+)?of\s+{PLACE}"
    rf"|\b(?:open to|available to|eligible:?)\s+(?:artists?\s+)?(?:from|in|living in)\s+{PLACE}"
    rf"|\b(?:anywhere|around|across)\s+the\s+world\b|\binternational (?:artists?|applicants?)\b"
    rf"|\b(?:nationwide|worldwide)\b)")

# ---------- medium ----------
MEDIA = [
    "photography", "photographs?", "photographers?", "video", "sculpture", "sculptors?", "painting", "paintings",
    "painters?", "drawing", "drawings", "printmaking", "prints?", "collage", "ceramics?", "glass", "glassmaking",
    "fiber", "fibre", "textiles?", "weaving", "jewelry", "metalwork", "metals?", "blacksmithing", "woodworking",
    "wood", "film", "filmmaking", "filmmakers?", "film/video", "animation", "mixed media", "new media",
    "installation", "installations", "performance art", "performance", "performances", "dance", "choreography",
    "theat(?:er|re)", "music", "music composition", "sound art", "sound", "poetry", "poems?", "fiction", "nonfiction",
    "non-fiction", "memoir", "essays?", "writing", "literature", "literary arts", "criticism", "playwriting",
    "visual arts?", "visual artists?", "performing arts", "social practice", "public art", "digital art",
    "illustration", "architecture", "design", "crafts?", "folk arts?", "any media", "any medium", "all media",
    "interdisciplinary", "multidisciplinary", "all (?:arts )?disciplines", "lithography", "ceramic",
]
MEDIUM = re.compile(r"(?<![\w-])(?:" + "|".join(sorted(MEDIA, key=len, reverse=True)) + r")(?![\w-])", re.I)


# ---------- extraction ----------

def _nearest(pattern, text, start, end):
    best = None
    for m in pattern.finditer(text, max(0, start - WINDOW), min(len(text), end + WINDOW)):
        d = max(m.start() - end, start - m.end(), 0)
        best = d if best is None else min(best, d)
    return best


def _deadlines(text):
    spans = set()
    for m in DEADLINE_RE.finditer(text):
        s, e = m.span("date")
        between = text[m.start():s]
        if NOT_DEADLINE.search(between) and not re.search(r"deadline|due|apply by", between, re.I):
            continue
        if WEAK_CUE.match(m.group(0)):
            # same line, up to 60 characters before the cue
            before = text[max(0, m.start() - 60):m.start()].split("\n")[-1]
            ctx = before + between
            if not APPLY_CTX.search(ctx) or BAD_CTX.search(ctx):
                continue
        spans.add((s, e))
    for rx in (HEADING_RE, AFTER_RE, RANGE_RE):
        for m in rx.finditer(text):
            s, e = m.span("date")
            if rx is RANGE_RE and NOT_DEADLINE.search(text[m.start():s]):
                continue
            spans.add((s, e))
    return sorted(spans)


def _fees(text):
    spans = []
    for m in MONEY.finditer(text):
        if not re.search(r"[1-9]", m.group(0)):  # "$0" is not a fee
            continue
        fee_d = _nearest(FEE_CUE, text, m.start(), m.end())
        if fee_d is None:
            continue
        award_d = _nearest(AWARD_CUE, text, m.start(), m.end())
        if award_d is None or fee_d < award_d:
            spans.append(m.span())
    return spans


def _careers(text):
    out = []
    for m in CAREER.finditer(text):
        word = m.group(0).strip()
        if CAREER_NEEDS_NOUN.match(word):
            continue
        out.append(m.span())
    return out


def extract(text):
    """Return a list of (label, start, end) with no overlaps. Longer spans win."""
    cands = []
    cands += [("deadline", s, e) for s, e in _deadlines(text)]
    cands += [("fee", s, e) for s, e in _fees(text)]
    cands += [("career_stage", s, e) for s, e in _careers(text)]
    cands += [("location", m.start(), m.end()) for m in LOCATION.finditer(text)]
    cands += [("medium", m.start(), m.end()) for m in MEDIUM.finditer(text)]
    cands.sort(key=lambda c: (-(c[2] - c[1]), c[1]))
    kept = []
    for c in cands:
        if all(c[2] <= k[1] or k[2] <= c[1] for k in kept):
            kept.append(c)
    return sorted(kept, key=lambda c: c[1])


# ---------- run ----------

def load_texts(ids):
    wanted, texts = set(ids), {}
    with open(CLEAN / "listings.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["listing_id"] in wanted:
                texts[r["listing_id"]] = r["page_text"]
    return texts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gold", help="Label Studio JSON export of the gold tasks (the real baseline number)")
    ap.add_argument("--silver-split", default="val", choices=["val", "train"],
                    help="dev proxy when --gold is not given (default val)")
    ap.add_argument("--out", help="write results here (default docs/results/regex_baseline_<name>.json)")
    args = ap.parse_args()

    if args.gold:
        gold, name = ev.load_label_studio(args.gold), "gold"
    else:
        gold, name = ev.load_silver(LABELED / "silver.jsonl", args.silver_split), f"silver_{args.silver_split}_check"
        print("NOTE: scoring against silver labels. This is a dev check, not the baseline number.\n")
    if not gold:
        raise SystemExit("no labeled listings found")

    texts = load_texts(gold)
    missing = [lid for lid in gold if lid not in texts]
    if missing:
        raise SystemExit(f"listings not in data/clean/listings.jsonl: {missing[:3]}")

    t0 = time.perf_counter()
    pred = {lid: extract(texts[lid]) for lid in gold}
    secs = time.perf_counter() - t0

    res = ev.score(gold, pred, texts)
    res["latency"] = {"seconds_per_listing": secs / len(gold), "seconds_per_1000": secs / len(gold) * 1000,
                      "cost_per_1000_usd": 0.0}
    md = ev.to_markdown(res, f"Regex baseline on {name}")
    md += f"\n\nLatency: {res['latency']['seconds_per_1000']:.2f} s per 1,000 listings. Cost: $0."
    print(md)

    RESULTS.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else RESULTS / f"regex_baseline_{name}.json"
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    out.with_suffix(".md").write_text(md + "\n", encoding="utf-8")
    print(f"\nwritten: {out}")


if __name__ == "__main__":
    main()
