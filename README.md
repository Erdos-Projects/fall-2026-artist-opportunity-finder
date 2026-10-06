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

## Repository layout (planned)

```
/data        raw, clean, and labeled listings (not checked in)
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
