"""Fetch each listing's organizer page as text, using Firecrawl.

The Hyperallergic and Res Artis listings link to the organizer's own page. Those
pages hold the long, messy text the extraction model has to learn from. Each
page is saved with the fields its aggregator listed (title, deadline, fees), so
they can be matched back into the page text when labeling.

Needs a Firecrawl API key as FIRECRAWL_API_KEY in the .env file at the project root.

Usage (from the project root):
    python scrapers/organizer_pages.py                    # list the domains, fetch nothing
    python scrapers/organizer_pages.py --scrape --limit 5
    python scrapers/organizer_pages.py --scrape

Each organizer has its own terms of use, and this script cannot read them.
Run it without --scrape first, read the terms of the domains it lists, and add
any that forbid automated access to SKIP_DOMAINS. It checks robots.txt for you.

Text only (no LLM extraction), 1 credit per page. Writes one line per page to
data/raw/organizer_pages.jsonl in the shared record format (see
common.make_record). Pages already saved are skipped, and Firecrawl's answers
are cached in data/raw/_cache/organizer_pages.
"""

import argparse
import hashlib
import json
from collections import Counter
from urllib.parse import urldefrag, urlparse
from urllib.robotparser import RobotFileParser

import requests

from common import (
    CACHE_DIR,
    RAW_DIR,
    USER_AGENT,
    append_records,
    firecrawl_page,
    load_api_key,
    load_saved,
    make_record,
    published_at,
)

PARENT_FILES = [RAW_DIR / "hyperallergic.jsonl", RAW_DIR / "resartis.jsonl"]
PAGE_CACHE = CACHE_DIR / "organizer_pages"
OUT_FILE = RAW_DIR / "organizer_pages.jsonl"

# Never fetched.
SKIP_DOMAINS = {
    # Social media and unfetched short links.
    "instagram.com", "facebook.com", "twitter.com", "x.com", "linkedin.com", "youtube.com", "bit.ly",
    # Application forms and platforms. The page text is mostly empty.
    "forms.gle", "docs.google.com", "drive.google.com", "jotform.com", "typeform.com", "submittable.com",
    # The aggregators themselves.
    "hyperallergic.com", "resartis.org",
    # Terms of use forbid automated access (checked October 2026).
    "wearecreativewest.org", "callforentry.org", "zapplication.org", "creative-capital.org",
    "artconnect.com", "artworkarchive.com",
}

_robots = {}


def is_skipped(url):
    host = urlparse(url).netloc.lower()
    return any(host == domain or host.endswith("." + domain) for domain in SKIP_DOMAINS)


def allowed_by_robots(url):
    """True if the site's robots.txt allows the page. A site that blocks us from reading it counts as no."""
    parts = urlparse(url)
    if parts.netloc not in _robots:
        parser = RobotFileParser()
        try:
            response = requests.get(
                f"{parts.scheme}://{parts.netloc}/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=15
            )
            if response.status_code in (401, 403):
                parser.disallow_all = True
            elif response.status_code == 200:
                parser.parse(response.text.splitlines())
            else:
                parser.allow_all = True
        except requests.RequestException:
            parser.allow_all = True
        _robots[parts.netloc] = parser
    return _robots[parts.netloc].can_fetch("*", url)


def load_parents():
    """Return {organizer url: the saved listing that links to it}, skipping links we never fetch."""
    parents = {}
    for path in PARENT_FILES:
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                url = urldefrag(row.get("website") or "")[0]
                if url.startswith("http") and not is_skipped(url):
                    parents.setdefault(url, row)
    return parents


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--scrape", action="store_true", help="fetch the pages (without this, only list the domains)")
    parser.add_argument("--limit", type=int, default=None, help="only fetch this many pages")
    args = parser.parse_args()

    parents = load_parents()
    domains = Counter(urlparse(url).netloc.lower().removeprefix("www.") for url in parents)
    print(f"{len(parents)} organizer pages on {len(domains)} domains")

    if not args.scrape:
        print("Read each domain's terms of use before scraping. Most pages first:")
        for domain, count in domains.most_common():
            print(f"  {count:>3}  {domain}")
        return

    api_key = load_api_key()
    saved = load_saved(OUT_FILE)
    todo = [(url, row) for url, row in parents.items() if url not in saved][: args.limit]
    print(f"{len(todo)} to fetch")

    for url, parent in todo:
        if not allowed_by_robots(url):
            print(f"robots.txt says no  {url}")
            continue
        cache_file = PAGE_CACHE / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".json")
        try:
            page = firecrawl_page(url, api_key, cache_file)
        except requests.RequestException as error:
            print(f"failed  {url}  ({error})")
            continue

        text = page.get("markdown", "")
        record = make_record(
            source="organizer",
            source_url=url,
            type=parent["type"],
            title=parent["title"],
            description=parent["description"],
            deadline=parent["deadline"],
            fees=parent["fees"],
            website=url,
            raw_text=text,
            published_at=published_at(page),
            listed_in=parent["source_url"],
            listed_by=parent["source"],
        )
        append_records(OUT_FILE, [record])
        note = "   (very short, maybe a form or an error page)" if len(text) < 300 else ""
        print(f"saved  {url}{note}")


if __name__ == "__main__":
    main()
