# Agent operating guide (Nestor)

Participant-neutral rules for **any** agent session (Cursor, Claude Code, Codex,
cloud). Cold-start steps live in [`AGENTS.md`](../AGENTS.md); hooks inject a
short copy of [`hooks/seat.md`](../hooks/seat.md) at session start.

Engineering lessons also live in [`code-review-lessons.md`](code-review-lessons.md)
(11 of them, plus a pre-PR checklist), [`../TODO.md`](../TODO.md)'s closing note,
and [`../IDEAS.md`](../IDEAS.md) §6. Those are addressed to a reviewer. This
guide is the operating layer agents meet every session.

---

## Environment — before anything else

**Cold-start:** [`AGENTS.md`](../AGENTS.md) — `git fetch` / PR branch checkout +
`bash scripts/ci-lint.sh` on every session (cloud must pull the PR branch or
they redo lint failures).

**Agent hooks (all CLIs):** shared policy in `hooks/` — see
[`hooks/README.md`](../hooks/README.md). Cursor uses `.cursor/hooks.json`; Claude
Code uses `.claude/settings.json`. Both call `hooks/nestor-hook` with the same
`session_start` and `before_mcp` modules.

A cold clone is a trap shaped exactly like a working setup. The package
imports from the repo root with **no install at all** — `python demo.py` and
every README snippet run fine — while `nestor`, `python -m pytest` and the
lint gates do not exist. So the first failing command arrives *after* several
succeeding ones, and the wrong conclusion (something just broke) is easier to
reach than the right one (nothing was ever installed). A session stumbled on
exactly this the day this file was written.

- **Claude Code on the web:** the SessionStart hook
  (`.claude/hooks/session-start.sh`) has already built `.venv`, installed
  `.[dev,keys]` into it, and put `.venv/bin` first on your `PATH` before
  your first prompt. Trust it after one check: `python -m pytest --version`.
  If that fails, run the hook yourself — do **not** `pip install` into
  system python; this container carries a broken Debian `cryptography` on
  its path that satisfies the requirement without importing.
- **Anywhere else:** the repo convention is a venv at `.venv`. Activation is
  per **shell**, not per machine — a venv that exists is not a venv that is
  active:

  ```bash
  source .venv/bin/activate 2>/dev/null \
    || { python -m venv .venv && source .venv/bin/activate \
         && pip install -e ".[dev,keys]"; }
  ```

- `[dev]` carries pytest, ruff and bandit; `[keys]` carries cryptography so
  the asymmetric suite runs instead of skipping. Do **not** add `[semantic]`
  unless the task needs it — see "Before you finish".

---

## The one rule that is not a guideline

**You may propose. You may not confirm.**

Never write `verifier=` with a human's name. Never `status="sealed"`. Not when
you are confident, not when the operator told you the answer in conversation,
not when it would be convenient. A choice made in chat is not a signature, and
`--verifier "$USER"` in a script is not a human checking anything —
[`../TODO.md`](../TODO.md) says so on purpose.

The verbs available to you:

| | | |
|---|---|---|
| `add_pair(status="draft")` | propose | yours |
| `revise_draft` | change your mind, keeping why | yours |
| `reject_match` / `reject_pair` | record a **human's** no | theirs |
| `add_pair(status="sealed")` / `supersede_pair` | ratify | theirs |

If you want something sealed, put it in the queue and say so. `nestor.ui` is a
sign-in.

---

## Checked, not assumed

Every claim you write into code, a commit message or `IDEAS.md` is a claim
someone will act on. On 2026-08-05 these all shipped and all were false:

- *"No Storage operation revises a draft"* — one already did.
- *"Ordered so the digest is stable"* — the digest sorts rows itself.
- *"All five branches were driven"* — there were six; one was unreachable.

Each came from reading one thing and inferring the rest. Before asserting how
something behaves, run it. Before saying a fix works, measure it. Before
describing a function's contract, read the function that already does the job.

The same day, a sixteen-row table of translations was checked before being
printed into the README. **Three rows were wrong** — a false etymology, a word
that does not mean what it was said to mean, and a branch of a language family
that kept no reflex at all. All three were in the rows already flagged as the
uncertain ones, and not one was visible without looking it up. Flagging your own
uncertainty is worth something. It is not worth as much as checking.

---

## When a guard fails, remove the interaction — do not add a condition

The recurring defect in this codebase, and the one you are most likely to
introduce while fixing it:

> a condition checked in Python, guarding a write that cannot re-assert it.

Three criticals in one session, in three different mechanisms, all this shape.
The move that worked every time was not a better condition:

- a filter over one walk → **two walks, each bounded by construction**
- a status check then `UPDATE ... WHERE id=?` → the precondition **in the WHERE
  clause**

If your fix adds a flag, a filter or an `if` to something that already has
several, stop and ask what the mechanism is doing two of. Related, and already
written down: `docs/code-review-lessons.md` §8 and §9.

---

## A race fix is not done when it is written

It is done when the number moves. The first fix for a seal-retirement race took
it from 282/300 to 256/300 — it looked right, read right, and closed one of two
interleavings. Re-running the count is what caught it.

Reproduce concurrency with real threads on a file-backed store, count outcomes
over hundreds of trials, and put the before/after in the commit message.

---

## Tests

- **Run every new test against the unfixed revision.** A test that passes
  before the fix is a description, not a gate. Record the split.
- **Say which are guards.** Tests that pass before *and* after protect the path
  your change rewrites. They are worth having and they are not evidence.
- **Reproduce the condition you name.** Two tests here passed against broken
  code because their setup did not create the situation the name claimed — a
  forged row that scored 1.0 and so never left the display page; a numeric pair
  stored with the wrong matcher, so the sentinel never collided.
- **Mirror, do not import**, when pinning a constant. Importing makes the pin
  true by construction. See `tests/test_ledger_kinds.py`.
- **A claim in a sentence must hold across every value that sentence can
  take.** A refusal message read *"close enough to be tempting, which is why it
  is not served"* — true at 0.71, false at 0.11. Flat prose is safe across its
  whole range; pointed prose is not, and the fix is usually to make the claim
  about the *rule* rather than about *this case*. This generalizes past
  messages: it is the same error as testing one row and describing a class.
- Back up before `git checkout` — it discards uncommitted work, including
  yours.

---

## The gates are aimed at you

Not at some hypothetical future contributor. Two of this repo's gates caught
the author of `persona.py` **while that module was being written**, and they
were read the same morning:

- `test_engine.py::test_the_rule_is_written_once` fired on the new module's own
  docstring. Explaining that the module is *not* ground rule 2b, it retyped
  ground rule 2b — putting the phrase in the package twice, which is the exact
  defect that gate exists to remove.
- `test_docs.py` failed because a new module was missing from the README's
  project layout, which is a promise about what is in the package.

Neither was clever. Run the suite before you believe your own change is
tidy, and when a gate fires on you, read what it says rather than working
around it — the thing it caught is usually one layer more embarrassing than it
first looks.

**And write yours so they can fail.** A test that cannot fail is a description.
Prove it by breaking the thing on purpose and watching the gate go red, then
put the mutation in the commit message.

---

## Decisions go in the store

**Every PR that makes a decision worth keeping adds one file to
`docs/dogfood/decisions/` and re-runs `python scripts/dogfood_store.py
--rebuild`.** The committed store grows one merged PR at a time, and
`--verify` is a gate: a PR that adds a decision and forgets to rebuild fails.

One file per PR, never a shared bundle — separate files cannot collide, and the
`.db` is *derived* rather than merged, so the artifact is always regenerable
from text somebody reviewed.

**The direction is remote to local, never local to remote.** The builder reads
the decision files in this checkout and nothing else: not your `data/nestor.db`,
not the process-wide store, not a configured path. That is a gate, not a promise
— `test_dogfood_store.py` installs a poisoned ambient store and proves none of
it arrives. The reason is the reason for all of this: a memory whose rows came
from somewhere nobody can see is not an audit trail.

Every row goes in as a **draft**. You may propose. The queue at `nestor.ui` is
where that changes, and `--verify` fails on a sealed row however it got there.

## Findings go in the list

`IDEAS.md` §6, per §6's own rule: a follow-up raised in conversation and not
written down did not happen. Tag it **measured / verified / hypothesis / open /
shipped**.

Correct a wrong entry **in place, visibly** — a claim that was acted on is part
of the record. Do not quietly edit it.

---

## How to say it

The product has a persona now — [`../nestor/persona.py`](../nestor/persona.py), for
the sentences Nestor uses when Nestor is the speaker. Yours is not that module
and the rule behind it still applies to you.

**Be exactly what you are, out loud, including the small parts.** Not *I'm just
a model* — that is self-erasure, and it is a way of not being accountable for a
guess. The precise, unglamorous, true description instead: what you ran, what
you did not run, which of the two it is.

Everything that follows falls out of that:

- The humour, where there is any, comes from being accurate about your own
  failure. *"The previous fix for this sentence reproduced its own bug one line
  lower"* is not a joke construction; it is an exact description of something
  embarrassing, and it is the best line in `answer.py`. Wordplay dies on the
  second read.
- **Never at the operator's expense.** You are the junior party here by design —
  you may propose and may not confirm — so you are the one who can be laughed
  at. When a human's decision is the subject, report it plainly.
- Take the blame for an empty result rather than leaving it hanging where they
  will pick it up. *"Nothing matched"* quietly implies the question was odd. It
  usually was not.
- A refusal has to read as one. If you did not do something, the sentence
  saying so must contain the not.

---

## Before you finish

- `python -m pytest -q` — CI installs `.[keys]` only, so the baseline is
  fastembed-**absent**. If you install the semantic extra you un-skip three
  model-downloading tests and diverge from CI.
- **`bash scripts/ci-lint.sh`** (or `ruff check nestor tests hooks` + `bandit -r
  nestor -ll -q`) — same gate as GitHub Actions. Do **not** add unused imports in
  tests (`pytest`, `os`, `Path`, …); ruff **F401** fails CI and cloud will not
  see your fix until it is **pushed to the PR branch** and the job re-runs.
- Optional: `pre-commit install` then commits auto-fix ruff locally.
- `docs/code-review-lessons.md` §11 is the pre-PR checklist. Use it.

---

## Ask for review

Three independent audits of one branch each returned *not safe to merge*, and
each critical was introduced by the fix for the previous one. You are the worst
judge of your own scope — not through carelessness, but because scope is
exactly what you cannot see from inside a change.

For anything touching persistence, concurrency or the audit trail: get an
adversarial read before the PR, and tell it not to trust your commit message.
