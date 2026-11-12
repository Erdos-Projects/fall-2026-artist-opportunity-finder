"""Turn token predictions back into page-level character spans.

The model predicts a tag for each token in each window. Windows overlap, so a
token can appear in two windows. This file averages the probabilities of the
same token (same character offsets) across windows, picks the best tag per
token, and joins B-/I- runs into (label, start, end) spans on the full page.
Those spans go straight into evaluate.py, the same scorer the regex baseline uses.

No torch needed: probabilities are numpy arrays of shape (n_tokens, n_labels)
for each window, including the [CLS] and [SEP] positions (offset [-1, -1]).
"""
from collections import defaultdict

import numpy as np


def decode_page(windows, probs, id2label, o_scale=1.0):
    """windows: window dicts from tokens_<split>.jsonl for ONE page.
    probs: one array per window. Returns [(label, start, end)] on the page.

    o_scale multiplies the probability of the "O" (no label) tag before the best tag is picked.
    1.0 is the plain argmax. A value above 1 makes the decoder more cautious: fewer spans,
    higher precision, lower recall. It needs no retraining."""
    o_id = next(i for i, l in id2label.items() if l == "O")
    acc = {}
    for w, p in zip(windows, probs):
        for (s, e), row in zip(w["offsets"], p):
            if s < 0:  # [CLS] or [SEP]
                continue
            if (s, e) in acc:
                acc[(s, e)][0] += row
                acc[(s, e)][1] += 1
            else:
                acc[(s, e)] = [np.array(row, dtype=float), 1]
    spans, cur = [], None
    for (s, e) in sorted(acc):
        scores = acc[(s, e)][0].copy()
        scores[o_id] *= o_scale
        tag = id2label[int(np.argmax(scores))]
        if tag == "O":
            if cur:
                spans.append(tuple(cur))
                cur = None
            continue
        prefix, label = tag.split("-", 1)
        if prefix == "B" or cur is None or cur[0] != label:
            if cur:
                spans.append(tuple(cur))
            cur = [label, s, e]
        else:
            cur[2] = e
    if cur:
        spans.append(tuple(cur))
    return spans


def snap_to_words(spans, text):
    """Extend each span outward so it does not start or end in the middle of a word.

    The model sometimes tags only the first piece of a long word ("chore" for "choreographers").
    A word is a run of letters and digits. Spans of the same label that overlap after snapping are
    merged. A fixed rule, nothing to tune. spans: [(label, start, end)]."""
    snapped = []
    for label, s, e in spans:
        while s > 0 and text[s - 1].isalnum() and text[s].isalnum():
            s -= 1
        while e < len(text) and text[e - 1].isalnum() and text[e].isalnum():
            e += 1
        snapped.append((label, s, e))
    merged = []
    for label, s, e in sorted(snapped, key=lambda x: (x[0], x[1], x[2])):
        if merged and merged[-1][0] == label and s < merged[-1][2]:
            merged[-1] = (label, merged[-1][1], max(e, merged[-1][2]))
        else:
            merged.append((label, s, e))
    return sorted(merged, key=lambda x: (x[1], x[2]))


def decode_all(windows, probs, id2label, o_scale=1.0):
    """Group windows by page and decode each. Returns {page_key: [(label, start, end)]}."""
    by_page = defaultdict(list)
    for i, w in enumerate(windows):
        by_page[w["page_key"]].append(i)
    return {key: decode_page([windows[i] for i in idx], [probs[i] for i in idx], id2label, o_scale)
            for key, idx in by_page.items()}
