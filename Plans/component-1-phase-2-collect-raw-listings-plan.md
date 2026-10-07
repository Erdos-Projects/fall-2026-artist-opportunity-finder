# Component 1, Phase 2: Collect Raw Listings (Implementation Plan)

This plan breaks Phase 2 of
[the Component 1 plan](component-1-local-and-colab-plan.md) into concrete steps.
Everything here runs on the local machine with the packages already in
[requirements.txt](../requirements.txt). There is no deep learning in this
phase. It is data engineering: getting messy text off the web and onto disk in a
form we can trust later.

**Goal:** 200 to 300 raw listings saved in `data/raw` from the first 2 to 3
sources, each with its source, URL, scrape date, raw text, and any structured
fields the site shows.

**Starting point:** Phase 1A is done. The virtual environment exists and
`data/raw`, `data/clean`, and `data/labeled` are created. The `scrapers` folder
does not exist yet.

## Concepts to know before starting

- **Scraping.** A program downloads a web page (the same HTML your browser
  receives) and pulls specific pieces out of it. `requests` does the download,
  `BeautifulSoup` lets you search the HTML for tags.
- **Index page versus detail page.** Most listing sites have an index (a list of
  many opportunities with links) and one detail page per opportunity. A scraper
  usually works in two passes: collect the detail links from the index, then
  visit each detail page.
- **robots.txt.** A file at the root of a site (for example
  `example.com/robots.txt`) that says which paths automated programs may visit.
  We follow it, along with the site's terms of service.
- **Raw layer.** The first copy of the data, saved exactly as collected and
  never edited. If cleaning code has a bug in Phase 3, we rerun it from raw
  instead of scraping again.
- **Structured fields.** Values the site shows in their own labeled slots
  (Deadline, Entry Fee, Type) separate from the description paragraph. These
  matter because in Phase 4 we match them back into the free text to create
  labels automatically. That trick is called distant supervision.
- **JSONL.** A text file with one JSON record per line. It is easy to append to
  and easy to read one record at a time, which suits a dataset that grows.

## What gets built

```
/scrapers
  common.py           # shared helpers: polite fetch, cache, save record
  artworkarchive.py   # source 1
  <source2>.py        # source 2
  <source3>.py        # source 3 (optional)
  check_raw.py        # counts and sanity checks on data/raw
/data/raw
  artworkarchive.jsonl   # one file per source, append only
  <source2>.jsonl
  /_cache                # saved HTML pages, one folder per source
/docs
  sources.md             # notes per source: rules, page structure, quirks
```

### The raw record format

Every scraper writes records with the same keys, so later phases never need to
know which source a record came from.

| Key | Meaning |
|---|---|
| `source` | Short source name, such as `artworkarchive` |
| `url` | The detail page URL. This is also the record's unique ID |
| `scraped_at` | Date and time of the download, in ISO format |
| `title` | The listing title as shown on the page |
| `raw_text` | The full free text description, untouched. This is what the model will read |
| `structured_fields` | A dictionary of labeled values the site shows separately. Keys and values are copied exactly as displayed, with no reformatting |
| `cache_path` | Where the saved HTML for this page lives under `data/raw/_cache` |

Two rules protect the raw layer:

1. **No cleaning here.** Do not trim, lowercase, or fix anything in `raw_text`
   or `structured_fields`. Cleaning belongs to Phase 3.
2. **Append only.** A scraper adds new lines and never rewrites the file. Before
   scraping a URL it checks whether that URL is already in the file and skips it
   if so.

## Steps

### Step 2.1: Choose the sources and read their rules

- Source 1 is Artwork Archive Calls for Entry (decided, because it has
  structured fields next to the free text).
- Pick sources 2 and 3 from the project list (NYFA, ArtConnect, Hyperallergic,
  Res Artis, TransArtists, Artist Communities Alliance). Prefer ones that also
  show structured fields and that cover residencies or grants, so the three
  opportunity types are all represented.
- For each candidate, open its `robots.txt` and skim its terms of service. Write
  down in `docs/sources.md` which paths are allowed, any stated crawl delay, and
  anything that forbids automated collection.
- If a source forbids scraping, drop it and pick another. Do not work around it.

**Done when:** `docs/sources.md` lists 2 to 3 approved sources with their rules.

### Step 2.2: Inspect Artwork Archive by hand

No code yet. This step decides what the scraper will look for.

- Open the index page in a browser, right click a listing, and choose Inspect.
  Find the repeating tag and class that wraps one listing, and the link to its
  detail page.
- Work out how paging works. Look for a `?page=2` style URL, a "next" link, or a
  "load more" button.
- Open one detail page and find the tags that hold the title, the description,
  and each structured field.
- Check whether the content is in the HTML the server sends. Use View Page
  Source (not Inspect) and search for a phrase from the listing. If it is not
  there, the page is filled in by JavaScript, and `requests` will not see it. In
  that case open the Network tab, reload, and look for a JSON request that
  carries the listing data. That request becomes the thing to fetch.
- Note whether listings expire off the site, since that affects how often to
  rerun the scraper.

**Done when:** `docs/sources.md` records the index URL pattern, the paging
method, and the selectors for title, description, and structured fields.

### Step 2.3: Write the shared helpers in `scrapers/common.py`

Every source needs the same polite behavior, so it is written once.

- `fetch(url, source)`: returns the page HTML. It checks robots.txt first (the
  standard library's `urllib.robotparser` does this), sends a User-Agent that
  honestly names the project and a contact, waits a few seconds between
  requests, and retries a small number of times on a failed request.
- **Caching inside `fetch`:** after a successful download the HTML is saved
  under `data/raw/_cache/<source>/`. If the file already exists, `fetch` reads
  it from disk and makes no request. This means a bug in the parsing code can be
  fixed and rerun without hitting the site again.
- `load_seen_urls(source)`: reads the source's JSONL file and returns the set of
  URLs already saved.
- `append_record(source, record)`: checks that all keys from the record format
  are present, then appends one line to `data/raw/<source>.jsonl`.

**Done when:** calling `fetch` twice on the same URL makes one network request,
and the second call is served from the cache.

### Step 2.4: Scrape one detail page

- In `scrapers/artworkarchive.py`, write `parse_listing(html, url)` that returns
  one record in the raw format.
- Run it on a single detail page and print the result.
- Compare the printed record against the page in the browser, field by field.
  The description must be complete (not cut off at a "read more"), and every
  structured field on the page must appear in `structured_fields`.
- Repeat on 2 more listings that look different (one with no fee, one with
  several deadlines) to catch fields that are sometimes missing. A missing field
  should be left out of the dictionary, not guessed.

**Done when:** 3 hand checked listings produce correct records.

### Step 2.5: Collect the detail URLs from the index

- Write `collect_listing_urls()` that walks the index pages using the paging
  method found in Step 2.2 and returns the list of detail URLs.
- Give it a `max_pages` limit and test with 1 or 2 pages first.
- Stop cleanly when a page returns no listings.

**Done when:** it returns a list of unique URLs whose count roughly matches what
the site shows in the browser.

### Step 2.6: Run the full Artwork Archive scrape

- Add a `main()` that ties it together: collect URLs, skip any already in
  `load_seen_urls`, then for each remaining URL fetch, parse, and append.
- If one listing fails to parse, log its URL and keep going. One odd page should
  not stop the run.
- Print a short summary at the end: saved, skipped, failed.
- Run it with `python -m scrapers.artworkarchive`. It will be slow on purpose
  because of the delay between requests.
- Run it a second time to confirm it saves nothing new and makes no requests.

**Done when:** `data/raw/artworkarchive.jsonl` exists and a rerun adds zero
records.

### Step 2.7: Sanity check the raw file

Write `scrapers/check_raw.py`, which loads the JSONL files with pandas and
reports, per source:

- Number of records and number of unique URLs (these should match).
- Records with empty or very short `raw_text`.
- The spread of `raw_text` length, to spot truncated descriptions.
- How often each structured field key appears, to spot a selector that silently
  fails on most pages.
- 5 random records printed in full, to read by eye against the live pages.

Fix any scraper bugs this reveals. Because pages are cached, the fix is to
correct the parser, move the bad JSONL file aside, and rebuild it from the
cache. This is the one case where a raw file is regenerated, and it is done
before any later phase depends on it.

**Done when:** the checks pass and 5 random records match their pages.

### Step 2.8: Add the second and third sources

For each remaining source, repeat Steps 2.2 and 2.4 to 2.7 in a new module. The
shared helpers are reused as they are.

- Each source gets its own `parse_listing` and `collect_listing_urls`, and its
  own JSONL file.
- Structured field names will differ between sites (one says "Deadline", another
  "Apply by"). Keep each site's own names. Mapping them to common names is a
  Phase 3 and Phase 4 job.
- If a source turns out to need much more effort than the first (a login wall,
  heavy JavaScript, blocking), record that in `docs/sources.md` and switch to a
  different source instead of sinking time into it.

**Done when:** each source has a JSONL file that passes `check_raw.py`.

### Step 2.9: Count checkpoint and wrap up

- Run `check_raw.py` across all sources and record the totals.
- Check the balance across grants, open calls, and residencies using whatever
  type field the sources provide. A set that is nearly all open calls will make
  a weak training set.
- If the total is under 200, either add a source or scrape deeper into the
  existing ones before moving on.
- Update `docs/sources.md` with the final count per source and any quirks worth
  remembering for Phase 3 (boilerplate that repeats, fields that are unreliable).
- Commit the scraper code and docs. The data itself stays out of git.

**Done when:** 200 to 300 raw listings are saved from 2 to 3 sources, and the
source notes are written.

## Things to watch for

- **The same opportunity on two sites.** This is expected and is not handled
  here. Keep both copies. Deduplication across sources happens in Phase 3.
- **Personal information.** Listings sometimes include a contact person's name
  and email. It stays in the local raw file and is never republished.
- **Truncated descriptions.** Some index pages show only a preview. Always take
  the text from the detail page.
- **Aggregator text versus the organizer's own page.** Some sources only
  summarize and link out. Whether to follow those links is still an open
  decision in the project guide. For this phase, save the aggregator text and
  keep the outbound link in `structured_fields` so the choice stays open.

## What this phase hands to Phase 3

One JSONL file per source in `data/raw`, all sharing the same record format,
plus `docs/sources.md` describing each source. Phase 3 reads these files and
never changes them.
