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

Date: October 10, 2026. This covers the work in `notebooks/EDA+Preprocessing.ipynb` since Session 1 (last edited October 9). The EDA is not finished.

### What the notebook does, in order

1. Loads `hyperallergic.jsonl` (407 listings, 11 columns) and `opportunity_pages.jsonl` (251 pages, 4 columns). The Google Colab cells for mounting Drive are commented out, and it reads the local files in `data/raw/`.
2. Checks the column types and the missing values.
3. Makes `common.py` importable by adding `scrapers/` to the path, then uses `url_key` to give every link a matching key.
4. Looks for text noise in the page text: invisible characters, odd spaces, extra blank lines. It explains why this matters: labels are character positions, so any change to the text after labeling shifts them.
5. Adds a `domain` column (the organizer's site) and a `month` column (taken from the post address).
6. Marks pages that are not usable text with `page_problem`.
7. Joins listings to pages on the key, adds `has_page` and `page_usable`, and prints the funnel.
8. Starts the EDA checks: completeness (blank percentages and field coverage by month), type balance (stacked bars by month), and listings per organizer.

### Findings so far

- **Missing values:** `fees` is blank for 313 of 407 listings (77%), and `deadline` for 7 (1.7%). Every other column is complete. The data types look fine for now.
- **Organizer pages:** `published_at` is filled in for only 15 of the 251 pages. For time analysis, use the listing's own `published_at`.
- **Text noise in the pages:** non-breaking spaces in 132 of 251 pages, zero-width characters in 17, runs of 2 or more spaces in 76, and 3 or more blank lines in a row in 102. There is no mojibake (garbled text from a wrong encoding).
- **Unusable pages:** 25 of the 251 pages are not usable text: 14 "page not found", 7 with no listing words (login walls or banners), and 4 nearly empty. That leaves 226 usable pages.
- **Join funnel:** 330 listings have a page and 301 have a usable one. The gap is 29 listings, not 25, because one page can serve several listings.
- **Type balance:** Residency/Fellowship is the largest type (181), then Grant (125) and Open Call (101).
- **Organizers that repeat:** the Silver Foundation has 8 listings, Center for Craft and apexart 7 each, and Foundwork 6. That is why the split must be by organizer.

### Decisions and reasons

- **Split train and test by organizer** (the `domain` column), not by listing. Organizers repeat their wording, so a model tested on an organizer it trained on would score higher than it should.
- **Only usable pages** (`page_usable`) go into labeling, training, and text length estimates.
- **Clean the text once, before labeling,** and keep curly quotes and en dashes, so labels match what the organizer wrote.
- **Join the two files on `url_key`,** not on the raw link.
- **Opportunity types:** the rule from Session 1 (fellowships with grants) will be applied at the end of the EDA.

### Open items

- **Gaps in the cleaner.** `normalize_text` does not remove the soft hyphen (U+00AD, 59 times in the pages), the word joiner (U+2060, 43), or the unusual spaces: narrow no-break space (U+202F, 28), thin space (U+2009, 26), and hair space. Decide whether to add them before labeling.
- **Duplicated code.** `normalize_text`, `page_problem`, `month_from_source_url`, and `domain` are copied into the notebook and also live in `preprocess/clean.py`. `page_problem` is even defined twice in one cell. Import them from `preprocess/clean.py` so there is one version.
- **Unanswered questions from the notebook:** are the blank fees really "not mentioned", or did the parser miss them, and why are 7 deadlines missing?
- **Unfinished cells:** the monthly ratio of Residency/Fellowship to the other types is an empty cell, and the type conclusion ends with an empty bullet.
- **EDA still to do:** text length, time and deadlines, duplicates, and content analysis. The noise check is only partly done.
- **A fuller EDA exists in `notebooks/01_eda.ipynb`.** Its findings are not yet reproduced here, for example about 285 distinct opportunities among the 407 rows, 78% of usable pages longer than 512 tokens, and only 37% of deadlines found in the page text.
