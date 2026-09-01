# Nestor

**Meaning infrastructure. *In medio, fides* — in the middle, trust.**

[![Tests](https://github.com/Die-Namic-Systems/Nestor/actions/workflows/tests.yml/badge.svg)](https://github.com/Die-Namic-Systems/Nestor/actions/workflows/tests.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)
[![Dependencies](https://img.shields.io/badge/runtime%20deps-none-lightgrey)](pyproject.toml)

Nestor answers one question about a machine-generated answer: **has a human
checked this?**

Not as a confidence score — as a structural fact you can audit. Every answer
Nestor serves is in exactly one of three states, and the state is never a guess:

| | State | What it means |
|---|-------|---------------|
| ✓ | **sealed** | A human verified this, and the seal still verifies. Served verbatim, instantly, forever. |
| ~ | **draft** | A machine produced it. Queued for review, never served as verified. |
| ! | **pending** | Nothing to offer. Said plainly rather than improvised. |

Read the first row precisely: *and the seal still verifies*. A row that merely
**says** `sealed` in the database is not served — a seal is bound to a key the
store does not hold, and one that does not verify is surfaced to a curator
instead of answering anyone ([seal signatures](docs/manual.md#seal-signatures),
[the curator](docs/manual.md#the-curator--seeing-what-was-verified)). A human
seals an answer once and can **reject** one just as durably, so a wrong match
is never served again. Both decisions are signed, both are appended to a hash-chained ledger.

In concrete terms it is a zero-dependency Python library, a `nestor` command
line, and a stdlib browser UI, all over one SQLite-backed store —
[Quick start](#quick-start) has the whole loop, machine draft to human seal to
served answer, in five commands.

**This page** — [The mechanic](#the-mechanic) ·
[The category](#the-category--verification-not-translation-memory) ·
[Install](#install) · [Quick start](#quick-start) ·
[Project layout](#project-layout) · [Going further](#going-further) ·
[Development](#development)

Frequently asked, honestly answered — including the "not yet"s:
[**QUESTIONS.md**](QUESTIONS.md). The story behind the name — the nest, Homer,
and Asimov's forged-seal-in-1947 — is [`docs/the-name.md`](docs/the-name.md).

---

## The mechanic

One loop, and it knows nothing about language:

> **normalize an input → fuzzy-match it against a memory of _sealed_ (verified)
> pairs → serve the match above a threshold, else queue it for a human seal →
> append every step to a hash-chained ledger.**

That loop is the product. What it compares — sentences, aliases, figures, dates,
column headers — is decided by a `Matcher`, a two-method seam holding the only
domain-specific code in the system. Everything the value depends on is on the
other side of it: what counts as verified, who verified it, what gets served,
what gets queued, and what the audit trail records.

| Recipe | Matcher | "source → target" means | Module |
|--------|---------|--------------------------|--------|
| Translation | `StringMatcher` | phrase → translation | `nestor.memory` + `nestor.cascade` |
| Entity resolution | `StringMatcher` | alias/surface → canonical entity | `nestor.entity` |
| Numeric reconciliation | `NumericMatcher` | figure → labelled baseline | `nestor.reconcile` |
| *yours* | *yours* | *whatever you can normalize and score* | — |

Translation is where Nestor was extracted from, and the examples below use it
most because it needs no setup to read. It is the origin story, not the
boundary — a date matcher and a CSV-header-to-schema mapper have both been built
against the shipped package without modifying it. Nestor has **no upward
dependency on any host**: persistence, the matcher, the draft engine and the
governance forwarder are all injected.

---

## The category — verification, not translation memory

Translation memory is where Nestor was extracted from. It is not what Nestor is
for, and reading it as a TM gets the economics backwards. A translation memory
is a cache: its value is the work it skips. Nestor's three states are not a cache
tier — they answer a different question, one being put to anyone shipping model
output into a regulated process:

> **Which model outputs did a human actually check?**

**Each verification is permanent capital.** The curve runs the opposite way to
inference: cost per answer *falls* as the proportion of verified answers rises,
and it never un-falls, because a seal does not expire and costs nothing to serve
again. Spending review time buys down a recurring cost rather than renting a
result. Verified once, served forever.

**Where it wins:** high-value, low-volume decisions where somebody is already
reading the output — contract clauses, clinical notes, regulatory filings,
anything with a named reviewer and a retention requirement. The review was
happening anyway; Nestor is the difference between it happening and it being
provable. **Where it loses, stated plainly:** high-volume serving. Lookup is
linear in corpus size and about 97% of that time is Python-side scoring, so this
is not a chat backend — see [Accuracy](docs/manual.md#accuracy-and-how-to-measure-yours). The
design target is decisions worth a person's attention, not throughput.

---

## Install

Python 3.10+, no runtime dependencies. The published package is
**`nestor-meaning`** (the shorter `nestor` is unclaimed on PyPI; `import nestor`
is unaffected either way). The blessed one-liner is
[`pipx`](https://pypa.github.io/pipx/), which isolates the `nestor` console
script in its own environment:

```bash
pipx install nestor-meaning          # or: pip install nestor-meaning
```

From a checkout instead of the index, same tool: `pipx install .` (or
`pip install .`). All four paths were run clean into empty environments before
this was written; the transcripts, and the `nestor init` → `nestor demo` →
`nestor ui` first run, are in [docs/install.md](docs/install.md). What this does
*not* solve: no Homebrew tap, no `curl | sh` — `pipx`/`pip` is the whole install
story for now.

Optional extras add capability without moving the core:

```bash
pip install "nestor-meaning[keys]"      # ed25519 per-verifier signing
pip install "nestor-meaning[cloud]"     # the Anthropic draft engine
pip install "nestor-meaning[semantic]"  # embedding matcher (fastembed)
pip install "nestor-meaning[browser]"   # Playwright browser lane (see docs/local-fleet.md)
pip install "nestor-meaning[gate]"      # the willow-gate seam
```

---

## Quick start

The core loop fits in one script. Save this as `demo.py` and run it, in the
translation recipe:

```python
from nestor import cascade, memory, storage
from nestor.sqlite_store import SqliteStore

storage.set_store(SqliteStore(":memory:"))

# 1. Nothing is known yet. Nestor says so rather than improvising.
p = cascade.translate_segment("Good evening.", "en", "es")
print(p.mark, p.state, repr(p.target))

# 2. A human verifies it — once.
memory.add_pair("Good evening.", "Buenas noches.", "en", "es",
                status="sealed", verifier="rudi")

# 3. Forever after, including when it is retyped differently.
p = cascade.translate_segment("good evening", "en", "es")
print(p.mark, p.state, repr(p.target), p.confidence, p.meta["verifier"])
```

```
! pending ''
✓ sealed 'Buenas noches.' 1.0 rudi
```

One human verification, and the answer is free, instant and attributed from then
on — both steps recorded in a tamper-evident ledger. That ledger is a file even
when the store is not: the run appends to `./data/ledger.jsonl`. (The run also
prints a `RuntimeWarning` about `NESTOR_SEAL_KEY` — Nestor telling you seals are
trusted on stored status alone; see [Seal signatures](docs/manual.md#seal-signatures) before
using it for anything real.)

**The product is three separate surfaces over one store** — a machine drafts, a
**human** seals, a model or a terminal serves — and the seal is a person sitting
down, not a function call. Here is that loop across all three, file-backed:

```bash
# 1. A machine draft enters the review queue (tier 2). Nobody has checked it yet.
python - <<'EOF'
from nestor import cascade, storage
from nestor.sqlite_store import SqliteStore
storage.set_store(SqliteStore("data/nestor.db"))   # the CLI's default store
cascade.translate_text("Good evening.", "es", source_lang="en")   # drafts, queues
EOF

nestor ask "Good evening."                 # 2. ! pending — a draft is not verified
python -m nestor.ui --db data/nestor.db    # 3. a human seals it under their own name
nestor ask "Good evening."                 # 4. ✓ sealed  Buenas noches.  (verified by you)
nestor ledger verify                       # 5. ✓ intact
```

Step 3 is the point, not an inconvenience. There is no `nestor seal` subcommand
and no way to seal from a script, because `--verifier "$USER"` in a cron job is
not a human checking anything. A model can draft (`nestor serve`), the terminal
can serve, but only a person at `nestor.ui` turns a draft into a sealed answer.

**The whole argument in sixty seconds**, against a scratch store it deletes
afterwards — eight beats, each asserting its own claim (the script exits non-zero
rather than narrate something that did not happen, and a test runs it):

```bash
python demo/sixty_seconds.py            # --fast to skip the pauses
python demo/record_demo.py              # capture it as an asciicast under demo/recordings/
```

From source, for development:

```bash
git clone https://github.com/Die-Namic-Systems/Nestor.git && cd Nestor
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"                 # + pytest, ruff, bandit
bash scripts/ci-test.sh core            # fast, deterministic, no live services
```

The bundled `SqliteStore` owns every table Nestor needs, so the whole cascade
runs end-to-end with no host application. It uses **WAL** mode, so a plain `cp`
of `nestor.db` is not a backup of a running server — use `nestor export`, SQLite
`VACUUM INTO`, or stop `nestor.ui` (which checkpoints on exit).

---

## Project layout

```
nestor/       the package — cascade, memory, matchers, curator, ui, cli, serve, ledger, signing
bench/        measuring where the seal threshold stops holding (bench/README.md)
demo/         scripted, self-asserting demos — a claim that fails the build when it stops being true
recipes/      the seam's "yours" row, built against the shipped package
tests/        no outbound network (one test binds a loopback socket), no fixtures on disk
docs/         design memos, operating rules, and the moved-out reference material
AGENTS.md · IDEAS.md · TODO.md · QUESTIONS.md · CHANGELOG.md
```

The full annotated manifest — every module, bench, demo and doc with a line on
what each is for — is [`docs/project-layout.md`](docs/project-layout.md).

---

## Going further

The front door stops here. Everything past it — each surface in detail, the
three shipped recipes, and the parts of the mechanic that only matter once you
are building on it — is [**the manual**](docs/manual.md).

| If you want to | Read |
|---|---|
| Write a matcher for your own domain | [The Matcher seam](docs/manual.md#the-matcher-seam) → [in depth](docs/matcher-seam.md) |
| See translation, entity resolution and reconciliation worked through | [The recipes](docs/manual.md#the-recipes) |
| Understand what a reviewer's "no" does | [Rejection](docs/manual.md#rejection--the-reviewers-no) · [The curator](docs/manual.md#the-curator--seeing-what-was-verified) |
| Sit a human in front of the queue | [The UI](docs/manual.md#the-ui--where-the-human-sits) |
| Drive it from a terminal | [The CLI](docs/manual.md#the-cli) |
| Move a memory between instances | [Export and import](docs/manual.md#export-and-import--taking-the-memory-elsewhere) |
| Let a model read it — and know what it cannot do | [Serving a model](docs/manual.md#serving-a-model--and-the-one-thing-it-cannot-do) |
| Audit what was verified, and by whom | [The ledger](docs/manual.md#the-ledger) |
| Put it over Postgres or your own schema | [Injected storage](docs/manual.md#injected-storage) → [the protocol](docs/storage-protocol.md) |
| Measure the accuracy of your own corpus | [Accuracy](docs/manual.md#accuracy-and-how-to-measure-yours) → [why the numbers are published](docs/accuracy.md) |
| Deploy it where the network is the problem | [Sovereign deployment](docs/sovereign-deployment.md) · [Policy brief](docs/policy-brief.md) |

Frequently asked and honestly answered, including the "not yet"s and the two
"never"s: [**QUESTIONS.md**](QUESTIONS.md).

**And how it was built.** This repository carries more history than product —
a decision store, benches, audits, and a working log. It is deliberately kept,
and deliberately kept separate: [`docs/build-record.md`](docs/build-record.md)
is the index. Nothing in it is needed to use Nestor.

---

## Development

```bash
pip install -e ".[dev]"
bash scripts/ci-test.sh core       # fast iteration: trust/core tests
bash scripts/ci-test.sh full       # pre-push suite; run in background
ruff check nestor tests            # enforced in CI
bandit -r nestor -ll -q            # enforced in CI
python bench/bench_accuracy.py     # measurements -> bench/results/
```

Optional integrations never activate merely because their dependency or daemon
is present. Run them deliberately with `scripts/ci-test.sh semantic`, `ollama`,
`browser`, or `external`; scale/corpus checks are the `slow` lane. Install
`pip install -e ".[browser]"` before the browser lane (Playwright must match
the Chromium build on disk — see `docs/local-fleet.md`). The `semantic`, `ollama`,
and `external` lanes set their opt-in environment flags themselves. Serial wall-clock assertions live in `performance`, because xdist
or coverage contention makes those numbers meaningless.

**Returning to an existing clone:** the install persists, the activation does
not — run `source .venv/bin/activate` in each new shell. The failure mode is
quiet if you forget: the package imports from the repo root without any install,
so snippets keep working while `nestor` and `pytest` are missing or stale. If
commands are half-working, check `which python` first. (Sessions on Claude Code
on the web skip this — a `SessionStart` hook builds `.venv` and puts it on `PATH`.)

**One test goes red after you edit or commit, and passes on a re-run:**
`test_version.py::test_version_agrees_with_the_installed_distribution`. The
version comes from `git describe --dirty` via hatch-vcs, and an editable
install regenerates its metadata during the run when that output changes — so
the first run after any commit *or* any edit to a tracked file compares a value
captured at import against the regenerated one. Run it again without touching
anything, or `pip install -e ".[dev]"`, and it goes green. CI never sees it:
one install, nothing changing mid-run.

CI runs lint and the test matrix (Python 3.10 and 3.12) on every pull request,
plus a daily scheduled run to catch drift. Ideas, open questions and measured
dead ends live in [`IDEAS.md`](IDEAS.md) — each entry tagged
**measured / verified / hypothesis / open**.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
