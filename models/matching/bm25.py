"""Layer 1: BM25 keyword ranking.

BM25 scores a listing by how many of the query's words it contains, weighting rare
words more than common ones and damping the effect of very long documents.
It only matches exact words (after lowercasing and light stemming), so
"sculpture" will not match "installation art". That gap is what the
sentence-transformer in Step 3 is meant to close.
"""
from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from .data import match_text
from .profile import ArtistProfile

_TOKEN = re.compile(r"[a-z0-9]+")

# Words that carry no signal for matching. Kept small and art-agnostic on purpose.
STOPWORDS = frozenset(
    "a an and are as at be by for from in is it of on or that the this to with "
    "we you your our will can has have may who their these those about also "
    "apply application applications applicants applicant artist artists".split()
)


def _stem(tok: str) -> str:
    """Very light stemming so 'painting', 'paintings', 'painter' share a root."""
    for suffix in ("ings", "ing", "ers", "er", "ies", "es", "s", "ed"):
        if tok.endswith(suffix) and len(tok) - len(suffix) >= 4:
            return tok[: -len(suffix)]
    return tok


def tokenize(text: str) -> list[str]:
    return [_stem(t) for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS and len(t) > 1]


class BM25Ranker:
    def __init__(self, listings: list[dict]):
        self.listings = listings
        self._index = BM25Okapi([tokenize(match_text(l)) for l in listings])

    def score(self, profile: ArtistProfile) -> list[float]:
        """BM25 score for every listing, in the same order as self.listings."""
        return list(self._index.get_scores(tokenize(profile.query_text())))

    def rank(self, profile: ArtistProfile, candidates: list[dict] | None = None, k: int = 10):
        """Top-k (listing, score). `candidates` restricts ranking to a filtered subset
        (listing_ids are looked up in the full index, so scores stay comparable)."""
        scores = self.score(profile)
        allowed = None if candidates is None else {c["listing_id"] for c in candidates}
        ranked = sorted(
            ((l, s) for l, s in zip(self.listings, scores)
             if allowed is None or l["listing_id"] in allowed),
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked[:k]
