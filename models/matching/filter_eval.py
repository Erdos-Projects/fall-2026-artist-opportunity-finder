"""Does filtering by the model's extracted location and career stage help or hurt the ranking?

Two checks, on the LLM-judged ratings (judged_llm.csv plus judged_llm_extra.csv):

A. Which rated listings would the filters drop? Only profiles that have a state or a career stage
   can be filtered. A good drop removes a listing rated 0 or 1 (not a fit). A harmful drop removes a
   listing rated 2 or 3 (a fit the artist could apply to). Listings the filters keep because the field
   is "not listed" are counted too.
B. Precision@10 and NDCG@10 for BM25 and the embedding ranker, with and without the filters applied
   before ranking. A listing in the new top 10 that nobody rated counts as 0 (reported), which can only
   make the filtered result look worse, never better.

Deadlines are ignored here, as in eval.py (fit only).

  python -m models.matching.filter_eval
"""
from __future__ import annotations

from collections import Counter
from statistics import mean

from .bm25 import BM25Ranker
from .data import load_listings
from .embed import EmbeddingRanker
from .eval import LABELED, RESULTS, K, load_ratings, ndcg_at_k, precision_at_k
from .filters import career_stage_ok, load_extracted, location_ok
from .profile import load_profiles
from .states import career_state, location_state


def main() -> None:
    listings = load_listings()
    by_id = {l["listing_id"]: l for l in listings}
    profiles = load_profiles()
    extracted = load_extracted()
    ratings = load_ratings(LABELED / "judged_llm.csv")
    ratings.update(load_ratings(LABELED / "judged_llm_extra.csv"))

    # ---- A. what gets dropped
    drop = Counter()      # (kind, rating bucket) -> count
    keep_nl = Counter()   # rated pairs kept only because the field is not listed
    n_pairs = 0
    examples = []
    for p in profiles:
        if not (p.state or p.career_stage):
            continue
        for (pid, lid), r in ratings.items():
            if pid != p.profile_id or lid not in by_id:
                continue
            n_pairs += 1
            rec = extracted.get(lid, {})
            ls = location_state(rec.get("location", []), p.state)
            cs = career_state(rec.get("career_stage", []), p.career_stage)
            bucket = "good fit (2-3)" if r >= 2 else "not a fit (0-1)"
            for kind, st in (("location", ls), ("career_stage", cs)):
                if st == "mismatch":
                    drop[(kind, bucket)] += 1
                    if r >= 2 and len(examples) < 12:
                        examples.append((p.profile_id, lid, kind, r, rec.get(kind, [])[:3]))
                elif st == "not_listed":
                    keep_nl[(kind, bucket)] += 1

    # ---- B. ranking with and without the filters
    bm, em = BM25Ranker(listings), EmbeddingRanker(listings)
    res = {}
    unrated = Counter()
    for name, ranker in (("BM25", bm), ("Embeddings", em)):
        for variant in ("no filters", "location + career stage filters"):
            ps, ns = [], []
            for p in profiles:
                pool = [v for (pid, _), v in ratings.items() if pid == p.profile_id]
                if not pool:
                    continue
                cand = None
                if variant != "no filters":
                    cand = [l for l in listings if location_ok(l, p, extracted) and career_stage_ok(l, p, extracted)]
                top = [l["listing_id"] for l, _ in ranker.rank(p, candidates=cand, k=K)]
                got = [ratings.get((p.profile_id, lid)) for lid in top]
                unrated[(name, variant)] += sum(g is None for g in got)
                got = [g or 0 for g in got]
                ps.append(precision_at_k(got))
                ns.append(ndcg_at_k(got, pool))
            res[(name, variant)] = (mean(ps), mean(ns), len(ps))

    lines = ["# Filters from the extracted fields, on the judged ratings", "",
             "Extracted fields come from the fine-tuned RoBERTa model (`roberta_neg3`) run on all cleaned listings. "
             "A filter drops a listing only on a clear mismatch (see `models/matching/states.py`). Ratings are LLM "
             "judged, 15 profiles, so treat as directional.", "",
             f"## A. Rated listings the filters would drop ({n_pairs} rated pairs for profiles that have a state or a career stage)", "",
             "| Filter | Dropped, not a fit (0-1) | Dropped, good fit (2-3) | Kept because 'not listed' (not a fit / good fit) |",
             "|---|---|---|---|"]
    for kind in ("location", "career_stage"):
        lines.append(f"| {kind} | {drop[(kind, 'not a fit (0-1)')]} | {drop[(kind, 'good fit (2-3)')]} | "
                     f"{keep_nl[(kind, 'not a fit (0-1)')]} / {keep_nl[(kind, 'good fit (2-3)')]} |")
    lines += ["", "A good filter drops many 'not a fit' listings and almost no 'good fit' ones.", ""]
    if examples:
        lines += ["Examples of harmful drops (good fit removed): profile, listing, filter, rating, extracted text", ""]
        lines += [f"- {a} {b} {c} rating {d}: {e}" for a, b, c, d, e in examples]
        lines.append("")
    lines += ["## B. Ranking with and without the filters", "",
              "| Ranker | Variant | Precision@10 | NDCG@10 | Unrated in top 10 |", "|---|---|---|---|---|"]
    for (name, variant), (p_, n_, n) in res.items():
        lines.append(f"| {name} | {variant} | {p_:.3f} | {n_:.3f} | {unrated[(name, variant)]} |")
    lines += ["", f"Profiles scored: {res[('BM25', 'no filters')][2]}. Unrated listings count as 0, so the filtered rows are, if anything, understated."]
    out = "\n".join(lines) + "\n"
    (RESULTS / "matching_filters_eval.md").write_text(out, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
