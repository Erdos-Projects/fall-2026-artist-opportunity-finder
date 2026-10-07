# Artist Opportunity Finder — Project Guide

## What this project is

A 4-week, end-to-end deep learning portfolio project (rescoped down from an
original 8-week plan, see "Scope cuts" below). It helps visual and media
artists find grants, exhibition open calls, and residencies that fit their work,
instead of hunting across dozens of inconsistent listing sites, PDFs, and
newsletters. The system extracts structured fields from messy listing text
and ranks opportunities against an artist's profile.

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

## Scope cuts (1 month, not 2 — decided)

Original plan assumed 8 weeks; only 4 are available. Cuts, in order of what
mattered least to the core interview story:

- **Component 2 (quality / high-risk classification) is cut from the build
  entirely.** It's described as future work in the writeup, not built.
  (It was already the first thing the 8-week plan said to cut, so this is
  the same call made earlier.)
- **Component 3's bi-encoder fine-tuning is cut.** Use BM25 as the baseline
  and an **off-the-shelf pretrained** sentence-transformer (no training) as
  the comparison, scored on a much smaller judged set.
- **SaaS layer (auth, paid tiers, Stripe) is cut entirely.** The demo is a
  plain Gradio or Streamlit app with no accounts or billing.
- **Data targets shrink:** ~500–800 raw listings (not 2,000–5,000), from
  2–3 sources (not 6+). Gold test set for extraction is ~50 listings (not
  ~100). Labeler agreement check sample is ~20 listings (not 50).
- **Component 1 (field extraction) keeps its full scope.** It's the one
  component that actually demonstrates fine-tuning a transformer, so it is
  not the place to cut.

The writeup should say explicitly what was cut and why (scoping to what can
be finished and validated in a month), and list the cuts as future work.

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

## System design: components in scope for this build

| # | Component | Baseline | Model | Evaluation |
|---|---|---|---|---|
| 1 | **Field extraction** (deadline, entry fee, award, eligibility location/career stage, medium, opportunity type) | Regex + rules | Fine-tuned **DeBERTa-v3** for token classification (BIO span tagging) | Per-field precision/recall/F1 on gold set; exact match for dates/fees; hallucination rate |
| 3 | **Matching & ranking** (artist profile → listings) | BM25 + hard eligibility/deadline filters | **Off-the-shelf pretrained** sentence-transformer (no fine-tuning) | Precision@10, NDCG@10 on a small judged set |

**Build order:** Component 1 → Component 3.

**Cut from this build (future work):** Component 2, quality / high-risk
classification (legitimate / low value / high risk), and fine-tuning the
Component 3 bi-encoder. See "Scope cuts" above.

## Repository layout (target)

```
/data
  /raw          # untouched scraped listings, one file per source, never edited
  /clean        # normalized text, dedup, structured fields matched to source
  /labeled      # gold (hand-labeled) and silver (auto/LLM-assisted) label sets
/scrapers       # one module per source (artworkarchive, plus one more)
/labeling       # labeling guide, Label Studio config, pre-label generation scripts
/models
  /extraction   # Component 1: DeBERTa fine-tuning, regex baseline, eval scripts
  /matching     # Component 3: off-the-shelf embedding baseline vs BM25
/app            # Streamlit or Gradio demo (no auth, no backend API needed unless time allows)
/notebooks      # Colab-first experimentation; promote working code back into /models
/docs           # proposal, writeups, comparison tables
CLAUDE.md       # this file
```

## Timeline: anchored to actual course checkpoints (hard end date Nov 5, no
## deliverable after that)

The course grades one model's iteration (baseline → iteration 1 →
iteration 2), not two separate components on their own schedule. That
graded model is **Component 1**. Component 3 (matching) is kept because
it's valuable for the project, but it is **not separately graded** and runs
**in parallel** on data Component 1 already cleaned, never on its own
dedicated week, so it never competes with a Component-1 deadline.

| Window | Component 1 (critical path) | Component 3 (parallel, lighter-weight) | Homework due |
|---|---|---|---|
| Now → Oct 8 | Scrape what's possible now, even partial; basic EDA; preprocessing plan | — | **HW1, Oct 8:** EDA + preprocessing discussion |
| Oct 8 → Oct 15 | Finish cleaning/dedupe; labeling guide; silver labels; hand-label gold set (~30–40 listings, scaled down further for this timeline); write up baseline and DeBERTa architecture decisions | Ask Amay + volunteers for relevance ratings now so they're ready later | **HW2, Oct 15:** architecture decisions for baseline + DL model |
| Oct 15 → Oct 22 | Build and score the regex baseline on the gold set | Build the BM25 baseline on the same cleaned data | **HW3, Oct 22:** baseline model performance |
| Oct 22 → Oct 29 | Fine-tune DeBERTa, iteration 1; evaluate against baseline | Score an off-the-shelf sentence-transformer against BM25 | **HW4, Oct 29:** fully preprocessed data + DL model performance, iteration 1 |
| Oct 29 → Nov 5 | Refine to iteration 2 (error analysis, LLM comparison, hallucination check) | Finalize the matching comparison table; wire both into a minimal demo; writeup | **HW5, Nov 5 (final):** DL model performance, iteration 2 |

If anything has to slip, Component 3 slips first, exactly as before, it's
just now running continuously at low intensity instead of in a single block.

## Development phases (use these for actual build work, independent of week mapping)

### Component 1 — Field extraction

0. Learn tokens, BIO tagging, and fine-tuning concepts before writing code.
1. Environment setup (`transformers`, `torch`, `seqeval`, `accelerate`).
2. Scrape raw listings into `/data/raw`, untouched. Start with Artwork
   Archive Calls for Entry (has structured fields alongside free text,
   needed for distant supervision in phase 4). Add one more source; stop
   at 2–3 sources total for this timeline.
3. Clean text into `/data/clean`: collapse whitespace, fix HTML entities,
   strip boilerplate, deduplicate near-identical listings across sources.
4. Labels:
   - Write the labeling guide (multiple deadlines, tiered fees, what
     counts as eligibility vs medium, high-risk vs low-value criteria).
   - Generate **silver** pre-labels via distant supervision (match each
     source's structured fields back into its free text) + regex + LLM;
     review only disagreements.
   - Hand-label ~30–40 listings with no pre-labels as the **gold test set**
     (scaled down further to fit the Oct 8–Nov 5 window).
   - Check labeler agreement on an overlapping ~15-listing sample
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

### Component 3 — Matching & ranking (runs in parallel with Component 1,
### not on its own week, not separately graded by the course)

1. Ask for relevance judgments early (Oct 8–15, alongside Component 1's
   labeling work): Amay (~30–40) + 1–2 artist volunteers (~10 each),
   ~40–60 total. Collecting these early means they're ready before
   Component 3 needs them.
2. Build the BM25 + hard-filter (eligibility, deadline) baseline on
   Component 1's already-cleaned data; score it on the judged set
   (alongside Component 1's own baseline week, Oct 15–22).
3. Score an **off-the-shelf pretrained** sentence-transformer (no
   fine-tuning) on the same judged set (alongside Component 1's
   iteration 1, Oct 22–29).
4. Evaluate: Precision@10, NDCG@10, compared against the BM25 baseline.
5. Finalize the comparison table and fold into the demo during the last
   week (Oct 29–Nov 5), alongside Component 1's iteration 2.

### Cut from this build: Component 2 and bi-encoder fine-tuning

Not built in this 4-week pass. Keep the criteria and plan written up as
future work (quality-class criteria: fee threshold, no named jurors, no
stated prize, rights grabs, no organizer track record, distinguishing
legitimate / low-value / high-risk; a fine-tuned bi-encoder plus XGBoost
baseline for Component 2 if revisited).

### Demo + writeup phase (after both components are evaluated)

1. Gradio or Streamlit demo: artist profile → ranked feed with extracted
   fields. No auth, no tiers, no backend API required unless time allows.
2. One-page writeup: sources, cleaning decisions, baseline vs model
   results, LLM cost/latency comparison, failure modes, and future work
   (explicitly naming what was cut and why: Component 2, larger data,
   bi-encoder fine-tuning).

## KPIs (set before experiments; revisit after baselines measured)

Note: gold and judged sets are smaller than the original 8-week plan
(~50 listings, ~60–80 ratings), so treat these as directional targets, not
statistically robust claims — say so plainly in the writeup.

| Area | KPI | Target |
|---|---|---|
| Extraction | Micro F1 on gold test set | ≥ 0.85, ≥ 20 pts above regex baseline |
| Extraction | Exact match on deadlines/fees | ≥ 95% |
| Extraction | Hallucinated (unsupported) values | 0% for fine-tuned model |
| Extraction | Fine-tuned vs large LLM | Within 3 F1 pts, 90% lower cost/1k listings, ≥10x lower latency |
| Matching | NDCG@10 | ≥ 20% above BM25 |
| Matching | Precision@10 | ≥ 0.60 |
| Data | Unique cleaned listings | ≥ 400 by Oct 8 (HW1) |
| Data | Labeler agreement (~15-listing sample) | Span-F1 ≥ 0.80 (extraction) |
| Data | Silver label precision (checked sample) | ≥ 90% |

## Working conventions

- Explain ML concepts from first principles in any discussion — Palak is
  learning as she builds.
- Prefer Colab notebooks for training experiments; promote stable code into
  `/models/*` once it works, so the repo stays reproducible outside Colab.
- Every model component needs a measured baseline before any fine-tuning
  work starts.
- Protect Component 1's weekly checkpoints (they're graded: HW2 through
  HW5). Component 3 runs in parallel at lower intensity and is the thing
  that slips if time runs short, never Component 1.
- Nov 5 (HW5) is the hard end date for this course; there is no deliverable
  after it, so nothing gets deferred past it.
- Respect each source's terms of service and robots.txt; scrape slowly;
  cache everything; never republish raw scraped data or personal info.
- No dashes in prose output (docs, writeups, commit messages prose).

## Open decisions (revisit as needed)

- Whether to follow aggregator links to primary sources for the full
  labeled subset, or label straight from aggregator text.
- Final ownership split across team members for sources/components.
