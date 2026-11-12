"""Layer 2: pretrained sentence-transformer ranking (no fine-tuning).

The model turns a text into a vector (a list of numbers) so that texts with similar
MEANING get vectors pointing in similar directions. We embed every listing once,
embed the artist profile, and rank listings by cosine similarity (the angle between
the two vectors; 1.0 means same direction). Unlike BM25 this can link "sculpture"
to "installation art" even when they share no words.

Note on length: models read only the first N tokens (256 for all-MiniLM-L6-v2),
so anything past that in the match text is ignored.
"""
from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

from .data import match_text
from .profile import ArtistProfile

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class EmbeddingRanker:
    def __init__(self, listings: list[dict], model_name: str = DEFAULT_MODEL):
        self.listings = listings
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        # normalize_embeddings=True makes every vector length 1, so a plain dot
        # product equals cosine similarity.
        self.doc_vecs = self.model.encode(
            [match_text(l) for l in listings],
            normalize_embeddings=True,
            batch_size=32,
            show_progress_bar=False,
        )

    def score(self, profile: ArtistProfile) -> list[float]:
        """Cosine similarity for every listing, in the same order as self.listings."""
        q = self.model.encode([profile.query_text()], normalize_embeddings=True)[0]
        return (self.doc_vecs @ q).tolist()

    def rank(self, profile: ArtistProfile, candidates: list[dict] | None = None, k: int = 10):
        scores = np.asarray(self.score(profile))
        allowed = None if candidates is None else {c["listing_id"] for c in candidates}
        order = np.argsort(-scores)
        out = []
        for i in order:
            if allowed is None or self.listings[i]["listing_id"] in allowed:
                out.append((self.listings[i], float(scores[i])))
            if len(out) == k:
                break
        return out
