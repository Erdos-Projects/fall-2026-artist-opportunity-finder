"""Score an LLM on the gold set, the same way the fine-tuned model and the regex baseline are scored.

The LLM is asked, with the same prompt used for the silver labels (scripts/labeling/silver_llm.py,
prompt v2), to quote every mention of the five fields. Each quote is located on the page to get
character offsets (a quote that cannot be found verbatim is dropped and counted as unsupported),
then scored with evaluate.py. Cost and latency are recorded per call.

One decision made before running: this is a zero-shot comparison. The prompt is the silver prompt
as it is, NOT adapted to the gold labeling rules (for example it skips "free" and does not label
inclusive phrases). Gold listings are sent once, here.

  python models/extraction/llm_gold.py                      # claude-opus-5-5
  python models/extraction/llm_gold.py --model claude-sonnet-5-5
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "labeling"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate as ev  # noqa: E402
import silver_llm as sl  # noqa: E402

LABELED = ROOT / "data" / "labeled"
RESULTS = ROOT / "docs" / "results"
# USD per million tokens (input, output), from the Claude API model table checked on 2026-11-11
PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0)}


def call(client, model, listing_id, title, text, cache_dir):
    path = cache_dir / f"{listing_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    t0 = time.time()
    message = client.messages.create(
        model=model, max_tokens=8000, system=sl.SYSTEM,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": sl.SCHEMA}},
        messages=[{"role": "user", "content": f"Title: {title}\n\nPage text:\n{text}"}],
    )
    seconds = time.time() - t0
    if message.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"{listing_id}: stop_reason={message.stop_reason}")
    reply = "".join(b.text for b in message.content if getattr(b, "type", None) == "text")
    rec = {"mentions": json.loads(reply), "seconds": seconds,
           "usage": {"input": message.usage.input_tokens, "output": message.usage.output_tokens}}
    path.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Add ANTHROPIC_API_KEY to .env")
    import anthropic
    workspace = (os.environ.get("ANTHROPIC_WORKSPACE_ID") or "").strip()
    client = anthropic.Anthropic(default_headers={"anthropic-workspace-id": workspace} if workspace else None)

    eg = json.loads((LABELED / "eval_gold.json").read_text(encoding="utf-8"))
    titles = {t["data"]["listing_id"]: t["data"].get("title", "")
              for t in json.loads((LABELED / "gold_scored.json").read_text(encoding="utf-8"))}
    gold = {lid: [tuple(s) for s in v["spans"]] for lid, v in eg.items()}
    texts = {lid: v["text"] for lid, v in eg.items()}
    cache_dir = LABELED / "_cache" / f"gold_llm_{args.model}"
    cache_dir.mkdir(parents=True, exist_ok=True)

    ids = sorted(eg)
    with ThreadPoolExecutor(args.workers) as pool:
        recs = list(pool.map(lambda lid: call(client, args.model, lid, titles[lid], texts[lid], cache_dir), ids))

    pred, stats = {}, {"items": 0, "ok": 0, "no_context": 0, "text_not_found": 0, "ambiguous": 0}
    for lid, rec in zip(ids, recs):
        spans, st = sl.llm_spans({"page_text": texts[lid]}, rec)
        for k in stats:
            stats[k] += st[k]
        pred[lid] = [(f, s, e) for f, lst in spans.items() for (s, e) in lst]
    res = ev.score(gold, pred, texts)
    tin = sum(r["usage"]["input"] for r in recs)
    tout = sum(r["usage"]["output"] for r in recs)
    secs = [r["seconds"] for r in recs]
    pin, pout = PRICES[args.model]
    cost = tin / 1e6 * pin + tout / 1e6 * pout
    res["run"] = {"model": args.model, "prompt": "silver prompt v2, zero-shot", "listings": len(ids),
                  "input_tokens": tin, "output_tokens": tout, "cost_usd": round(cost, 3),
                  "cost_per_1000_listings_usd": round(cost / len(ids) * 1000, 1),
                  "mean_seconds_per_call": round(sum(secs) / len(secs), 1), "max_seconds": round(max(secs), 1),
                  "quotes": stats, "unsupported_quote_rate": round(
                      (stats["text_not_found"] + stats["ambiguous"]) / max(1, stats["items"]), 3)}
    md = ev.to_markdown(res, f"{args.model} on gold ({len(ids)} listings, zero-shot with the silver prompt)")
    md += (f"\n\nQuotes returned: {stats['items']}; not found on the page: {stats['text_not_found']}; "
           f"ambiguous: {stats['ambiguous']}.\nTokens: {tin} in, {tout} out. Cost: ${cost:.2f} "
           f"(${cost / len(ids) * 1000:.0f} per 1,000 listings). Latency: {sum(secs) / len(secs):.1f} s per call "
           f"(max {max(secs):.1f} s).")
    name = f"llm_gold_{args.model}"
    (RESULTS / f"{name}.md").write_text(md, encoding="utf-8")
    (RESULTS / f"{name}.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    json.dump({k: v for k, v in pred.items()}, open(LABELED / f"predictions_gold_{args.model}.json", "w"))
    print(md)


if __name__ == "__main__":
    main()
