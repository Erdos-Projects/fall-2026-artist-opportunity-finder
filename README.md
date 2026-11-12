# Artist Opportunity Finder

Team project: fall-2026-artist-opportunity-finder

Artist Opportunity Finder helps visual and media artists find grants, exhibition
open calls, and residencies that fit their work, instead of hunting across dozens
of inconsistent listing sites, PDFs, and newsletters. It is an 8-week, end-to-end
deep learning course project covering data collection, labeling, fine-tuning,
evaluation, and a local demo app. The scope is U.S.-based opportunities, and the
data comes from one source, Hyperallergic's monthly opportunity posts.

For a two-page summary of what we built and how it scored against our targets,
read the [Executive Summary](docs/executive_summary.md) (also as
[.docx](docs/executive_summary.docx)).

## What was built

Each component is measured against a simple baseline.

| Component | What it does | Baseline | Model | Status |
|---|---|---|---|---|
| Field extraction | Pulls deadline, entry fee, career stage, location, and medium out of messy listing text | Regex and rules | Fine-tuned RoBERTa-base token classifier (BIO span tagging), compared with DeBERTa-v3-base and with an LLM | Done |
| Matching and ranking | Filters listings by the extracted fields, then ranks them against an artist's profile | BM25 | Pretrained sentence embeddings (all-MiniLM-L6-v2), not fine-tuned | Done, directional |
| Quality classification | Would label listings as legitimate, low value, or high risk | Rules | Text classifier | Not built |

## Results

Extraction, scored once on 33 hand-labeled ("gold") listings with 183 labeled
spans (exact-match F1):

| Field | Regex | Fine-tuned | LLM (claude-opus-5-5, no training) |
|---|---|---|---|
| All fields (micro) | 0.19 | **0.41** | 0.40 |
| Deadline | 0.70 | 0.72 | 0.88 |
| Fee (6 spans only) | 0.55 | 0.67 | 1.00 |
| Career stage | 0.08 | 0.33 | 0.28 |
| Location | 0.05 | 0.09 | 0.20 |
| Medium | 0.17 | 0.36 | 0.26 |

- The fine-tuned model more than doubles the regex baseline and ties the LLM
  overall. Our 0.85 micro F1 target was not met.
- The LLM costs about $49 per 1,000 listings and 4.3 seconds per call. The
  fine-tuned model takes about 0.1 seconds per listing on a GPU (estimated) and
  has no per-call fee.
- None of the 280 spans the model predicted was unsupported, because a tagger
  can only point at text on the page.
- Matching (15 artist profiles, ratings from an LLM judge): BM25 precision@10
  0.33 and NDCG@10 0.52, embeddings 0.36 and 0.51. They tie within noise, and
  the targets (NDCG 20% above BM25, precision@10 0.60) were not met.
- The test set is small and was labeled by one person, so differences of a few
  points are noise. A hybrid (LLM for deadline and fee, fine-tuned model for
  medium and career stage) is an idea to test on new data, not a result.

More detail is in [docs/results/](docs/results/) and in the labeling rules in
[docs/gold_labeling_guide.md](docs/gold_labeling_guide.md).

## Why fine-tune instead of prompting an LLM

A span-tagging model can only point at text that exists in the listing, so it
cannot invent a deadline or a fee the way a generative model can. It is also
cheaper and faster at scale. On our test it matched the LLM overall but was
weaker on deadlines and fees, so the case for it rests on cost, speed, and
not making values up, not on accuracy.

## Getting started

This sets up the local environment for data collection, cleaning, and labeling.
Model training runs in Google Colab and has its own setup, so no deep learning
libraries are installed here.

**You need:** Git, plus either [uv](https://docs.astral.sh/uv/) (recommended) or
Python 3.12. With uv, the setup script downloads the right Python for you.

1. Clone the repository and move into it.

   ```
   git clone https://github.com/Erdos-Projects/fall-2026-artist-opportunity-finder.git
   cd fall-2026-artist-opportunity-finder
   ```

2. Run the setup script for your system from the project folder.

   Windows (PowerShell):

   ```powershell
   .\scripts\setup.ps1
   ```

   Linux or macOS:

   ```bash
   source scripts/setup.sh
   ```

   The script creates a virtual environment in `.venv`, installs the packages in
   [requirements.txt](requirements.txt), creates the `data` folders, and leaves
   the environment active in your terminal. It is safe to run again, for example
   after `requirements.txt` changes.

3. In later sessions, activate the environment before you work.

   Windows (PowerShell):

   ```powershell
   .venv\Scripts\Activate.ps1
   ```

   Linux or macOS:

   ```bash
   source .venv/bin/activate
   ```

   Run `deactivate` to leave it.

If PowerShell refuses to run scripts, allow them for the current terminal and
try again:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

## Building the datasets

Each source has its own scraper in `scripts/scrapers/`. Run them from the project folder
with the environment active (see Getting started).

### Hyperallergic

The Hyperallergic data is built in two steps, and the second depends on the
first. Both write to `data/raw/`.

| Step | Script | Writes | One line per |
|---|---|---|---|
| 1. Listings | `scripts/scrapers/hyperallergic/hyperallergic.py` | `hyperallergic.jsonl` | Opportunity |
| 2. Opportunity pages | `scripts/scrapers/hyperallergic/fetch_opportunity_page.py` | `opportunity_pages.jsonl` | Linked page |

**Step 1: the listings.** Hyperallergic publishes a monthly "Opportunities in
<Month> <Year>" post. This scraper reads the newest 30 of them and saves one line
per opportunity: title, description, deadline, fees, website, type, and the
original text. Each listing's `website` is the link Hyperallergic gives for it,
cleaned of tracking labels, and it usually points to the organizer's own page.

Windows (PowerShell):

```powershell
.venv\Scripts\python.exe scripts\scrapers\hyperallergic\hyperallergic.py --months 30
```

Linux or macOS:

```bash
.venv/bin/python scripts/scrapers/hyperallergic/hyperallergic.py --months 30
```

Downloaded pages are cached in `data/raw/_cache/hyperallergic`, and months that
are already in the output file are skipped, so it is safe to run again. The first
run takes a while because it waits a few seconds between requests. The scraper
prints a note for any paragraph it could not read, so check those after a run.

**Step 2: the opportunity pages.** The blurbs in Step 1 are only a sentence or
two. The organizer's own page holds the long, messy text the extraction model has
to learn from. This script reads the `website` links from `hyperallergic.jsonl`
(and from `resartis.jsonl`, if it exists), removes repeated links, and saves the
text of each page. It keeps only four keys per page: `source_url` (the cleaned
link), `raw_text`, `published_at`, and `scraped_at`.

It uses [Firecrawl](https://www.firecrawl.dev/), so put your key in a `.env` file
in the project folder (copy `.env.example`):

```
FIRECRAWL_API_KEY=your-key-here
```

Run Step 1 first. Then run the script without `--scrape` to list the domains it
would visit. This makes no requests and uses no credits.

```powershell
.venv\Scripts\python.exe scripts\scrapers\hyperallergic\fetch_opportunity_page.py
```

Each organizer has its own terms of use, which the script cannot read. Read the
terms of the sites you are comfortable with, and add any that forbid automated
access to `SKIP_DOMAINS` in the script. It checks robots.txt for you. Then fetch
a few pages to check the result, and then all of them:

```powershell
.venv\Scripts\python.exe scripts\scrapers\hyperallergic\fetch_opportunity_page.py --scrape --limit 5
.venv\Scripts\python.exe scripts\scrapers\hyperallergic\fetch_opportunity_page.py --scrape
```

On Linux or macOS, use `.venv/bin/python` and forward slashes. Each page costs
about one Firecrawl credit. Pages already saved are skipped, so you can stop and
run it again.

**How the two files connect.** Each opportunity page is the page behind a
listing's `website` link. The two files are joined on that link:

```
hyperallergic.jsonl     website     (listing: title, deadline, fees, ...)
opportunity_pages.jsonl source_url  (page: raw_text)
```

Links to the same page can differ in small ways, such as `http` against `https`,
`www.`, or a trailing slash, so do not compare them as plain text. Run both sides
through `url_key` from `scripts/scrapers/common.py`, which gives the same key for the same
page:

```python
import sys
import pandas as pd

sys.path.insert(0, "scripts/scrapers")
from common import url_key

listings = pd.read_json("data/raw/hyperallergic.jsonl", lines=True)
pages = pd.read_json("data/raw/opportunity_pages.jsonl", lines=True)

listings["key"] = listings["website"].map(url_key)
pages["key"] = pages["source_url"].map(url_key)
joined = listings.merge(pages, on="key", how="left", suffixes=("", "_page"))
```

Several listings can link to one page, so a page can match more than one listing.
That is expected: in the next phase the listing's title, deadline, and fees can be
searched for in the page text to help create labels.

The data stays on your machine. Do not republish it.

## From listings to results

After the datasets are built, the project runs in this order.

1. **Clean.** `preprocess/clean.py` and `notebooks/EDA+Preprocessing.ipynb`
   remove menus and dead pages, merge repeat postings, and split by organizer.
2. **Chunk.** `scripts/labeling/chunk_pages.py` cuts pages into windows.
3. **Silver labels.** `scripts/labeling/make_silver.py` combines regex, distant
   (listing fields matched back to the page), and LLM labels. The LLM step needs
   `ANTHROPIC_API_KEY` in `.env`.
4. **Gold labels.** `scripts/labeling/make_gold_tasks.py` makes tasks for
   Label Studio, and `build_gold_tokens.py` turns the export into token labels.
   The rules are in [docs/gold_labeling_guide.md](docs/gold_labeling_guide.md).
5. **Train.** `notebooks/finetune_models.ipynb` fine-tunes the models in Google
   Colab on a GPU. Model weights are not checked in.
6. **Evaluate.** `models/extraction/` holds the regex baseline, the decoder,
   scoring (`evaluate.py`), the LLM comparison (`llm_gold.py`), and error
   analysis. Results are written to `docs/results/`.
7. **Match.** `models/matching/` holds the filters, BM25 and embedding rankers,
   and the evaluation against LLM-rated pairs.

## Demo app

A local Streamlit app takes a short description of your practice, filters out
listings that clearly exclude you, ranks the rest, and shows each opportunity
with its extracted deadline, fee, and eligibility. It needs the listing data and
extraction output, which are not in the repository.

```powershell
.venv\Scripts\streamlit.exe run app\streamlit_app.py
```

## Repository layout

```
/data        raw, clean, and labeled listings (not checked in)
/scripts     setup scripts, one scraper per source, and the labeling scripts
/preprocess  cleaning code
/models      extraction (baseline, decoding, scoring) and matching (filters, rankers)
/app         Streamlit demo
/notebooks   EDA and the Colab fine-tuning notebook
/docs        executive summary, labeling guide, results, figures
/Plans       project plans and the running progress log
```

## Status

The project timeline has ended. Extraction and matching are built and
evaluated; the quality classifier, a fine-tuned matching model, more data
sources, and a deployed app were out of scope in the end. See
[Plans/Progress.md](Plans/Progress.md) for the decision log and
[Plans/CLAUDE.md](Plans/CLAUDE.md) for the original project guide and KPIs.

Authors: Palak Arora, Viacheslav Ivanov.
