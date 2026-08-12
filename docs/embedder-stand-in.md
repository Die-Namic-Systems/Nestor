# A language model standing in for the embedder

The semantic seam (`nestor.semantic_matcher`) needs either `fastembed` weights
from HuggingFace or a local Ollama daemon. Where a container has neither — a
locked-down egress policy refuses both hosts, which is the case this was written
in — the seam cannot be exercised at all, and the two things a semantic matcher
is supposed to buy stay unmeasured.

A language model can stand in, and this is the protocol that was used. **It is a
measuring instrument, not a backend.** The boundary is at the end and it is the
most important part of the file.

## What it answers

Not embeddings. It answers the `score(raw_a, raw_b) -> float` half of the
`Matcher` protocol directly (`docs`: README → The Matcher seam), which is the
part `memory.lookup` actually calls when a matcher provides it.

Requests are batched; the reply is a JSON array and nothing else:

```json
{"id": 1, "sim": 0.450, "note": "same ecosystem, different control mechanisms"}
```

## The rubric

```
1.000  identical meaning; interchangeable with no loss
0.900  paraphrase; same claim, different wording
0.750  same subject, compatible but not equivalent claims
0.500  same domain or family, different subject
0.250  incidental overlap only (shared words, unrelated meaning)
0.000  unrelated
```

Plus two instructions: interpolate to three decimals, and *"judge meaning only —
two names that look alike but denote different things are LOW (≤0.35)"*.

**That last clause contradicts the 0.500 anchor and you should not copy it as
written.** A pair like `willow-gate` / `willow-config` satisfies both "look alike
and denote different things" (≤0.35) and "same domain or family, different
subject" (0.500). Three instantiations resolved it three ways — 0.500, 0.450 and
0.300 — and the 0.300 run was the only one obeying the rule as stated. Either
drop the ≤0.35 clause or scope it to pairs that share *no* domain; leaving both
in produces a spread that looks like model noise and is authored.

## What it measures well

Against `StringMatcher` on the same inputs, on this fleet's own corpus:

| pair | StringMatcher | stand-in |
|---|---|---|
| `willow-gate` ↔ its own one-line description | **0.098** | **0.900** |
| `homestead-law` ↔ `homestead-ledger` | **0.741** | 0.600 |

Those are the two failures a semantic matcher exists to fix — a name that cannot
reach its own description by character ratio, and two names that reach each other
far too easily — and neither number was obtainable in this container by any other
means.

## What it is not

**It is not deterministic, and the obvious test says it is.** Resume the same
agent and it reproduces its previous answers exactly, floats and free-text notes
alike, three times over many turns. That is *recall*: it is reading its own
transcript. A fresh instantiation of the identical protocol moves every
non-identical pair.

Measured across three independent instantiations (IDEAS §6.99):

- mean absolute spread **0.150**, max **0.300**
- the max case is `homestead-law` / `homestead-ledger` at 0.600 against 0.300 —
  a factor of two on the same input under the same prompt
- an n=2 comparison of the same thing reported mean 0.050 and max 0.075. **One
  extra sample quadrupled it**, so treat any two-instantiation figure as a lower
  bound rather than a measurement.

What does hold across every run: **identical input strings return exactly
1.000**.

## The boundary

Decisions `0084` and `0089`, both drafts in `docs/dogfood/decisions/`:

> A measuring instrument, not a backend. It may put numbers on what the semantic
> seam would buy. It may **not** key the embedding cache and it may **not** stand
> behind a seal.

`nestor/embedding_store.py` keys cached vectors by `model_name`, and a key is a
promise that the function behind it is fixed. This one is not: a cache hit and a
fresh call return different numbers, which makes the stored row unreproducible —
the one property the whole store exists to protect.

At the shipped `SEAL_THRESHOLD` of 0.92, a spread of 0.300 puts roughly
**0.62–1.00** in play. That is most of the range in which a semantic matcher
would ever be asked to decide anything, so the boundary above is not a
precaution about edge cases near the bar.
