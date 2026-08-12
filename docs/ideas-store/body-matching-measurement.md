# Match the body, not the title — measured, and it is the fix

The previous two rounds ([titles](semantic-standin-measurement.md),
[surfaces](authored-surfaces-measurement.md)) left one honest hypothesis: the
question-shaped misses are *the wrong entry scores highest*, because the probe is
scored against a **terse title** while the answer lives in the **body**. This
measures body-matching. It is the first variant that serves the correct referent
on every probe.

Still a measuring instrument (Haiku stand-in, [`../embedder-stand-in.md`](../embedder-stand-in.md)):
nothing sealed, no cache keyed, every row still a draft.

## Method

Same 29-referent slice. Each entry's body is split into ≤3 chunks of ~420 chars
(the way a real semantic index chunks a document); the probe is scored against
every chunk; **referent score = max over its chunks**. 83 chunks total. Compared
to the title-only arm (`A`) from the earlier rounds.

## Result

Rank of the correct referent out of 29, its score, and whether it clears 0.92 —
title vs body, with the full-corpus (143) title baseline for reference.

| probe | title/143 baseline | A title (29) | D body (29) |
|---|---|---|---|
| two reviewers seal same phrase | 1 · 0.667 | 1 · 1.00 ✓ | 1 · 0.95 ✓ |
| measure false-verification rate | 20 · 0.333 | 2 · 0.75 | **2 · 0.95 ✓** |
| import reviving a rejected pair | 1 · 0.621 | 1 · 0.90 | **1 · 0.925 ✓** |
| may a model verify itself | 1 · 0.468 | **19 · 0.00** | **1 · 0.95 ✓** |
| audit-log tamper check | 122 · 0.208 | 3 · 0.90 | **1 · 0.95 ✓** |

**Serves the correct referent: title 1/5, surfaces 2/5, body 5/5.**
**Correct referent at rank 1: title 3/5, surfaces 3/5, body 4/5.**

## What it says

**The two misses nothing else could fix are fixed here, and the reason is
concrete.** The model-verify probe went from rank 19 (score 0.00) to **rank 1
(0.95)** — because §5.7's body actually contains the answer the title hides:
*"a server that let a model seal … would be a system where the machine grades its
own work"* (chunk 44, scored 0.95). The audit-tamper probe went from 122/143 to
**rank 1**. Surfaces failed on both because you cannot author an honest surface
for a meaning the title lacks; the body already had the meaning. This confirms
the earlier diagnosis — it was a *matching-target* problem, not a matcher or a
title-wording problem.

## Three limits, stated so the win is not oversold

**1. Everything serves at 0.92–0.95, which is inside the drift band.** Per §6.99
the stand-in moves 0.150/0.300 between instantiations, and every "✓" above sits
in exactly that range. So *serves / does-not-serve* is an instrument reading, not
a guarantee — a second instantiation would flip some of them. What is **not**
fragile is the **rank** movement (19→1, 122-baseline→1): those are large and no
sample-of-one drift argument touches them.

**2. Body-matching raises scores broadly — precision was not measured, and looks
worse.** The audit-tamper probe scored *many* unrelated chunks 0.70–0.95 (a third
of the corpus talks about ledgers and integrity). The correct referent won, but
the margin is thin and the high-scoring field is wide, which is the signature of
a matcher that will **false-seal when the true answer is absent**. §3.4 stage-4
measured exactly this with leave-one-out and found `TokenOverlap` at 0.683 false
seals; the equivalent LOO control for body-matching was **not run here** and is
the necessary next measurement before any of this could serve. Rank up, precision
unknown-and-probably-down.

**3. One "serve" is a legitimate near-neighbor, not the target.** The
false-verification-rate probe serves at rank 2 behind §1.1 (*Margin, not just
magnitude*) at 0.95 — which genuinely is about false-seal rate. That is §1.3's
own "genuine near-duplicate" case, not a bug; but "serve the top match" would
serve §1.1, so even the body win argues for **ranking into a human queue** over
auto-serving a single answer.

## Where the three rounds leave it

| variant | serves | fixes cryptic-title miss (P4) | cost |
|---|---|---|---|
| title (canonical) | 1/5 | no | — |
| + authored surfaces | 2/5 | **no** (got worse) | authoring; false-lift |
| **body chunks** | **5/5** | **yes** | precision unmeasured; index size ×3 |

Body-matching is the answer to the question the first doc asked, and it relocates
the open problem cleanly: **not recall — precision.** The remaining work is the
leave-one-out false-seal control (limit 2), a per-chunk provenance so a served
answer can point at *which* span matched, and the standing conclusion the corpus
keeps returning (§3.4, and here): for question-shaped retrieval the mechanic is
**ordering a human's review queue**, not serving one answer at a bar.
