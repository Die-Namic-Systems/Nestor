# What is left

The queue, in priority order. Longer arguments live in
[`IDEAS.md`](IDEAS.md) (each entry tagged **measured / verified / hypothesis /
open / shipped**) and [`QUESTIONS.md`](QUESTIONS.md) (what this gets asked, and
the honest "not yet"s). This file is only the index — if an item here disagrees
with one of those, they are right and this is stale.

---

## Shipped (kept for the "why not" records)

* ~~**Asymmetric seal signatures.**~~ Shipped: `nestor.keyring`, `[keys]` extra,
  decisions `0074`/`0077`/`0078`. `QUESTIONS.md` §6; `IDEAS.md` §2.
* ~~**Three deferred audit findings.**~~ Shipped: decisions `0073`/`0076`,
  `test_findings_2026_08_07_deferred.py`. `IDEAS.md` §6.92.
* ~~**Hot backup while WAL is open.**~~ Shipped: `nestor db checkpoint --out`.
  `IDEAS.md` §6.7; `docs/local-fleet.md`.
* ~~**UI domain matcher.**~~ Shipped: `ui.App(matcher=)`, `nestor ui --matcher`.
  `IDEAS.md` §6.40–§6.41.
* **A terminal `nestor seal`** is deliberately absent — `--verifier "$USER"` in a
  cron job is not a human checking anything. `IDEAS.md` §5.1.

## Open

* **Sync between instances.** `QUESTIONS.md` §8.
* **An erasure path.** `QUESTIONS.md` §10.
* **Semantic matching.** `IDEAS.md` §3.3 (and §3.4 for the measurement).
* **A store that takes concurrent writers.** `QUESTIONS.md` §15.
* **A checkpoint somebody else holds.** `IDEAS.md` §5.5.
* **Seal staleness and quorum.** `IDEAS.md` §1.4.
* **Record the sixty seconds.** `IDEAS.md` §4.3.

---

## A note on how this repo finds things

Four of the six defects fixed on 2026-07-31 were the same shape: **a guarantee
enforced by convention at call sites, and a second path into the store that never
passes it.** Rejection lived in `add_pair` and the import path walked around it.
The seal audit lived in the callers and `add_pair` did not have it. One row per
source was assumed by four modules and enforced by none.

If you add a write path, the question to ask is not "did I remember the guard" —
it is "can this guard be reached around", and then move the rule into the one
place that cannot be bypassed. `IDEAS.md` §1.6, §1.7 and §1.8 are the three
worked examples. [`docs/code-review-lessons.md`](docs/code-review-lessons.md)
collects the pre-PR checklist from the PR #22–#24 review rounds.

The same test retired the held-back bench branch: it carried a second review
surface, weaker than `nestor.ui`, that could seal into the same store. The
dashboard landed and the playground did not. Two paths in, one of them
unguarded, is the defect — it does not stop being one because it is a UI.

And a variant worth naming separately, from the same day's work: **a guarantee
that only holds where somebody thought to look.** `best_sealed` filtered
`lookup()`'s top five, so a verified seal ranked sixth was invisible to tier 1.
Nothing was bypassed and no rule was missed; the code just answered a narrower
question than the one it was asked. That one is only found by asking what the
code does when the easy case does not hold.
