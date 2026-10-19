"""Fetch each listing's organizer page as text, using Firecrawl, and add one linked page.

The Hyperallergic and Res Artis listings link to the organizer's own page. Those
pages hold the long, messy text the extraction model has to learn from. Only the
address and the text are saved. To get a listing's title, deadline, or fees, join
this file to the listing's file on url_key (see common.py).

Many organizer pages do not state the deadline or fee. The details sit one link
deeper (an "Apply" or "Guidelines" page). So the work has three steps:

    A. fetch    Fetch the organizer page (python ... --scrape).
    B. pick     If the current page already has a deadline (regex), store no link.
                Otherwise an LLM reads the links and chooses the one most likely
                to state the deadline, fee, and who can apply, or none.
                No Firecrawl credits. Run it, read the picks, fix any that are wrong.
    C. follow   Fetch each chosen link and append its text to raw_text.

Needs a Firecrawl API key as FIRECRAWL_API_KEY in the .env file at the project root.
Step B also needs ANTHROPIC_API_KEY there, and `pip install anthropic`.
If the key is not scoped to one workspace, add ANTHROPIC_WORKSPACE_ID too.

Usage (from the project root):
    python scrapers/hyperallergic/fetch_opportunity_page.py                    # list the domains, fetch nothing
    python scrapers/hyperallergic/fetch_opportunity_page.py --scrape --limit 5
    python scrapers/hyperallergic/fetch_opportunity_page.py --scrape           # step A

    python scrapers/hyperallergic/fetch_opportunity_page.py --pick --limit 5   # step B
    python scrapers/hyperallergic/fetch_opportunity_page.py --pick
    # Review data/raw/link_picks_review.csv. Edit linked_url / linked_reason if needed.
    python scrapers/hyperallergic/fetch_opportunity_page.py --apply-review     # copy CSV edits into the jsonl
    python scrapers/hyperallergic/fetch_opportunity_page.py --follow           # step C, dry run: counts the credits
    python scrapers/hyperallergic/fetch_opportunity_page.py --follow --scrape  # step C, fetches and appends
    # --follow --scrape ignores robots.txt. SKIP_DOMAINS still applies.

Each organizer has its own terms of use, and this script cannot read them.
Run it without --scrape first, read the terms of the domains it lists, and add
any that forbid automated access to SKIP_DOMAINS. It checks robots.txt for you.
--ignore-robots turns that check off for step A (a deliberate choice by the
project owner, recorded in Plans/Progress.md). Step C (--follow --scrape)
ignores robots.txt by default. SKIP_DOMAINS and the delay between pages still apply.

Text only (no LLM extraction), 1 credit per page. Writes one line per page to
data/raw/opportunity_pages.jsonl with these keys: source_url (the cleaned link),
raw_text, published_at, and scraped_at. Step B adds linked_url and linked_reason
to that file (this is what --follow reads) and also writes
data/raw/link_picks_review.csv, a short table with no page text, for checking
picks. Editing the csv does not change the records until you run --apply-review.
Pages already saved are skipped, and Firecrawl's answers are cached in
data/raw/_cache/organizer_pages (the organizer pages) and
data/raw/_cache/linked_pages (the linked pages).

Step C sets raw_text to the organizer page's cached text, then a line
--- followed page ---, then the linked page's text. It always starts again from
the cache, so running it twice
never adds a page twice, and changing a pick only needs --follow --scrape again.
If an organizer page serves several listings, one link is chosen for the page and
the LLM sees all of those listing titles.
"""

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from dotenv import load_dotenv

# common.py lives one folder up, in scrapers/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common import (
    CACHE_DIR,
    RAW_DIR,
    ROOT,
    USER_AGENT,
    append_records,
    clean_url,
    firecrawl_page,
    load_api_key,
    load_saved,
    published_at,
    url_key,
)

PARENT_FILES = [RAW_DIR / "hyperallergic.jsonl", RAW_DIR / "resartis.jsonl"]
PAGE_CACHE = CACHE_DIR / "organizer_pages"
LINKED_CACHE = CACHE_DIR / "linked_pages"
OUT_FILE = RAW_DIR / "opportunity_pages.jsonl"
REVIEW_FILE = RAW_DIR / "link_picks_review.csv"
REVIEW_FIELDS = ["source_url", "titles", "linked_url", "linked_reason", "n_candidates", "candidates"]

# Step B settings.
PICK_MODEL = "claude-haiku-5-5"
MAX_CANDIDATES = 80
MIN_PAGE_CHARS = 200  # a page with less text than this has nothing worth following

# Never fetched.
SKIP_DOMAINS = {
    # Social media and unfetched short links.
    "instagram.com", "facebook.com", "twitter.com", "x.com", "linkedin.com", "youtube.com", "bit.ly",
    # Application forms and platforms. The page text is mostly empty.
    "forms.gle", "docs.google.com", "drive.google.com", "jotform.com", "typeform.com", "submittable.com",
    "slideroom.com",
    # The aggregators themselves.
    "hyperallergic.com", "resartis.org",
    # Terms of use forbid automated access (checked October 2026).
    "wearecreativewest.org", "callforentry.org", "zapplication.org", "creative-capital.org",
    "artconnect.com", "artworkarchive.com",
}

# [anchor](href) or [anchor](href "title"). href may be absolute, /path, or a relative file.
_LINK = re.compile(
    r"\[([^\]]{1,120})\]\(\s*<?([^\s)>]+)>?(?:\s+[\"'][^\"']*[\"'])?\s*\)"
)
_LOGIN = re.compile(r"log-?in|sign-?in|sign-?up|account|auth|/cart|checkout|password", re.I)
# Images and archives only. PDFs stay in the list: they often hold deadline, fee, and eligibility.
_ASSET = re.compile(r"\.(docx?|xlsx?|zip|jpe?g|png|gif|webp|svg)(\?|$)", re.I)
_PDF = re.compile(r"\.pdf(\?|$)", re.I)
_SKIP_HREF = re.compile(r"^(#|mailto:|tel:|javascript:|data:)", re.I)
_USEFUL = re.compile(
    r"apply|guideline|eligib|prospectus|deadline|how[\s-]?to|submission|"
    r"call[\s-]?for|open[\s-]?call|\bfees?\b",
    re.I,
)
_FAQ = re.compile(r"\bfaqs?\b|frequently[\s-]?asked", re.I)

_MONTH = (
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?"
)
_DATE = (
    rf"(?:{_MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?(?:\s*[–\-]\s*(?:{_MONTH}\s+)?\d{{1,2}}(?:st|nd|rd|th)?)?,?\s*\d{{4}}"
    r"|\d{1,2}/\d{1,2}/\d{4})"
)
# Cue and a date within a short window, either order. A lone date in a footer does not count.
_PAGE_DEADLINE = re.compile(
    rf"(?:deadline|applications?\s+(?:are\s+)?(?:due|must\s+be\s+submitted|close|closes|closing|accepted)|"
    rf"due\s+(?:by|on|date)|submit(?:ted)?\s+by|closes?\s+on|apply\s+by).{{0,160}}{_DATE}"
    rf"|{_DATE}.{{0,80}}\bdeadlines?\b"
    r"|\brolling\s+deadline\b",
    re.I | re.S,
)

PICK_PROMPT = """You help collect details about an art opportunity. The page belongs to: {titles}.
Below are links found on that page. Each line is: number | kind | link text | path.
kind is "pdf" (a downloadable document) or "page" (another HTML page).

Pick the ONE link most likely to state the application deadline, fee, and who can apply.
A guidelines, eligibility, prospectus, fees, or how-to-apply page or PDF is a good choice,
even if the filename is a hash. Prefer those over About, News, Donate, Home, or calendar.
Do not pick FAQ or "frequently asked questions" unless no other candidate could hold the
deadline or fee. If several look related, pick the one that matches the program named above.
Do not pick images, press kits, or a different program's file.
If no link is likely to help, answer null.

Reply with JSON only: {{"choice": <link number or null>, "reason": "<one short sentence>"}}

Links:
{links}"""

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


def load_links():
    """Return {url_key: cleaned url} for every link in the listing files.

    Links to the same page, even with different tracking labels, share one
    key, so each page is fetched once. Links we never fetch are left out.
    """
    links = {}
    for path in PARENT_FILES:
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            for line in f:
                url = clean_url(json.loads(line).get("website") or "")
                if url.startswith("http") and not is_skipped(url):
                    links.setdefault(url_key(url), url)
    return links


# ---------------------------------------------------------------------------
# Files: the page records and the caches
# ---------------------------------------------------------------------------

def cache_file(url, folder):
    return folder / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".json")


def cached_text(url, folder):
    """The text Firecrawl returned for a page, from the cache, or None if it is not cached."""
    path = cache_file(url, folder)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get("markdown") or ""


def load_pages():
    with OUT_FILE.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def save_pages(pages):
    """Rewrite the page file. Written to a temporary file first, so a crash cannot leave half a file."""
    tmp = OUT_FILE.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for page in pages:
            f.write(json.dumps(page, ensure_ascii=False) + "\n")
    tmp.replace(OUT_FILE)


def load_titles():
    """Return {url_key: [listing titles]} so the LLM knows which program a page is for."""
    titles = {}
    for path in PARENT_FILES:
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                url = clean_url(row.get("website") or "")
                title = (row.get("title") or "").strip()
                if url.startswith("http") and title and title not in titles.setdefault(url_key(url), []):
                    titles[url_key(url)].append(title)
    return titles


# ---------------------------------------------------------------------------
# Step B: pick a link
# ---------------------------------------------------------------------------

def site(url):
    parts = urlparse(url).netloc.lower().removeprefix("www.").split(".")
    return ".".join(parts[-2:])


def is_pdf(url):
    return bool(_PDF.search(urlparse(url).path))


def usefulness(anchor, url):
    """Higher scores are shown first, so a guidelines PDF is not cut by the 80-link cap.

    FAQ links stay in the list but sort last. They rarely hold the deadline or fee.
    """
    blob = f"{anchor} {urlparse(url).path}"
    score = 0
    if _USEFUL.search(blob):
        score += 3
    if is_pdf(url):
        score += 2
        if _USEFUL.search(blob):
            score += 2
    if _FAQ.search(blob):
        score -= 8
    return score


def format_candidate(n, anchor, url):
    """One line for the LLM. Kind and filename matter when the path is a hash."""
    path = urlparse(url).path
    name = path.rsplit("/", 1)[-1][:80]
    kind = "pdf" if is_pdf(url) else "page"
    label = anchor.strip()[:80] or name
    shown = name if is_pdf(url) else path[:90]
    return f"{n} | {kind} | {label} | {shown}"


def candidate_links(text, base):
    """Links on the page that could hold the details. Returns [(anchor text, url)].

    Only the same website. Login pages, images, archives, social media, and
    application platforms are left out. Same-site PDFs are kept.
    """
    own, seen, found = url_key(base), set(), []
    for anchor, href in _LINK.findall(text):
        href = href.strip()
        if _SKIP_HREF.search(href) or href.startswith("<"):
            continue
        url = clean_url(urljoin(base, href))
        key = url_key(url)
        if key == own or key in seen or not url.startswith("http"):
            continue
        seen.add(key)
        if site(url) != site(base) or is_skipped(url) or _ASSET.search(urlparse(url).path):
            continue
        if _LOGIN.search(urlparse(url).path + "?" + urlparse(url).query):
            continue
        found.append((anchor.strip(), url))
    found.sort(key=lambda item: -usefulness(*item))
    return found[:MAX_CANDIDATES]


def parse_choice(choice, n):
    """Turn the model's choice into a 1-based index, or None."""
    if choice is None or choice is False or choice == "":
        return None
    if isinstance(choice, str) and choice.strip().isdigit():
        choice = int(choice.strip())
    if isinstance(choice, float) and choice.is_integer():
        choice = int(choice)
    if isinstance(choice, int) and 1 <= choice <= n:
        return choice
    return None


_DEADLINE_NOISE = re.compile(r"https?://|www\.|/uploads/|wp-content", re.I)


def page_has_deadline(text):
    """True if this page already states an application deadline, so no extra link is needed."""
    if not text:
        return False
    for match in _PAGE_DEADLINE.finditer(text):
        if not _DEADLINE_NOISE.search(match.group(0)):
            return True
    return False


def message_text(message):
    """Join the text blocks. Newer models may put a thinking block first."""
    return "\n".join(block.text for block in message.content if getattr(block, "type", None) == "text")


def ask_for_link(client, titles, candidates):
    """Ask the LLM for one link. Returns (url or None, a one sentence reason)."""
    links = "\n".join(format_candidate(n, a, u) for n, (a, u) in enumerate(candidates, 1))
    reply = message_text(
        client.messages.create(
            model=PICK_MODEL,
            max_tokens=1024,
            thinking={"type": "disabled"},
            messages=[{"role": "user", "content": PICK_PROMPT.format(titles=" / ".join(titles[:4]), links=links)}],
        )
    )
    match = re.search(r"\{.*\}", reply, re.S)
    try:
        data = json.loads(match.group(0))
        choice, reason = data.get("choice"), str(data.get("reason", ""))
    except (AttributeError, ValueError):
        return None, f"unreadable reply: {reply[:80]}"
    index = parse_choice(choice, len(candidates))
    if index:
        return candidates[index - 1][1], reason
    return None, reason or "no link likely to help"


def page_candidates(page):
    """Rebuild the menu the LLM would see, from the cached organizer page."""
    url = page["source_url"]
    text = cached_text(url, PAGE_CACHE)
    if text is None or len(text) < MIN_PAGE_CHARS:
        return []
    return candidate_links(text, url)


def review_row(page, all_titles):
    url = page["source_url"]
    titles = all_titles.get(url_key(url)) or []
    cands = page_candidates(page)
    return {
        "source_url": url,
        "titles": " / ".join(titles[:4]),
        "linked_url": page.get("linked_url") or "",
        "linked_reason": page.get("linked_reason") or "",
        "n_candidates": len(cands),
        "candidates": "\n".join(format_candidate(n, a, u) for n, (a, u) in enumerate(cands, 1)),
    }


def write_review_csv(pages, all_titles):
    """Short table for the pages in this --pick run. No page text. --follow does not read this file.

    Earlier picked rows stay in the file. Unpicked rows from a previous full dump are dropped.
    """
    by_key = {}
    if REVIEW_FILE.exists():
        with REVIEW_FILE.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                src = (row.get("source_url") or "").strip()
                if src and ((row.get("linked_url") or "").strip() or (row.get("linked_reason") or "").strip()):
                    by_key[url_key(src)] = row
    for page in pages:
        by_key[url_key(page["source_url"])] = review_row(page, all_titles)
    rows = list(by_key.values())
    with REVIEW_FILE.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {REVIEW_FILE.name} (review only, this pick batch plus earlier picks)")


def apply_review():
    """Copy linked_url and linked_reason from the review csv into opportunity_pages.jsonl."""
    if not REVIEW_FILE.exists():
        raise SystemExit(f"No {REVIEW_FILE.name}. Run --pick first.")
    pages = load_pages()
    by_key = {url_key(p["source_url"]): p for p in pages}
    changed, missing, blocked = 0, 0, 0
    with REVIEW_FILE.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows or "source_url" not in rows[0] or "linked_url" not in rows[0]:
        raise SystemExit(f"{REVIEW_FILE.name} needs source_url and linked_url columns.")
    for row in rows:
        src = (row.get("source_url") or "").strip()
        page = by_key.get(url_key(src)) if src else None
        if page is None:
            missing += 1
            print(f"not in {OUT_FILE.name}  {src}")
            continue
        new_url = clean_url((row.get("linked_url") or "").strip())
        new_reason = (row.get("linked_reason") or "").strip()
        if new_url and is_skipped(new_url):
            blocked += 1
            print(f"SKIP_DOMAINS, left unchanged  {new_url}")
            continue
        old_url = page.get("linked_url") or ""
        old_reason = page.get("linked_reason") or ""
        if new_url == old_url and new_reason == old_reason:
            continue
        page["linked_url"] = new_url
        page["linked_reason"] = new_reason or "edited in link_picks_review.csv"
        changed += 1
    save_pages(pages)
    print(f"Updated {changed} records in {OUT_FILE.name} from {REVIEW_FILE.name}")
    if missing:
        print(f"{missing} csv rows had no matching page")
    if blocked:
        print(f"{blocked} csv links were on SKIP_DOMAINS and were not applied")


def review_overrides(pages):
    """True if the review csv has a different linked_url or linked_reason than the jsonl."""
    if not REVIEW_FILE.exists():
        return False
    by_key = {url_key(p["source_url"]): p for p in pages}
    with REVIEW_FILE.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows or "linked_url" not in (rows[0] or {}):
        return False
    for row in rows:
        src = (row.get("source_url") or "").strip()
        page = by_key.get(url_key(src)) if src else None
        if page is None:
            continue
        csv_url = clean_url((row.get("linked_url") or "").strip())
        csv_reason = (row.get("linked_reason") or "").strip()
        rec_url = page.get("linked_url") or ""
        rec_reason = page.get("linked_reason") or ""
        if csv_url != rec_url or (csv_reason and csv_reason != rec_reason):
            return True
    return False


def pick_links(limit, repick):
    """Step B: write linked_url and linked_reason into each page record. Uses no Firecrawl credits."""
    load_dotenv(ROOT / ".env")
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Add ANTHROPIC_API_KEY=... to the .env file.")
    import anthropic

    workspace = (os.environ.get("ANTHROPIC_WORKSPACE_ID") or "").strip()
    headers = {"anthropic-workspace-id": workspace} if workspace else None
    client = anthropic.Anthropic(default_headers=headers)
    pages = load_pages()
    all_titles = load_titles()
    todo = [p for p in pages if repick or "linked_reason" not in p][:limit]
    print(f"{len(todo)} pages to check ({len(pages)} in the file)")

    try:
        for n, page in enumerate(todo, 1):
            url = page["source_url"]
            titles = all_titles.get(url_key(url)) or [url]
            text = cached_text(url, PAGE_CACHE)
            if text is None:
                print(f"[{n}/{len(todo)}] no cached page, skipped  {url}")
                continue
            if page_has_deadline(text):
                link, reason = None, "deadline already on this page"
            else:
                candidates = candidate_links(text, url) if len(text) >= MIN_PAGE_CHARS else []
                if candidates:
                    link, reason = ask_for_link(client, titles, candidates)
                else:
                    link, reason = None, "no usable links on the page"
            page["linked_url"], page["linked_reason"] = link or "", reason
            print(f"[{n}/{len(todo)}] {titles[0][:45]:45} -> {link or 'none'}   ({reason[:70]})")
            if n % 10 == 0:
                save_pages(pages)
    finally:
        save_pages(pages)
        write_review_csv(todo, all_titles)


# ---------------------------------------------------------------------------
# Step C: follow the picked link
# ---------------------------------------------------------------------------

def follow_links(limit, scrape, ignore_robots=False):
    """Step C: fetch each picked link and rebuild raw_text as organizer text + linked text."""
    pages = load_pages()
    if not any("linked_reason" in p for p in pages):
        raise SystemExit("No picks yet. Run --pick first.")
    if review_overrides(pages):
        raise SystemExit(
            f"{REVIEW_FILE.name} has edits that are not in {OUT_FILE.name}. "
            "Run --apply-review first, or --follow will use the old jsonl picks."
        )
    wanted = sorted({p["linked_url"] for p in pages if p.get("linked_url")})
    todo = [u for u in wanted if cache_file(u, LINKED_CACHE).exists() is False][:limit]
    print(f"{len(wanted)} unique picked URLs, {len(todo)} not fetched yet (= {len(todo)} Firecrawl credits)")

    if not scrape:
        print("Dry run. Add --scrape to fetch them and append the text.")
        return

    if ignore_robots:
        print("Ignoring robots.txt for followed pages. SKIP_DOMAINS still applies.")
    api_key = load_api_key()
    for n, url in enumerate(todo, 1):
        if is_skipped(url) or not (ignore_robots or allowed_by_robots(url)):
            print(f"[{n}/{len(todo)}] not allowed  {url}")
            continue
        try:
            firecrawl_page(url, api_key, cache_file(url, LINKED_CACHE), delay=8)
        except requests.RequestException as error:
            print(f"[{n}/{len(todo)}] failed  {url}  ({error})")
            continue
        print(f"[{n}/{len(todo)}] saved  {url}")

    appended = 0
    for page in pages:
        base = cached_text(page["source_url"], PAGE_CACHE)
        if base is None:  # the original is gone, so leave this record alone
            continue
        linked = cached_text(page["linked_url"], LINKED_CACHE) if page.get("linked_url") else None
        page["raw_text"] = (
            base + "\n\n--- followed page ---\n\n" + linked.strip()
            if linked and linked.strip()
            else base
        )
        appended += bool(linked and linked.strip())
    save_pages(pages)
    print(f"{appended} pages now have a linked page appended to raw_text")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--scrape", action="store_true", help="fetch the pages (without this, only list the domains)")
    parser.add_argument("--pick", action="store_true", help="step B: an LLM picks one link per page, no Firecrawl")
    parser.add_argument("--repick", action="store_true", help="with --pick: choose again for pages that already have a pick")
    parser.add_argument(
        "--apply-review",
        action="store_true",
        help="copy linked_url and linked_reason from link_picks_review.csv into opportunity_pages.jsonl",
    )
    parser.add_argument("--follow", action="store_true", help="step C: fetch the picked links and append them (needs --scrape)")
    parser.add_argument(
        "--ignore-robots",
        action="store_true",
        help="do not check robots.txt on step A. Step C already ignores robots when --scrape is set. SKIP_DOMAINS still applies.",
    )
    parser.add_argument("--limit", type=int, default=None, help="only handle this many pages")
    args = parser.parse_args()

    if args.pick:
        return pick_links(args.limit, args.repick)
    if args.apply_review:
        return apply_review()
    if args.follow:
        # Followed guidelines pages: ignore robots.txt whenever we actually fetch.
        return follow_links(args.limit, args.scrape, ignore_robots=(args.ignore_robots or args.scrape))

    links = load_links()
    domains = Counter(urlparse(url).netloc.lower().removeprefix("www.") for url in links.values())
    print(f"{len(links)} organizer pages on {len(domains)} domains")

    if not args.scrape:
        print("Read each domain's terms of use before scraping. Most pages first:")
        for domain, count in domains.most_common():
            print(f"  {count:>3}  {domain}")
        return

    api_key = load_api_key()
    saved = {url_key(url) for url in load_saved(OUT_FILE)}
    todo = [url for key, url in links.items() if key not in saved][: args.limit]
    print(f"{len(todo)} to fetch")

    for url in todo:
        if not (args.ignore_robots or allowed_by_robots(url)):
            print(f"robots.txt says no  {url}")
            continue
        try:
            page = firecrawl_page(url, api_key, cache_file(url, PAGE_CACHE))
        except requests.RequestException as error:
            print(f"failed  {url}  ({error})")
            continue

        text = page.get("markdown", "")
        record = {
            "source_url": url,
            "raw_text": text,
            "published_at": published_at(page),
            "scraped_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        append_records(OUT_FILE, [record])
        note = "   (very short, maybe a form or an error page)" if len(text) < 300 else ""
        print(f"saved  {url}{note}")


if __name__ == "__main__":
    main()
