"""The artist profile: what we know about the person looking for opportunities."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# Must match the `type` values in data/clean/listings.jsonl
ALL_TYPES = ("Grant/Fellowship", "Residency", "Open Call")


@dataclass
class ArtistProfile:
    profile_id: str
    # Free text. This is what BM25 and the embedding model actually compare.
    about: str
    # Used by the hard filters (Layer 0). None or empty means "no constraint".
    state: str | None = None                      # e.g. "NY"
    career_stage: str | None = None               # "emerging" | "mid-career" | "established"
    wanted_types: tuple[str, ...] = ALL_TYPES
    max_fee: float | None = None                  # skip listings that charge more than this
    notes: list[str] = field(default_factory=list)

    def query_text(self) -> str:
        """Text used as the search query for ranking."""
        return self.about


PROFILES_PATH = Path(__file__).resolve().parents[2] / "data" / "labeled" / "profiles.json"


def load_profiles(path: Path = PROFILES_PATH) -> list[ArtistProfile]:
    """Load hand-written profiles. Skips template rows that still say FILL IN."""
    out = []
    for row in json.loads(path.read_text(encoding="utf-8")):
        if "FILL IN" in row["about"]:
            continue
        out.append(ArtistProfile(
            profile_id=row["profile_id"],
            about=row["about"],
            state=row.get("state"),
            career_stage=row.get("career_stage"),
            wanted_types=tuple(row.get("wanted_types") or ALL_TYPES),
            max_fee=row.get("max_fee"),
        ))
    return out
