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

## Week 2 - Session 3

Date: October 16, 2026. This covers all the preprocessing added to `notebooks/EDA+Preprocessing.ipynb` since Session 2 (October 10): text normalization, page cleaning, field normalization, deduplication, merge, chunking, the train/val/test split, and the files written to `data/clean/`. Numbers are from the last run.

### What was done, in order

**1. Text normalization.** A new `normalize_for_model` builds on `normalize_text` from `preprocess/clean.py`. It repairs encoding (ftfy), applies Unicode NFC and then NFKC, and removes the soft hyphen (U+00AD) and word joiner (U+2060). It turns curly quotes into straight quotes, folds the unusual spaces (narrow no-break, thin, hair) into plain spaces, and collapses whitespace. En and em dashes are kept.

An **offset map** is stored with every cleaned page. It is a list of `[clean_start, raw_start, length]` stretches that survived cleaning, and `clean_to_raw_span` turns a span on the clean text into a span on the raw text. A random check of 6,758 words mapped them back correctly 99.4% of the time. The map is built by diffing line by line first and character by character only inside changed lines, because a character diff of a whole page was too slow (the longest page is 65,000 characters).

**2. Page cleaning.** The original page text is kept in `page_text_raw` and the cleaned text in `page_text`. A page is dropped (its text set to empty, with a reason in `page_problem`) if it is empty, a not-found page, or has no opportunity words. Short lines (100 characters or fewer) that match navigation, cookie, or footer patterns are removed. Results: 226 of 251 pages are usable (13 not found, 7 no signal, 5 empty), and 368 boilerplate lines were removed from 127 pages. The counts differ slightly from the EDA (14, 7, 4) because `page_problem` now runs on the normalized text.

**3. Field normalization.** Starting again from the raw listings table, with `*_raw` copies of every changed column.
- **Deadline:** `parse_deadline` gives an ISO date (the end date for a range), with `dateparser` as a fallback for anything the regex cannot read (it was never needed). Flags: `is_rolling` (2) and `deadline_suspect`, where the deadline is before the post date (3, the year typos from the EDA). 7 deadlines are missing, 0 are unreadable.
- **Fees:** `parse_fees` gives `fee_min`, `fee_max`, `fee_currency`, `fee_mentioned` (94), amounts (88), and a new `fee_free` flag for wording such as "no fee" (4). A blank fee still means "not mentioned".
- **Type:** the combined `Residency/Fellowship` label is split into the three project types. `Grant` becomes Grant/Fellowship, and a Residency/Fellowship row that says fellowship but not residency becomes Grant/Fellowship (58); the rest become Residency (123). Totals: Grant/Fellowship 183, Residency 123, Open Call 101.

**4. Deduplication.** Done before any split. Explained in detail below, because it took two rounds.

### Deduplication in detail

**First version (the EDA rules).** Titles were compared as whole strings with `token_set_ratio`. Rows matched if they shared an organizer link and scored 80 or more, or scored 92 or more on title alone. Rows were joined into clusters with union-find. This gave 285 canonical listings.

**Spot check.** A check of every merged pair (213 pairs: 137 matched by link, 67 by title alone, 9 only chained through a third row) showed wrong merges:
- `token_set_ratio` scores 100 whenever one title's words are all inside the other's, so a short title merged into any longer title that contained its words.
- Titles look like `Organizer - Program`, so the shared organizer name pushed every score up, even for different programs.
- Wrong merges found: Silver Foundation `Grant for Writing on Sculpture` with `Grant for Sculpture`, Lewis Center `Hodder Fellowships` with `Princeton Arts Fellowships`, Haystack's three programs, and Millay Arts' `Core & Steepletop Residencies` with two other programs.

**Revised rules (now in the notebook).** Each title is split at the first dash into organizer and program, and years are removed (`2025`, `2026-27`), so the same program in different years still merges. Programs are compared with `token_sort_ratio`, which penalizes extra or missing words. Rows match if:
1. they share an organizer link and the programs score 80 or more, or
2. the organizer matches (`token_set_ratio` 90 or more, which tolerates a leading "The" or "(LMCC)") and the programs score 90 or more, or
3. the full year-stripped titles score 95 or more, which also catches titles written program first.

The canonical row of each cluster is the most recent post. The record keeps `months`, `n_occurrences`, `source_urls`, `member_titles`, and `all_deadlines`, so the repetition is not lost.

**Result.** 407 rows become **299 canonical listings** (108 merged away; the first version gave 285, so 14 programs that were wrongly merged are now separate). 227 listings appear once, 50 twice, 13 three times, 5 four times, 3 five times, and 1 six times. July 2024 (28 rows from 2 posts) collapses to 14 listings, all of which also appeared in another post, so the doubled month is resolved. The wrong merges above are now separate, and weak chains dropped from 9 pairs to 2.

**Review list.** A second check lists merged pairs that differ by a word, with description similarity and deadline signals. It found 16 pairs and flagged 6, all of which turned out to be false alarms caused by title formatting (a leading "The", program-first titles, different organizer spelling). No pair was two calls from the same post month with different deadlines.

**Manual inspection.** The Banff pair `Visual Arts Residencies` and `Visual Arts Thematic Residencies` had a description similarity of 71, so a helper, `inspect_merge`, shows the links and blurbs of any merge. Both Banff listings point to the same organizer page and the same application fee, so they are **kept merged**. A commented-out `NEVER_MERGE` override, with where to paste it in step 4, is in the notebook for a pair that should be split.

### Decisions, trade-offs, and impact

| Decision | What was weighed | Impact |
|---|---|---|
| Keep an offset map, built from a diff of raw against clean | Storing a position for every character vs. describing only the stretches that survived | Small to store, and exact inside kept text. A position inside deleted text snaps to the nearest kept character, so a label should never be placed on removed text |
| Straighten curly quotes (reverses the Session 2 choice to keep them) | Labels matching exactly what the organizer typed vs. one form of each quote for the model | The model and the label matching see one form of each quote. The raw text and the offset map still give the original |
| NFKC as well as NFC | NFKC also folds ligatures and full-width characters vs. changing the text less | More consistent text, at the price of more edits, which the offset map absorbs |
| Remove boilerplate only from short lines (100 characters or fewer) | Removing every line with "newsletter" or "cookie" vs. keeping real sentences | Real sentences are safe, but a long cookie paragraph would stay. Nav words like "Contact" or "News" are removed only when they are the whole line |
| Keep rejected pages in the data with the reason | Dropping the listing vs. keeping it | Listings without a usable page keep their blurb and fields, with `has_page` false. Raw text is never lost |
| Deadlines flagged, not corrected | Fixing the 3 year typos vs. leaving them | Nothing is invented. The flag is there for a hand check |
| Type rule by keyword: fellowship without residency means Grant/Fellowship | The Session 1 rule had a third "review by hand" group (11 listings) vs. no manual step | Fully automatic, so ambiguous listings (both words, or neither) land in Residency by default. Spot check them before labeling |
| Compare programs, not whole titles | Whole-title scores are simple, but the organizer name inflated them | Fewer false merges (299 listings, not 285). The cost is that titles with no dash get no organizer, and a reworded program title can now split |
| `token_sort_ratio` instead of `token_set_ratio` | Set ratio ignores extra words, sort ratio penalizes them | Stops short titles matching long ones. A real rewording of a program name (for example adding "Young") scores lower |
| Catch false merges first | A false merge hides a distinct program, a false split can put one program in both train and test | The train and test split is by organizer, which limits the damage of a false split, so merges were tightened more than splits |
| Canonical row is the newest post | Keeping all cycles vs. one row per program | One row per program with `all_deadlines` and `months`, but older wording is only in `member_titles`. The Session 2 question of which cycle to keep is closed |
| Chaining kept (see below) | A stricter cluster rule vs. extra code for 2 pairs | Simple and reproducible for now |
| Review list and `inspect_merge` instead of auto-fixing | Auto-deciding "same program" vs. a short list for a human | Nothing is guessed, and the Banff call is recorded as a human decision |

### Chaining: not fixed yet, and it may be needed for new listings

Clusters are built with union-find, which is transitive: if A matches B and B matches C, all three are one cluster even when A and C do not match. A generic title such as `Millay Arts Residencies` can then bridge two different programs. After the title fix, only 2 pairs are joined this way (both the AICA Incentive Prize, a prize whose title was reworded, so the chain gives the right answer).

A stricter rule was considered: a row joins a cluster only if it matches the canonical row, or every member. It was **not applied now** because:
- it would split the AICA prize into two listings, a wrong split in the only case where chaining currently matters;
- it makes the result depend on the order the rows are processed, so it needs a fixed sort and its own tests;
- the `NEVER_MERGE` override already handles any single bad chain.

**To do when new listings are added (more months, a second source, or the organizer pages):** re-run the spot check, and look at part 2 (weak chains) first. If the number of chained pairs that are clearly wrong grows beyond a handful, replace chaining with the stricter rule. Generic titles from a second source are the most likely cause, so this is a real risk and not a theoretical one.

### Merge, chunking, split, and outputs (steps 5 to 8)

**5. Merge.** Each of the 299 canonical listings is joined to its organizer page on `url_key`. Two columns are kept apart: `page_fetched` (a page row exists) and `has_page` (the page survived cleaning, so `page_text` is usable). Result: 236 listings have a fetched page and **215 have usable text**. The other 84 are kept, with only their blurb and fields.

*Why 84 listings have no usable text.* A breakdown cell gives each one a single reason: 53 allowed links with no saved page, 21 fetched and rejected (10 not found, 7 no signal, 4 empty), 9 on skipped domains (6 Submittable, Jotform, Google Docs, Creative Capital), and 1 with no link. The fetch script finds 305 allowed links but only 251 pages are saved, and none of the 53 has a cache file, so they were either never fetched or blocked by `robots.txt`. Open Calls lose the most: 41% have no page, against 23% for Grant/Fellowship and 25% for Residency. Only 1 of the 53 could be recovered from another row in its cluster.

**6. Chunking.** Pages are cut into overlapping windows of 300 words (about 390 tokens, using tokens ≈ words × 1.3), advancing 240 words, so neighbours share 60 words (about 20%). A tail of fewer than 40 words is added to the last window, so the longest chunk is 340 words (about 440 tokens, under DeBERTa's 512). Each chunk records its position on the cleaned page (`char_start`, `char_end`) and on the raw page (`raw_start`, `raw_end`, from the offset map). Chunks are made once per page, and each lists every `listing_ids` that uses the page. Result: **1,058 chunks from 207 pages**, a median of 3 chunks per page (maximum 37), a median of 390 estimated tokens and a maximum of 434. 38 pages fit in a single chunk, and 28 chunks belong to more than one listing. Two checks run in the cell: every chunk is under 512 estimated tokens, and every chunk's text is exactly the slice of its page.

**7. Split.** Whole organizers (by domain) are shuffled with a fixed seed (42), then assigned largest first to the split furthest below its target share (70, 15, 15). A listing with no domain is its own group. The cell asserts that no organizer sits in two splits and that a page shared by several listings is never split. Chunks inherit the split of their listings.

| Split | Listings | Organizers | Chunks | Grant/Fellowship | Open Call | Residency |
|---|---|---|---|---|---|---|
| train | 209 | 165 | 750 | 45.5% | 22.5% | 32.1% |
| val | 45 | 45 | 139 | 35.6% | 35.6% | 28.9% |
| test | 45 | 45 | 169 | 37.8% | 33.3% | 28.9% |

**8. Outputs.** Four files are written to `data/clean/` and rewritten on every run, with the same output for the same seed:

| File | Content |
|---|---|
| `listings.jsonl` | 299 rows, 39 columns: normalized fields, `*_raw` originals, parsed deadline, fees and type, `months`, `n_occurrences`, `page_text`, `page_text_raw`, `page_offsets`, `has_page`, `split_group` |
| `chunks.jsonl` | 1,058 rows: text, clean and raw character offsets, `listing_ids` |
| `splits.json` | the seed, the ratios, and the listing ids, chunk ids and organizers of each split |
| `data_report.md` | what was dropped or flagged and why, generated from a `drops` log kept during the run, so it is not written by hand |

### Decisions, trade-offs, and impact (steps 5 to 8)

| Decision | What was weighed | Impact |
|---|---|---|
| Keep listings without usable page text | Dropping them vs. keeping the blurb and fields | 84 listings stay with `has_page` false. They add no chunks, but the structured fields can still be used. A filter on `has_page` is needed wherever page text is required |
| Two page columns, `page_fetched` and `has_page` | One column vs. separating "no page" from "page rejected" | The reason for a missing page can be traced, which is how the fetching gap was found |
| Chunk per page, not per listing | Per listing is simpler vs. avoiding duplicate text | No repeated chunks when listings share a page. Each chunk carries a list of `listing_ids`, and the split step has to check that list |
| 300 words with 60 words of overlap (stride 240) | Larger windows have more context but risk the 512 limit; small overlap is cheaper but can cut a deadline sentence | About 390 tokens per chunk, safely under 512. About 20% of text appears twice, so scores must be computed per page, or the overlap handled, to avoid counting a span twice |
| Words times 1.3 instead of a real tokenizer | Installing `transformers` locally vs. an estimate | No new dependency. Word windows can exceed 512 real tokens for text with many numbers or links, so re-check with the DeBERTa tokenizer in Colab |
| Absorb a tail of fewer than 40 words | Short last chunks are cheap but weak, with little context | No tiny chunks. The longest chunk is 340 words |
| Split by organizer domain, not by listing or by time | Random split is simple but leaks organizers; time split is realistic but the data is only a few years | The test score measures unseen organizers. Domain is only a proxy: a shared host such as a university site or a platform can group unrelated programs, and the same organizer on two domains would not be grouped |
| Largest organizers first, fixed seed 42 | Pure random assignment vs. balanced sizes | The sizes come close to 70, 15, 15 (209, 45, 45). The side effect is that all multi-listing organizers go to train |
| No stratification by type | Stratifying by type would balance the mix, but conflicts with grouping | The mix differs: Open Call is 22.5% in train but 33% to 36% in val and test, so results by type are noisy |
| Write `data_report.md` from a `drops` log | A hand-written report vs. numbers generated by the run | The report cannot drift from the data, but it only covers what was logged |
| Raw text kept in the clean files (`page_text_raw`, `*_raw` columns) | Smaller files vs. never losing the source | `listings.jsonl` is about 5.4 MB. Every label can be traced back to the original text |

**What the split table tells us**
- **Val and test hold only organizers with one listing each** (45 listings from 45 organizers), because the largest organizers were placed first and all went to train. The biggest organizer has 4 listings (Vermont Studio Center). The test therefore says nothing about organizers that repeat themselves, which is the case the EDA worried about, so the split protects against leakage but is not representative of repeat organizers.
- **Val and test are small.** 45 listings and 169 chunks give wide error bars, and the gold set (about 30 to 40 hand-labeled listings) will be drawn from them. Differences of a few points between models will not be reliable.
- **The type mix differs between splits** (Open Call 22.5% in train, 33% to 36% in val and test), and Open Calls also have the most missing pages (41%), so the Open Call numbers will be the least stable.
- **Splitting happens after deduplication,** so the same opportunity cannot be in both train and test.

### Code moved into `preprocess/clean.py`

`normalize_for_model`, `build_offset_map`, `clean_to_raw_span`, `strip_boilerplate`, `project_type`, and `split_title` are now in `preprocess/clean.py`, and the notebook imports them in its setup cell. The notebook keeps only a short demo of the offset map. Re-running the notebook gave byte-identical `listings.jsonl`, `chunks.jsonl`, `splits.json`, and `data_report.md`, so the move changed no results. `build_offset_map` no longer needs numpy. The notebook keeps its own copies of the older EDA functions (`parse_deadline`, `parse_fees`, `page_problem`), which also exist in the file.

### Session 2 open items that changed

- **Gaps in the cleaner:** closed for the soft hyphen, word joiner, and unusual spaces (added in `normalize_for_model`). They now live in `preprocess/clean.py` (see above).
- **Which cycle to keep:** decided, the newest post (see above).
- **Fellowship and grant grouping:** applied, with the keyword rule above.
- **July 2024 doubled:** resolved by deduplication.
- **The 7 missing deadlines:** still not investigated.
- **The keyword flags for non-U.S. and odd types:** still not hand checked, and not carried into the clean listings.

### Still open

- **Banff has a third row**, `Visual & Indigenous Arts Residencies`, in its own cluster. Its blurb is nearly the same as the first Banff listing's, and its organizer page is `https://www.banffcentre.ca/programs`. Decide if it is a separate program. <--> Keeping it separate for now
- **Textile Arts Center `Cycle 17` and `Cycle 18`** merge because only years are stripped. This was kept as one program, and other cycle-numbered programs would behave the same way.
- **Spot check the ambiguous type listings** (both words or neither) and a sample of the title-split cases before labeling starts.
- **Fetch the missing pages.** 54 allowed links have no saved page (see step 5). Run the fetch script for them, dry run first (about 54 credits), then re-run the notebook. If many are blocked by `robots.txt`, accept the loss and report the Open Call gap.
- **Re-check chunk size with the real tokenizer** in Colab, since it was set with a words times 1.3 estimate.
- **Decide how to handle overlap** (60 words repeated between chunks) when scoring, so a span in the overlap is not counted twice.
- **Small val and test sets.** Consider whether the gold set should come from val and test, and whether to add a stratified or time based check.
- **Test has no repeat organizers.** If needed, report a second check on a split that includes organizers with several listings.
