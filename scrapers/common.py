"""Helpers shared by the scrapers.

Every scraper builds its records with make_record, so listings from different
sources have the same keys and can be combined later.
"""

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
CACHE_DIR = RAW_DIR / "_cache"

USER_AGENT = "ArtistOpportunityFinder/0.1 (student research project)"
FIRECRAWL_URL = "https://api.firecrawl.dev/v2/scrape"

# Link shorteners that hide the real address of a listing.
SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "ow.ly", "buff.ly", "lnkd.in", "goo.gl", "is.gd", "rb.gy", "shorturl.at"}

FEE_WORD = re.compile(r"\bfees?\b", re.I)

# Labels added to links to track where a visitor came from. They never change the page.
TRACKING_PARAMS = {"gclid", "gbraid", "wbraid", "gad_source", "gad_campaignid", "fbclid", "srsltid", "mc_cid", "mc_eid"}


def make_record(
    *, source, source_url, type, title, description, deadline, fees, website, raw_text, published_at=None, **extra
):
    """Build one raw listing record. All sources use the same keys.

    source_url is the page the listing was found on, and is also how a page
    that is already saved gets skipped. published_at is when that page was
    published, kept so the data can be split by time later. Anything source
    specific goes in extra.
    """
    return {
        "title": title,
        "description": description,
        "deadline": deadline,
        "fees": fees,
        "website": website,
        "raw_text": raw_text,
        "type": type,
        "source": source,
        "source_url": source_url,
        "published_at": published_at,
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **extra,
    }


def find_fee_text(*texts):
    """Return the exact pieces of text that mention a fee, joined with ' | ', or None.

    This is a plain keyword match on the word "fee" or "fees". It does not
    understand the text, so a cost written another way ("costs $150") is missed.
    """
    pieces = []
    for text in texts:
        for line in (text or "").splitlines():
            if line.lstrip().startswith("#"):  # markdown headings such as "Fees and support"
                continue
            for piece in re.split(r"(?<=[.!?])\s+|;", line):
                piece = piece.strip()
                if FEE_WORD.search(piece) and piece not in pieces:
                    pieces.append(piece)
    return " | ".join(pieces) or None


def _host(url):
    return urlparse(url).netloc.lower().removeprefix("www.")


def clean_url(url):
    """Remove the parts of a link that do not change which page it opens.

    That is the #fragment (where to scroll on the page) and tracking labels
    such as utm_source=..., gclid=..., or ref=hyperallergic.com.
    """
    if not url:
        return url
    parts = urlparse(url)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
        and key.lower() not in TRACKING_PARAMS
        and not (key.lower() == "ref" and "hyperallergic" in value.lower())
    ]
    return urlunparse(parts._replace(query=urlencode(query), fragment=""))


def url_key(url):
    """A form of a link for matching: the same page always gives the same key.

    Use it to join two files on a link. It ignores http or https, "www.",
    capital letters in the host, and a trailing slash.
    """
    parts = urlparse(clean_url(url))
    return urlunparse(("https", parts.netloc.lower().removeprefix("www."), parts.path.rstrip("/") or "/", "", parts.query, ""))


_resolved_file = CACHE_DIR / "resolved_links.json"
_resolved = None


def resolve_url(url):
    """Return the real address behind a listing's link.

    Short links such as bit.ly are followed one hop at a time, and only while
    the address is still a shortener, so the organizer's own site is never
    contacted. Answers are cached, so a rerun makes no requests.
    """
    global _resolved
    if not url:
        return url
    # Hyperallergic adds tracking labels (utm_..., ref=...) to every outbound link.
    url = clean_url(url)
    # An email security wrapper that holds the real address between "__" marks.
    wrapped = re.search(r"urldefense\.com/v3/__(.+?)__;", url)
    if wrapped:
        return clean_url(wrapped.group(1))
    if _host(url) not in SHORTENERS:
        return url

    if _resolved is None:
        _resolved = json.loads(_resolved_file.read_text(encoding="utf-8")) if _resolved_file.exists() else {}
    if url in _resolved:
        return clean_url(_resolved[url])

    final = url
    time.sleep(1)
    try:
        for _ in range(5):
            if _host(final) not in SHORTENERS:
                break
            response = requests.head(final, headers={"User-Agent": USER_AGENT}, allow_redirects=False, timeout=15)
            location = response.headers.get("Location")
            if not location:
                break
            final = urljoin(final, location)
    except requests.RequestException:
        pass

    final = clean_url(final)
    _resolved[url] = final
    _resolved_file.parent.mkdir(parents=True, exist_ok=True)
    _resolved_file.write_text(json.dumps(_resolved, indent=1), encoding="utf-8")
    return final


def load_api_key():
    """Return the Firecrawl API key from the .env file at the project root."""
    load_dotenv(ROOT / ".env")
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        raise SystemExit("Add your key to the .env file as FIRECRAWL_API_KEY=...")
    return api_key


def firecrawl_page(url, api_key, cache_file, use_cache=True, wait_ms=0, delay=3):
    """Return Firecrawl's answer for one page: its text ("markdown") and "metadata".

    Text only, with no LLM extraction, so each page costs 1 credit. The answer
    is saved in cache_file, and read back from it when use_cache is True.
    """
    if use_cache and cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    time.sleep(delay)
    body = {"url": url, "formats": ["markdown"], "onlyMainContent": True}
    if wait_ms:
        body["waitFor"] = wait_ms  # pages that fill in their list with JavaScript need time
    if not use_cache:
        body["maxAge"] = 0  # ask Firecrawl for a fresh copy, not one it saved earlier
    response = requests.post(FIRECRAWL_URL, headers={"Authorization": f"Bearer {api_key}"}, json=body, timeout=120)
    response.raise_for_status()
    data = response.json()["data"]

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def published_at(data):
    """Return the publish date from a Firecrawl answer's metadata, or None."""
    metadata = data.get("metadata", {})
    return metadata.get("publishedTime") or metadata.get("datePublished")


def load_saved(out_file, key="source_url"):
    """Return the values of `key` already saved in out_file."""
    saved = set()
    if not out_file.exists():
        return saved
    with out_file.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            if key not in row:
                raise SystemExit(
                    f"{out_file.name} is in an older format. Move it aside (cached pages are "
                    "reused, so nothing is downloaded again) and run again."
                )
            saved.add(row[key])
    return saved


def append_records(out_file, records):
    """Append records to out_file, one JSON object per line."""
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("a", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
