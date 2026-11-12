"""LLM judge: rate each (artist profile, listing) pair in the rating pool on the same
0 to 3 fit scale human raters would use.

The judge sees only the artist profile and the listing text. It is never told which
ranker returned the listing or at what rank. Every answer is cached in
data/labeled/_cache/llm_judge/, so reruns cost nothing.

  python -m models.matching.llm_judge --limit 5     # try a few first
  python -m models.matching.llm_judge               # whole pool

Output: data/labeled/judged_llm.csv  (profile_id, listing_id, rating, reason, judge)
NOTE for the writeup: these are model ratings, not artist ratings. Validate against a
small human-rated subset (see compare_judges, to be added) before trusting them.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv

from .data import ROOT, load_listings, match_text

LABELED = ROOT / "data" / "labeled"
CACHE = LABELED / "_cache" / "llm_judge"
MODEL = "claude-sonnet-5-5"
PROMPT_VERSION = "v1"

SYSTEM = """You judge how well an art opportunity (grant, fellowship, residency, or open call) fits a specific artist, so we can test search rankings.

Rate FIT on this scale:
0 = Not a fit: wrong medium or kind of work, or the listing clearly excludes this artist (for example, only for residents of one city or country they are not in, or only for a career stage they are clearly not in).
1 = Weak fit: loosely related, or the artist would apply only if nothing better existed.
2 = Good fit: matches the artist's medium or themes, and they could plausibly apply.
3 = Great fit: you would tell this artist to apply right away.

Rules:
- Judge fit between the artist's practice and the opportunity. Ignore deadlines, they are not part of this rating.
- Ignore location unless the listing clearly rules the artist out; then rate 0. Many opportunities accept international applicants.
- Do not reward a listing for merely sharing a generic word like "artist" or "arts".
- Use only what the listing text says. Do not assume details it does not state.
Give a one sentence reason."""

SCHEMA = {
    "type": "object",
    "properties": {
        "rating": {"type": "integer", "enum": [0, 1, 2, 3]},
        "reason": {"type": "string"},
    },
    "required": ["rating", "reason"],
    "additionalProperties": False,
}


def _cache_file(profile_id: str, listing_id: str):
    return CACHE / f"{profile_id}__{listing_id}.json"


def judge_one(client, row: dict, listing: dict, model: str) -> dict:
    path = _cache_file(row["profile_id"], row["listing_id"])
    if path.exists():
        rec = json.loads(path.read_text(encoding="utf-8"))
        if rec.get("prompt_version") == PROMPT_VERSION and rec.get("model") == model:
            return rec
    user = (
        f"ARTIST PROFILE:\n{row['artist_profile']}\n\n"
        f"OPPORTUNITY:\nType: {listing['type']}\nTitle: {listing['title']}\n\n"
        f"{match_text(listing)}"
    )
    msg = client.messages.create(
        model=model,
        max_tokens=500,
        system=SYSTEM,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": user}],
    )
    if msg.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"stop_reason={msg.stop_reason}")
    answer = json.loads("".join(b.text for b in msg.content if getattr(b, "type", None) == "text"))
    rec = {"profile_id": row["profile_id"], "listing_id": row["listing_id"],
           "rating": answer["rating"], "reason": answer["reason"],
           "model": model, "prompt_version": PROMPT_VERSION}
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()

    load_dotenv(ROOT / ".env")
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    by_id = {l["listing_id"]: l for l in load_listings()}
    with open(LABELED / "rating_pool.csv", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if a.limit:
        rows = rows[: a.limit]

    with ThreadPoolExecutor(a.workers) as ex:
        recs = list(ex.map(lambda r: judge_one(client, r, by_id[r["listing_id"]], a.model), rows))

    out = LABELED / ("judged_llm.csv" if not a.limit else "judged_llm_sample.csv")
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["profile_id", "listing_id", "rating", "reason", "judge"])
        for r in recs:
            w.writerow([r["profile_id"], r["listing_id"], r["rating"], r["reason"], r["model"]])
    dist = {k: sum(1 for r in recs if r["rating"] == k) for k in range(4)}
    print(f"judged {len(recs)} rows -> {out.name}   rating counts: {dist}")


if __name__ == "__main__":
    main()
