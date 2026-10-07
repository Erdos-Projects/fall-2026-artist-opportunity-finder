# Artist Opportunity Finder

Team project: fall-2026-artist-opportunity-finder

Artist Opportunity Finder helps visual and media artists find grants, exhibition
open calls, and residencies that fit their work, instead of hunting across dozens
of inconsistent listing sites, PDFs, and newsletters. It is an 8-week, end-to-end
deep learning project covering data collection, labeling, fine-tuning, evaluation,
and a small deployed app. The current scope is U.S.-based opportunities.

## How it works

The system has three components, each measured against a simple baseline before
any fine-tuning.

| Component | What it does | Baseline | Model |
|---|---|---|---|
| Field extraction | Pulls deadline, entry fee, award, eligibility, medium, and opportunity type out of messy listing text | Regex and rules | Fine-tuned DeBERTa-v3 token classifier (BIO span tagging) |
| Matching and ranking | Ranks listings against an artist's profile | BM25 with hard eligibility and deadline filters | Fine-tuned bi-encoder, optional cross-encoder reranker |
| Quality classification | Labels listings as legitimate, low value, or high risk | Rules (fee threshold, no named jurors, no stated prize) | Fine-tuned text classifier, plus XGBoost on structured features |

## Why fine-tune instead of prompting an LLM

A span-tagging model can only point at text that exists in the listing, so it
cannot invent a deadline or a fee the way a generative model can. It is also
cheaper, faster, and deterministic at scale. The final design is a hybrid: the
fine-tuned model handles routine fields, and an LLM handles reasoning-heavy or
low-confidence cases through a router. Results are reported for the baseline,
the fine-tuned model, the LLM, and the hybrid.

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

Each source has its own scraper in `scrapers/`. Run them from the project folder
with the environment active (see Getting started).

### Hyperallergic

The Hyperallergic data is built in two steps, and the second depends on the
first. Both write to `data/raw/`.

| Step | Script | Writes | One line per |
|---|---|---|---|
| 1. Listings | `scrapers/hyperallergic/hyperallergic.py` | `hyperallergic.jsonl` | Opportunity |
| 2. Opportunity pages | `scrapers/hyperallergic/fetch_opportunity_page.py` | `opportunity_pages.jsonl` | Linked page |

**Step 1: the listings.** Hyperallergic publishes a monthly "Opportunities in
<Month> <Year>" post. This scraper reads the newest 30 of them and saves one line
per opportunity: title, description, deadline, fees, website, type, and the
original text. Each listing's `website` is the link Hyperallergic gives for it,
cleaned of tracking labels, and it usually points to the organizer's own page.

Windows (PowerShell):

```powershell
.venv\Scripts\python.exe scrapers\hyperallergic\hyperallergic.py --months 30
```

Linux or macOS:

```bash
.venv/bin/python scrapers/hyperallergic/hyperallergic.py --months 30
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
.venv\Scripts\python.exe scrapers\hyperallergic\fetch_opportunity_page.py
```

Each organizer has its own terms of use, which the script cannot read. Read the
terms of the sites you are comfortable with, and add any that forbid automated
access to `SKIP_DOMAINS` in the script. It checks robots.txt for you. Then fetch
a few pages to check the result, and then all of them:

```powershell
.venv\Scripts\python.exe scrapers\hyperallergic\fetch_opportunity_page.py --scrape --limit 5
.venv\Scripts\python.exe scrapers\hyperallergic\fetch_opportunity_page.py --scrape
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
through `url_key` from `scrapers/common.py`, which gives the same key for the same
page:

```python
import sys
import pandas as pd

sys.path.insert(0, "scrapers")
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

## Repository layout (planned)

```
/data        raw, clean, and labeled listings (not checked in)
/scripts     environment setup scripts
/scrapers    one module per source
/labeling    labeling guide, Label Studio config, pre-label scripts
/models      extraction, quality, and matching components
/api         FastAPI backend (extract, classify, rank)
/app         Streamlit or Gradio front end
/notebooks   Colab experiments
/docs        proposal, writeups, comparison tables
```

## Status

Early setup. Data collection and labeling come first (weeks 1 to 3), followed by
models, evaluation, and deployment. See [CLAUDE.md](CLAUDE.md) for the full
project guide, timeline, and KPIs.
