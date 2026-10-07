# Component 1: Field Extraction — Step-by-Step Plan

This is the full, explicit build plan for Component 1 of the Artist Opportunity
Finder: extracting structured fields (deadline, fee, award, eligibility, medium,
opportunity type) from messy listing text. Written for a learner with no prior
deep learning background — every concept is explained as it comes up.

## What Component 1 actually is

You're building a system that reads a messy paragraph like this:

> "Submissions are due March 15, 2027. Entry fee is $35 for the first 3
> images, $10 for each additional. Open to artists residing in the United
> States, working in painting, drawing, or photography."

...and turns it into structured data:

```json
{
  "deadline": "March 15, 2027",
  "entry_fee": "$35 for the first 3 images, $10 for each additional",
  "eligibility_location": "United States",
  "medium": "painting, drawing, photography"
}
```

This is called **Named Entity Recognition (NER)**, or more precisely **span
extraction**: finding the exact stretch of text that answers each field and
labeling it. You're not generating new text; you're pointing at text that
already exists.

---

## Phase 0: Learn the minimum theory you need (before touching code)

Don't skip this. Building the model without understanding why it works will
make every bug impossible to debug.

### Step 0.1: Understand tokens

Before a neural network can read text, the text must be broken into
**tokens**: small chunks, often sub-word pieces. "Submissions" might become
`["Sub", "##missions"]`. This matters because every label you assign later is
assigned **per token**, not per character.

**Action:** Install the `transformers` library and run this in a Python
notebook to see tokenization happen:

```python
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained("microsoft/deberta-v3-base")
text = "Submissions are due March 15, 2027."
tokens = tokenizer.tokenize(text)
print(tokens)
```

Look at the output. Notice words get split oddly. This is normal and you'll
need to handle it.

### Step 0.2: Understand BIO tagging

To mark a span like "March 15, 2027" as a deadline, you label each token
that's part of it:

| Token | Label |
|---|---|
| March | B-DEADLINE (Beginning) |
| 15 | I-DEADLINE (Inside) |
| , | I-DEADLINE |
| 2027 | I-DEADLINE |
| . | O (Outside, not part of any field) |

This is called **BIO tagging** (Beginning, Inside, Outside). It's the
standard way to do span extraction. You'll have one such label per field
type (B-FEE, I-FEE, B-ELIGIBILITY, etc.), plus O for everything else.

**Action:** Read or watch one short explainer on "BIO tagging NER" until you
could explain it to someone else in one sentence.

### Step 0.3: Understand what "fine-tuning a transformer" means

A model like DeBERTa has already learned general English from huge amounts
of text (this is called **pretraining**, and you don't do this part; a
research lab already did it). **Fine-tuning** means taking that pretrained
model and continuing to train it, but now on your small labeled dataset,
with a new output layer added on top that predicts BIO tags for each token.

Think of it like this: the pretrained model already understands grammar and
meaning. Fine-tuning teaches it the specific, narrow skill of "in this
listing text, which words are a deadline."

### Step 0.4: Checkpoint before moving on

You should be able to answer, in your own words, without looking anything up:
1. What is a token?
2. What does a B- vs I- tag mean?
3. Why don't we train a model from scratch instead of fine-tuning?

If any of these are shaky, spend another hour here. Everything downstream
depends on this.

---

## Phase 1: Set up your environment

### Step 1.1: Create a clean Python environment

```bash
python3 -m venv dl_env
source dl_env/bin/activate   # on Mac/Linux
```

### Step 1.2: Install the core libraries

```bash
pip install transformers datasets torch scikit-learn pandas numpy seqeval accelerate sentencepiece
```

What each one does:
- `transformers`: Hugging Face's library, gives you DeBERTa and the training tools
- `datasets`: Hugging Face's data handling library, works well with `transformers`
- `torch`: PyTorch, the underlying deep learning engine
- `seqeval`: computes precision/recall/F1 specifically for BIO-tagged
  sequences (regular accuracy metrics don't work right for this task)
- `accelerate`: lets training use a GPU automatically if one is available
- `sentencepiece`: required by DeBERTa's tokenizer

### Step 1.3: Confirm it works

```python
import torch
print(torch.cuda.is_available())  # True if you have a GPU, False if CPU-only
```

Fine-tuning DeBERTa-base on a few hundred examples is small enough to run on
a CPU (slowly) or a free Colab GPU. You don't need expensive hardware for
this.

---

## Phase 2: Collect your raw listings (this is the data engineering work)

This phase has nothing to do with deep learning yet. You're just gathering
text.

### Step 2.1: Pick your first 2-3 sources

Start small. Don't try to scrape 10 sites at once. Begin with **Artwork
Archive Calls for Entry**, because it shows structured fields next to the
free text, which will help you later in Phase 4.

### Step 2.2: Write a simple scraper for one source

Use `requests` and `BeautifulSoup`:

```python
import requests
from bs4 import BeautifulSoup

url = "https://www.artworkarchive.com/call-for-entry"
response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
soup = BeautifulSoup(response.text, "html.parser")
```

**Before writing the real scraper:** open the page in your browser,
right-click a listing, choose "Inspect," and find the HTML tag/class that
wraps one listing. You're looking for a repeating pattern (e.g., every
listing is a `<div class="opportunity-card">`).

### Step 2.3: Extract one listing's raw text

Write code that pulls out, per listing:
- the full free-text description (this is what your model will read)
- any structured fields shown separately (deadline, fee, type) — save
  these too, you'll need them in Phase 4

### Step 2.4: Save raw data immediately, untouched

```python
import json
with open("raw_listings.jsonl", "a") as f:
    f.write(json.dumps({
        "source": "artworkarchive",
        "url": listing_url,
        "scraped_at": "2026-10-06",
        "raw_text": full_text,
        "structured_fields": structured_dict
    }) + "\n")
```

Never overwrite this file. This is your "raw layer" from the project plan.
If your cleaning code has a bug later, you can always re-derive clean data
from here.

### Step 2.5: Repeat for your other 1-2 sources, then stop and check your count

**Checkpoint:** You should have at least 200-300 raw listings saved before
moving to Phase 3. If you have fewer, keep scraping before moving on — the
later steps need enough raw material.

---

## Phase 3: Clean the text

### Step 3.1: Write a text-cleaning function

Raw scraped HTML often has leftover junk: extra whitespace, HTML entities
(`&amp;`), stray navigation text. Write one function and apply it to every
listing:

```python
import re

def clean_text(raw):
    text = re.sub(r"\s+", " ", raw)          # collapse multiple spaces/newlines
    text = text.replace("&amp;", "&")         # fix common HTML entities
    text = text.strip()
    return text
```

### Step 3.2: Remove near-duplicate listings

If you scraped from more than one source, the same opportunity may appear
twice with slightly different wording. For now (with only 1-3 sources), a
simple approach: compare the organization name + deadline, and if both match
another listing, treat it as a duplicate and keep only one copy.

### Step 3.3: Save the cleaned version as a new file

Keep this separate from your raw file (`clean_listings.jsonl`). This is
Phase 3 output.

**Checkpoint:** Open 10 random cleaned listings and read them. Do they read
like normal English sentences with no broken formatting? If not, go back
and fix your cleaning function.

---

## Phase 4: Create labels (this is where most of your time goes)

You need two kinds of labels: **gold** (hand-labeled, careful, for testing)
and **silver** (automatic, for training).

### Step 4.1: Write your labeling guide first

Before labeling anything, write a half-page document answering:
- If a listing has two dates (early deadline, final deadline), which do
  you tag as DEADLINE?
- If the fee is "$35 for 3 images, $10 each additional," is that one span
  or two?
- What exact field names will you use? Suggested starting set:
  - `DEADLINE`
  - `FEE`
  - `AWARD`
  - `ELIGIBILITY_LOCATION`
  - `ELIGIBILITY_CAREER`
  - `MEDIUM`

Keep this document open while you label; you'll refine it as you hit edge
cases.

### Step 4.2: Install Label Studio

```bash
pip install label-studio
label-studio start
```

This opens a web interface at `localhost:8080`.

### Step 4.3: Set up a labeling project

1. Create a new project in Label Studio.
2. Import your `clean_listings.jsonl` file.
3. Set up a labeling config for **NER/span labeling** (Label Studio has a
   built-in template for this called "Named Entity Recognition"). Edit the
   label list to match your field names from Step 4.1.

### Step 4.4: Generate automatic "pre-labels" using distant supervision

This is a key trick so you don't label 100% by hand. For listings from
Artwork Archive, you already have structured fields (from Step 2.3)
separate from the free text. Write code to find where that structured value
appears inside the free text, and automatically create a label there:

```python
def find_span(text, value):
    start = text.find(value)
    if start == -1:
        return None
    return {"start": start, "end": start + len(value)}

deadline_span = find_span(listing["raw_text"], listing["structured_fields"]["deadline"])
```

Import these as pre-annotations into Label Studio (it supports importing
predictions alongside the text).

### Step 4.5: Hand-label ~100 listings with NO pre-labels (your gold test set)

Pick 100 listings Label Studio hasn't pre-labeled (or turn pre-labels off
for this subset). Go through each one and highlight the spans yourself,
following your Step 4.1 guide exactly. This is slow — budget 1 to 3 minutes
per listing, so roughly 2 to 5 hours total. This set is your **ground
truth** for measuring the model later, so accuracy here matters more than
speed.

### Step 4.6: Correct the pre-labels on the rest (your silver training set)

For your remaining listings, review the auto-generated labels from Step 4.4
and fix any that are wrong. This is much faster than labeling from scratch —
you're checking, not creating.

### Step 4.7: Export labeled data from Label Studio

Label Studio exports to a JSON format. Export both sets separately:
- `gold_labels.json` (from Step 4.5)
- `silver_labels.json` (from Step 4.6)

**Checkpoint:** Open the exported JSON and confirm each entry has the text
plus a list of spans with `start`, `end`, and `label`. If the format looks
different, you'll need to adjust Phase 5 to match it.

---

## Phase 5: Convert labels into a format the model can train on

This step trips up most beginners, so go slowly.

### Step 5.1: Understand the conversion problem

Your labels are in **character positions** (start=21, end=35 in the raw
string). But your model needs **token-level BIO tags** (Phase 0, Step 0.2).
You must convert character spans into per-token labels. This requires
aligning tokens to characters.

### Step 5.2: Write the alignment function

```python
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("microsoft/deberta-v3-base")

def align_labels(text, spans, tokenizer):
    encoding = tokenizer(text, return_offsets_mapping=True)
    offset_mapping = encoding["offset_mapping"]  # list of (char_start, char_end) per token
    labels = ["O"] * len(offset_mapping)

    for span in spans:
        span_start, span_end, field = span["start"], span["end"], span["label"]
        first_token_in_span = True
        for i, (tok_start, tok_end) in enumerate(offset_mapping):
            if tok_start == tok_end:
                continue  # special tokens like [CLS], [SEP]
            if tok_start >= span_start and tok_end <= span_end:
                labels[i] = f"B-{field}" if first_token_in_span else f"I-{field}"
                first_token_in_span = False

    return encoding["input_ids"], labels
```

**What `return_offsets_mapping=True` does:** it tells you, for each token,
which characters of the original text it came from. This is exactly the
bridge between character spans and token labels.

### Step 5.3: Test this on 3 examples by hand

Print the tokens next to their assigned labels and visually check they look
right:

```python
input_ids, labels = align_labels(text, spans, tokenizer)
tokens = tokenizer.convert_ids_to_tokens(input_ids)
for tok, lab in zip(tokens, labels):
    print(f"{tok:15} {lab}")
```

**Do not proceed until this looks correct on several examples.** A silent
bug here (e.g., off-by-one character errors) will quietly ruin your entire
model and you won't find out until evaluation, when it's much harder to
debug.

### Step 5.4: Build your full label list and label-to-id mapping

```python
label_list = ["O", "B-DEADLINE", "I-DEADLINE", "B-FEE", "I-FEE",
              "B-AWARD", "I-AWARD", "B-ELIGIBILITY_LOCATION", "I-ELIGIBILITY_LOCATION",
              "B-MEDIUM", "I-MEDIUM"]
label2id = {label: i for i, label in enumerate(label_list)}
id2label = {i: label for label, i in label2id.items()}
```

### Step 5.5: Apply this to every listing and save as a Hugging Face Dataset

```python
from datasets import Dataset

def process_all(listings):
    all_input_ids, all_labels = [], []
    for listing in listings:
        input_ids, labels = align_labels(listing["text"], listing["spans"], tokenizer)
        label_ids = [label2id[l] for l in labels]
        all_input_ids.append(input_ids)
        all_labels.append(label_ids)
    return Dataset.from_dict({"input_ids": all_input_ids, "labels": all_labels})

train_dataset = process_all(silver_listings)
test_dataset = process_all(gold_listings)
```

---

## Phase 6: Build your baseline (do this before touching the neural network)

You need a baseline to prove the fine-tuned model is actually worth it.

### Step 6.1: Write regex rules for the easy fields

```python
import re

def extract_deadline_regex(text):
    pattern = r"(January|February|March|...|December)\s+\d{1,2},?\s+\d{4}"
    match = re.search(pattern, text)
    return match.group() if match else None

def extract_fee_regex(text):
    pattern = r"\$\d+(\.\d{2})?"
    match = re.search(pattern, text)
    return match.group() if match else None
```

### Step 6.2: Run the baseline on your gold test set and score it

For each listing in `gold_labels.json`, run your regex, compare its output
to the true label, and compute how often it's exactly right. Write this
number down. This is the number your real model must beat.

---

## Phase 7: Fine-tune DeBERTa

### Step 7.1: Load the pretrained model with a token-classification head

```python
from transformers import AutoModelForTokenClassification

model = AutoModelForTokenClassification.from_pretrained(
    "microsoft/deberta-v3-base",
    num_labels=len(label_list),
    id2label=id2label,
    label2id=label2id,
)
```

This loads DeBERTa's pretrained weights and attaches a new, untrained
linear layer on top that outputs one of your BIO labels per token.

### Step 7.2: Set up the training configuration

```python
from transformers import TrainingArguments, Trainer, DataCollatorForTokenClassification

data_collator = DataCollatorForTokenClassification(tokenizer)

training_args = TrainingArguments(
    output_dir="./deberta_extractor",
    learning_rate=2e-5,
    per_device_train_batch_size=8,
    num_train_epochs=10,
    evaluation_strategy="epoch",
    save_strategy="epoch",
    load_best_model_at_end=True,
)
```

What these mean, briefly:
- `learning_rate=2e-5`: a small step size for fine-tuning, standard for
  transformers. Too high and training becomes unstable; too low and it
  trains too slowly.
- `num_train_epochs=10`: the model sees your entire training set 10 times.
  With a small dataset, you need multiple passes.
- `load_best_model_at_end=True`: keeps the checkpoint that performed best
  on validation, not just the last one trained (models can get worse again
  if overtrained, called **overfitting**).

### Step 7.3: Write the evaluation function

```python
from seqeval.metrics import classification_report
import numpy as np

def compute_metrics(eval_pred):
    predictions, labels = eval_pred
    predictions = np.argmax(predictions, axis=2)

    true_labels = [[id2label[l] for l in label_row if l != -100] for label_row in labels]
    true_predictions = [
        [id2label[p] for p, l in zip(pred_row, label_row) if l != -100]
        for pred_row, label_row in zip(predictions, labels)
    ]

    report = classification_report(true_labels, true_predictions, output_dict=True)
    return {"f1": report["micro avg"]["f1-score"]}
```

(The `!= -100` check matters: special tokens and padding get label `-100`
so they're ignored in scoring.)

### Step 7.4: Train

```python
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=test_dataset,
    data_collator=data_collator,
    compute_metrics=compute_metrics,
)

trainer.train()
```

Watch the output. The `f1` score should generally rise over epochs. If it's
flat or dropping from the start, something upstream (likely Phase 5's
alignment) is broken.

### Step 7.5: Save the model

```python
trainer.save_model("./final_deberta_extractor")
tokenizer.save_pretrained("./final_deberta_extractor")
```

---

## Phase 8: Evaluate and compare against baselines

### Step 8.1: Get your fine-tuned model's metrics on the gold test set

This comes directly from `compute_metrics` during the final evaluation;
also print the full `seqeval.classification_report` to see per-field
breakdowns, not just the overall average.

### Step 8.2: Run a large LLM on the same gold test set

Use a structured-output prompt (ask it to return JSON with the same field
names) on each gold listing, then score its output the same way: did it
return the exact right span.

### Step 8.3: Build your comparison table

| Model | F1 | Deadline exact match | Cost per 1,000 listings | Latency |
|---|---|---|---|---|
| Regex baseline | ? | ? | ~$0 | instant |
| Fine-tuned DeBERTa | ? | ? | ~$0 (after training) | fast, runs on CPU |
| Large LLM | ? | ? | $$ | slower |

This table is your deliverable for this component, and it's the evidence
behind the KPIs in your project plan.

### Step 8.4: Check for hallucinated values

For deadline and fee, specifically check: did the model (or the LLM) ever
return a value that doesn't appear anywhere in the source text? Your
fine-tuned span-tagger structurally cannot do this (it only points at
existing text); the LLM might. Count and report this difference — it's one
of your strongest findings.

---

## Summary of what you'll have at the end of Component 1

- A raw, clean, and labeled dataset (gold + silver)
- A working regex baseline with a measured score
- A fine-tuned DeBERTa model that extracts 5-6 fields from messy listing text
- A comparison table against the baseline and against a large LLM
- A measured hallucination rate difference

Each phase above has a clear checkpoint before moving to the next. If you
get stuck at any specific step, note exactly where things went wrong (the
error message, or what the output looked like versus what you expected)
before debugging further.
