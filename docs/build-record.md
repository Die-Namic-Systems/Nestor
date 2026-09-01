# The build record

Nestor is a small library. This repository is not a small repository, and the
difference is on purpose.

Roughly 10 MB of the 16 MB tracked here is not the product — it is the record of
building it: every decision and why, every measurement and what it refuted, the
audits, the benches, and a working log. None of it is needed to use Nestor.
None of it ships: the wheel contains `nestor/` and nothing else, and the sdist
adds only `tests/` and four root files ([`pyproject.toml`](../pyproject.toml)
names both lists explicitly, for exactly this reason).

So this page exists to draw the line, and then to make the other side of it
navigable. If you are here to use the tool, [`README.md`](../README.md) and
[the manual](manual.md) are the whole of it. If you are here to judge the tool,
this is the evidence.

---

## Why it is kept

A verification tool that could not show its own working would be an argument
against itself. The claim Nestor makes about an answer — *a human checked this,
here is who and when, and here is the chain that proves the record was not
edited afterwards* — is a claim this repository also tries to make about its own
construction.

That is not a claim that the record is complete or that every entry is right.
It is a claim that the entries exist, are dated, and can be read against the
code. Several of them record being wrong.

## What is in it

| | Size | What it is |
|---|---|---|
| [`../IDEAS.md`](../IDEAS.md) | 172 K, 2,453 lines | The argument log. Every entry is tagged **measured / verified / hypothesis / open / shipped**, and the tags are load-bearing: §7 is the list of shipped standard parts, §6 is the running log of what was tried. |
| [`dogfood/`](dogfood/) | 2.3 M | Nestor's memory of its own development — 79 decision files folded into a store of 229 sealed pairs, each seal a reviewable JSON file. Rebuilt by `python scripts/dogfood_store.py --rebuild`; verified by `bash scripts/ci-docs.sh`. |
| [`agent-log.md`](agent-log.md) | 436 K, 7,762 lines | The session-by-session working log. Long, unedited, and the only place some dead ends are written down. |
| [`archive/`](archive/) | 1.5 M, 111 files | Retired decisions, and five dated `FINDINGS-*.md` reviews. |
| [`../audits/`](../audits/) | 1.0 M, 40 files | The 2026-08-19 capability probe — a simulated deployment run against the tool, including the parts it failed. |
| [`../bench/`](../bench/) | 37 files, 1.2 M of results | Where the seal threshold stops holding. Accuracy, margin, and surface benches, with their recorded numbers. See [`bench/README.md`](../bench/README.md). |
| [`accuracy.md`](accuracy.md) | — | Why those numbers are published rather than summarised. |
| [`../scripts/corpus/`](../scripts/corpus/) | 22 extractors | The corpus pipeline that read 35 prior repositories to find what had already been built before building it again. |
| [`progress-catalog/`](progress-catalog/) | 19 files | A consolidated inventory across trees, with a shareable [snapshot](progress-catalog/PROGRESS-SNAPSHOT.md). |
| [`../hooks/`](../hooks/) | 18 files | The seat rules, enforced. The gates an agent working in this tree passes through — including the one that refuses to let it seal anything. |
| [`journal/`](journal/) | 4 files | Notes that are neither decisions nor measurements. |

## Where to start, by what you are asking

**"Is any of this measured, or is it all assertion?"** —
[`accuracy.md`](accuracy.md), then `bench/results/`. The headline trade is that
a string matcher cannot be both safe and useful at one threshold, which is why
the policy has three bars rather than a score:
[`progress-catalog/THRESHOLD-POLICY.md`](progress-catalog/THRESHOLD-POLICY.md).

**"What did it get wrong?"** — the five `FINDINGS-*.md` files in
[`archive/findings/`](archive/findings/), and
[`code-review-lessons.md`](code-review-lessons.md), which collects the pre-PR
checklist that came out of the PR #22–#24 review rounds. `TODO.md`'s closing
section names the defect shape that four separate bugs shared.

**"Why is it built this way and not the obvious way?"** — `IDEAS.md` §6, and
the decision files under [`dogfood/decisions/`](dogfood/decisions/). Decision
`0202` is a good short example: a narrow fix, a wider alternative named and
explicitly deferred, and a test that locks the limitation so the next person to
widen it has to move a decision first.

**"What does it refuse to do?"** — [`../QUESTIONS.md`](../QUESTIONS.md) §4 and
§10, and [`../hooks/seat.md`](../hooks/seat.md).

## What this record does not establish

- **That the numbers generalise.** They were measured on the corpora in
  `bench/`, and `nestor calibrate` exists because the right threshold is a
  per-corpus question, not a constant.
- **That the decisions were reviewed by anyone but their author.** Most were
  not. A sealed pair in the dogfood store means a human signed it in
  `nestor ui`; it does not mean a second human disagreed and lost.
- **That the record is current.** A sealed pair is true as of its seal.
  [`seal-staleness-and-quorum.md`](seal-staleness-and-quorum.md) is the open
  question about what to do when it stops being. At least one pair in the store
  is a measurement that a later release fixed, still reading as present tense.

---

Nothing on this page is a dependency, a build step, or a thing to maintain in
order to run Nestor. It is here to be read once, by whoever wants to know what
the code cost.
