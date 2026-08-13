# Releasing

Nestor has never been released. `pyproject.toml` has said `0.1.0` since
`7fb841e` — the extraction commit — there are no tags, and nothing has been
uploaded anywhere. Everything below is set up and inert.

This file is the runbook, and it opens with the two decisions that come before
any of it, because neither is a mechanical step and neither is mine to take.

---

## Decision 1 — the name is not free the way it looks free

Checked 2026-08-06:

| index | `nestor` | what is there |
|---|---|---|
| pypi.org | **404 — available** | nothing |
| test.pypi.org | **200 — taken** | `Nestor 0.2.dev2`, Thurston Sexton, `usnistgov/nestor` |

The TestPyPI occupant is NIST's — *"Quantifying tacit human knowledge for Smart
Manufacturing Maintenance"*, a real project with a real GitHub repository. So
two things follow, and the second is the one that matters.

**The rehearsal step is blocked.** The normal move — upload to TestPyPI first
and check the page renders — cannot be done under this name. Either rehearse
under a different name (`nestor-<something>`, TestPyPI only, throwaway), or skip
rehearsal and rely on `twine check --strict` plus the workflow's install-and-import
step. Both are defensible; the first is closer to how a release should feel.

**Publishing as `nestor` on PyPI would collide with an existing project in the
same ecosystem.** Not legally — the production name is genuinely unclaimed, and
first-come is how PyPI works. But somebody searching for Nestor and finding two
unrelated projects is a cost this project pays, not NIST. The alternative costs
one line: a distribution name that is not the import name.

```toml
[project]
name = "nestor-verify"        # or nestor-memory, nestor-tm, …
```

`pip install nestor-verify` then gives you `import nestor`, unchanged — the
distribution name and the import name are independent, and nothing else in the
tree moves. `[tool.setuptools.packages.find] include = ["nestor*"]` already does
the right thing either way.

**Not decided here.** Whoever releases picks. If the answer is plain `nestor`,
nothing needs changing.

## Decision 2 — what the first version number is

`0.1.0` is where the extraction landed and it has never moved, so it carries no
information: it is not a considered *"this is early"*, it is a default nobody
revisited. Things worth weighing:

- The **bundle format is already at version 2**, with version 1 still supported
  and a per-version field map (`portable.py`). The wire format has real history
  the package version does not reflect.
- `0.x` signals *the API may move*, which is honest — `TODO.md` §1 (asymmetric
  seals) would change the deployment story, and §6.29's export fix changes the
  public surface.
- Anything `1.x` is a promise about compatibility that `IDEAS.md` §1.4 and
  `TODO.md` §2 are not ready to make.

`0.1.0` as a first release is defensible. So is `0.2.0`, to leave `0.1.0`
meaning "the unreleased extraction". Pick deliberately; the number is the one
part of a release nobody can correct afterwards.

---

## One-time setup

**1. PyPI Trusted Publishing.** No API token is stored in this repository — the
workflow authenticates with a short-lived OIDC token instead, so there is no
long-lived credential to leak or rotate. On PyPI, under the project (or as a
*pending* publisher if the name is not yet claimed), add:

| field | value |
|---|---|
| Owner | `rudi193-cmd` |
| Repository | `Nestor` |
| Workflow | `publish.yml` |
| Environment | `pypi` |

The workflow filename is part of what PyPI checks. Renaming `publish.yml`
without updating PyPI breaks uploads with an authentication error that does not
mention the filename.

**2. The `pypi` environment.** Repo → Settings → Environments → New environment
→ `pypi`. Add yourself as a **required reviewer** while you are here: that makes
every upload wait for a human click, which is the same shape as everything else
in this project — the machine may propose and may not confirm.

---

## Releasing

```bash
# 0. Rehearse without publishing anything. Actions → Publish → Run workflow.
#    Builds, checks, installs the wheel in a clean venv and asks its version.
#    The publish job is skipped: it is gated on the ref being a tag.

# 1. Decide the version, and move it in ONE place.
$EDITOR pyproject.toml            # version = "X.Y.Z"

# 2. Close the changelog section.
$EDITOR CHANGELOG.md              # ## [Unreleased] -> ## [X.Y.Z] - YYYY-MM-DD

# 3. Add the install line to the README. It is absent on purpose until now,
#    because a README that lies about how to install is worse than one that
#    omits it. Same commit as the bump.
$EDITOR README.md

# 4. Gates, the same ones docs/code-review-lessons.md §11 asks for.
python -m pytest -q
python -m ruff check nestor tests
bandit -r nestor -ll -q

# 5. Build locally and look at what you are about to publish.
pip install -e ".[publish]"
rm -rf dist && python -m build
python -m twine check --strict dist/*
python -c "import zipfile;print(sorted({n.split('/')[0] for n in zipfile.ZipFile('dist/nestor-X.Y.Z-py3-none-any.whl').namelist()}))"

# 6. Commit, then tag. The tag is the trigger — nothing before it can publish.
git commit -am "release: X.Y.Z"
git tag -a vX.Y.Z -m "X.Y.Z"
git push origin master --follow-tags

# 7. Approve the `pypi` environment when Actions asks.
```

The workflow refuses a tag whose version disagrees with `pyproject.toml` before
it builds anything. That check exists because a filename on PyPI is permanent:
`nestor-0.1.0.tar.gz` uploaded from a tag saying `v0.2.0` cannot be renamed,
reassigned or deleted-and-replaced.

---

## A release that touches the schema requires a restart

**If a release changes `_SCHEMA` or any `_ensure_*` migration in
`sqlite_store.py`, the release notes must say that long-lived processes have to
be restarted.** This is not a nicety. Since IDEAS §6.8, `memory_init` skips its
work on a connection that has already done it, so a process holding warm pooled
connections will not run a migration it did not have when those connections were
opened.

Reproduced, on the §6.8 code:

```
warm memory_init      -> new migration ran: False
after checkpoint_wal  -> new migration ran: True
```

The second line is the shape of the hazard rather than a workaround: the pool
happens to clear on `checkpoint_wal`, so whether a migration lands depends on
whether something unrelated flushed the WAL first. That is not a rule anybody
should have to reason about at upgrade time.

Before §6.8 this self-healed, because every `memory_init` replayed the idempotent
DDL. The performance win and this hazard are the same change, and the honest
statement of the trade is: **Nestor's store upgrades on process start, not on
package upgrade.**

**This rule is latched, because a rule that only lives in a document is a rule
that fails silently.** `tests/test_sqlite_store.py::test_a_schema_change_has_to_be_a_deliberate_release_decision`
pins a digest of the DDL `memory_init` actually leaves in `sqlite_master` — the
effective schema, not the source that produced it, so comments and refactors move
nothing and a real change moves it every time. Change the schema and the build
stops with this paragraph's requirement in the failure message. Verified by
adding a plausible column and watching it go red:

```
the effective schema changed (f42f4ae579f0c8bd -> 0a1db724f072da1a).
Since §6.8 a warm connection skips migrations it did not have when it was
opened, so long-lived processes will NOT pick this up on a package upgrade —
only on restart. docs/releasing.md requires the release notes to say so.
```

Tripping it is not a bug. It means: say the restart line, then update the pin in
the same commit.

Documentation remains the weaker half of the fix, and the latch does not change
that. The strong one is a schema generation in the database that invalidates the
flag when it moves — which is §6.31, which argues that stamping a version into
persistence is a decision to be argued rather than slipped into another change.
Shipping half of it inside a performance reland is the shape this repository
keeps punishing. **If the next migration is security-relevant, that argument
happens before it, not after.**

## What is deliberately not automated

- **No version bumping from tags** (`setuptools-scm` and friends). It makes the
  version a function of git state, which means a dirty tree or a shallow clone
  produces a different number than the one you meant. One literal in
  `pyproject.toml`, read at runtime through `importlib.metadata`, is checkable by
  reading two files — and the workflow checks it for you.
- **No release-on-merge.** Publishing is irreversible in a way merging is not.
- **No auto-generated changelog.** The commit log is already the record of what
  changed; a changelog is the shorter, edited claim about what *matters*, and
  generating it from commits produces neither.

---

## Known gaps in this setup

- **CI does not test everything the classifiers claim.** `requires-python` says
  `>=3.10` and the classifiers list 3.10 through 3.13; the matrix in `tests.yml`
  runs **3.10 and 3.12** — floor and current, which its own comment says is the
  strategy and which is a reasonable one. The gap is not the matrix, it is that
  the classifiers assert four versions where two are covered by interpolation.
  Either widen the matrix or narrow the claim; doing neither is the only wrong
  answer, and this note exists so that choice is made rather than defaulted.

  Run once by hand on 2026-08-06, one venv per interpreter, `.[keys] pytest
  coverage` as CI installs: **3.10, 3.11, 3.12 and 3.13 all green**, 597 passed
  / 7 skipped on each. That is a snapshot, not a gate — it will not notice the
  day 3.11 breaks. It does mean the two interpolated claims were true once,
  which is more than could be said for them before. (The suite has grown since:
  a 2026-08-10 run on 3.11 reports 937 passed / 19 skipped. The 597/7 above is
  left as the dated cross-version record it was, not edited to match.)

  This gap was not hypothetical for long: the first draft of
  `tests/test_version.py` imported `tomllib` (3.11+) and broke
  `test-matrix (3.10)` — a release-readiness suite that would not run on the
  oldest version being released for. The matrix caught it, which is the
  argument for keeping a floor in it.
- **No rehearsal target**, per Decision 1 above.
- **`nestor.__version__` describes the installed distribution, not the file that
  is running.** Measured, and all three cases are documented at the definition:
  a clone with no install and no `nestor.egg-info/` reports `0+unknown`; a clone
  that has ever been installed into keeps an `egg-info` that
  `importlib.metadata` reads as a distribution, so it reports a version with
  nothing in the venv; and a working tree shadowing an installed nestor reports
  the *installed* version while running the tree's code. The last is a property
  of `importlib.metadata`, and the only way to defeat it is a literal in the
  package — which is the thing `tests/test_version.py` refuses. If a host that
  vendors rather than installs becomes a real deployment shape, ship the version
  in the artifact; do not hardcode it here.
- **The ledger still carries no version** — `IDEAS.md` §6.31. The *store* now
  carries a `user_version` as of 0.2.0 (#91, ratified as decision `0121`), which
  is the strong fix the schema-restart section above pointed at. The ledger is
  the half that did not move, and the one that gets harder the longer it waits:
  it is hash-chained, so historical entries cannot be re-hashed under new rules
  without breaking the chain they exist to protect. Versioning it is a separate,
  deliberate argument that has not been made.
