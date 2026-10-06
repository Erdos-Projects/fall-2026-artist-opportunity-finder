"""Scrape Hyperallergic's monthly opportunities posts using Firecrawl.

Same job as hyperallergic.py, but instead of picking fields out of the HTML
with BeautifulSoup, Firecrawl's LLM reads each post and returns the fields.
This version also returns fees.

Needs a Firecrawl API key in the FIRECRAWL_API_KEY environment variable.

Usage (from the project root):
    python scrapers/hyperallergic_firecrawl.py              # newest month only
    python scrapers/hyperallergic_firecrawl.py --months 10  # newest 10 months

Writes one line per opportunity to data/raw/hyperallergic_firecrawl.jsonl.
Firecrawl's answers are saved in data/raw/_cache/hyperallergic_firecrawl so
credits are never spent twice on the same post.
"""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

from hyperallergic import collect_post_urls, resolve_url

API_URL = "https://api.firecrawl.dev/v2/scrape"

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "raw" / "_cache" / "hyperallergic_firecrawl"
OUT_FILE = ROOT / "data" / "raw" / "hyperallergic_firecrawl.jsonl"

PROMPT = (
    "Extract every opportunity listed in this article. "
    "Copy title, description, deadline, and fees word for word from the page. "
    "Do not summarize, reword, or reformat them. "
    "fees: the exact words that state an application or entry fee, including "
    "'no fee' statements. Use null when the listing does not mention a fee. "
    "Prize money, stipends, and grant amounts are not fees. "
    "website: the URL of the last link in the listing. "
    "type: decided by the section heading the listing sits under. "
    "'Awards & Grants' is Grant, 'Open Calls' is Open Call, "
    "'Residencies & Fellowships' is Residency/Fellowship."
)

# The shape of the answer we want back. Firecrawl makes the LLM follow it.
SCHEMA = {
    "type": "object",
    "properties": {
        "opportunities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "deadline": {"type": "string"},
                    "fees": {"type": ["string", "null"]},
                    "website": {"type": "string"},
                    "type": {"type": "string", "enum": ["Grant", "Open Call", "Residency/Fellowship"]},
                },
                "required": ["title", "description", "deadline", "fees", "website", "type"],
            },
        }
    },
    "required": ["opportunities"],
}


def extract(post_url, api_key):
    """Return Firecrawl's answer for one post, reading from the cache when we have it."""
    cache_file = CACHE_DIR / (post_url.rstrip("/").split("/")[-1] + ".json")
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    response = requests.post(
        API_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "url": post_url,
            "onlyMainContent": True,
            # markdown is the page text, used below to check the fees.
            "formats": ["markdown", {"type": "json", "prompt": PROMPT, "schema": SCHEMA}],
        },
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()["data"]

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def squash(text):
    """Collapse all whitespace so two pieces of text can be compared."""
    return " ".join(text.split())


def load_done_posts():
    """Return the post URLs that are already saved in the output file."""
    if not OUT_FILE.exists():
        return set()
    with OUT_FILE.open(encoding="utf-8") as f:
        return {json.loads(line)["post_url"] for line in f if line.strip()}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--months", type=int, default=1, help="how many monthly posts to scrape, newest first")
    args = parser.parse_args()

    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        raise SystemExit("Set the FIRECRAWL_API_KEY environment variable first.")

    done = load_done_posts()
    for post_url in collect_post_urls(args.months):
        if post_url in done:
            print(f"already saved  {post_url}")
            continue

        data = extract(post_url, api_key)
        listings = data["json"]["opportunities"]
        page_text = squash(data.get("markdown", ""))
        scraped_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

        with OUT_FILE.open("a", encoding="utf-8") as f:
            for listing in listings:
                # Keep the link as listed, and make website the real address.
                listing["listed_link"] = listing["website"]
                listing["website"] = resolve_url(listing["website"])
                listing.update(
                    source="hyperallergic",
                    extracted_by="firecrawl",
                    post_title=data["metadata"].get("title"),
                    post_url=post_url,
                    scraped_at=scraped_at,
                )
                f.write(json.dumps(listing, ensure_ascii=False) + "\n")

        print(f"saved {len(listings):>3}      {post_url}")
        # An LLM can reword a value. Flag any fee that is not on the page as written.
        for listing in listings:
            if listing["fees"] and squash(listing["fees"]) not in page_text:
                print(f"   fee not found word for word: {listing['title']} -> {listing['fees']}")


if __name__ == "__main__":
    main()
