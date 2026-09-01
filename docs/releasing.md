# Releasing

**Nestor is released.** `nestor-meaning` **0.3.0** went to PyPI on 2026-08-15 at
18:17Z, from tag `v0.3.0` through `publish.yml`'s Trusted Publishing path. `pip
install nestor-meaning` gives you `import nestor`, unchanged. `0.2.0` was tagged
but never uploaded and is pinnable by git ref only.

Everything below is live, not a rehearsal. The two decisions this file used to
open with are **both taken**; they are kept as records because the reasoning
still governs the next release, and because how the name resolved is the part
somebody will otherwise re-derive from scratch.

---

## Decision 1 — the name, and how it actually resolved

**Taken: the distribution is `nestor-meaning`; the import name stays `nestor`.**

Three checks, three different answers, and the middle one is the trap:

| date | index | `nestor` | what was there |
|---|---|---|---|
| 2026-08-06 | pypi.org | **404 — available** | nothing |
| 2026-08-06 | test.pypi.org | **200 — taken** | `Nestor 0.2.dev2`, Thurston Sexton, `usnistgov/nestor` |
| 2026-08-15 | pypi.org | **200 — 0 files** | a *reserved* project, no releases |

**A 200 with zero files is not a published package — it is a claim on the
name.** Registering a *pending* trusted publisher creates the project before
anything is uploaded, which is what moved `nestor` from 404 to 200 in those nine
days. Read as "somebody published here" it looks like a squatter; read correctly
it is a reservation, and PyPI does not release one just because it holds no
files. Either way `twine upload` under that name stops.

The 2026-08-13 attempt at `v0.2.0` reached PyPI and was rejected at the claim
exchange — the run log shows `environment url: https://pypi.org/p/nestor` and no
matching publisher. The rename followed, and `v0.3.0` published cleanly.

So the cost this section originally weighed — *"somebody searching for Nestor and
finding two unrelated projects"* — was paid the other way round, by renaming, and
it cost one line:

```toml
[project]
name = "nestor-meaning"
```

The distribution name and the import name are independent;
`[tool.setuptools.packages.find] include = ["nestor*"]` does the right thing
either way, and nothing else in the tree had to move.

**One thing the rename does not do by itself.** Extras hints live in shipped
error messages — `keyring.py`, `signing.py`, `semantic_matcher.py`, `answer.py`,
`cloud_seal.py` — and 0.3.0 went out still telling users `pip install
nestor[semantic]`, which now fails with `No matching distribution found`. A user
only sees those strings once something has already gone wrong. `tests/
test_version.py::test_shipped_install_hints_name_the_distribution_that_exists`
reads the name out of `pyproject.toml` and fails on any shipped file that names a
different one, so the next rename cannot leave them behind.

## Decision 2 — what the first version number is

**Taken: `0.2.0` was the first release prepared, and `0.3.0` is the first one
published.** `0.1.0` was left behind meaning "the unreleased extraction", exactly
as the last paragraph here proposed. The reasoning is kept because it is the
argument the *next* bump has to answer, not because the question is still open.

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
| Owner | `Die-Namic-Systems` |
| Repository | `Nestor` |
| Workflow | `publish.yml` |
| Environment | `pypi` |

The workflow filename is part of what PyPI checks. Renaming `publish.yml`
without updating PyPI breaks uploads with an authentication error that does not
mention the filename.

**The owner is part of it too, and this repository changed owners.** Nestor
moved from `rudi193-cmd/Nestor` into the `Die-Namic-Systems` organisation. A
GitHub transfer redirects clones and web links, but PyPI's Trusted Publishing
check is on the OIDC claim, not on a redirect: a publisher still registered
against the old owner rejects the upload. This is unverified from inside the
repository — nothing in this tree can read PyPI's configuration — so before the
next tag, open <https://pypi.org/manage/projects/> and confirm the publisher
reads `Die-Namic-Systems`. The failure mode if it does not is a tag that builds
green and never uploads.

**A pending publisher claims the name.** Registering one creates the PyPI
project immediately, with zero release files — so the name stops being available
to anyone else, including a later you under a different spelling. That is the
point of it, but it means the registration is a decision about the name, not a
preparatory step before one. See Decision 1: this is what put `nestor` at
`200 / 0 files` and is worth checking at
<https://pypi.org/manage/projects/> before assuming a name was taken by a
stranger.

**2. The `pypi` environment.** Repo → Settings → Environments → New environment
→ `pypi`. The workflow's `publish` job is gated on it, so it must exist.

**3. `RELEASE_PLEASE_TOKEN`.** A fine-grained PAT scoped to this repo with
**Contents: read/write** and **Pull requests: read/write**, stored as a
repository secret. `release-please.yml` refuses to run without it rather than
falling back to `GITHUB_TOKEN`, and that refusal is the point: GitHub suppresses
workflow runs for events generated with `GITHUB_TOKEN`, so the fallback opens a
healthy-looking release PR, cuts a tag, and starts no publish run — with no
error anywhere. jeles spent three releases learning this (`v0.2.0` tagged,
released, absent from PyPI).

**4. Auto-merge and a required check.** Settings → General → *Allow auto-merge*,
and the default branch's protection must require at least one status check.
`release-please.yml` arms auto-merge on its release PR; with no required check
there is nothing for it to wait on and GitHub declines to arm it at all. The
workflow fails loudly and says so rather than merging directly.

**A required reviewer on it is deliberately not used.** The earlier version of
this line said to add one so "every upload waits for a human click". That click
is redundant, and asking for it a second time is worse than not asking.

**The tag push was the human gate — corrected in place: it is not any more.**
This section used to say that a tag is something an agent in this repo cannot
do, and that was true and is still true of an *agent's* credentials: a session's
git credentials carry `refs/heads/*` and refuse `refs/tags/*`, confirmed the
hard way when v0.3.1 was prepared (four `git push origin v0.3.1` attempts, HTTP
403 every time, until a human pushed it).

What changed is that nobody is pushing tags by hand now. `release-please.yml`
cuts the tag with `RELEASE_PLEASE_TOKEN`, and auto-merge decides when. So the
guarantee had been resting on an accident of credentials rather than on a
decision, and the accident no longer holds the line.

The gate is now review of the feature PRs plus what CI proves before auto-merge
can fire: the suite on 3.10 and 3.12, ruff, bandit, detect-secrets,
`twine check --strict`, and `publish.yml` installing the built wheel into a clean
venv to import it and run the console script. Deliberate — the same posture
willow-mcp and kartikeya run, and the reason a required reviewer is still not
used above.

Add one anyway if a *second* person should sign off on uploads — that is a real
reason, and the only one. It is not a substitute for the tag push, because
nothing reaches that prompt without one.

---

## Releasing

**There is no manual release procedure any more.** Version numbers, the
changelog entry and the tag are all produced by `release-please.yml` from the
conventional-commit prefixes on what has merged. The steps below are what a
person still does.

```bash
# 1. Type your commits, because they are the release input.
#    feat / fix / security / perf / refactor / build / deps  -> cut a release
#    docs / test / ci / chore                                -> do not
#    A `!` or a BREAKING CHANGE footer goes to the next major.
#    The set lives in release-please-config.json; pr-title.yml reads it from
#    there rather than restating it, so hiding a type moves both at once.

# 2. Title the PR the same way. This repo merges with merge commits, so GitHub
#    writes the PR TITLE into the merge commit body and release-please parses
#    that too. pr-title.yml fails a title that would cut a release its commits
#    would not — and the reverse, a release for a PR touching nothing under
#    nestor/ or pyproject.toml.

# 3. Merge the feature PR. release-please opens or updates a
#    "chore(master): release X.Y.Z" PR showing the exact version and the exact
#    changelog section that will ship. Nothing publishes while it sits there.

# 4. Auto-merge is armed on that release PR: when CI is green it merges, the tag
#    is cut, and the tag push starts publish.yml. Merge it by hand if auto-merge
#    is not armed (see One-time setup 4).

# Optional, any time: rehearse without publishing anything.
#   Actions -> Publish -> Run workflow. Builds, checks, installs the wheel in a
#   clean venv and asks its version. The publish job is skipped — it is gated on
#   the ref being a tag.
```

**Nothing in this tree carries a version number.** `pyproject.toml` declares
`dynamic = ["version"]` and hatch-vcs derives it from the git tag, so there is
no bump commit and no file to forget. Off a tag, a build produces a
`X.Y.Z.devN+g<sha>` version that PyPI refuses outright — an accidental publish
from an untagged commit fails loudly instead of shipping something mislabelled.

`publish.yml` still refuses a tag whose version disagrees, but it now compares
the tag against the **built artefact** rather than a `pyproject.toml` literal,
because there is no literal. The failure it catches has changed shape with it:
not "somebody forgot to bump" but "the checkout could not see the tags", which
yields a development version off an otherwise perfectly correct tag. That check
exists because a filename on PyPI is permanent — `nestor_meaning-0.1.0.tar.gz`
uploaded from a tag saying `v0.2.0` cannot be renamed, reassigned or
deleted-and-replaced.

**Where the human gate sits now.** It used to be the tag push, and that was
enforced by an accident rather than a decision: a session's git credentials
carry `refs/heads/*` and refuse `refs/tags/*`, which is why preparing v0.3.1 took
four `git push origin v0.3.1` attempts returning HTTP 403 until a human pushed
it. release-please cuts the tag with the PAT, and auto-merge decides when, so
that accident no longer holds the line. The gate is now review of the feature
PRs plus what CI proves before auto-merge can fire: the suite on 3.10 and 3.12,
ruff, bandit, detect-secrets, `twine check --strict`, and publish.yml installing
the built wheel into a clean venv to import it and run the console script. That
is the deliberate trade, and the same posture willow-mcp and kartikeya run.

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

All three entries that used to live here have been reversed. They are kept with
their original objections, because two of the three were correct about the
failure mode and the answer is what was built to handle it, not that the
objection was silly.

- **~~No version bumping from tags~~ — now hatch-vcs.** The objection was that
  it "makes the version a function of git state, which means a dirty tree or a
  shallow clone produces a different number than the one you meant". Both halves
  are real and both were reproduced while making this change: a dirty tree at
  tag `v9.9.9` builds `9.9.10.dev0+g<sha>.d<date>`, and a shallow clone warns and
  derives nothing usable. Neither can reach PyPI. A dev-suffixed version is
  rejected by PyPI outright, `publish.yml` checks out with `fetch-depth: 0` and
  `fetch-tags: true`, and its guard compares the tag against the **built**
  artefact, so a checkout that could not see the tags fails the release instead
  of shipping. What the literal cost in exchange was a number in a file that
  somebody has to remember on release day — the failure kartikeya's v0.0.8 shipped.
- **~~No release-on-merge~~ — now release-on-merge, via the release PR.**
  Publishing is still irreversible in a way merging is not; what changed is that
  the merge being acted on is a `chore(master): release X.Y.Z` PR whose entire
  content is the version and the changelog section about to ship. That is a more
  legible thing to approve than a `git tag` was.
- **~~No auto-generated changelog~~ — now generated, and the objection stands.**
  "A changelog is the shorter, edited claim about what *matters*, and generating
  it from commits produces neither" is still true. The mitigation is that the
  commit subjects **are** the changelog now, so they have to be written as such,
  and the release PR is editable before it merges. `docs`, `test`, `ci` and
  `chore` are hidden types, so noise stays out by construction rather than by
  editing it back out afterwards.

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
- **No rehearsal target on TestPyPI**, per Decision 1: `nestor` there is NIST's.
  `nestor-meaning` was never rehearsed on TestPyPI either — 0.3.0 went straight
  to production on `twine check --strict` plus the workflow's install-and-import
  step. That worked, and it is still the weaker of the two options the original
  Decision 1 laid out; `nestor-meaning` is free on TestPyPI now, so the next
  release can rehearse properly.
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
