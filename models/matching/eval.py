"""Score the rankers (BM25, embeddings) against judged ratings.

For each artist profile and each ranker we take the top 10 listings (no deadline
filter, we judge fit only) and look up each listing's 0 to 3 rating.

Metrics
  Precision@10  Share of the top 10 rated "relevant" (rating >= 2, a good or great fit).
  NDCG@10       Rewards putting the best listings first. DCG adds each listing's rating
                divided by log2(rank + 1), so a rating of 3 at rank 1 counts for far more
                than at rank 10. It is divided by the best possible DCG (the same listings
                sorted by rating) so scores run from 0 to 1 and profiles are comparable.

Listings in a top 10 that nobody rated count as 0 and are reported. With pool depth >= 10
for both rankers there should be none.

  python -m models.matching.eval                         # LLM ratings
  python -m models.matching.eval --ratings judged.csv    # human ratings, when they exist
"""
from __future__ import annotations

import argparse
import csv
import math
import random
from statistics import mean

from .bm25 import BM25Ranker
from .data import ROOT, load_listings
from .embed import EmbeddingRanker
from .profile import load_profiles

LABELED = ROOT / "data" / "labeled"
RESULTS = ROOT / "docs" / "results"
K = 10
RELEVANT_AT = 2


def load_ratings(path) -> dict[tuple[str, str], int]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {(r["profile_id"], r["listing_id"]): int(r["rating"])
                for r in csv.DictReader(f) if r["rating"] != ""}


def precision_at_k(ratings: list[int], k: int = K) -> float:
    return sum(r >= RELEVANT_AT for r in ratings[:k]) / k


def dcg(ratings: list[int], k: int = K) -> float:
    return sum(r / math.log2(i + 2) for i, r in enumerate(ratings[:k]))


def ndcg_at_k(ranked: list[int], all_rated: list[int], k: int = K) -> float:
    ideal = dcg(sorted(all_rated, reverse=True), k)
    return dcg(ranked, k) / ideal if ideal > 0 else 0.0


def bootstrap_ci(diffs: list[float], n: int = 5000, seed: int = 0) -> tuple[float, float]:
    """95% interval for the mean of per-profile differences, resampling profiles."""
    rng = random.Random(seed)
    means = sorted(mean(rng.choices(diffs, k=len(diffs))) for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n)]


def evaluate(ratings_path) -> str:
    listings = load_listings()
    profiles = load_profiles()
    ratings = load_ratings(ratings_path)
    rankers = {"BM25": BM25Ranker(listings), "Embeddings": EmbeddingRanker(listings)}

    per = {name: {"p": [], "n": []} for name in rankers}
    unjudged = {name: 0 for name in rankers}
    rows = []
    kept = []
    for p in profiles:
        pool = [v for (pid, _), v in ratings.items() if pid == p.profile_id]
        if not pool:
            continue
        kept.append(p.profile_id)
        row = [p.profile_id, len(pool)]
        for name, ranker in rankers.items():
            top = [l["listing_id"] for l, _ in ranker.rank(p, k=K)]
            got = [ratings.get((p.profile_id, lid)) for lid in top]
            unjudged[name] += sum(g is None for g in got)
            got = [g or 0 for g in got]
            per[name]["p"].append(precision_at_k(got))
            per[name]["n"].append(ndcg_at_k(got, pool))
            row += [f"{per[name]['p'][-1]:.2f}", f"{per[name]['n'][-1]:.2f}"]
        rows.append(row)

    m = {name: (mean(v["p"]), mean(v["n"])) for name, v in per.items()}
    dn = [e - b for e, b in zip(per["Embeddings"]["n"], per["BM25"]["n"])]
    dp = [e - b for e, b in zip(per["Embeddings"]["p"], per["BM25"]["p"])]
    n_lo, n_hi = bootstrap_ci(dn)
    p_lo, p_hi = bootstrap_ci(dp)
    rel = (m["Embeddings"][1] / m["BM25"][1] - 1) * 100 if m["BM25"][1] else float("nan")

    out = [
        "# Matching evaluation",
        "",
        f"Ratings: `{ratings_path.name}`. Profiles scored: {len(kept)}. Relevant means rating >= {RELEVANT_AT}. "
        "Ranking ignores deadlines (fit only). With this few profiles treat results as directional.",
        "",
        "| Ranker | Precision@10 | NDCG@10 |",
        "|---|---|---|",
        *[f"| {n} | {m[n][0]:.3f} | {m[n][1]:.3f} |" for n in rankers],
        "",
        f"Embeddings vs BM25, NDCG@10: {rel:+.1f}% relative (KPI target: +20% or more).",
        f"Mean per-profile difference (Embeddings minus BM25), 95% bootstrap interval over profiles:",
        f"- NDCG@10: {mean(dn):+.3f} [{n_lo:+.3f}, {n_hi:+.3f}]",
        f"- Precision@10: {mean(dp):+.3f} [{p_lo:+.3f}, {p_hi:+.3f}]",
        "If an interval includes 0, the difference could be noise.",
        f"Unrated listings found in top 10 (counted as 0): {unjudged}",
        "",
        "## Per profile",
        "",
        "| Profile | Rated | BM25 P@10 | BM25 NDCG | Emb P@10 | Emb NDCG |",
        "|---|---|---|---|---|---|",
        *[f"| {' | '.join(map(str, r))} |" for r in rows],
        "",
    ]
    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ratings", default=str(LABELED / "judged_llm.csv"))
    a = ap.parse_args()
    from pathlib import Path
    path = Path(a.ratings)
    report = evaluate(path)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"matching_eval_{path.stem}.md").write_text(report, encoding="utf-8")
    print(report)
