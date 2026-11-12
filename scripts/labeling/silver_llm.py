"""Silver source 3: LLM pre-labels.

For each train and val listing, ask Claude for the exact quoted text of each
field mention plus the sentence it sits in. The quote is then searched for in the
page to get character offsets. An answer whose quote cannot be found verbatim is
dropped and counted: that is a hallucination, and the rate goes in the writeup.

Every response is cached in data/labeled/_cache/silver_llm/, so a rerun costs
nothing. The cache keeps the model's raw answer, so how quotes are located can
change without calling the API again. Gold listings are never sent.

  python scripts/labeling/silver_llm.py --limit 3     # try a few first
  python scripts/labeling/silver_llm.py               # all train and val
"""
import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from silver_common import FIELDS, LABELED, ROOT, find_all, load_listings, silver_ids

MODEL = "claude-opus-5-5"
PROMPT_VERSION = "v2"
CACHE = LABELED / "_cache" / "silver_llm"
MAX_CONTEXT_CHARS = 400

SYSTEM = """You label web pages about art opportunities (grants, fellowships, residencies, open calls) so a small model can learn to find key facts in text.

For each field below, return every mention on the page. For each mention give:
- text: the exact span, copied character for character from the page. Never reword, shorten with ellipses, or fix typos.
- context: the exact sentence or line that contains the span, copied verbatim (at most about 40 words).

Fields:
- deadline: the date an application or submission is due, such as "March 3, 2026". Label the date only, starting at the month (or the day number) and ending at the year if one is written; leave out the weekday and words like "Deadline:". If there are several rounds, label each date. Do not label event, notification, program start, or exhibition dates. A rolling deadline or no stated deadline gives an empty list.
- fee: a money amount the applicant pays to apply or submit, such as "$35". Label the amount only. With tiers, label each amount. Do not label awards, stipends, prizes, program or residency costs, or wording like "free" or "no fee".
- career_stage: who may apply by career level, such as "emerging artists", "mid-career", "students". Use the shortest phrase that names the stage.
- location: where applicants must live, work, or be from to be eligible, such as "residents of New York State" or "U.S. citizens". Use the shortest phrase. The place of the residency itself counts only if it is also an eligibility rule.
- medium: the art forms or media the opportunity accepts, such as "painting", "sculpture", "video art". Use the shortest phrase, one mention per item.

Only label what the page states. If a field is not stated, return an empty list for it. When unsure, leave it out."""

MENTION = {
    "type": "object",
    "properties": {"text": {"type": "string"}, "context": {"type": "string"}},
    "required": ["text", "context"],
    "additionalProperties": False,
}
SCHEMA = {
    "type": "object",
    "properties": {f: {"type": "array", "items": MENTION} for f in FIELDS},
    "required": FIELDS,
    "additionalProperties": False,
}


def cache_path(listing_id):
    return CACHE / f"{listing_id}.json"


def ask(client, listing, model):
    """Call the API once for one listing. Returns the cache record."""
    user = f"Title: {listing['title']}\n\nPage text:\n{listing['page_text']}"
    message = client.messages.create(
        model=model,
        max_tokens=8000,
        system=SYSTEM,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": user}],
    )
    if message.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"stop_reason={message.stop_reason}")
    reply = "".join(b.text for b in message.content if getattr(b, "type", None) == "text")
    return {
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "mentions": json.loads(reply),
        "usage": {"input": message.usage.input_tokens, "output": message.usage.output_tokens},
    }


def label_one(client, listing, model):
    path = cache_path(listing["listing_id"])
    if path.exists():
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("prompt_version") == PROMPT_VERSION:
            return "cached", record
    try:
        record = ask(client, listing, model)
    except Exception as err:
        return f"failed: {err}", None
    path.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    return "called", record


def locate(text, mention):
    """Turn one {text, context} answer into spans. Returns (spans, status).

    status is "ok", "no_context" (context not found but the text is unambiguous),
    or a drop reason: "text_not_found" or "ambiguous".
    """
    quote, context = mention["text"].strip(), mention["context"].strip()[:MAX_CONTEXT_CHARS]
    if not quote:
        return [], "text_not_found"
    spans = []
    for c_start, c_end in find_all(text, context) if context else []:
        spans += find_all(text, quote, c_start, c_end)
    if spans:
        return sorted(set(spans)), "ok"
    anywhere = find_all(text, quote)
    if not anywhere:
        return [], "text_not_found"
    if len(anywhere) == 1:
        return anywhere, "no_context"
    return [], "ambiguous"


def llm_spans(listing, record):
    """Return ({field: [(s, e)]}, stats) from a cache record."""
    text = listing["page_text"]
    out = {f: [] for f in FIELDS}
    stats = {"items": 0, "ok": 0, "no_context": 0, "text_not_found": 0, "ambiguous": 0}
    for field in FIELDS:
        for mention in record["mentions"].get(field, []):
            spans, status = locate(text, mention)
            stats["items"] += 1
            stats[status] += 1
            out[field] += spans
        out[field] = sorted(set(out[field]))
    return out, stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="only the first N listings (train first)")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Add ANTHROPIC_API_KEY=... to the .env file.")
    import anthropic

    workspace = (os.environ.get("ANTHROPIC_WORKSPACE_ID") or "").strip()
    headers = {"anthropic-workspace-id": workspace} if workspace else None
    client = anthropic.Anthropic(default_headers=headers)

    ids = silver_ids()
    todo = (ids["train"] + ids["val"])[: args.limit]
    rows = load_listings(todo)
    CACHE.mkdir(parents=True, exist_ok=True)

    with ThreadPoolExecutor(args.workers) as pool:
        results = list(pool.map(lambda lid: label_one(client, rows[lid], args.model), todo))

    counts, tokens = {"cached": 0, "called": 0, "failed": 0}, {"input": 0, "output": 0}
    for lid, (status, record) in zip(todo, results):
        counts[status.split(":")[0]] += 1
        if status.startswith("failed"):
            print(lid, status)
        elif status == "called":
            tokens["input"] += record["usage"]["input"]
            tokens["output"] += record["usage"]["output"]
    print(counts, "tokens this run:", tokens)


if __name__ == "__main__":
    main()
