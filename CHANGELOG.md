# Changelog

Notable changes, newest first. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**The first release is `0.2.0`**, prepared in this section. `pyproject.toml`
said `0.1.0` from the extraction commit `7fb841e` until here; `0.1.0` was never
tagged and stands for "the unreleased extraction," so the first real release
leaves it behind rather than reusing it (`docs/releasing.md` Decision 2). The
tag is the trigger and is cut on merge to `master`, not by the branch that
writes this — see [`docs/releasing.md`](docs/releasing.md).

This file records *releases*, not commits. The argument for a change lives in
[`IDEAS.md`](IDEAS.md), the queue in [`TODO.md`](TODO.md); a changelog entry is
the one-line version for somebody who has installed a version and wants to know
what moved.

---

## [Unreleased]

### Changed

- **BREAKING — Nestor's household root is now `~/.nestor` (`NESTOR_HOME`).**
  `nestor/homestead_paths.py` becomes `nestor/home_paths.py`, and the resolver
  no longer defaults to another product's root. This is
  `docs/roots-willow-and-homestead.md`'s own audience test applied to Nestor:
  the rule there is that someone who only installs a household product should
  not be handed a vocabulary that isn't theirs — `WILLOW_*` was the example,
  and a Nestor-only install creating a `.homestead` directory is the same
  mistake one brand along. `~/.homestead` remains a real root owned by
  `rudi193-cmd/homestead`; Nestor just no longer resolves to it unasked.

  A host that wants the keep tree where it already is names the root:
  `NESTOR_HOME="$HOMESTEAD_HOME"`. That is the entire migration.

  `home_init`'s layout marker is now `nestor_household_v1`, so a tree stood up
  by an earlier version keeps its own `layout.json` untouched (the scaffolder
  never overwrites) and reads as stood-up either way.

### Added

- **A refusal instead of a silent relocation.** `home_paths.home()` raises
  `HomeRelocationRefused` when `HOMESTEAD_HOME` is set and `NESTOR_HOME` is
  not, rather than falling back to either root. `keep/ledger.jsonl` is a hash
  chain: resolving the other way would not move it, it would start a second
  one, and both halves then verify on their own while the history between them
  is gone. The session-start hook carries the same refusal as its `[nestor]`
  ask, so a host in this state is told at boot rather than at the first append.

### Security

- The bash guard's secret-path family now covers `~/.nestor` alongside
  `~/.homestead`. Both stay guarded — a host that pinned `NESTOR_HOME` at the
  old location still keeps live state there, and dropping a rule to tidy a
  rename is how a guard quietly narrows.

---

## [0.3.1] - 2026-08-15

A correctness patch for what 0.3.0's rename left behind. No schema, ledger or
API change; the only shipped difference is that the install commands Nestor
prints when it refuses now name a distribution that exists.

### Fixed

- **Runtime install hints named the old distribution.** Renaming to
  `nestor-meaning` in 0.3.0 updated `pyproject.toml`, the README and this file,
  but not the strings five modules print when an optional extra is missing —
  `keyring.py`, `signing.py`, `semantic_matcher.py`, `answer.py` and
  `cloud_seal.py` all still said `pip install nestor[keys]` / `[semantic]` /
  `[gate]`. Those commands fail outright (`No matching distribution found`),
  because `nestor` on PyPI is a reserved project with no files. A user only
  reads those strings once something has already gone wrong, so the failure
  handed them a second one. Recorded as dogfood decision `0129`.

  `tests/test_version.py::test_shipped_install_hints_name_the_distribution_that_exists`
  now reads `name` out of `pyproject.toml` and fails on any module under
  `nestor/` that names a different distribution, so a future rename cannot leave
  them behind again.

### Changed

- **`[dev]` installs every gate `scripts/ci-lint.sh` runs.** `detect-secrets`
  was wired into the lint script and CI by decision `0101` but never declared,
  so `pip install -e ".[dev]"` built an environment that cleared ruff and bandit
  and then died on `No module named detect_secrets`. Pinned to `==1.5.0`, the
  version CI installs, because the scan is judged against a committed
  `.secrets.baseline`. Decision `0124`.

- **The SessionStart seat context answers three more questions.** `[check]
  lint:` reports whether every gate in `scripts/ci-lint.sh` can actually run;
  `[nestor]` says whether a Nestor is stood up and, when none is, hands the
  agent the question to put to the user rather than standing one up itself.
  Neither modifies anything it inspects. Decisions `0126`, `0127`, `0128`.
  Repository tooling only — `hooks/` is not part of the distribution.

---

## [0.3.0] - 2026-08-15

The first release published to PyPI, as `nestor-meaning` (`pip install
nestor-meaning`; the import name stays `nestor`); `0.2.0` was pinnable by git
ref only. No schema or ledger change, so a warm process needs no restart to
adopt it (`docs/releasing.md`).

### Added

- **A worked proof that the loop runs on a corpus from outside this repo** —
  `demo/the_dispatches_audit.py` over `demo/dispatches_audit_corpus.json`
  (#114). It drives propose → review → seal end to end on external text and is
  covered by `tests/test_dispatches_audit.py`, so the claim "Nestor works on
  your corpus, not just its own dogfood" is a runnable demonstration rather than
  an assertion. Recorded as dogfood decision `0122`.

### Changed

- **Ratify a draft where you read it.** In Memory, a plain draft's proposed
  answer is now editable in the detail panel with a single **Seal this
  decision** button (and Reject); sealing **auto-advances to the next plain
  draft**, so a long review queue is a rhythm rather than a dropdown round-trip
  each time. "Seal a pair by hand" reverts to new-pairs-only (#113). Governance
  is unchanged: sealing still requires an acting verifier and, when signing is
  on, a real signature.
- **`reconcile` reports the tolerance a verdict turned on.** When a reconcile
  verdict hinges on the match tolerance, that tolerance is now surfaced in the
  CLI and page output instead of being left implicit, so a near-miss reads as a
  near-miss (#115, `reconcile.py` / `matcher.py` / `cli.py`). Recorded as
  dogfood decision `0123`.

### Fixed

- **The provenance detail panel no longer renders a literal `null`.** A bare
  `card.append(null)` stringifies to the text `"null"`; children are now
  filtered with `h()`'s own null/undefined/false predicate before appending
  (IDEAS §6.97, part of #113).

## [0.2.0] - 2026-08-13

### Added

- **The store schema now carries a version.** `sqlite_store.py` stamps
  `PRAGMA user_version = SCHEMA_VERSION` (1), runs an ordered forward-migration
  ladder (empty this release — there has been one generation), and **refuses a
  file whose `user_version` is newer than it understands** (`StoreSchemaToo`
  `NewError`) rather than reading a shape it half-knows. This is the "schema
  generation in the database" `IDEAS.md` §6.31 named as the strong fix for the
  §6.8 warm-connection hazard. §6.31 had reserved it as a decision to be argued
  rather than stamped; it arrived inside a reland (#91) and was **ratified
  deliberately** — decision `0121`, and the §6.31 note. The **ledger** is still
  unversioned, by the same entry's still-open argument. No table/column/index
  DDL changed, so the effective-schema digest is unmoved; the interim rule
  holds — a schema change lands on process restart, not package upgrade.
- **`nestor.config`** — one layered configuration resolver (env > file >
  default) with typed accessors. A *missing* file is an empty layer that drops
  to the default; a *malformed or unreadable* file raises `ConfigError` rather
  than degrading to one — unknown, not a silent wrong value. Secrets resolve
  env-only, never from the file layer.
- **`nestor.home_init`** — an idempotent scaffolder for the homestead home
  (`~/.homestead`), built on `homestead_paths`: it creates the keep/record/logs/
  drafts tree if absent and never clobbers existing operator content. (It does
  not pre-create `keep/ledger.jsonl`; `cascade` treats a missing ledger as a
  fresh genesis chain.)
- **A tested guarantee that `import nestor` is dependency-light.** The package
  docstring has always promised the transports (`ui`/`cli`/`serve`) load on
  demand "since a library import should not pull in an HTTP server," and core
  `dependencies = []`. `tests/test_import_purity.py` now enforces it: a fresh
  subprocess imports nestor and asserts nothing third-party entered `sys.modules`
  and no transport or `cloud_seal` gate seam was pulled in eagerly, with a
  mutation test proving the guard can fail. This is the contract a zero-egress
  host (UTETY, terpsi-music) needs before it will vendor the seal/ledger organ.
- **A cold open for `nestor ui`.** `nestor demo` (and `nestor ui --demo`) seed a
  small live store across all three recipes plus a short review queue, so a
  freshly cloned or `pip install`ed Nestor opens onto real content, not an empty
  desk. The browser page now greets a newcomer with a **front door** — a
  three-door welcome framed by audience — and carries **Nestor himself** in the
  header as a small robot whose expression tracks the verdict on screen (settled
  on a served seal, unconvinced on a draft, alarmed on a signature that does not
  verify). The **Memory** rows gained a status **lamp** and a bold
  **served / not-served flag**, so a row that says sealed but would be refused is
  visible at a glance. `nestor ui --demo` also **signs** the demo's seals (an
  ephemeral key beside the store) and seeds one **forged seal** — a row written
  straight in as sealed by a trusted name, with no signature that name could have
  produced — so the "scores 1.000 and is refused anyway" story is live, not just
  described: it shows `not servable` in Memory and comes back refused when asked.
  Stdlib-only and CSP-clean, as the page has always been. `IDEAS.md` §6.107.
- `nestor.__version__`, read from installed distribution metadata rather than
  written into the package. A tree with no install *and no `nestor.egg-info/`*
  reports `0+unknown` — a legal PEP 440 local version that sorts below every
  release and cannot be mistaken for one. It describes the **distribution**, not
  the file that is executing; the three cases that fall out of that are measured
  and written at the definition.
- Packaging metadata PyPI will actually render: long description from the
  README, classifiers, keywords, project URLs, and a PEP 639 license expression
  with `LICENSE` and `NOTICE` both shipped in the wheel.
- A `publish` extra (`build`, `twine`), deliberately outside `dev` so CI's test
  install does not carry a release toolchain it never uses.
- `.github/workflows/publish.yml` — builds and checks on a `v*` tag or a manual
  dry run, and uploads only from a tag, only through a `pypi` environment, only
  via Trusted Publishing. It refuses a tag whose version disagrees with
  `pyproject.toml`, and it installs the built wheel into a clean virtualenv and
  asks it its version before anything is uploaded.
- [`docs/releasing.md`](docs/releasing.md) — the runbook, including the two
  decisions that have to be made before a first release and the reason neither
  of them is mine.
- `nestor.ledger.unreadable()` — the ledger lines that are not valid JSON, as
  `{"line", "error"}`. `entries()` discarded them silently, so a four-line
  ledger listed three records with nothing marking the gap; the export bundle's
  `ledger` block, the UI's ledger tab and `nestor ledger entries` all inherited
  that. All three now report the damage — the CLI on stderr, so a script parsing
  stdout is unaffected. `IDEAS.md` §6.34.

### Fixed

- **The provenance card no longer renders the literal string `null`.** The UI's
  `detailPanel` built its card with native `card.append(...)`, which stringifies
  a `null`/`undefined`/`false` child to a text node — unlike the page's `h()`
  helper, whose kid loop drops them. An ordinary row with no commitment choices
  and no reason rendered `nullnull`. Fixed by filtering with `h()`'s own
  predicate at the one native-append site. (#94)
- **`nestor_propose` names what it refused instead of dropping it silently.** A
  forbidden wire key was discarded without a word; a caller passing
  `status`/`verifier`/`sealed` read an unqualified success where it should read
  a refusal. The reply now lists the ignored fields and calls out any
  seal-authority field with the reason it was dropped — the row still lands as
  an unsealed draft. A refusal has to read as one. (#98)
- **`keys add` prints the key that actually opens a session for an ed25519
  verifier.** It printed `entry.key`, which for ed25519 is the *public* half —
  it verifies the verifier's seals but can never sign in, so an enrolled
  verifier was handed a key that 403s. It now prints the private signing half
  `Sessions.open` authenticates against, branching on kind, and handles a
  public-key-only (`--public`) enrollment separately. (#99)
- **`nestor serve` and `nestor ask` can be told a custom matcher too**, which
  closes the half of `IDEAS.md` §6.41 that §6.40's fix did not reach. Both are
  launched as *processes*, so there is no earlier moment at which a host could
  call `memory.set_matcher()`, and a shipped name off a command line cannot
  conjure a matcher nobody shipped — so a custom domain could not use either
  surface at all. Measured end to end over stdio MCP, on one sealed row: without
  a matcher the model is told **pending** for a phrase a human sealed; with one
  it gets the seal and the verifier's name.

  `answer.load_matcher` takes a shipped name *or* `module:attribute` — a module
  attribute, a class, or a factory — and `nestor serve`, `nestor ask`, `nestor
  match` and `nestor ui` all take the same spec through the same loader. It
  validates at load time — a spec that is not a matcher, a factory that returns a
  class rather than an instance, a class whose `__init__` wants arguments, or a
  module that raises on import all refuse to start with a message naming the spec
  rather than failing at the first query or tracebacking out of a stdio server.
  It **imports the module named**, which is the
  same authority the command line already has; that is why it is a flag and never
  a value read from a request, a bundle or a stored row. `serve.Server` gains
  `matcher` and the same `domain_matcher()` rule `ui.App` learned: the server's
  matcher for the server's domain and no other, because every tool takes per-call
  domain tags. `nestor_match` refuses a name that disagrees with what is in force
  and honours one that agrees — compared against the *spec*, because comparing
  against the matcher's class name refused `numeric` on a server started
  `--matcher numeric` while accepting `NumericMatcher`, and the tool schema
  offers a model only the former. A shipped name also stays a name internally, so
  per-call `abs_tol`/`pct_tol` still reach it; against a custom matcher, which
  owns its own notion of nearness, they are refused rather than silently ignored.
  `nestor_resolve` gets the matcher too — without it one server answered `sealed`
  from `nestor_ask` and `unverified` from `nestor_resolve` for the same row — and
  `answer.resolve` now scores its candidate list with the matcher that reached
  the verdict instead of the process-wide one, so a payload can no longer carry
  `verified: false` beside a candidate scoring 1.0. `nestor calibrate --matcher`
  takes the spec as well: it is the tool `memory.py` tells you to measure with,
  and it was the last flag that could not name a custom matcher.

  Third-party code now runs inside `nestor serve`, so the import happens with
  stdout redirected to stderr: a `print()` in a matcher module would otherwise
  land in front of the JSON-RPC handshake and most hosts drop the connection.

  `ui --matcher` is no longer restricted to `choices=answer.MATCHERS`, which had
  made a custom matcher unnameable at the one surface that could already take one.

- **`nestor ui` can be told the matcher that keys its domain.** A domain is its
  tags *and* its matcher; the surface took only the tags, so every decision a
  human made through it — seal, seal-in-place, reject-match, queue seal and
  reject — was keyed with the process-wide default instead of the domain's own.
  Measured consequence, on a domain keying incident reports to the device serial
  they name: the human clicked seal, got a `200` and a valid signature, and the
  row that became sealed was a **second** row under a key her domain never
  computes. The draft she was sealing stayed queued, `best_sealed` for the exact
  wording she sealed returned `None`, and her recorded rejection was filed where
  nothing looks it up — so the wrong match was served again. Both promises this
  README leads with, void for any domain that took the Matcher seam at its word.

  `ui.App` now carries `matcher`, `nestor ui` takes `--matcher` for the shipped
  ones, and it is threaded through every decision the surface makes, including
  the cascade behind `/api/ask` (`translate_segment`, `translate_text`,
  `graduate_segment` and `reject_segment` all accept `matcher=` now). `None`
  still means *defer to the process-wide matcher*, so nothing changes for a host
  that never had this problem. `/api/state` reports which matcher is in force and
  where it came from — two surfaces keyed differently used to describe themselves
  identically, which is what kept this invisible. `/api/match` refuses a named
  matcher on a domain with its own rather than silently scoring under a different
  notion of similarity.

  The audit trail was correct throughout, which is the part worth sitting with: a
  hash chain cannot catch a true record of an answer nobody can reach.
  `IDEAS.md` §6.40, and §6.41 — which asked whether the optional `score()` should
  become mandatory — is answered by this rather than by promoting the method,
  and finished by the `--matcher` spec entry above.

  **The first version of this fix shipped three defects of its own**, found by an
  adversarial audit before merge and fixed here. They are listed because two of
  them are the same mistake the fix was for, one level up:

  - **`App.matcher` was applied to every request, including ones about another
    domain.** `/api/reject-match` is shared by every recipe, so the Entity view's
    reject started keying alias rejections with the *incident* domain's matcher —
    a human's "no", recorded and signed, filed where `EntityResolver` never
    looks. §6.40's own symptom, in the neighbouring recipe, caused by §6.40's fix.
    A matcher now applies only to the domain it describes; anything else defers
    to the process-wide default, which is what those recipes already used.
  - **The refusal broke the browser.** `/api/match` rejected any named matcher on
    a custom-matcher surface, and the Match view's picker is a `<select>` that
    always sends a value — so the panel returned a 400 blaming the caller for a
    field the page itself filled in. The page now shows the matcher's name
    instead of a picker and sends no name; the API accepts a name that agrees
    with the domain's matcher and refuses only a genuinely different one.
  - **The threading stopped at tier 1.** `Engine.translate` had no matcher
    parameter, so the shipped engines called `memory.lookup` with the
    process-wide one: in a custom domain the offline engine matched nothing, and
    every unsealed query landed `pending` and never entered the review queue.
    `Engine.translate` now takes `matcher=`, widened the same way `store=` was
    and tolerated the same way, so an engine written against the old signature
    still works.

  Also: `--matcher semantic` without the extra now refuses to start with a
  message instead of a traceback (and before the store is opened), and the Ask
  view shows which matcher is in force — the `/api/state` field added for that
  purpose went one release with nothing rendering it, which is the same defect
  one layer up.

### Changed

- `nestor ledger verify` numbers lines from 1. It counted from 0 and reported
  the third line of a damaged ledger as `line 2`, which sends the person acting
  on the message to the wrong line.

- Build requirement raised to `setuptools>=77` for PEP 639. The old
  `license = { text = "Apache-2.0" }` table still built but is deprecated, and a
  packaging change is the cheap moment to stop carrying it.

- `frank.WillowForwarder` reads `NESTOR_FRANK_APP_ID` before `WILLOW_APP_ID`
  when choosing the seat to call as. `WILLOW_APP_ID` is client-scoped — one
  value per shell for whatever seat that shell drives — so read first it
  silently re-seated the forwarder: a fleet shell set up for the orchestrator
  made Nestor call `frank_append` as `willow`, which willow-mcp refuses
  outright, and a correctly seated Nestor stopped mirroring the moment the
  fleet env was sourced. `WILLOW_APP_ID` still works on its own, so a seat
  named only that way is unaffected. `docs/local-fleet.md`.

### Not changed, and named so nobody assumes otherwise

- **No PyPI publish.** This release is pinnable by git ref only (`git+…@v0.2.0`);
  the distribution-name decision (`docs/releasing.md` Decision 1 — `nestor` is
  free on PyPI but taken on TestPyPI) is deferred to a later, deliberate publish.
- **No tag on this branch.** The version and changelog are prepared here, but the
  tag is the trigger and is cut on merge to `master` — pulling that trigger is
  not a thing a feature branch does on its own.
- **No ledger format version.** The store now carries a `user_version` (above),
  but the hash-chained ledger deliberately does not: it cannot be re-hashed under
  new rules, so its format is frozen by its first entry and versioning it is a
  larger, still-open argument — `IDEAS.md` §6.31.
