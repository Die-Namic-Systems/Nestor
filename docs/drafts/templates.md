# Templates — draft

*Filling the gap §7.5 names: a PR template and pre-commit exist;
`CONTRIBUTING.md` and `.github/ISSUE_TEMPLATE` do not. Low-stakes,
high-standard.*

**Status: draft — proposed, not decided.**

---

## The problem

The loop has a single template (`.github/pull_request_template.md`) and
relies on convention for everything else. Three surfaces are absent:

1. **Issue templates.** A bug report and a feature request both land in the
   same blank textarea. A contributor cannot see what information is expected.
2. **Contributor guide.** `AGENTS.md` and `docs/agent-guide.md` address
   machine agents. Nothing addresses a human contributor opening their first
   PR — the governance rules, the propose-never-seal boundary, the decision
   store, the CI gates.
3. **Decision JSON template.** The `{"pr", "date", "decisions"}` shape is
   enforced by `dogfood_common.load_decisions` at runtime but not documented
   as a template a contributor (human or agent) can copy.

A fourth is named in §7.4 step 4: **task templates** inside the recipe
domain — structured extraction output shapes. That one is tightly coupled
to the recipe implementation and is included here as a schema reference,
not a file template.

## What ships

### 1. `.github/ISSUE_TEMPLATE/bug_report.yml`

GitHub's YAML-based issue form (not the older markdown template), because
it enforces required fields and renders a structured form in the browser.

```yaml
name: Bug report
description: Something is broken or behaving unexpectedly.
labels: ["bug"]
body:
  - type: textarea
    id: what-happened
    attributes:
      label: What happened?
      description: >
        What did you do, what did you expect, and what happened instead?
      placeholder: "I ran `nestor ask ...` and got ..."
    validations:
      required: true
  - type: textarea
    id: reproduce
    attributes:
      label: Steps to reproduce
      description: >
        Minimal sequence to reproduce the behavior. Include the command,
        the store state (empty store? seeded with `nestor demo`?), and any
        env vars that matter.
      placeholder: |
        1. `nestor demo --db /tmp/test.db`
        2. `nestor ask --db /tmp/test.db "..."`
        3. See error
    validations:
      required: true
  - type: input
    id: version
    attributes:
      label: Nestor version
      description: "Output of `nestor --version` or `pip show nestor-meaning`."
      placeholder: "0.9.0"
    validations:
      required: true
  - type: textarea
    id: context
    attributes:
      label: Additional context
      description: >
        Anything else — logs, screenshots, the store file, the env. If the
        store is relevant, `nestor export --db <path>` produces a portable
        bundle that does not carry secrets.
    validations:
      required: false
```

### 2. `.github/ISSUE_TEMPLATE/feature_request.yml`

```yaml
name: Feature request
description: Propose a change or a new capability.
labels: ["enhancement"]
body:
  - type: textarea
    id: problem
    attributes:
      label: What problem does this solve?
      description: >
        The situation today and why it matters. "I want X" is fine; "when I
        do Y, I hit Z, and X would fix that" is better.
    validations:
      required: true
  - type: textarea
    id: proposal
    attributes:
      label: Proposed solution
      description: >
        What you think should happen. If you have a design, include it;
        if you don't, describe the outcome.
    validations:
      required: true
  - type: textarea
    id: alternatives
    attributes:
      label: Alternatives considered
      description: >
        Anything you tried or thought about instead, and why it didn't fit.
    validations:
      required: false
  - type: dropdown
    id: surface
    attributes:
      label: Which surface?
      description: Where does this change show up?
      options:
        - CLI (`nestor` commands)
        - MCP server (`nestor serve`)
        - Browser UI (`nestor ui`)
        - Core library (`nestor/`)
        - Documentation
        - Other
    validations:
      required: true
```

### 3. `.github/ISSUE_TEMPLATE/config.yml`

```yaml
blank_issues_enabled: true
contact_links: []
```

Blank issues stay enabled — a structured template should guide, not gate.

### 4. `CONTRIBUTING.md`

Not a wall of text. The shape:

```markdown
# Contributing to Nestor

## The one rule

**You may propose. You may not confirm.** No PR, no script, and no
automated step writes `status="sealed"` or sets `verifier=` to a human's
name. Only a human, in `nestor ui`, seals. The test suite enforces this
structurally (`tests/test_onboarding.py::TestNeverSeals`), and the MCP
server (`nestor/serve.py`) does not expose seal, unseal, reject, or
override — they do not exist on the wire.

## Setup

```sh
git clone <repo>
cd nestor
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Before you push

```sh
bash scripts/ci-lint.sh   # ruff, bandit, mypy, detect-secrets, pip-audit
python -m pytest -q        # the full suite
```

Both must pass. The CI matrix runs the same commands; a local failure is a
CI failure.

## Decisions

A product decision made in a PR goes in `docs/dogfood/decisions/` as a
JSON file (see the template in this directory or any existing file), then:

```sh
python scripts/dogfood_store.py --rebuild
```

All decisions land as `status="draft"`. Sealing happens later, by a human,
in `nestor ui`. The decision store is the dogfood corpus — Nestor's own
decisions, stored in Nestor.

## Code layout

See `docs/project-layout.md` for the full map.

## PRs

Fill in the PR template (`.github/pull_request_template.md`). The
"Evidence" section means receipts, not claims — paste the command and its
output, or say what you ran and saw.
```

### 5. Decision JSON template documentation

The shape `dogfood_common.load_decisions` expects, documented in the
decisions directory itself:

**`docs/dogfood/decisions/TEMPLATE.md`**

```markdown
# Decision file template

Each PR that makes a product decision adds a JSON file here, named
`<NNNN>-<slug>.json` where `NNNN` is the PR number (zero-padded to 4
digits) and `<slug>` is a short kebab-case name.

## Shape

```json
{
  "pr": 123,
  "date": "2026-08-19",
  "decisions": [
    {
      "question": "The question this decision answers — phrased as a question.",
      "commitment": "What was decided — the answer, not the rationale.",
      "why": "Why this answer and not another — the rationale."
    }
  ]
}
```

## Rules

- **`pr`** (int): the PR number. Must be unique across all files in this
  directory — `dogfood_common` refuses a duplicate.
- **`date`** (string): ISO 8601 date of the decision. Used as `created_at`
  in the store.
- **`decisions`** (array): one or more decision entries. Each is a
  `(question, commitment, why)` triple.
- **`question`** (string): phrased as a question. This becomes the
  `source_text` in the store.
- **`commitment`** (string): the answer. This becomes the `target_text`.
- **`why`** (string): the rationale. This becomes the `reason` column — the
  N4 field Nestor records for every pair.

## What happens next

`python scripts/dogfood_store.py --rebuild` reads every file here, loads
them into `docs/dogfood/nestor.db` as `status="draft"` pairs with
`source_lang="decision"` and `target_lang="decision"`, and exports the
bundle to `docs/dogfood/decisions.json`. All draft — sealing is a human
act in `nestor ui`.
```

### 6. Task template shape (recipe domain, §7.4 step 4)

This is a schema reference, not a file that ships. The recipe domain's
structured extraction produces typed output; a task template defines what
that output looks like for a given `(source_lang, target_lang)` pair.

```python
# The shape a recipe's structured extraction returns.
# Not a file template — a schema the recipe implementation defines.

TASK_TEMPLATE = {
    "source_lang": str,       # e.g. "question", "entity", "glossary"
    "target_lang": str,       # e.g. "decision", "answer", "definition"
    "fields": {
        "source_text": str,   # the input (always present)
        "candidate": str,     # the output (always present)
        "title": str | None,  # optional title / label
        "metadata": dict,     # recipe-specific extra fields
    },
    "constraints": {
        "max_source_len": int | None,
        "max_candidate_len": int | None,
        "required_metadata": list[str],
    },
}
```

This is the gap §7.4 step 4 names. Its implementation belongs in the
recipe module, not in a template file. Documenting the shape here anchors
the design conversation.

## What this is NOT

- **Not a scaffolder.** No `nestor new` or `cookiecutter`. The templates
  are GitHub-native forms and a contributor guide — the standard parts
  §7.5 names as absent.
- **Not a code generator.** The task template shape describes structured
  extraction output; it does not generate code.
- **Not opinionated about workflow.** Issue templates guide, they don't
  gate (blank issues stay enabled). The PR template is already shipped
  and already carries the governance line.

## Interaction with existing surfaces

| Surface | Exists | What this adds |
|---------|--------|----------------|
| `.github/pull_request_template.md` | yes | nothing (already shipped) |
| `.github/ISSUE_TEMPLATE/` | no | bug report + feature request forms |
| `CONTRIBUTING.md` | no | contributor guide with the one rule |
| `docs/dogfood/decisions/TEMPLATE.md` | no | decision JSON shape documentation |
| Recipe task templates | no (§7.4 step 4) | schema reference only |
