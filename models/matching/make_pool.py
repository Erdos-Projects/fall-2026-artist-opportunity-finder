"""Build the rating pool: the listings raters will judge for each artist profile.

For every profile we take the top-K from BM25 and the top-K from the embedding model,
merge them (removing duplicates), and SHUFFLE. Raters never see which ranker returned
what or in which position, so their ratings cannot be biased toward either method.
Both rankers are pooled so neither one gets judged on a list the other chose.

No deadline filter: raters judge FIT only (see RATING_GUIDE).

Outputs (data/labeled/):
  rating_pool.csv    for raters. Fill in the `rating` column.
  pool_key.csv       for us only. Which ranker returned each row, and at what rank.

Run:  python -m models.matching.make_pool --k 10
"""
from __future__ import annotations

import argparse
import csv
import random

from .bm25 import BM25Ranker
from .data import ROOT, load_listings
from .embed import EmbeddingRanker
from .profile import load_profiles

OUT_DIR = ROOT / "data" / "labeled"

RATING_GUIDE = """\
RATING GUIDE (judge FIT between the artist and the opportunity)
  0 = Not a fit: wrong medium or type of work, or the listing clearly excludes this
      artist (for example, only for residents of one city or country they are not in).
  1 = Weak fit: loosely related, or you would apply only if nothing better existed.
  2 = Good fit: matches their medium or themes, and they could plausibly apply.
  3 = Great fit: you would tell this artist to apply right away.
Ignore deadlines, they are not part of this rating.
Ignore location unless the listing clearly rules the artist out (then rate 0).
"""


def build_pool(k: int, seed: int) -> None:
    listings = load_listings()
    profiles = load_profiles()
    bm25 = BM25Ranker(listings)
    emb = EmbeddingRanker(listings)
    rng = random.Random(seed)

    pool_rows, key_rows = [], []
    for p in profiles:
        picked: dict[str, dict] = {}
        for name, ranker in (("bm25", bm25), ("embed", emb)):
            for rank, (l, score) in enumerate(ranker.rank(p, k=k), start=1):
                rec = picked.setdefault(l["listing_id"], {"listing": l})
                rec[f"{name}_rank"] = rank
                rec[f"{name}_score"] = round(score, 4)
        items = list(picked.values())
        rng.shuffle(items)
        for rec in items:
            l = rec["listing"]
            pool_rows.append({
                "profile_id": p.profile_id,
                "artist_profile": p.about,
                "listing_id": l["listing_id"],
                "title": l["title"],
                "type": l["type"],
                "description": l.get("description") or "",
                "link": l.get("website") or "",
                "rating": "",
            })
            key_rows.append({
                "profile_id": p.profile_id,
                "listing_id": l["listing_id"],
                "bm25_rank": rec.get("bm25_rank", ""),
                "embed_rank": rec.get("embed_rank", ""),
                "bm25_score": rec.get("bm25_score", ""),
                "embed_score": rec.get("embed_score", ""),
            })

    for name, rows in (("rating_pool.csv", pool_rows), ("pool_key.csv", key_rows)):
        with open(OUT_DIR / name, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    (OUT_DIR / "RATING_GUIDE.txt").write_text(RATING_GUIDE, encoding="utf-8")

    per = {}
    for r in key_rows:
        per[r["profile_id"]] = per.get(r["profile_id"], 0) + 1
    both = sum(1 for r in key_rows if r["bm25_rank"] != "" and r["embed_rank"] != "")
    print(f"profiles={len(profiles)}  rows={len(pool_rows)}  per-profile min/max="
          f"{min(per.values())}/{max(per.values())}  in both rankers={both}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=10, help="top-K from each ranker")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    build_pool(a.k, a.seed)
