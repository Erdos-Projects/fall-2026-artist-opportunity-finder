"""Scrape residency open calls from Res Artis.

The open calls list is read with plain code. Each call's own page is fetched
through Firecrawl as text only (no LLM extraction, 1 credit per page), and the
fields are then picked out of that text with plain code.

Res Artis was not asked for permission. Its robots.txt allows these pages and
its published policies do not forbid collection, but its firewall rejects
requests that identify themselves as a scraper (HTTP 403), so pages are fetched
through Firecrawl. Keep the volume low and never republish the saved data.

Needs a Firecrawl API key as FIRECRAWL_API_KEY in the .env file at the project root.

Usage (from the project root):
    python scrapers/resartis_firecrawl.py --limit 5    # try 5 open calls
    python scrapers/resartis_firecrawl.py              # all open calls on the list
    python scrapers/resartis_firecrawl.py --us-only    # only U.S. open calls

Writes one line per open call to data/raw/resartis.jsonl, using the record
format shared by all scrapers (see common.make_record). Firecrawl's answers are
saved in data/raw/_cache/resartis, so credits are never spent twice on the same
page, and open calls already saved are skipped.

Only the first page of the list is read. The list shows the calls that are open
now, sorted by deadline. A click on its "next" button did not change the list,
so this is probably all of them, but that has not been confirmed.
"""

import argparse
import re

import requests

from common import (
    CACHE_DIR,
    RAW_DIR,
    append_records,
    find_fee_text,
    firecrawl_page,
    load_api_key,
    load_saved,
    make_record,
    published_at,
)

INDEX_URL = "https://resartis.org/open-calls/"
INDEX_WAIT_MS = 4000  # the list is filled in by JavaScript

PAGE_CACHE = CACHE_DIR / "resartis"
OUT_FILE = RAW_DIR / "resartis.jsonl"

# The site spells the United States several ways.
US_COUNTRIES = {"united states", "us", "usa", "united-states/united states"}

# Sites that host call pages for many organizations. A link to one of these is
# only used for "website" when the page has no link to the organizer itself.
AGGREGATOR_DOMAINS = ("wearecreativewest.org", "callforentry.org", "zapplication.org", "resartis.org")


def parse_index(markdown):
    """Return a list of {title, url, deadline, country} from the open calls list."""
    pattern = re.compile(
        r"## \[(?P<title>.+?)\]\((?P<url>https://resartis\.org/open-call/[^)\s]+)\)\s+"
        # Rolling calls show "Open Call" in place of "Deadline: <date>".
        r"(?:Deadline: )?(?P<deadline>.+?)\s+Country: (?P<country>.+?)\s*(?:\n|$)"
    )
    return [m.groupdict() for m in pattern.finditer(markdown)]


def parse_call_page(markdown):
    """Return (body, description, website) from the text of one call page.

    body is the page text between the cookie notice at the top and the footer.
    description is the intro text before the first section heading, which is
    what the organization wrote about the residency.
    """
    start = re.search(r"\[Skip to content\]\([^)]*\)\s*", markdown)
    end = re.search(r"\[Res Artis\]\(https://resartis\.org/\?blackhole", markdown)
    body = markdown[start.end() if start else 0 : end.start() if end else len(markdown)].strip()

    description = re.split(r"^#{4,6} ", body, maxsplit=1, flags=re.M)[0].strip()

    website = None
    section = re.search(r"^#{4,6} Link to more information\s*(.*)$", body, flags=re.S | re.M)
    if section:
        urls = list(dict.fromkeys(re.findall(r"https?://[^\s)\]]+", section.group(1))))
        organizer = [u for u in urls if not any(domain in u for domain in AGGREGATOR_DOMAINS)]
        website = (organizer or urls or [None])[0]
    return body, description, website


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--limit", type=int, default=None, help="only scrape this many open calls")
    parser.add_argument("--us-only", action="store_true", help="skip open calls outside the United States")
    args = parser.parse_args()

    api_key = load_api_key()

    index = firecrawl_page(INDEX_URL, api_key, PAGE_CACHE / "_index.json", use_cache=False, wait_ms=INDEX_WAIT_MS)
    entries = parse_index(index["markdown"])
    if not entries:
        raise SystemExit("No open calls found on the list page. It may not have finished loading, try again.")
    if args.us_only:
        entries = [e for e in entries if e["country"].strip().lower() in US_COUNTRIES]

    saved = load_saved(OUT_FILE)
    todo = [e for e in entries if e["url"] not in saved][: args.limit]
    print(f"{len(entries)} open calls on the list, {len(todo)} to scrape")

    for entry in todo:
        slug = entry["url"].rstrip("/").split("/")[-1]
        try:
            page = firecrawl_page(entry["url"], api_key, PAGE_CACHE / f"{slug}.json")
        except requests.RequestException as error:
            print(f"failed  {entry['title']}  ({error})")
            continue

        body, description, website = parse_call_page(page.get("markdown", ""))
        record = make_record(
            source="resartis",
            source_url=entry["url"],
            type="Residency",
            title=entry["title"],
            description=description,
            deadline=entry["deadline"],
            fees=find_fee_text(body),
            website=website,
            raw_text=body,
            published_at=published_at(page),
        )
        append_records(OUT_FILE, [record])
        print(f"saved  {entry['title']}")


if __name__ == "__main__":
    main()
