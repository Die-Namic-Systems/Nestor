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

**Character and token matching cannot fix the gate.** They rank the right
decision first almost always (88%, 96%) but score it *far below* 0.92 — at the
shipped bar they catch **nothing** (0% recall). Switching `constraints_on` to a
fuzzy `StringMatcher`/`TokenOverlap` would buy the gate zero re-worded recall.
This is §3.4 / §6.106 reproduced on the decision corpus: **rank, not serve.** The
exact-match caveat now printed by `nestor decision check` is correct and not
removable by a character/token swap.

**Semantic matching is the only lever that lifts recall over the bar** — and a
second, independent measurement agrees: §6.11 benched `fastembed` in the SAFE
store's playground at 0.90–0.95 with `wrong_key` 0. Two roads to the same place.

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

- **Keep `constraints_on` exact-match for now.** It is the conservative choice —
  zero false constraints — and the bench shows the only alternative that helps
  (semantic) cannot have its *cost* (wrong-key) credibly measured by this
  stand-in. `nestor decision check`'s exit-0 caveat stands.
- **Adopting a semantic matcher for `constraints_on` is justified in principle**
  (this bench and §6.11 both point at it) **but gated on a real-embedder
  wrong-key measurement** — the next bite is to run this same bench with an
  actual `fastembed`/`ollama` backend (in an environment that can reach it) and,
  ideally, a paraphrase author independent of the scorer, to get an honest
  wrong-key number rather than an optimistic one.
