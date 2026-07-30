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
python bench/bench_accuracy.py --probes 250 --verify 15 --equiv 15
python bench/bench_accuracy.py --resume          # continue an interrupted run
```

**Use `--resume`.** The full sweep takes roughly ten minutes and a bench cannot
count on outliving the session that launched it — three attempts at this one were
lost to that before rows were checkpointed and reusable. `--resume` reuses rows
already recorded with the same `--probes`, `--seed` and `--floor`, and recomputes
only what is missing. Different parameters are a different measurement and are
never reused.

`--floor` (default `0.80`, the lowest swept threshold) seeds the scan's incumbent
score so candidates are discarded on their upper bound from the first row. Scores
below it are censored to `0.0` and reported via `scores_censored_below_floor`;
the sweep is unaffected, since it never evaluates a threshold that low. It is
worth ~8.8x on prose. Pass `--floor 0` for exact scores everywhere, much slower.

Nothing here touches `data/` — the ledger is redirected to a temp file and every
store is `:memory:` unless a bench says otherwise.

## What each bench asks

| Bench | Question |
|-------|----------|
| `bench_accuracy.py` | As the sealed memory fills, how often is an *unverified* phrase served as verified — and what does that cost in recall? |
| `bench_margin.py` | Does the gap between the best and second-best candidate separate a true match from a false seal? (Tests `IDEAS.md` §1.1 — answer: mostly no.) |

`bench_margin.py` censors margins wider than `top - floor`, so its reported
percentiles are compressed. The **grid is exact** for every margin it sweeps:
a measured margin is `min(true_margin, top - floor)`, and since the grid only
counts probes with `top >= threshold >= 0.90` while the widest swept margin is
`0.10`, `top - floor >= 0.10` always holds. Censoring can only understate a
margin, which biases against the hypothesis rather than for it.

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

## Reading a results file

`results/<bench>.json` is **append-only and tracked in git**, so it accumulates
every run anyone has made, including the ones that turned out to be wrong. Two
fields decide whether a run is worth reading, and both have to be checked:

**`superseded`** — present when a later fix invalidated the numbers, with the
reason written out. The runs are kept rather than deleted: a discarded run is
still evidence about how the harness moved, and removing it would leave the file
agreeing with itself for the wrong reason. `surfaces_human.json` carries fifteen.

**`environment.code_digest`** — a hash of the source files the bench declares as
determining its numbers. Two runs with the same digest ran the same code.

`environment.git_rev` is **not** provenance, and this file is the proof. Every
one of `surfaces_human.json`'s first 23 runs recorded `111c187`, because the
bench was untracked while it was being edited: HEAD could not move, so a commit
hash could not tell a correct run from one produced by a harness carrying two
known defects. `git_dirty` is recorded for the same reason — a dirty tree makes
the revision a lower bound on what changed, and nothing more.

Runs recorded before the digest existed carry `code_digest: null`. They are not
superseded, but they rest on reproduction rather than on a fingerprint: the
stage-3 figures were reproduced independently on another machine, which is the
only reason they are still quoted.

```bash
python - <<'EOF'
import json
runs = json.load(open("bench/results/surfaces_human.json"))["runs"]
for r in runs:
    if r.get("superseded"):
        continue
    print(r["run_id"], r["params"].get("matcher"),
          r["environment"].get("code_digest"))
EOF
```

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

**Recall is reported in two tiers. Quote the paraphrase one.**
`corpora.perturb(..., tier=)` produces either:

- **`surface`** — case, punctuation, whitespace, a trailing pad, one typo.
  **80% of these normalize to a byte-identical key**, because
  `StringMatcher.normalize` strips case/punctuation/whitespace *before* scoring.
  They score exactly 1.0 and are recalled at every threshold. A "100% recall"
  over this tier means only *near-identical input still matches* — never in
  doubt, and for a long time this bench reported nothing else.
- **`paraphrase`** — meaning-preserving rewrites that survive normalization:
  synonym substitution from a curated table, clause reordering, contraction, and
  a stopword-drop fallback. 0% of boilerplate and 5% of prose paraphrases
  normalize identically.

The gap between them is large and is the point: at the shipped 0.92, boilerplate
24k reports 100% surface recall and **23.6%** paraphrase recall.

Two properties the paraphrase tier must keep if you extend it. Every
transformation has to be genuinely meaning-preserving — a rewrite that changes
meaning is a false-seal probe wearing a recall probe's clothes, and it corrupts
both columns at once, which is why `_SYN_PROSE` is deliberately small. And a
"paraphrase" that returns the input unchanged is an identity probe that inflates
recall while measuring nothing, so strategies are tried in shuffled order until
one actually changes the text, with `_telegraphic` as a guaranteed fallback.
Before that fallback existed, 55% of prose paraphrases were silently identity.

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
