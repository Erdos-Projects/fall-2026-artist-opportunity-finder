# Component 1: Field Extraction, Split by Environment

This is a high-level plan for Component 1 that separates the work into two
parts, each with its own setup:

- **Part A, Data (local machine):** collecting, cleaning, and labeling listings
  with plain Python scri`pts. No deep learning libraries, no GPU.
- **Part B, Deep learning (Google Colab):** turning labels into model inputs,
  training, and evaluation. This is where the GPU and the heavy libraries live.

The phases and their numbering are the same as in
[the archived original plan](<(archive)component-1-field-extraction-plan.md>).
That document keeps the step-by-step detail and code. This one only decides
where each phase runs and what passes between the two parts. Separate
implementation plans will be written for each phase when it is time to build it.

## Where each phase runs

| Phase | What happens | Where |
|---|---|---|
| 0 | Learn tokens, BIO tagging, fine-tuning | Reading, plus a scratch Colab notebook |
| 1 | Environment setup | Split: 1A local, 1B Colab |
| 2 | Collect raw listings | Local |
| 3 | Clean and deduplicate text | Local |
| 4 | Create gold and silver labels | Local |
| | **Handoff: labeled data moves to Colab** | |
| 5 | Convert labels to token-level BIO tags | Colab |
| 6 | Regex baseline | Colab |
| 7 | Fine-tune DeBERTa | Colab |
| 8 | Evaluate and compare | Colab |

**Deep learning starts at Phase 5.** Everything before it is data engineering
and needs nothing beyond ordinary Python.

## Why split it this way

- **Different needs.** Scraping and labeling are slow, long-running, and tied to
  files on disk. Training needs a GPU for a short burst. Colab sessions reset
  and lose their files, which is fine for training and bad for a growing dataset.
- **Lighter local setup.** The local environment never installs PyTorch or
  `transformers`, so it stays small and quick to rebuild.
- **A clean contract.** Part A's only job is to produce labeled files in a fixed
  format. Part B's only job is to consume them. Either side can be reworked
  without touching the other.

## Phase 0: Learn the concepts

Unchanged, and it comes first. The goal is to be able to explain a token, a B
tag versus an I tag, and why we fine-tune instead of training from scratch.

The one hands-on exercise (watching a tokenizer split a sentence) needs
`transformers`, so do it in a throwaway Colab notebook. Nothing has to be
installed locally for this phase.

---

# Part A: Data (local)

## Phase 1A: Local setup

- Create a Python virtual environment in the project folder.
- Install from [requirements.txt](../requirements.txt), which covers scraping,
  cleaning, and the labeling tool only.
- Create the `data/raw`, `data/clean`, and `data/labeled` folders. These are
  ignored by git, so the data stays on this machine.

**Done when:** the environment activates and the packages import without errors.

## Phase 2: Collect raw listings

- One scraper script per source under `/scrapers`, starting with Artwork Archive
  Calls for Entry because it shows structured fields next to the free text.
- Each script writes untouched listings to `data/raw`, one file per source,
  including the source, URL, scrape date, raw text, and any structured fields.
- Raw files are never edited or overwritten. Respect robots.txt and terms of
  service, scrape slowly, and cache responses.

**Done when:** 200 to 300 raw listings are saved from the first 2 to 3 sources.

## Phase 3: Clean the text

- One cleaning script reads `data/raw` and writes `data/clean`: collapse
  whitespace, fix HTML entities, strip boilerplate, remove near-duplicates.
- Cleaning is always re-runnable from raw, so a bug here never costs data.

**Done when:** 10 random cleaned listings read like normal English.

## Phase 4: Create labels

- Write the labeling guide first (field names, how to handle multiple deadlines
  and tiered fees).
- Run Label Studio locally for span labeling.
- Generate **silver** pre-labels by matching each source's structured fields
  back into its free text, then correct them by hand.
- Hand-label about 100 listings with no pre-labels as the **gold** test set.

**Done when:** gold and silver sets are exported to `data/labeled`.

---

# Handoff: from local to Colab

This is the only point where the two parts touch.

**What Part A delivers:** two files, gold and silver, where each record has the
listing text plus a list of labeled spans (`start`, `end`, `label`) given as
**character positions**. Nothing in these files depends on any model or
tokenizer.

**How it gets to Colab:** upload the labeled files to a Google Drive folder and
mount Drive in the notebook. The data is not in git, so Drive is the bridge.

**Before handing off, check:**

- Every span's `start` and `end` actually select the intended text.
- Duplicates are removed, so the same listing cannot land in both training and
  test data.
- The label names match the labeling guide exactly.

Keeping labels as character positions is deliberate. If the model changes later,
the labels stay valid and only Phase 5 is rerun.

---

# Part B: Deep learning (Colab)

## Phase 1B: Colab setup

- Create a notebook under `/notebooks` and switch the runtime to GPU.
- Colab already includes PyTorch and `transformers`. The first cell installs the
  few extras (such as `seqeval` and `sentencepiece`) and mounts Google Drive.
- Create a Drive folder for the project with the labeled data in and model
  checkpoints out, since Colab's own disk is wiped when a session ends.

**Done when:** the notebook sees a GPU and can read the labeled files from Drive.

## Phase 5: Convert labels for the model

- Use the model's tokenizer to map each character span to per-token BIO tags.
- Check the result by eye on a few examples before running it on everything. A
  silent off-by-one error here ruins the model without any visible warning.
- Split into train, validation, and test by time or source, not randomly.

This phase lives in Colab because the tokenizer must be the exact one the model
uses.

## Phase 6: Regex baseline

- Simple pattern rules for the easy fields (dates, dollar amounts), scored on
  the gold test set.
- There is no neural network here. It sits in Part B only so that it is scored
  with the same evaluation code and the same gold set as the model, which keeps
  the numbers directly comparable.

**Done when:** the baseline score is written down. This is the number to beat.

## Phase 7: Fine-tune DeBERTa

- Load `microsoft/deberta-v3-base` with a token classification head and train
  on the silver set, checking progress on the validation set each epoch.
- Save the best checkpoint to Drive.

**Done when:** F1 rises over epochs and a saved model can be reloaded.

## Phase 8: Evaluate and compare

- Score the fine-tuned model on the gold test set, with a per-field breakdown.
- Run a large LLM on the same gold set and score it the same way.
- Build the comparison table: F1, exact match on deadlines and fees, cost per
  1,000 listings, latency, and hallucination rate.

**Done when:** the comparison table is filled in for the regex baseline, the
fine-tuned model, and the LLM.

---

## What moves back into the repo

Colab is for experiments. Once something works, the stable version is copied
back into the repo so the project can be reproduced without the notebook:

- Alignment, baseline, and evaluation code go to `/models/extraction`.
- Notebooks are saved to `/notebooks`.
- Results tables go to `/docs`.
- Model weights stay on Drive. They are too large for git and are ignored.
