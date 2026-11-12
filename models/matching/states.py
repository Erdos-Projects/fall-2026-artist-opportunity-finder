"""Turn the extracted location and career stage text of a listing into a matching state.

States (from the null-handling decision in Plans/Progress.md):
  match         the listing's stated eligibility includes this artist
  mismatch      the listing states an eligibility that excludes this artist
  not_listed    nothing usable was extracted (no text, no span, or text we cannot read)
  no_constraint the artist has no value for this field, so nothing can be checked

A hard filter drops a listing ONLY on mismatch. not_listed and no_constraint pass (fail open).

The rules are keyword based and conservative: a mismatch needs a clearly named place or stage.
Negations ("full-time students are not eligible") are not understood, so the filter can be wrong,
and filter_eval.py measures how often against the judged ratings.
"""
from __future__ import annotations

import re

MATCH, MISMATCH, NOT_LISTED, NO_CONSTRAINT = "match", "mismatch", "not_listed", "no_constraint"

# ---------- career stage ----------
_ALL = re.compile(r"all (career )?(stages|levels|ages)|any (career )?(stage|level)|all career|regardless of (career|experience)", re.I)
_EMERGING = re.compile(r"emerg|early[- ]?career|early[- ]?stage|beginning|novice|young|up[- ]and[- ]coming|junior", re.I)
_MID = re.compile(r"mid[- ]?career", re.I)
_ESTABLISHED = re.compile(r"establish|senior|experienced|accomplished|seasoned|mature", re.I)


def career_state(spans: list[str], stage: str | None) -> str:
    """stage: 'emerging' | 'mid-career' | 'established' | None."""
    if not stage:
        return NO_CONSTRAINT
    text = " ; ".join(spans)
    if not text:
        return NOT_LISTED
    if _ALL.search(text):
        return MATCH
    found = set()
    if _EMERGING.search(text):
        found.add("emerging")
    if _MID.search(text):
        found.add("mid-career")
    if _ESTABLISHED.search(text):
        found.add("established")
    if not found:
        return NOT_LISTED          # e.g. "students", "professional": not a stage we can compare
    if "emerging" in found and "established" in found:
        found.add("mid-career")    # "emerging to established" covers the middle
    return MATCH if stage in found else MISMATCH


# ---------- location ----------
STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO",
    "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
    "rhode island": "RI", "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
    "utah": "UT", "vermont": "VT", "virginia": "VA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}
CITIES = {
    "new york city": "NY", "nyc": "NY", "brooklyn": "NY", "manhattan": "NY", "the bronx": "NY", "queens": "NY",
    "los angeles": "CA", "san francisco": "CA", "oakland": "CA", "san diego": "CA", "chicago": "IL",
    "houston": "TX", "austin": "TX", "dallas": "TX", "san antonio": "TX", "miami": "FL", "orlando": "FL",
    "tampa": "FL", "jacksonville": "FL", "seattle": "WA", "boston": "MA", "philadelphia": "PA",
    "pittsburgh": "PA", "atlanta": "GA", "new orleans": "LA", "detroit": "MI", "cleveland": "OH",
    "cincinnati": "OH", "columbus": "OH", "minneapolis": "MN", "denver": "CO", "baltimore": "MD",
    "nashville": "TN", "memphis": "TN", "knoxville": "TN", "houston": "TX",
}
_FOREIGN = ("canada|canadian|mexico|united kingdom|\\buk\\b|england|scotland|wales|ireland|greece|germany|france|"
            "italy|spain|portugal|netherlands|sweden|norway|denmark|finland|australia|new zealand|india|china|japan|"
            "korea|africa|european|europe|asia|latin america|caribbean|middle east|balkans|israel|brazil|"
            "argentina|colombia|nigeria|south africa|kenya")
_FOREIGN_RE = re.compile(_FOREIGN, re.I)
_INCLUSIVE = re.compile(r"international|worldwide|world\b|global|all nationalit|nationwide|anywhere|any country|"
                        r"united states|u\.s\.|\bus\b|\busa\b|\bamerican|national\b", re.I)
_AMBIGUOUS_ABBR = {"OR", "IN", "OK", "ME", "HI", "OH", "LA", "MA", "ID", "DE", "PA", "AL"}


def _mentions(text: str, state: str) -> bool:
    low = text.lower()
    names = [n for n, a in STATES.items() if a == state] + [c for c, a in CITIES.items() if a == state]
    if any(re.search(rf"\b{re.escape(n)}\b", low) for n in names):
        return True
    return state not in _AMBIGUOUS_ABBR and re.search(rf"\b{state}\b", text) is not None


def _other_place(text: str, state: str) -> bool:
    low = text.lower()
    for n, a in list(STATES.items()) + list(CITIES.items()):
        if a != state and re.search(rf"\b{re.escape(n)}\b", low):
            return True
    return _FOREIGN_RE.search(text) is not None


def location_state(spans: list[str], state: str | None) -> str:
    """state: two letter US state of the artist, or None."""
    if not state:
        return NO_CONSTRAINT
    text = " ; ".join(spans)
    if not text:
        return NOT_LISTED
    if re.search(r"kansas city", text, re.I):   # the metro area is in both Missouri and Kansas
        if state in ("MO", "KS"):
            return MATCH
        text = re.sub(r"kansas city", " ", text, flags=re.I)   # do not read the city as the state of Kansas
        if not text.strip(" ;"):
            return NOT_LISTED
    if _mentions(text, state) or _INCLUSIVE.search(text):
        return MATCH
    if _other_place(text, state):
        return MISMATCH
    return NOT_LISTED
