# bench — measuring where Nestor bends

Nestor's correctness claim is structural: a tier-1 answer is *verified*, served
verbatim with no review queue. This directory exists to put numbers on when that
claim stops holding, and to keep those numbers as files rather than as something
someone remembers.

Every bench writes a JSON blob to `bench/results/<name>.json` containing its
parameters, the machine it ran on, the git revision, and its raw measurements.
Runs accumulate, newest last, so a result can be compared against the same bench
run months earlier.

**Results are checkpointed after every row**, not written once at the end. Each
run carries a stable `run_id` and is rewritten in place as it progresses, with
`"complete": false` until the final row lands. Two reasons, both learned the hard
way: a long run that dies partway — the first full accuracy run was killed by its
own timeout, the second by a corpus-size guard — used to take every finished row
with it; and a bench that writes nothing for half an hour is indistinguishable
from a bench that has hung. Writes go through a temp file and an atomic replace,
so a kill mid-write cannot leave truncated JSON where results used to be.

**Check `complete` before citing a number.** A `false` there means the run was
still going or never finished, and the rows present are a prefix of the plan.

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

**The recall column is weaker than it looks — read this before quoting it.**
`corpora.perturb` re-types a sealed phrase five ways: case, punctuation,
whitespace, a trailing pad, and a single-character typo. Measured against the
boilerplate corpus, **81% of those perturbations normalize to a byte-identical
key**, because `StringMatcher.normalize` erases case, punctuation and whitespace
*before* scoring. They score exactly 1.0 and are recalled at every threshold. The
typo is the only kind that survives normalization, and one changed character in a
70-character phrase still scores ≈0.986.

So a reported "recall 100% at 0.98" means *near-identical inputs are still
matched* — which was never in doubt. It does **not** show what raising the
threshold costs for genuinely varied phrasing: a synonym, a reordered clause, a
different construction. That is exactly where recall would fall, and it is
currently untested. Any "raising the threshold is free" conclusion drawn from
this bench is directional only until the perturbation set includes real
paraphrase.

**Examples travel with rates.** Each result keeps the five worst false seals
*with the sealed phrase they collided with*. A probe that near-duplicates
something already sealed is a different finding from one that resembles nothing
in the corpus, and a bare percentage cannot tell you which you have.

**The fast scan is proved equal, per run.** Scoring every probe against every row
is the bulk of a run's cost, so `best_match_fast` skips candidates whose difflib
upper bound (`real_quick_ratio` / `quick_ratio`) cannot beat the best score so
far — provably the same argmax, less work. `--equiv N` scores N probes *both*
ways and records any disagreement under `fast_path_equivalence`. Two ways to
break it silently, both hit while writing it: `ratio()` is **not symmetric**, so
pinning the row as sequence `b` to reuse difflib's index measures a different
function; and `autojunk` changes results past 200 elements. Either produces a
plausible, slightly wrong benchmark rather than an obvious failure — hence the
per-run check rather than a one-off proof.
