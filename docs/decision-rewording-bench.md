# N1 — does the matcher recognize a re-worded decision?

`docs/decision-memory.md`'s build order puts this bench *before* N9 trusts the
graph, and N9(1) (`nestor decision check`) shipped without it. This is that
measurement. Apparatus: [`bench/bench_decision_n1.py`](../bench/bench_decision_n1.py),
corpus [`bench/corpus_decision_n1/`](../bench/corpus_decision_n1/), results
[`bench/results/decision_n1.json`](../bench/results/decision_n1.json).

## Why it decides the gate

`constraints_on` matches a question by its **exact** normalized form, so
`nestor decision check` catches a rejected/contradicted decision only when the
new proposal is worded identically. A re-worded proposal of a rejected question
returns exit 0 — a false clear. The obvious fix is to make retrieval *fuzzy*.
The obvious hazard is **wrong-key**: a re-worded probe whose best match is a
*different* decision, above the bar — a false constraint that would block the
wrong thing (or mask the right one). §6.14 measured 2/3 re-wordings ranking a
different decision first on the string matcher, so the hazard is not theoretical.

## Method

24 real decisions sampled from the committed dogfood store (`decision` domain).
A Haiku agent, seeing **only the questions**, wrote one re-wording of each — a
different engineer typing the same question from memory. Each probe is scored
against all 24 decision questions; the correct decision's rank and score, the
top match, and whether a *wrong* decision clears the bar, are tallied.
**Paraphrase-bite control (every run): 0/24 probes normalize identically to
their source** — the probes are genuinely re-worded, so recall is not a lookup
test in disguise.

## Result (bar 0.92)

| matcher | rank@1 (correct is top) | recall@0.92 (caught) | wrong-key@0.92 (false constraint) |
|---|---|---|---|
| StringMatcher (character) | 21/24 · 88% | **0/24 · 0%** | 0/24 |
| TokenOverlap (token) | 23/24 · 96% | **0/24 · 0%** | 0/24 |
| Haiku semantic stand-in | 24/24 · 100% | **24/24 · 100%** | 0/24 |

## What it establishes

> **Corrected in place — the first version of this section overreached, and the
> correction is the whole point of the bench.** It read: *"Character and token
> matching cannot fix the gate … switching `constraints_on` to a fuzzy
> `StringMatcher`/`TokenOverlap` would buy the gate zero re-worded recall …
> semantic matching is the only lever."* That is measured to be **false**, and
> the number that refutes it was in the table above the whole time: **rank@1 was
> 88–96%.** The correct decision was the *top match* almost every time — it just
> scored below **0.92**. The failure was the **bar**, not the matcher. Kept
> verbatim so the overreach is checkable; the truth is below.

**At the shipped 0.92 bar, character/token serve nothing — but that bar is the
defect, not the matcher.** 0.92 is tuned for exact-match translation; on a corpus
of *decisions* it is simply the wrong dial. Sweep it (the bench's `--sweep`, which
is what `nestor calibrate` is for) and a clean window opens:

| bar | StringMatcher recall | wrong-key | TokenOverlap recall | wrong-key |
|--:|--:|--:|--:|--:|
| 0.92 | 0% | 0 | 0% | 0 |
| 0.55 | 54% | 0 | 42% | 0 |
| **0.45** | **75%** | **0** | **62%** | **0** |
| 0.40 | 83% | 4% | 67% | 4% |
| 0.30 | 96% | 12% | 88% | 4% |

**A calibrated character matcher recovers ~60–75% of re-wordings with zero false
constraints** — no embedder, no new dependency, using a dial Nestor already ships.
That is the load-bearing correction: the gate's exact-match blindness is mostly a
**dial it owns**, not a capability it lacks.

**Two honest edges, so this doesn't overreach in the other direction:**

- **§1.1 still bites below the knee.** At 0.40 and under, wrong-key climbs — the
  genuine-near-duplicate inversion returns. And this corpus is 24 *distinct*
  decisions; on a corpus with genuine near-duplicate decisions the clean window
  shrinks. So it is **calibrate per corpus**, Nestor's actual thesis, not "0.45
  is the answer."
- **Semantic is demoted, not dismissed.** The residual ~25% that score under the
  knee *even for the correct decision* (heavy paraphrase, little character
  overlap) are the **tail** a semantic matcher would earn its keep on — consistent
  with §6.11's `fastembed` result. Not the whole problem; the hard quarter of it.

## What it does NOT establish — read before trusting the 100%

The semantic arm is a **Haiku embedder stand-in** (`docs/embedder-stand-in.md`);
`fastembed`/`ollama` are egress-blocked here. Its 100% recall / 0 wrong-key is an
**optimistic upper bound**, for two reasons the bench does not hide:

1. **Author = scorer.** The same model family wrote the paraphrases and scored
   them. §3.4 stage 2 measured exactly this: *"against another agent it is
   rewarded for agreeing with itself."* A language model trivially recognizes
   its own paraphrase family, so recall is inflated.
2. **Recognition, not graded similarity.** The stand-in returned the correct
   decision at 0.95–1.0 and almost everything else at 0.0 — it *identified* the
   source rather than producing an embedding distribution. A real bi-encoder
   gives topical neighbours non-zero scores and can confuse them, so **0
   wrong-key is the least trustworthy number here**, and wrong-key is the one
   that decides whether fuzzy retrieval is *safe*. (Per §6.99 the stand-in also
   drifts 0.15–0.30 between instantiations; correct scored 0.95 in one batch and
   1.00 in three.)

## Decision this supports

- **The cheap fix is the right first fix: rank + a calibrated bar.** Point
  `constraints_on` at a fuzzy matcher and calibrate the bar for the decision
  corpus (`nestor calibrate`), and re-worded recall goes from 0% to ~60–75% with
  no false constraints on a corpus of distinct decisions — no dependency, today.
  This is a genuine improvement over exact-match and it was in the box the whole
  time. `nestor decision check`'s caveat should say *"calibrate the bar,"* not
  *"wait for semantic."*
- **A real semantic embedder is the tail fix, not the whole fix** — for the
  ~25% with too little character overlap to clear any safe character bar. Still
  worth doing, still gated on a real-embedder wrong-key number (the stand-in's
  100%/0 is an optimistic upper bound: author=scorer, recognition not graded
  similarity), and now correctly scoped to the residual rather than the problem.
- **Whatever the matcher, calibrate per corpus.** The clean window is a property
  of *these* decisions being distinct; near-duplicate decisions close it (§1.1).
  There is no one bar; there is the dial and the measurement — which is the whole
  Nestor argument, and the reason the sweep, not a single number, is the result.
