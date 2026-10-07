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

Hyperallergic publishes a monthly "Opportunities in <Month> <Year>" post. This
scraper reads the newest 30 of them and saves one line per opportunity (title,
description, deadline, fees, website, and the original text) to
`data/raw/hyperallergic.jsonl`.

Windows (PowerShell):

```powershell
.venv\Scripts\python.exe scrapers\hyperallergic.py --months 30
```

Linux or macOS:

```bash
.venv/bin/python scrapers/hyperallergic.py --months 30
```

Downloaded pages are cached in `data/raw/_cache/hyperallergic`, and months that
are already in the output file are skipped, so it is safe to run again. The first
run takes a while because it waits a few seconds between requests. The scraper
prints a note for any paragraph it could not read, so check those after a run.

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
