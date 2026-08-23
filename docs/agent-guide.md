# Agent operating guide (Nestor)

Participant-neutral rules for **any** agent session (Cursor, Claude Code, Codex,
cloud). Cold-start steps live in [`AGENTS.md`](../AGENTS.md); hooks inject a
short copy of [`hooks/seat.md`](../hooks/seat.md) at session start.

Engineering lessons also live in [`code-review-lessons.md`](code-review-lessons.md)
(11 of them, plus a pre-PR checklist), [`../TODO.md`](../TODO.md)'s closing note,
and [`../IDEAS.md`](../IDEAS.md) §6. Those are addressed to a reviewer. This is
the part addressed to you, and it exists because on 2026-08-05 an agent read
none of them until after making the mistakes two of them describe.

Which is also the reason it is worth saying plainly that **this file is not
auto-loaded.** `CLAUDE.md` is, and it forwards here; every other CLI reaches
this through `AGENTS.md`. So the guarantee that you are reading this is one
pointer weaker than it used to be, and the incident in the paragraph above is
what that costs when it fails. Read to the end.

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
  your first prompt. You do not have to check it by hand: the boot context
  carries a `[check] pytest:` line and a `[check] lint:` line, and the lint
  line names any module `scripts/ci-lint.sh` needs and cannot import. Read
  them. `python -m pytest --version` alone is *not* the check — it passes on
  a venv whose secret-scan gate is missing, which is how a broken pre-push
  command survived a boot that looked green.
  The boot also carries a `[nestor]` line saying whether a Nestor is stood
  up. When it is not, that line is an **instruction to ask the user** whether
  to stand one up — put the question, do not answer it by running the
  command. Ask early: `nestor stats` on a tree with no store creates
  `data/nestor.db` and prints `0 pair(s)`, so the first command you type makes
  an absent Nestor indistinguishable from an empty one.
  If either line is red, run the hook yourself — do **not** `pip install` into
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

- `[dev]` carries pytest and every gate `scripts/ci-lint.sh` runs — ruff,
  bandit, mypy and detect-secrets; `[keys]` carries cryptography so
  the asymmetric suite runs instead of skipping. Do **not** add `[semantic]`
  unless the task needs it — see "Before you finish".

- **`ci-lint.sh` refuses to run against tool versions CI does not use.** The
  pins live in `scripts/lint-pins.txt`, which the workflow installs from; if
  your environment differs the gate stops and names the tool and the fix:

  ```bash
  pip install -r scripts/lint-pins.txt
  ```

  This is not fussiness. A ruff one minor ahead of the pin reported 530
  pre-existing findings on a tree CI called clean (agent-log §6.114) — a gate
  that answers under a different version has not answered about your push, and
  a gate that cries wolf 530 times is one nobody reads on the run that matters.

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

### Not a signature is not the same as not a decision

The sentence above is about **evidence**, and it keeps being read as though it
were about **authority**. Those come apart, and the difference matters in
exactly one direction.

When the operator tells you to do something, that is an instruction and it
carries its full weight. They own the repository. Reading their intent
correctly is the job, not a liberty you are taking, and *"commit the work"*
said once covers the commits that follow it without needing to be re-said.
A decision made in conversation is **a real decision, made deliberately, the
moment it is made**.

What conversation cannot do is **bind**. Nothing ties those words to a key, so
nobody reading the row in two years — a regulator, a colleague, the operator
having forgotten — can check that the person whose name is on it is the person
who decided. That is the entire objection, and it is a claim about what
survives the conversation rather than about what happened in it. The queue and
the keyring exist to close that gap, not to doubt anybody.

**Why this is worth a heading.** Conflating the two is safe in one direction
and expensive in the other. An agent that reads *"chat is not a signature"* as
*"the operator's instructions are unverified"* starts treating ordinary
direction as a governance problem: narrating its own authorisation, auditing
consent it already has, and being precious about a rule aimed at the store
rather than at the person. That happened on 2026-08-06, in a session with this
file open, and the operator had to point it out — *"a choice made in chat does
carry weight. I made those choices, deliberately."* They were right. The rule
was never about them.

Both halves, so neither can be quoted alone:

| | |
|---|---|
| chat **is** authority | do what you were asked, and read it like a colleague would |
| chat **is not** evidence | it cannot be bound to a key, so it cannot seal a row |

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

### Reviewing the queue — the command, and why it is not the obvious one

`--verify` failing on a sealed row means you cannot seal **in** the committed
store. Take a copy and point the browser at that:

```bash
python -c "import sqlite3; sqlite3.connect('docs/dogfood/nestor.db').execute(\"VACUUM INTO 'review.db'\")"
nestor ui --db review.db --verifier <you>          # 127.0.0.1:8765
```

`VACUUM INTO` rather than `cp`: a plain copy of a live WAL store takes a stale
file. `review.db*` is gitignored, which covers the ledger `nestor` writes
beside it and SQLite's own `-wal`/`-shm` companions.

**Know what this does and does not do.** The seals live in `review.db` and
nowhere else. The next `--rebuild` regenerates an all-draft store that knows
nothing about them, because the builder reads the decision files and nothing
else — deliberately, and it is the rule that makes the store trustworthy. So
the project's decision memory currently cannot record that a human agreed with
it. That is written up as [agent-log §6.123](agent-log.md) with three proposed
shapes and none built; until one is, sealing here is for your own reading.

An agent may not seal in that copy either. Nothing about a local database
changes the one rule.

## Tooling you built to answer a question ships with the answer

**If you wrote a script, a harness or a fixture to reach a finding, it goes in
the PR that carries the finding.** Not tidied away, not left in `/tmp`, not
described in a commit message as *"measured locally"*.

The container dies. A measurement whose apparatus died with it is a number
nobody can reproduce, and `IDEAS.md` is already carrying entries that had to be
re-earned because their scratch directory was gone by the next session — see
§6.37–§6.39 and the fixture that had to be written to make them executable
again.

The bar is not *"is this reusable?"* — you are the worst judge of that, and the
honest record of `scripts/two_instances.py` is **written once, used once, found
§6.36 on the way**. The bar is:

> would somebody have to rebuild this to check my claim, or to answer the same
> question again?

If yes, commit it. Three things follow:

- **It gets a test**, even if nothing consumes it yet — otherwise it is
  scaffolding with nothing holding it to its claims. `tests/test_desks.py`
  exists for a module whose first real consumer arrived two commits later.
- **It gets its limits in the docstring**, especially the ones that bit you.
  `demo/desks.py` says one process holds one matcher because a fixture built on
  it silently wrote two desks into one chain and then counted the total as one
  desk's.
- **It says what its record is.** Used once is a fine record. Claiming more
  than that is the thing to avoid.

Prefer `demo/` for anything a reader is meant to run and watch, `scripts/` for
what an operator runs, `hooks/` for what fires without being asked. A reusable
piece extracted from a fixture goes in **persona-free** — the story belongs to
the fixture that earned it, and machinery carrying somebody's grandmother around
is machinery nobody reuses.


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
  nestor -ll -q` + `mypy nestor`) — same gate as GitHub Actions. Do **not** add
  unused imports in tests (`pytest`, `os`, `Path`, …); ruff **F401** fails CI
  and cloud will not see your fix until it is **pushed to the PR branch** and
  the job re-runs. Mypy is scoped to `nestor` only, at a pragmatic baseline —
  see `[tool.mypy]` in `pyproject.toml` and IDEAS §7.5 for exactly what that
  does and does not cover.
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
