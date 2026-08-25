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
| `nestor/`, `recipes/`, `tests/`, `scripts/`, `hooks/`, `demo/` | `bash scripts/ci-lint.sh && python -m pytest -q` |
| `docs/`, `IDEAS.md`, `docs/dogfood/decisions/*.json` | `bash scripts/ci-docs.sh` |
| `README.md`, `AGENTS.md`, `CLAUDE.md`, `.github/` | `bash scripts/ci-lint.sh` |
| Mixed | `bash scripts/ci-lint.sh && python -m pytest -q` |

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
