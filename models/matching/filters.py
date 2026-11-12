"""Layer 0: hard filters. Rules, not ML.

A filter drops a listing only when it is SURE the listing is a mismatch. If a
field is missing or unreadable we keep the listing, because hiding a good
opportunity is worse than showing a mediocre one.

Location and career stage use the fields the fine-tuned model extracted (Component 1), turned into
match / mismatch / not_listed by states.py. Pass `extracted` (the dict in data/labeled/extracted_all.json)
to switch them on. Without it they pass everything, as before.
"""
from __future__ import annotations

import json
from datetime import date

from .data import ROOT
from .profile import ArtistProfile
from .states import MISMATCH, career_state, location_state

EXTRACTED_PATH = ROOT / "data" / "labeled" / "extracted_all.json"


def load_extracted(path=EXTRACTED_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def deadline_ok(listing: dict, as_of: date) -> bool:
    """Keep rolling listings, listings with no readable deadline, and any listing
    with at least one deadline on or after `as_of`."""
    if listing.get("is_rolling"):
        return True
    dates = listing.get("all_deadlines") or listing.get("deadline_dates") or []
    if listing.get("deadline_iso"):
        dates = [*dates, listing["deadline_iso"]]
    if not dates:
        return True
    return max(dates) >= as_of.isoformat()  # ISO strings sort like dates


def type_ok(listing: dict, profile: ArtistProfile) -> bool:
    return listing.get("type") in profile.wanted_types


def fee_ok(listing: dict, profile: ArtistProfile) -> bool:
    if profile.max_fee is None:
        return True
    fee = listing.get("fee_min")
    return fee is None or fee <= profile.max_fee


def location_ok(listing: dict, profile: ArtistProfile, extracted: dict | None = None) -> bool:
    """Drops a listing only when its extracted eligibility location clearly excludes the artist's state."""
    if extracted is None:
        return True
    rec = extracted.get(listing["listing_id"], {})
    return location_state(rec.get("location", []), profile.state) != MISMATCH


def career_stage_ok(listing: dict, profile: ArtistProfile, extracted: dict | None = None) -> bool:
    """Drops a listing only when its extracted career stage clearly excludes the artist's stage."""
    if extracted is None:
        return True
    rec = extracted.get(listing["listing_id"], {})
    return career_state(rec.get("career_stage", []), profile.career_stage) != MISMATCH


def passes_filters(listing: dict, profile: ArtistProfile, as_of: date, extracted: dict | None = None) -> bool:
    return (
        deadline_ok(listing, as_of)
        and type_ok(listing, profile)
        and fee_ok(listing, profile)
        and location_ok(listing, profile, extracted)
        and career_stage_ok(listing, profile, extracted)
    )


def apply_filters(listings: list[dict], profile: ArtistProfile, as_of: date,
                  extracted: dict | None = None) -> list[dict]:
    return [l for l in listings if passes_filters(l, profile, as_of, extracted)]
