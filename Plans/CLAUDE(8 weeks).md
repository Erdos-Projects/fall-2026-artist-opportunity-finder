# Artist Opportunity Finder — Project Guide

## What this project is

An 8-week, end-to-end deep learning portfolio project. It helps visual and media
artists find grants, exhibition open calls, and residencies that fit their work,
instead of hunting across dozens of inconsistent listing sites, PDFs, and
newsletters. The system extracts structured fields from messy listing text,
flags low-value or high-risk listings, and ranks remaining opportunities against
an artist's profile.

This project exists to demonstrate a full ML pipeline for job interviews: messy
multi-source data collection, labeling, fine-tuning transformers, baselines,
rigorous evaluation, and a small deployed app — not just prompting an LLM.

**Owner:** Palak. **Domain expert:** Amay (practicing media artist), plus 5–8
artist volunteers for relevance ratings. **Learner context:** Palak is learning
deep learning and AI engineering hands-on through this project — explain
concepts explicitly in any planning or code-review conversation, don't assume
prior ML background.

## Scope (decided)

- **Opportunity types:** grants, exhibition open calls, and residencies only
  (not commissions or art fairs, for now).
- **Geography:** U.S.-based opportunities.
- **Quality label naming:** the risky class is called **"high risk"**, not
  "predatory," in all UI, docs, and code (renamed from the original proposal).
- **Primary dev environment:** Google Colab for model training/experimentation;
  this repo is for the rest (scraping, cleaning, APIs, app, docs).
- **No dashes** ("--" or em dashes) in generated docs/writeups — use commas,
  parentheses, or separate sentences instead.

## Why fine-tune instead of just prompting an LLM (keep this framing in all writeups)

- Shows DL depth: tokenization, label alignment, class imbalance, overfitting,
  calibration — the actual point of the project.
- Span-tagging models are grounded: they can only point at text that exists,
  so they can't hallucinate a deadline or fee the way a generative LLM can.
- Cost, latency, and determinism at scale.
- Mirrors a real industry pattern: large LLM as teacher/labeler, small model
  as the production student.
- Final architecture is a **hybrid**: fine-tuned model handles routine
  fields; an LLM handles reasoning-heavy fields (e.g. complex eligibility) or
  low-confidence cases, via a router. Always report accuracy, hallucination
  rate, cost, and latency for: baseline, fine-tuned model alone, LLM alone,
  and the hybrid.

## System design: three components

| # | Component | Baseline | DL / ML model | Evaluation |
|---|---|---|---|---|
| 1 | **Field extraction** (deadline, entry fee, award, eligibility location/career stage, medium, opportunity type) | Regex + rules | Fine-tuned **DeBERTa-v3** for token classification (BIO span tagging) | Per-field precision/recall/F1 on gold set; exact match for dates/fees; hallucination rate |
| 2 | **Quality classification** (legitimate / low value / high risk) | Rules (fee threshold, no named jurors, no stated prize) | Fine-tuned text classifier + **XGBoost** on structured features as a second baseline | Macro F1; precision on the high-risk class (precision matters more than recall — false flags hurt trust) |
| 3 | **Matching & ranking** (artist profile → listings) | BM25 + hard eligibility/deadline filters | Fine-tuned **bi-encoder** (sentence-transformer), optional cross-encoder reranker | Precision@10, NDCG@10 on judged artist profiles |

**Build order:** Component 1 → Component 3 → Component 2 (2 is the one to cut
first if time runs short).

## Repository layout (target)

```
/data
  /raw          # untouched scraped listings, one file per source, never edited
  /clean        # normalized text, dedup, structured fields matched to source
  /labeled      # gold (hand-labeled) and silver (auto/LLM-assisted) label sets
/scrapers       # one module per source (artworkarchive, nyfa, hyperallergic, ...)
/labeling       # labeling guide, Label Studio config, pre-label generation scripts
/models
  /extraction   # Component 1: DeBERTa fine-tuning, regex baseline, eval scripts
  /quality      # Component 2: classifier + XGBoost baseline
  /matching     # Component 3: bi-encoder + BM25 baseline
/api            # FastAPI backend (extract, classify, rank endpoints)
/app            # Streamlit or Gradio front end
/notebooks      # Colab-first experimentation; promote working code back into /models
/docs           # proposal, writeups, comparison tables
CLAUDE.md       # this file
```

## Timeline (8 weeks total)

- **Weeks 1–3 — Data.** Scrape, clean, deduplicate, and label listings
  (gold + silver sets) across all three components. Go/no-go checkpoint at
  end of week 3: need ≥1,000 unique cleaned listings and both gold sets done,
  or cut sources rather than cut label quality.
- **Weeks 4–5 — Models.** Build and evaluate Component 1 first, then
  Component 3, then Component 2 if time allows. Each gets a measured baseline
  before any fine-tuning.
- **Week 6 — Evaluation.** Consolidate comparison tables for all three
  components (baseline vs fine-tuned vs LLM vs hybrid where applicable).
  Error analysis.
- **Weeks 7–8 — Deployment + writeup.** FastAPI backend, Streamlit/Gradio
  front end, SaaS layer (auth, tiers, Stripe test mode), one-page writeup.

## Development phases (use these for actual build work, independent of week mapping)

### Component 1 — Field extraction

0. Learn tokens, BIO tagging, and fine-tuning concepts before writing code.
1. Environment setup (`transformers`, `torch`, `seqeval`, `accelerate`).
2. Scrape raw listings into `/data/raw`, untouched. Start with Artwork
   Archive Calls for Entry (has structured fields alongside free text,
   needed for distant supervision in phase 4). Add NYFA, ArtConnect,
   Hyperallergic, Res Artis, TransArtists, Artist Communities Alliance,
   organization pages/PDFs, and a shared newsletter inbox.
3. Clean text into `/data/clean`: collapse whitespace, fix HTML entities,
   strip boilerplate, deduplicate near-identical listings across sources.
4. Labels:
   - Write the labeling guide (multiple deadlines, tiered fees, what
     counts as eligibility vs medium, high-risk vs low-value criteria).
   - Generate **silver** pre-labels via distant supervision (match each
     source's structured fields back into its free text) + regex + LLM;
     review only disagreements.
   - Hand-label ~100 listings with no pre-labels as the **gold test set**.
   - Check labeler agreement on an overlapping 50-listing sample
     (span-F1 ≥ 0.80 target).
5. Token-label alignment: use `tokenizer(text, return_offsets_mapping=True)`
   to map character spans to per-token BIO labels. Test on 3 examples by
   hand before scaling up; a silent off-by-one bug here silently ruins the
   model. Dedupe before splitting; split by time or source (~70/15/15),
   not randomly.
6. Build and score the regex baseline on the gold test set first — this
   number is what the fine-tuned model must beat.
7. Fine-tune `microsoft/deberta-v3-base` with
   `AutoModelForTokenClassification`, using `seqeval` for `compute_metrics`.
   Typical config: `learning_rate=2e-5`, ~10 epochs, `load_best_model_at_end=True`.
8. Evaluate on gold set; compare regex baseline vs fine-tuned model vs
   large LLM on F1, exact match, cost per 1,000 listings, latency, and
   hallucination rate (does the model ever return a value not present in
   the source text — fine-tuned span model structurally cannot; LLM might).

### Component 3 — Matching & ranking (build second)

1. Collect relevance judgments: Amay (~50) + 5–8 artist volunteers (~20
   each) rate listings against real artist profiles, ~150–200 total.
2. Build the BM25 + hard-filter (eligibility, deadline) baseline; score it
   on the judged set.
3. Fine-tune a bi-encoder (sentence-transformer) on profile/listing pairs;
   add an optional cross-encoder reranker.
4. Evaluate: Precision@10, NDCG@10, compared against the BM25 baseline.

### Component 2 — Quality classification (build third, cut first if short on time)

1. Write quality-class criteria (fee threshold, no named jurors, no stated
   prize, rights grabs, no organizer track record) distinguishing
   legitimate / low-value / high-risk.
2. Amay reviews 30–50 borderline cases to validate the criteria.
3. Build the rules-based baseline; score it.
4. Build XGBoost on structured features as a second baseline.
5. Fine-tune a text classifier on listing text + extracted features.
6. Evaluate: macro F1, precision on the high-risk class (precision matters
   more than recall here — false flags hurt trust more than a missed flag).

### Deployment phase (after all three components are evaluated)

1. FastAPI backend: `/extract`, `/classify`, `/rank` endpoints.
2. Streamlit or Gradio front end: artist profile → ranked feed with
   extracted fields and risk flags.
3. SaaS layer: auth, free tier (a few matches/week), paid tier (weekly
   digest, deadline reminders), Stripe in test mode.
4. One-page writeup: sources, cleaning decisions, baseline vs model
   results, LLM cost/latency comparison, failure modes, future work.

## KPIs (set before experiments; revisit after baselines measured)

| Area | KPI | Target |
|---|---|---|
| Extraction | Micro F1 on gold test set | ≥ 0.85, ≥ 20 pts above regex baseline |
| Extraction | Exact match on deadlines/fees | ≥ 95% |
| Extraction | Hallucinated (unsupported) values | 0% for fine-tuned model |
| Extraction | Fine-tuned vs large LLM | Within 3 F1 pts, 90% lower cost/1k listings, ≥10x lower latency |
| Quality | High-risk class | Precision ≥ 0.85, recall ≥ 0.70, macro F1 ≥ 15% above rules baseline |
| Matching | NDCG@10 | ≥ 20% above BM25 |
| Matching | Precision@10 | ≥ 0.60 |
| Data | Unique cleaned listings | ≥ 1,000 by end of week 3 |
| Data | Labeler agreement (50-listing sample) | Kappa ≥ 0.70 (quality); span-F1 ≥ 0.80 (extraction) |
| Data | Silver label precision (checked sample) | ≥ 90% |
| Deployment | Extraction API p95 latency (CPU) | < 500 ms |
| User value | Artist testers rating top-10 feed useful | ≥ 4 of 5 |

## Working conventions

- Explain ML concepts from first principles in any discussion — Palak is
  learning as she builds.
- Prefer Colab notebooks for training experiments; promote stable code into
  `/models/*` once it works, so the repo stays reproducible outside Colab.
- Every model component needs a measured baseline before any fine-tuning
  work starts.
- Respect each source's terms of service and robots.txt; scrape slowly;
  cache everything; never republish raw scraped data or personal info.
- No dashes in prose output (docs, writeups, commit messages prose).

## Open decisions (revisit as needed)

- Whether to follow aggregator links to primary sources for the full
  labeled subset, or label straight from aggregator text.
- Final ownership split across team members for sources/components.
