# Progress

A running log of what was done, the decisions made, and what is still open.

## Week 1 - Session 1

Date: October 7, 2026. Numbers below are from the last time they were checked.

### What exists now

| Item | State |
|---|---|
| `scrapers/common.py` | Shared helpers: one record format, fee finder, link cleaning (`clean_url`, `url_key`), link resolving, Firecrawl fetch, saving |
| `scrapers/hyperallergic/hyperallergic.py` | BeautifulSoup scraper for the monthly posts. Default 22 months, the README uses 30 |
| `data/raw/hyperallergic.jsonl` | 407 listings across 29 months, back to July 2024 |
| `scrapers/hyperallergic/fetch_opportunity_page.py` | Fetches the organizer page behind each listing's link, as text. Dry run by default |
| `data/raw/opportunity_pages.jsonl` | 38 pages so far, four keys each: `source_url`, `raw_text`, `published_at`, `scraped_at` |
| `scrapers/resartis_firecrawl.py` | Written and tested offline only. As far as can be seen it has never been run |
| `scrapers/hyperallergic/hyperallergic_firecrawl.py` | Obsolete, left in place |
| `.env`, `.env.example`, README | Firecrawl key setup, and the two step Hyperallergic process documented |

### Decisions, tradeoffs, and impact

| Decision | What was weighed | Impact |
|---|---|---|
| Start with one source (Hyperallergic) | The 9 step plan with several sources vs a simple start | Fast progress, but only one source and one writing style at first |
| JSONL, not CSV | CSV opens in Excel, JSONL holds nested labels and text with line breaks | Safe for character position labels. Use a CSV copy only to browse |
| BeautifulSoup for Hyperallergic | Firecrawl's LLM extraction vs plain code | Exact text, no credits, repeatable. Firecrawl reworded a fee ("$20 - $65"), which would break label matching |
| Firecrawl only as a text fetcher, no LLM extraction | About 5 credits per page with extraction vs 1 credit for text | Cheaper, and the raw text stays exact. Labels come later in Phase 4 |
| Fees by keyword match | An LLM reading fees vs matching the word "fee" | Nothing is invented, but a cost written as "costs $150" is missed, and an empty value means "not mentioned", not "free" |
| Skipped CaFE and Creative Capital | Both are rich sources, but their terms explicitly ban automated access | Lost the biggest sources. Emailing them for permission is the open alternative |
| Went ahead with Res Artis without asking permission | Its policies do not forbid collection, but its firewall blocks an honest scraper | Pages are fetched through Firecrawl. This is a gray area and the owner's call. The script's docstring says permission was not asked |
| Hyperallergic scraped for private use | Its terms have no bot clause but a broad copying clause | Fine if the data stays local and is never republished |
| Res Artis: all countries, not U.S. only | The project guide says U.S., but only 14 of 290 calls were U.S. | More data, but about 290 credits for the full list, and most of it is out of scope. A U.S. only option exists in the script |
| Featured listings: fix, not skip | Skipping lost 53 real unique listings (about 13%). The fix strips the "Featured" line | Keeps the data. Promoted listings repeat across months, so Phase 3 has to merge them |
| Added all three date rules | `Application Period:`, a bare date, and no date if the paragraph has a link | Recovered 14 listings. 7 have an empty deadline |
| Organizer pages store only four keys | Copying the listing's title, deadline, and fees in vs a lean record | No misleading or duplicated values. Join to the listings file on `url_key` |
| Scripts moved into `scrapers/hyperallergic/` | Flat folder vs one folder per source | Tidier. Needed a small import path line in each script |
| Opportunity types: fellowships go with grants | Hyperallergic groups "Residencies & Fellowships". Of those 181 listings, 58 mention fellowship but not residency, and most of those describe funding, not a place to work. A residency often has funding too, but it is mainly a place and time | Three types: Grant/Fellowship, Residency, Open Call. The scraper's raw `type` stays as Hyperallergic grouped it. The clean label is added later, so nothing needs rescraping |

### Choices made without an explicit decision

- Link resolving follows only short links (bit.ly and similar), so organizers' sites are not contacted just to resolve a link.
- A title warning prints for titles that look wrong (over 140 characters, or "Featured").
- The organizer script defaults to a dry run, and skips social media, forms, and sites whose terms forbid scraping.
- A shared `common.py`, and the `python-dotenv` package.

### Corrections along the way

- Res Artis was first reported as having 240 U.S. calls. That was an all-time filter count, and only 14 are U.S. now.
- The "Featured" title bug (86 rows, 22% of the file) came from the first parser checking only 2026 posts.

### Still open

- Data volume: about 407 listings, short of the 1,000 target. Organizer pages and more sources are the way up.
- Component 2 (high risk): Hyperallergic and Res Artis are curated, so there are almost no risky examples. Cut it, or find an uncurated source.
- Hyperallergic file: the Long Beach Island title is merged into its description, July 2024 is in twice (about 12 doubled listings), and the Digital Security Clinic is typed as a residency though it is not one.
- Organizer pages: the terms of use across about 250 domains have not been read. The full run is about 305 credits.
- Res Artis: page 2 of the list is unconfirmed, and the scraper has not been run.
- TransArtists, Alliance of Artists Communities, NYFA: checked but no scrapers written. TransArtists is the clearest yes, with a 30 second crawl delay.
- The cache folder is still named `organizer_pages`.
- Phase 3 deduplication: listings, repeated featured entries, and organizer pages are the same opportunities and must be merged before splitting train and test.
- Opportunity type rule (decided, not yet applied): Grant/Fellowship (funding, including fellowships), Residency (a place and time to work, even if funded), Open Call. Apply it at the end of the EDA and write it into the labeling guide. A first rule that looks at the title and then the description sorted 181 listings into 105 Residency, 65 Grant/Fellowship, and 11 to review by hand. The 11 are mostly programs that mention both words, or neither (some, like workshops and trainings, may be out of scope).

### If more data is needed, consider

1. TransArtists. Its colophon says material "may be reproduced and/or adapted for personal, non-commercial purposes only". Its robots.txt asks for a 30 second delay. This is the closest to a clear yes, but it needs a slow scraper (about 2.5 hours for 300 pages).
2. Alliance of Artists Communities. No automated access clause in the terms that were read. It reserves copyright, and its robots.txt does not block the directory. Probably fine, but it is a gray area like Hyperallergic.
3. Newsletters in email. Subscribe to the curators' newsletters and collect the compiled lists and their links. Possibly accessible through Claude Cowork, if it can read the emails and follow the links. This is not yet checked.

## Week 1 - Session 2

Date: October 10, 2026. This covers the work in `notebooks/EDA+Preprocessing.ipynb` since Session 1, as saved on October 10. The EDA checks are done, including the content analysis (whether a listing's deadline and fee also appear in its organizer page).

### What the notebook does, in order

1. Loads `hyperallergic.jsonl` (407 listings, 11 columns) and `opportunity_pages.jsonl` (251 pages, 4 columns). The Google Colab cells for mounting Drive are commented out, and it reads the local files in `data/raw/`.
2. Checks the column types and the missing values.
3. Makes `common.py` importable by adding `scrapers/` to the path, then uses `url_key` to give every link a matching key.
4. Looks for text noise in the page text: invisible characters, odd spaces, extra blank lines. It explains why this matters: labels are character positions, so any change to the text after labeling shifts them.
5. Adds a `domain` column (the organizer's site) and a `month` column (taken from the post address).
6. Marks pages that are not usable text with `page_problem`, then joins listings to pages on the key and adds `has_page` and `page_usable`.
7. Runs the EDA checks: completeness, type balance (including each type's share per month), listings per organizer, text length, time and deadlines (with a `parse_deadline` function), duplicates (clusters by link and title similarity), and noise.
8. Checks whether a listing's deadline and fee also appear in its organizer page, to see how many automatic labels are possible later (with a `parse_fees` function).
9. Flags listings that look non-U.S. or not a grant, open call, or residency. Nothing is dropped.

### Findings

**Completeness**
- `fees` is blank for 313 of 407 listings (77%), `deadline` for 7 (1.7%), and `description` for 1 (0.2%). Every other column is complete. A blank fee means no "fee" keyword was found, not that the listing is free.
- `published_at` is filled in for only 15 of the 251 pages. For time analysis, use the listing's own `published_at`.

**Organizer pages**
- 25 of the 251 pages are not usable text: 14 "page not found", 7 with no listing words (login walls or banners), and 4 nearly empty. That leaves 226 usable pages.
- 330 listings have a page and 301 have a usable one. The gap is 29 listings, not 25, because one page can serve several listings.

**Type balance**
- Residency/Fellowship is the largest type (181), then Grant (125) and Open Call (101).
- In most months Residency/Fellowship has the biggest share, typically 40 to 55%. Grant leads in 2026-06 (tied with Open Call), 2026-07, and 2026-08. Three months (2025-05, 2025-06, 2025-08) are an even 33% split. A month has only 7 to 20 listings, so the shares swing a lot.
- Organizers that repeat the most: the Silver Foundation (8 listings), Center for Craft and apexart (7 each), and Foundwork (6).

**Text length**
- Hyperallergic blurbs are about 240 characters, too short to train on.
- The 226 usable pages have a median of about 6,980 characters, or about 1,023 estimated tokens (90th percentile 3,202). 78% are longer than 512 tokens, so pages must be split into chunks.

**Time and deadlines**
- 7 deadlines are missing. Every other one parses. 14 contain more than one date, and 2 are rolling.
- 381 of the 400 deadlines were already past on October 7, 2026.
- The median notice between the post date and the deadline is 30 days (25% at 20 days, 75% at 45, longest 155). 3 deadlines fall before the post date, which are year typos in the source.

**Duplicates**
- 66 titles repeat exactly, and 90 extra rows share a link with another listing.
- Merging by link plus a similar title, or by a very similar title, gives 285 clusters from 407 rows (212 appear once, 45 twice, 18 three times, and the rest 4 to 8 times). 4 links are shared by listings that stay in separate clusters, for example apexart's open calls page.
- A cluster can hold different years of one program (for example A.I.R. Gallery 2025 and 2026).

**Noise**
- Real noise is small: non-breaking spaces (163 listings' page text), zero-width characters (27), and curly quotes. No replacement characters or broken encoding.
- 1 title is over 140 characters and 1 description is empty.

**Making labels from the listing data**
- Only 37% of deadlines (294 checked) are found in the organizer page text. The cause is timing: the pages were fetched in October 2026, so a page for an old listing usually shows the next cycle's dates. For deadlines since September 2026 the match rate is 74% (27 listings), against 33% for older ones.
- Of the 94 listings with fee text, 88 have an amount, 76 are application fees, and 18 are other costs (artist, workshop, or program fees). Amounts are mostly $10 to $50, and 2 are in another currency. Only 38% of application fee amounts (55 checked) are found in the page text. The fee keyword match is noisy, so `fees` should not be used as a label without checking.

**Scope flags**
- 35 listings are flagged non-U.S. and 27 as an odd type (festival, workshop, commission, job). By type, the non-U.S. flags are Grant 14, Open Call 12, Residency/Fellowship 9, and the odd-type flags are Grant 3, Open Call 14, Residency/Fellowship 10. The keyword lists are rough, so a sample needs a hand check.

### Decisions and reasons

- **Split train and test by organizer, and by cluster.** Organizers repeat their wording, so a model tested on an organizer it trained on would score higher than it should.
- **Only usable pages** (`page_usable`) go into labeling, training, and the text length estimates.
- **Chunk the pages,** since most are longer than the 512 tokens DeBERTa reads at once.
- **Clean the text once, before labeling,** and keep curly quotes and en dashes, so labels match what the organizer wrote.
- **Join the two files on `url_key`,** not on the raw link.
- **Use recent listings for automatic labels** (deadlines since September 2026 match the page far more often) and expect to hand label the rest.
- **Flag, do not drop,** listings that look non-U.S. or the wrong type.
- **Fellowships go with grants** (decided, not yet applied). It will be applied at the end of the EDA.

### Open items

- **Gaps in the cleaner.** `normalize_text` does not remove the soft hyphen (U+00AD, 59 times in the pages), the word joiner (U+2060, 43), or the unusual spaces: narrow no-break space (U+202F, 28), thin space (U+2009, 26), and hair space. Decide whether to add them before labeling.
- **The 7 missing deadlines** have not been investigated yet.
- **Which cycle to keep.** For a cluster of repeated listings, decide whether to keep the newest cycle or all cycles.
- **The fellowship and grant grouping** is decided but not applied.
- **The keyword flags** for non-U.S. and odd types need a hand check on a sample.
- **July 2024 is in the data twice** (two posts with 14 listings each), so that month is doubled until the duplicates are merged.
- **Decision to make: `days_until_deadline`.** Should it be a column in the dataframe at this step, or should the platform work it out automatically when it shows a listing? A stored value is only correct on the day it was computed and goes stale, while computing it from the parsed deadline date when the app runs is always current. The notebook already has `days_notice` (deadline minus the post date), which is a different, fixed number and is fine to keep. Think about this before the app is built. Leaning towards computing it in the platform, from the parsed deadline date, so it is always current.
