"""Scrape Hyperallergic's monthly "Opportunities in <Month> <Year>" posts.

Usage (from the project root):
    python scrapers/hyperallergic.py              # newest month only
    python scrapers/hyperallergic.py --months 10  # newest 10 months

Writes one line per opportunity to data/raw/hyperallergic.jsonl.
Downloaded pages are saved in data/raw/_cache/hyperallergic so nothing is
downloaded twice. Months already in the output file are skipped.
"""

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

TAG_URL = "https://hyperallergic.com/tag/opportunities/"
HEADERS = {"User-Agent": "ArtistOpportunityFinder/0.1 (student research project)"}
DELAY_SECONDS = 3

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "raw" / "_cache" / "hyperallergic"
OUT_FILE = ROOT / "data" / "raw" / "hyperallergic.jsonl"

# Each monthly post groups its listings under one of these headings.
TYPE_BY_HEADING = {
    "Awards & Grants": "Grant",
    "Open Calls": "Open Call",
    "Residencies & Fellowships": "Residency/Fellowship",
}


def fetch(url, use_cache=True):
    """Return the HTML for a URL, reading from the cache when we have it."""
    cache_file = CACHE_DIR / (url.rstrip("/").split("/")[-1] + ".html")
    if use_cache and cache_file.exists():
        return cache_file.read_text(encoding="utf-8")

    time.sleep(DELAY_SECONDS)
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"

    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
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
    website = links[-1]["href"] if links else None

    # Each listing is "title <br> description <br> Deadline: ... | link".
    for br in paragraph.find_all("br"):
        br.replace_with("\n")
    raw_text = paragraph.get_text()
    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]

    deadline_lines = [line for line in lines if line.startswith("Deadline")]
    if len(lines) < 3 or not deadline_lines:
        return None

    deadline_line = deadline_lines[-1]
    deadline = deadline_line.split(":", 1)[-1].split("|")[0].strip()
    description = " ".join(lines[1 : lines.index(deadline_line)])

    return {
        "title": lines[0],
        "description": description,
        "deadline": deadline,
        "website": website,
        "raw_text": raw_text,
    }


def parse_post(html, post_url):
    """Return (listings, skipped) for one monthly post."""
    soup = BeautifulSoup(html, "lxml")
    post_title = soup.find("meta", property="og:title")["content"]
    scraped_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    listings, skipped = [], []
    current_type = None
    for element in soup.select_one("section.gh-content").find_all(["h2", "p"], recursive=False):
        if element.name == "h2":
            heading = element.get_text(strip=True)
            # An unknown heading is kept as written so it shows up in the output.
            current_type = TYPE_BY_HEADING.get(heading, heading)
            continue
        # Listings start with a bold title and only appear under a heading.
        if current_type is None or not element.find("strong"):
            continue

        listing = parse_listing(element)
        if listing is None:
            skipped.append(element.get_text(" ", strip=True)[:80])
            continue
        listing.update(
            type=current_type,
            source="hyperallergic",
            post_title=post_title,
            post_url=post_url,
            scraped_at=scraped_at,
        )
        listings.append(listing)
    return listings, skipped


def resolve_url(url):
    """Return the real address behind a listing's link.

    Most links are bit.ly short links, so this follows the redirects to see
    where they land. If a hop fails, the last address reached is returned.
    """
    if not url:
        return url
    # Hyperallergic adds this tracking tag to every outbound link.
    url = re.sub(r"[?&]ref=hyperallergic\.com$", "", url)
    # An email security wrapper that holds the real address between "__" marks.
    wrapped = re.search(r"urldefense\.com/v3/__(.+?)__;", url)
    if wrapped:
        return wrapped.group(1)
    time.sleep(1)
    try:
        # One hop at a time, so a broken destination site still leaves us its address.
        for _ in range(5):
            response = requests.head(url, headers=HEADERS, allow_redirects=False, timeout=15)
            if "Location" not in response.headers:
                break
            url = urljoin(url, response.headers["Location"])
    except requests.RequestException:
        pass
    return url


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

    done = load_done_posts()
    for post_url in collect_post_urls(args.months):
        if post_url in done:
            print(f"already saved  {post_url}")
            continue

        listings, skipped = parse_post(fetch(post_url), post_url)
        with OUT_FILE.open("a", encoding="utf-8") as f:
            for listing in listings:
                # Keep the link as listed, and make website the real address.
                listing["listed_link"] = listing["website"]
                listing["website"] = resolve_url(listing["website"])
                f.write(json.dumps(listing, ensure_ascii=False) + "\n")

        print(f"saved {len(listings):>3}      {post_url}")
        for text in skipped:
            print(f"   could not parse: {text}")


if __name__ == "__main__":
    main()
