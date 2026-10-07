"""Scrape Hyperallergic's monthly "Opportunities in <Month> <Year>" posts.

Usage (from the project root):
    python scrapers/hyperallergic.py              # newest 22 months
    python scrapers/hyperallergic.py --months 3   # newest 3 months

Writes one line per opportunity to data/raw/hyperallergic.jsonl, using the
record format shared by all scrapers (see common.make_record). Downloaded pages
are saved in data/raw/_cache/hyperallergic so nothing is downloaded twice.
Months already in the output file are skipped.
"""

import argparse
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from common import (
    CACHE_DIR,
    RAW_DIR,
    USER_AGENT,
    append_records,
    find_fee_text,
    load_saved,
    make_record,
    resolve_url,
)

TAG_URL = "https://hyperallergic.com/tag/opportunities/"
DELAY_SECONDS = 3

PAGE_CACHE = CACHE_DIR / "hyperallergic"
OUT_FILE = RAW_DIR / "hyperallergic.jsonl"


def type_from_heading(heading):
    """Map a section heading to one of our types.

    The headings changed over time ("Awards & Grants", "Grants & Awards",
    "Residencies & Fellowships", "Residencies, Workshops, & Fellowships", ...),
    so this matches on words. Returns None for a section to skip (jobs), and
    the heading itself if it is not recognized.
    """
    words = heading.lower()
    if "job" in words:
        return None
    if "open call" in words:
        return "Open Call"
    if "residenc" in words or "fellowship" in words:
        return "Residency/Fellowship"
    if "grant" in words or "award" in words:
        return "Grant"
    return heading


def fetch(url, use_cache=True):
    """Return the HTML for a URL, reading from the cache when we have it."""
    cache_file = PAGE_CACHE / (url.rstrip("/").split("/")[-1] + ".html")
    if use_cache and cache_file.exists():
        return cache_file.read_text(encoding="utf-8")

    time.sleep(DELAY_SECONDS)
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"

    if use_cache:
        PAGE_CACHE.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(response.text, encoding="utf-8")
    return response.text


def collect_post_urls(months):
    """Walk the tag pages, newest first, and return the monthly post URLs."""
    post_urls = []
    page_url = TAG_URL
    while page_url and len(post_urls) < months:
        # The tag pages change every month, so they are never cached.
        soup = BeautifulSoup(fetch(page_url, use_cache=False), "lxml")
        for card in soup.select("article.gh-card"):
            title = card.select_one(".gh-card-title")
            link = card.select_one("a.gh-card-link")
            # The tag also holds sponsored announcements. Keep the roundups only.
            if title and link and title.get_text(strip=True).startswith("Opportunities in"):
                post_urls.append(urljoin(page_url, link["href"]))
        next_link = soup.find("link", rel="next")
        page_url = next_link["href"] if next_link else None
    return post_urls[:months]


def parse_listing(paragraph):
    """Turn one <p> into a dict of fields, or return None if it does not fit."""
    links = paragraph.find_all("a")
    link = links[-1]["href"] if links else None

    # A listing is "title <br> description <br> Deadline: ... | link".
    for br in paragraph.find_all("br"):
        br.replace_with("\n")
    raw_text = paragraph.get_text()
    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
    if len(lines) < 2:
        return None

    # The line break before "Deadline:" is sometimes missing, so search the
    # text after the title as one string and use the last "Deadline:" in it.
    # A short qualifier is allowed before the colon ("Deadline & Fee:").
    body = " ".join(lines[1:])
    matches = list(re.finditer(r"Deadlines?[^:|\n]{0,20}:\s*(?P<deadline>[^|]+)", body))
    if not matches:
        return None
    match = matches[-1]

    return {
        "title": lines[0],
        "description": body[: match.start()].strip(),
        "deadline": match.group("deadline").strip(),
        "link": link,
        "raw_text": raw_text,
    }


def parse_post(html):
    """Return (listings, skipped, published_at) for one monthly post."""
    soup = BeautifulSoup(html, "lxml")
    published = soup.find("meta", property="article:published_time")
    published_at = published["content"] if published else None

    listings, skipped = [], []
    current_type = None
    for element in soup.select_one("section.gh-content").find_all(["h2", "p"], recursive=False):
        if element.name == "h2":
            heading = element.get_text(strip=True)
            if not heading:  # an empty heading, used as spacing
                continue
            current_type = type_from_heading(heading)
            if current_type == heading:
                skipped.append(f"unknown heading kept as the type: {heading!r}")
            continue
        text = element.get_text(" ", strip=True)
        # Everything after this line is a list of links to other posts.
        if text.startswith("Other opportunities closing soon"):
            current_type = None
            continue
        # Listings start with a bold title and only appear under a wanted heading.
        if current_type is None or not element.find("strong"):
            continue

        listing = parse_listing(element)
        if listing is None:
            skipped.append(f"could not parse: {text[:80]}")
            continue
        listing["type"] = current_type
        listings.append(listing)
    return listings, skipped, published_at


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--months", type=int, default=22, help="how many monthly posts to scrape, newest first")
    args = parser.parse_args()

    saved = load_saved(OUT_FILE)
    post_urls = collect_post_urls(args.months)
    print(f"found {len(post_urls)} monthly posts (asked for {args.months})")

    for post_url in post_urls:
        if post_url in saved:
            print(f"already saved  {post_url}")
            continue

        listings, skipped, published_at = parse_post(fetch(post_url))
        records = [
            make_record(
                source="hyperallergic",
                source_url=post_url,
                type=listing["type"],
                title=listing["title"],
                description=listing["description"],
                deadline=listing["deadline"],
                fees=find_fee_text(listing["description"], listing["deadline"]),
                website=resolve_url(listing["link"]),
                raw_text=listing["raw_text"],
                published_at=published_at,
            )
            for listing in listings
        ]
        append_records(OUT_FILE, records)

        print(f"saved {len(records):>3}      {post_url}")
        for note in skipped:
            print(f"   {note}")


if __name__ == "__main__":
    main()
