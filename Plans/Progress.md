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
