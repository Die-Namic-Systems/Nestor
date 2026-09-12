# Contributing to Nestor

Nestor is licensed under [Apache 2.0](LICENSE). Contributions are welcome — this
document is the single path from clone to merged PR.

## Setup

```bash
git clone https://github.com/Die-Namic-Systems/Nestor.git && cd Nestor
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,keys]"
python -m pytest -q          # no outbound network, should pass clean
```

Python 3.10+ is required. Runtime has zero dependencies; `[dev]` pulls in test
and lint tooling, `[keys]` adds `cryptography` for signed seals.

Optional: `pre-commit install` to run ruff on staged files automatically.

## The gate table

Which verification to run depends on what you changed:

| Changed paths | Gate command |
|---|---|
| `nestor/`, `recipes/`, `tests/`, `scripts/`, `hooks/`, `demo/` | `bash scripts/ci-lint.sh && bash scripts/ci-test.sh full` |
| `docs/`, `IDEAS.md`, `docs/dogfood/decisions/*.json` | `bash scripts/ci-docs.sh` |
| `README.md`, `AGENTS.md`, `CLAUDE.md`, `.github/` | `bash scripts/ci-lint.sh` |
| Mixed | `bash scripts/ci-lint.sh && bash scripts/ci-test.sh full` |

This is the same table `AGENTS.md` carries; the two must not disagree.
`bash scripts/ci-test.sh full` is what CI's `test` job runs (the whole suite,
`-n auto --dist loadgroup`), and `bash scripts/ci-test.sh core` is the fast
deterministic lane for use while implementing. Installing an optional extra
never enlarges either lane — the `semantic`, `ollama`, `browser`, `slow`,
`performance` and `external` lanes are explicit.

CI runs the lint job, a test matrix (Python 3.10 and 3.12 with coverage), and a
JS test job on every PR. The branch-protection check is named `test` — it must
be green to merge.

If `ci-lint.sh` refuses to run, your local tool versions differ from the pins in
`scripts/lint-pins.txt`. Fix with `pip install -r scripts/lint-pins.txt`.

## Commit and PR conventions

**Conventional commits.** PR titles are validated against conventional-commit
prefixes (`feat:`, `fix:`, `docs:`, `ci:`, `refactor:`, `test:`, `chore:`,
etc.). A title claiming a release-cutting type (`feat`, `fix`) must touch
packaged files (`nestor/` or `pyproject.toml`).

**PR template.** The repo has a PR template — fill in every section. The
*Evidence* section asks for receipts: the actual command you ran and its result,
not a claim that tests pass.

**Decisions.** If your PR makes a product decision worth keeping, add a file to
`docs/dogfood/decisions/` and run `python scripts/dogfood_store.py --rebuild`.
Decisions land as **drafts** — only a human seals them in `nestor ui`.

## The Idea-Id commit-trailer convention

A commit that lands an idea recorded in [`docs/ideas.md`](docs/ideas.md) carries
an `Idea-Id: willow-ideas-<num>` git trailer (add `Idea-Status: partial` when a
commit only partly lands it). It is the durable join key willow-reconciler
reads; a wrong id is worse than no id, so never type one by hand:

    reconciler id --repo ./ --doc docs/ideas.md --grep "words from the item"
    reconciler install-hook --repo ./     # derives it from a branch named idea-NN

`.github/workflows/trailers.yml` runs `reconciler verify` on every PR and fails
on a trailer that names an item the doc does not contain. The reconciler is not
one of this repo's pinned dev tools; `pip install "willow-reconciler>=0.6.0"`
in your venv when you need the two commands above (`--repo ./` is a path — a
bare `.` is read as a repo name and will not resolve).

## The one rule

**You may propose. You may not confirm.**

The full statement and its implications are in
[`docs/agent-guide.md`](docs/agent-guide.md). The short version: no code path
you write may seal a pair or name a human verifier — only `nestor ui` does that.

## Writing tests

- Run new tests against the *unfixed* revision first. A test that passes before
  the fix is a description, not a gate.
- Mirror constants in tests; do not import them from the module under test.
- No outbound network. One test binds a loopback socket; that is the ceiling.

## Pre-PR checklist

Before opening, run the gate for your change class (see the table above). For
anything touching persistence, concurrency, or the audit trail, also walk
through the operator checklist in `docs/code-review-lessons.md` §11.

## Reporting issues

Use the [issue templates](.github/ISSUE_TEMPLATE/) — pick *Bug report* or
*Feature request*. If neither fits, open a blank issue with enough context to
reproduce or evaluate.

## Further reading

| Document | What it covers |
|---|---|
| [`AGENTS.md`](AGENTS.md) | Cold-start for agents: git sync, CI, hooks |
| [`docs/agent-guide.md`](docs/agent-guide.md) | Operating rules: seals, tests, dogfood, voice |
| [`docs/code-review-lessons.md`](docs/code-review-lessons.md) | Pre-merge checklist from prior review rounds |
| [`docs/install.md`](docs/install.md) | Install paths: pipx, pip, from source |
| [`IDEAS.md`](IDEAS.md) | Running idea log with status tags |
