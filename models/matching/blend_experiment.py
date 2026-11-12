"""Exploratory: does blending BM25 and embedding scores beat either alone?

Blends tried
  RRF          Reciprocal Rank Fusion: score = 1/(60+rank_bm25) + 1/(60+rank_emb).
               No tuning knob, so it is the fair headline blend.
  alpha=...    Weighted mix of per-profile z-scores. alpha is BM25's weight. These are
               EXPLORATORY: with 15 profiles, picking the best alpha overfits. Report all
               of them, never only the winner.

A blend's top 10 can contain listings nobody rated. We have the LLM judge rate those
(cached, written to judged_llm_extra.csv) and score ALL methods on the enlarged set.

  python -m models.matching.blend_experiment
"""
from __future__ import annotations

import csv
from statistics import mean

import numpy as np

from .bm25 import BM25Ranker
from .data import load_listings
from .embed import EmbeddingRanker
from .eval import LABELED, RESULTS, K, bootstrap_ci, load_ratings, ndcg_at_k, precision_at_k
from .llm_judge import MODEL, judge_one
from .profile import load_profiles


def z(x):
    x = np.asarray(x, dtype=float)
    return (x - x.mean()) / (x.std() or 1.0)


def rank_of(scores):
    order = np.argsort(-np.asarray(scores))
    r = np.empty(len(order), dtype=int)
    r[order] = np.arange(1, len(order) + 1)
    return r


def main() -> None:
    import os
    from dotenv import load_dotenv
    import anthropic
    from .data import ROOT
    load_dotenv(ROOT / ".env")
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    listings = load_listings()
    ids = [l["listing_id"] for l in listings]
    by_id = {l["listing_id"]: l for l in listings}
    profiles = load_profiles()
    bm, em = BM25Ranker(listings), EmbeddingRanker(listings)
    ratings = load_ratings(LABELED / "judged_llm.csv")
    extra_path = LABELED / "judged_llm_extra.csv"
    if extra_path.exists():
        ratings.update(load_ratings(extra_path))

    methods = ["BM25", "Embeddings", "RRF", "z-blend a=0.25", "z-blend a=0.50", "z-blend a=0.75"]
    tops: dict[str, dict[str, list[str]]] = {m: {} for m in methods}
    for p in profiles:
        b, e = np.array(bm.score(p)), np.array(em.score(p))
        scores = {
            "BM25": b, "Embeddings": e,
            "RRF": 1 / (60 + rank_of(b)) + 1 / (60 + rank_of(e)),
        }
        for a in (0.25, 0.5, 0.75):
            scores[f"z-blend a={a:.2f}"] = a * z(b) + (1 - a) * z(e)
        for m in methods:
            tops[m][p.profile_id] = [ids[i] for i in np.argsort(-scores[m])[:K]]

    # Judge any top-10 listing that has no rating yet.
    need = sorted({(pid, lid) for m in methods for pid, t in tops[m].items() for lid in t
                   if (pid, lid) not in ratings})
    print(f"unrated (profile, listing) pairs to judge: {len(need)}")
    about = {p.profile_id: p.about for p in profiles}
    new = []
    for pid, lid in need:
        rec = judge_one(client, {"profile_id": pid, "listing_id": lid, "artist_profile": about[pid]},
                        by_id[lid], MODEL)
        ratings[(pid, lid)] = rec["rating"]
        new.append(rec)
    if new:
        with open(extra_path, "a", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            if f.tell() == 0:
                w.writerow(["profile_id", "listing_id", "rating", "reason", "judge"])
            for r in new:
                w.writerow([r["profile_id"], r["listing_id"], r["rating"], r["reason"], r["model"]])

    per = {m: {"p": [], "n": []} for m in methods}
    for p in profiles:
        pool = [v for (pid, _), v in ratings.items() if pid == p.profile_id]
        for m in methods:
            got = [ratings[(p.profile_id, lid)] for lid in tops[m][p.profile_id]]
            per[m]["p"].append(precision_at_k(got))
            per[m]["n"].append(ndcg_at_k(got, pool))

    lines = ["# Blend experiment (exploratory)", "",
             f"Profiles: {len(profiles)}. Ratings: LLM judge, enlarged with {len(new)} new ratings so every top 10 is fully rated. "
             "Treat as directional; the alpha rows are exploratory and picking a winner would overfit.", "",
             "| Method | Precision@10 | NDCG@10 | NDCG diff vs BM25 [95% CI] |", "|---|---|---|---|"]
    for m in methods:
        d = [x - y for x, y in zip(per[m]["n"], per["BM25"]["n"])]
        ci = "" if m == "BM25" else f"{mean(d):+.3f} [{bootstrap_ci(d)[0]:+.3f}, {bootstrap_ci(d)[1]:+.3f}]"
        lines.append(f"| {m} | {mean(per[m]['p']):.3f} | {mean(per[m]['n']):.3f} | {ci} |")
    report = "\n".join(lines) + "\n"
    (RESULTS / "matching_blend_experiment.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
