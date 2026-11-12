# Artist Opportunity Finder: Executive Summary

Palak Arora, Viacheslav Ivanov

## What we set out to do

Grants, residencies and open calls for artists are scattered across listing sites, PDFs and newsletters, with the deadline, fee and eligibility buried in free text. We set out to read each listing and extract the key facts, match listings to an artist's profile, and show a ranked feed, comparing every model against a simple baseline and against a large LLM on accuracy, cost and speed.

## What we built

- **Data.** Hyperallergic's monthly opportunity posts (407 listings), plus the organizer page behind each link. After cleaning dead pages and merging repeats: 299 unique opportunities, 260 with usable text. Split by organizer so no organizer is in both training and test.
- **Field extraction.** Five fields: deadline, fee, career stage, location, medium. A fine-tuned RoBERTa token classifier (it can only point at text on the page, so it cannot invent a value), compared with a regex baseline and with an LLM (claude-opus-5-5, no training).
- **Labels.** 220 listings with machine ("silver") labels for training; 94% of a 50-span check was correct. 40 listings labeled by hand ("gold") for the final test; 7 were dead pages or announcements, so scoring uses 33 listings and 183 labeled spans.
- **Matching.** Keyword search (BM25) against sentence embeddings (all-MiniLM-L6-v2), with hard filters built from the extracted fields. Tested on 15 artist profiles with 324 LLM-rated pairs.

## Results

Extraction, scored once on the hand-labeled gold test (exact-match F1):

| Field | Regex | Fine-tuned | LLM |
|---|---|---|---|
| All fields (micro) | 0.19 | **0.41** | 0.40 |
| Deadline | 0.70 | 0.72 | 0.88 |
| Fee (6 spans only) | 0.55 | 0.67 | 1.00 |
| Career stage | 0.08 | 0.33 | 0.28 |
| Location | 0.05 | 0.09 | 0.20 |
| Medium | 0.17 | 0.36 | 0.26 |

- The fine-tuned model more than doubles the regex baseline and ties the LLM overall. The date itself is right with F1 0.79.
- The LLM is better on deadline and fee. The fine-tuned model is better on medium and career stage.
- The LLM costs about $49 per 1,000 listings and 4.3 seconds per call. The fine-tuned model takes about 0.1 seconds per listing on a GPU (estimated) with no per-call fee.
- Matching: BM25 precision@10 0.33, NDCG@10 0.52; embeddings 0.36 and 0.51. They tie within noise. The filters removed 28 listings rated not a fit and 4 rated a good fit, but moved the scores little.

## Targets from the proposal

| Target | Result | Met? |
|---|---|---|
| Micro F1 0.85 or higher, 20 points above regex | 0.41 exact (0.46 overlap); 22 points above regex | Gap to baseline yes, 0.85 no |
| Exact match 95% on deadlines and fees | Deadline value F1 0.79; fee exact F1 0.67 | No |
| 0% unsupported deadline or fee values | 0 of 280 predicted spans unsupported | Yes |
| Within 3 F1 points of the LLM | 0.41 against 0.40 | Yes |
| 90% lower cost, 10x lower latency | No per-call fee against about $49 per 1,000; about 40x faster (estimated, on GPU) | Yes (estimated; GPU time not priced) |
| NDCG@10 20% above BM25 | Embeddings 0.51 against 0.52 | No |
| Precision@10 0.60 or higher | 0.36 | No |
| Silver label precision 90% or higher | 94% (50-span sample) | Yes |
| 1,000 or more unique cleaned listings | 299 (260 usable) | No |
| Two-labeler agreement; CPU latency; artist testers; quality flagging | Not done | Not done |

## Why the scores are lower than the targets

- Exact match is strict: a right phrase with different edges counts as wrong. The regex also over-predicts (946 spans for 183 labels).
- The model finds almost every deadline (recall 0.97) but also marks open and announcement dates, so precision is 0.57.
- Machine labels flattered the model (0.62 F1 on silver validation, 0.41 on hand labels), and the silver and gold labeling rules differ.
- One source, 299 listings, 33 gold listings, one labeler, one seed. Differences of a few points are noise.

## Limits to keep in mind

- Matching ratings come from an LLM judge, not from artists, and cover 15 profiles. Treat the matching results as directional.
- The LLM also wrote the silver labels, so the LLM and fine-tuned comparison is not fully independent.
- Scope was cut to extraction and matching. We did not build the quality (predatory call) classifier, fine-tune an embedding model, collect more sources, or finish a deployed app with accounts and reminders.

## What we would do next

1. Teach the model to tell deadlines from other dates, and retrain with the gold labeling rules (every list item, plus a layer that stops phrases being cut in two).
2. Add sources and remove dead pages before labeling.
3. Test an LLM prompt written with the gold rules on new held-out listings. Then compare a single LLM, the fine-tuned model alone, and a hybrid (LLM for deadline and fee, fine-tuned model for medium and career stage). None of these has been measured, and choosing by the current gold scores would be tuning on the test.
4. Get human ratings for matching, clean the match text, and fine-tune an embedding model on rated pairs.
5. Handle calls open to a community or field (not a medium) and "outside of" wording in the location filter.
