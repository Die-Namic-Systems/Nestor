# bench — measuring where Nestor bends

Nestor's correctness claim is structural: a tier-1 answer is *verified*, served
verbatim with no review queue. This directory exists to put numbers on when that
claim stops holding, and to keep those numbers as files rather than as something
someone remembers.

Every bench writes a JSON blob to `bench/results/<name>.json` containing its
parameters, the machine it ran on, the git revision, and its raw measurements.
Runs append, newest last, so a result can be compared against the same bench run
months earlier.

## Running

```bash
pip install -e ".[dev]"
python bench/bench_accuracy.py                  # defaults; a few minutes
python bench/bench_accuracy.py --probes 400 --sizes 500 2000 8000 24000
```

Nothing here touches `data/` — the ledger is redirected to a temp file and every
store is `:memory:` unless a bench says otherwise.

## What each bench asks

| Bench | Question |
|-------|----------|
| `bench_accuracy.py` | As the sealed memory fills, how often is an *unverified* phrase served as verified — and what does that cost in recall? |

## Corpora

Accuracy depends almost entirely on how much the sealed phrases resemble each
other, so `corpora.py` provides both ends of that spectrum:

- **`boilerplate`** — templated contract language from a small word pool. Near
  worst case for a character-ratio matcher: every phrase shares most of its
  characters with every other one.
- **`prose`** — real English sentences harvested from Python standard-library
  docstrings. No network, no vendored fixtures, genuinely varied vocabulary and
  length.

Both are seeded and reproducible.

## Method notes (read before trusting a number)

**Held-out probes must be exchangeable with sealed ones.** The first version of
`bench_accuracy.py` drew its absent probes from a disjoint id range, which made
their section numbers longer than the sealed set's. `difflib` could then separate
them on length alone and the false-seal rate collapsed to 0% — for a reason
having nothing to do with Nestor. The bench now draws a single pool and
shuffle-splits it. If you add a corpus, preserve that property.

**The threshold is swept, not assumed.** False seals and recall trade off
against `SEAL_THRESHOLD`. Reporting one cutoff hides the trade, so every run
evaluates the full sweep from a single scan per probe.

**The shortcut is verified, not trusted.** Sweeping cheaply requires computing
each probe's best match directly rather than calling `memory.best_sealed` once
per threshold. `--verify N` re-runs N probes through the real `best_sealed` path
and records whether the two agree; `fidelity_check` in the results carries that
count. A run whose `agreed_with_best_sealed` is below `checked` is measuring
something other than what Nestor serves.

**Examples travel with rates.** Each result keeps the five worst false seals
*with the sealed phrase they collided with*. A probe that near-duplicates
something already sealed is a different finding from one that resembles nothing
in the corpus, and a bare percentage cannot tell you which you have.
