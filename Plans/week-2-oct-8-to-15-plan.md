# Week 2 Plan (Oct 8 to Oct 15): Labels and Architecture Decisions

Deliverable for the window: **HW2 (Oct 15), architecture decisions for the
baseline model and the DL model.** To make those decisions on evidence, this
week also finishes the labeled data that the baseline (Oct 15 to 22) and
DeBERTa (Oct 22 to 29) both depend on.

This plan follows [CLAUDE.md](CLAUDE.md) (Component 1 is the critical path,
Component 3 runs in parallel and slips first) and builds on the preprocessing
recorded in [Progress.md](Progress.md) (Session 3).

## Starting point

| Item | State |
|---|---|
| Cleaned listings | 299 canonical listings in `data/clean/listings.jsonl` (target was 400, see risk 1) |
| Usable page text | 215 listings have a usable organizer page, 84 have only a blurb and fields |
| Chunks | 1,058 chunks (about 390 estimated tokens each) in `data/clean/chunks.jsonl`, with clean and raw character offsets |
| Split | train 209, val 45, test 45 listings, split by organizer domain (`splits.json`) |
| Not done yet | Labeling guide, silver labels, gold set, agreement check, architecture write-up, relevance ratings request |

## Concepts to be comfortable with before the work (30 minutes)

- **Span labeling.** A label is "characters 120 to 131 of this chunk are the
  deadline". The model later turns this into one tag per token (B for the first
  token of a span, I for the rest, O for everything else). This week only needs
  the character spans. Token tags come in Phase 5 (Colab).
- **Gold vs silver.** Gold is labeled by a human with no help, and is only used
  to measure models. Silver is produced automatically (rules, matching known
  values back into the text, an LLM) and is used to train. Silver is noisy by
  design, so we check a sample of it.
- **Distant supervision.** Take a value we already know (the listing's parsed
  deadline) and find where it appears in the text. The position becomes a
  free silver label. It only works when the value is actually written in the
  text, which Progress.md shows is true for only 37% of deadlines and 38% of
  fee amounts, so expect partial coverage.

## Decisions to make first (Day 1, before any labeling)

These change what everyone labels, so settle them together with Amay.

1. **Field list and span rules.** The fields are deadline, entry fee, award,
   eligibility location, career stage, medium, and opportunity type. For each
   one write: what counts, what does not, and whether the span is the whole
   phrase or only the value (for example the fee "$35" or "a $35 application
   fee"). Recommendation: label the shortest span that carries the value, so
   exact match scoring is fair.
2. **Label unit.** Label **chunks** (the model's real input), not whole pages.
   A field that appears in the overlap between two chunks is labeled in both,
   which is correct, since each chunk is a separate training example.
3. **Hard cases.** Multiple deadlines (label each, tag as a separate span
   type only if time allows, otherwise label all of them as deadline), tiered
   fees (label each amount), rolling deadlines (no span), "free" entry (no span,
   it is recorded by the `fee_free` flag instead), and values that only appear
   in the blurb, not the page.
4. **Opportunity type.** Already decided: Grant/Fellowship, Residency, Open
   Call. This is a listing-level label, not a span, so it is checked by
   hand on the ambiguous cases (listings with both keywords or neither) and
   not span-tagged. Decide whether it is in the DeBERTa task or a separate
   small classifier (see the architecture section).

Output of Day 1: a first draft of `labeling/labeling_guide.md`.

## Step by step

### Step 1. Finish data fixes that affect labels (Day 1 to 2)

Small items from the Progress.md open list that would otherwise change the
text after labeling starts. Labels are character positions, so the text must
be frozen first.

- Run the fetch script for the 54 allowed links with no saved page (dry run
  first, about 54 credits), then re-run the notebook. If most are blocked by
  `robots.txt`, accept the loss and note the Open Call gap in the write-up.
- Spot check the ambiguous opportunity type listings and a sample of the
  title-split cases.
- Look at the 7 missing deadlines.
- Freeze `data/clean/` once this is done. Record the file hashes in
  `data_report.md` so any later change is visible.

Exit check: `listings.jsonl` and `chunks.jsonl` are final for labeling.

### Step 2. Labeling guide (Day 2)

Turn the Day 1 decisions into `labeling/labeling_guide.md`, with 2 or 3
worked examples per field taken from real chunks, including a hard one. This is
also the document the agreement check tests, so it should be specific enough
that Amay can follow it without asking questions.

### Step 3. Pick the labeling sets (Day 2)

- **Gold set: about 30 to 40 listings from the test split** that have a usable
  page. With 45 test listings, some have no page, so check how many remain. If
  fewer than 30 have pages, top up from val.
  Label every chunk of each chosen listing, so the gold set is complete
  at the page level.
- **Agreement sample: about 15 of the gold listings**, labeled independently by
  Palak and by Amay.
- **Silver set: all train listings with a usable page** (about 150 listings).
- Gold listings must never appear in silver. Write the ids to
  `data/labeled/gold_ids.json` and have the silver script read it and refuse
  to touch those ids.

### Step 4. Set up the labeling tool (Day 2 to 3)

- Use Label Studio with a config for the span types (`labeling/label_config.xml`).
  Load chunks as tasks, with the chunk id in the task data.
- Export format: JSON with character offsets relative to the **chunk text**.
- Test the round trip on 3 chunks by hand: label, export, and check that
  `chunk_text[start:end]` equals the highlighted text. A silent offset error
  here would ruin everything after, so this check is not optional.

### Step 5. Hand label the gold set (Day 3 to 5)

- Label with **no pre-labels**, so the gold set is not biased by the silver
  rules. Do not look at silver output for these listings.
- Budget: about 40 listings times about 3 chunks is about 120 chunks, at about 3 to
  4 minutes a chunk, which is 6 to 8 hours. Split across days.
- Keep a running list of guide gaps (a case the guide did not cover). Update
  the guide, then relabel anything labeled before the update.

### Step 6. Agreement check with Amay (Day 5 to 6)

- Amay labels the 15 shared listings independently from the guide.
- Score with span-level F1 (`seqeval` or a short script that counts exact span
  matches per field). Target: **span F1 of at least 0.80**.
- If a field is below target, read the disagreements, fix the guide wording,
  and re-label that field. Record the number before and after the fix.
- Resolve disagreements by discussion, and write the final version into the
  gold file. Keep both raw versions for the write-up.

### Step 7. Silver labels (Day 4 to 6, runs alongside step 5)

Three sources, combined by simple voting. Build them as separate scripts in
`labeling/` so each can be checked on its own.

1. **Distant supervision** (`labeling/silver_distant.py`). Match each listing's
   parsed deadline, fee amounts, and type back into its chunks. Needs
   the number and date formats written several ways ("March 5", "5 March
   2026", "03/05/2026"). Expect low coverage (about 37% for deadlines), so
   unmatched fields stay unlabeled and are not treated as negatives.
2. **Regex rules** (`labeling/silver_regex.py`). Start from the existing
   `parse_deadline` and `parse_fees` logic and extend to spans in the text.
   Reuse this same code as the Oct 15 to 22 regex baseline, so one piece of
   work serves both. It must stay a separate module from the silver pipeline in its
   final form, because the baseline is scored on gold only, and the silver
   labels must not be measured against themselves.
3. **LLM pre-labels** (`labeling/silver_llm.py`). Ask an LLM to return, for each
   field, the **exact quoted text** from the chunk. Then find the quote in the
   chunk to get offsets, and **drop any answer whose quote is not found
   verbatim** (that is a hallucination, and it also gives a first hallucination
   rate number for the write-up). Cache every response. Run on train chunks
   only, never on gold.

Combine: keep a span when at least two sources agree on the same offsets, send
disagreements to a review file, and review only those (this is the plan from
CLAUDE.md). Output: `data/labeled/silver.jsonl`.

**Silver quality check.** Hand check a random sample of about 50 silver spans
and record precision. Target: **at least 90%**. If lower, tighten the rules and
rerun before the data is handed to Colab.

### Step 8. Component 3 request (Day 1, 10 minutes of work, then it waits)

Ask for relevance ratings now so they are ready by Oct 22 to 29.

- Amay: about 30 to 40 ratings. 1 to 2 volunteers: about 10 each.
- Prepare a short sheet: a few artist profiles (medium, career stage,
  location) and 10 or so candidate listings each, rated 0 (not relevant),
  1 (maybe), 2 (relevant). Pull candidates from the train and val splits so the
  rated listings are not the gold test listings.
- Send it, then do not touch it again until next week.

### Step 9. Architecture decisions write-up, HW2 (Day 6 to 7)

Write `docs/hw2_architecture_decisions.md`. Each decision states the choice,
the alternatives, the reason, and what would change our mind. Cover:

**Baseline (regex and rules)**
- Which fields are regex-friendly (deadline, fee) and which are not (eligibility,
  medium, career stage, which need word lists or are likely to score low).
- How a rule outputs a span (offsets, not just a value), so it is scored the
  same way as the DL model.
- Scoring: per field precision, recall, F1 on exact span match, plus a looser
  overlap match, reported separately.

**DL model (DeBERTa-v3 token classification)**
- Why token classification (BIO) rather than generation: grounded in the text,
  so it cannot invent a deadline.
- Tag set: one B and I pair per span field (about 6 fields, so 13 tags with O).
  Opportunity type is probably a chunk-level classification head or a rule plus
  review, not BIO spans. Decide and write it down.
- Input handling: chunk size (300 words, about 390 tokens, re-check with the real
  tokenizer in Colab), overlap, and how predictions from overlapping chunks
  are merged back to a page (take the union and drop duplicate spans) so a span
  in the overlap is not counted twice.
- Subword alignment: label the first subtoken only or all subtokens, and
  how special tokens are ignored in the loss (-100). Pick the first-subtoken
  approach unless there is a reason, and test it on 3 examples by hand.
- Class imbalance: most tokens are O. Say how that is handled (weighted loss
  or just monitor per-field F1).
- Training setup from CLAUDE.md: `microsoft/deberta-v3-base`, learning rate
  2e-5, up to 10 epochs, `load_best_model_at_end=True`, seqeval for metrics.
- Evaluation plan: gold set F1, exact match for dates and fees, hallucination
  rate, and the later LLM and hybrid comparison.
- What the data limits mean: only about 150 silver listings and about 40 gold listings,
  so results are directional, not statistically solid. Say it plainly.

**Data decisions**
- Split by organizer domain and its limit (val and test have no repeat
  organizers).
- Silver as training labels and gold as the only test labels.

## Checklist (exit criteria for the window)

- [ ] `data/clean/` frozen, missing pages handled
- [ ] `labeling/labeling_guide.md` written with examples
- [ ] Label Studio round trip tested on 3 chunks
- [ ] Gold set labeled (about 30 to 40 listings), ids saved, kept out of silver
- [ ] Agreement sample scored, span F1 of at least 0.80 (or the guide fixed and
      rescored)
- [ ] Silver labels built from 3 sources, disagreements reviewed
- [ ] Silver precision of at least 90% on a 50 span sample
- [ ] Relevance rating request sent to Amay and volunteers
- [ ] `docs/hw2_architecture_decisions.md` written and submitted

## Risks and what to cut

1. **Data volume.** 299 listings is short of the 400 target. Do not stop to
   scrape more this week. The writeup states the number plainly.
   If a fast gain is available, TransArtists is the clearest source, but it needs
   a slow crawl, so only start it if it runs in the background.
2. **Gold set size.** 45 test listings with only some having pages makes
   about 30 the realistic number. Take about 30 and do not stretch. A smaller, clean
   set that passes the agreement check is better than a larger noisy one.
3. **Silver coverage is low** (about 37% of deadlines match). Fall back on
   regex and LLM for the rest. Do not force a match.
4. **Time.** If a day is lost, cut in this order: LLM pre-labels (use
   distant supervision plus regex only), then the second sample of silver
   checking (reduce to 30 spans), then the agreement sample (reduce to 10
   listings). Do **not** cut the gold set, the labeling guide, or the HW2
   write-up, since those are what is graded and what the baseline needs.
5. **Component 3 slips first.** Only the rating request goes out this week.

## What this hands to next week (Oct 15 to 22, HW3)

- `data/labeled/gold.jsonl` and `data/labeled/silver.jsonl`
- `labeling/silver_regex.py`, the starting point of the regex baseline
- `docs/hw2_architecture_decisions.md`, which the baseline and DeBERTa runs
  will follow
- Relevance ratings coming in, ready for the BM25 baseline
