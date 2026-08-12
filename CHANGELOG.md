# Changelog

Notable changes, newest first. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**Nothing has been released.** `pyproject.toml` has said `0.1.0` since
`7fb841e`, the extraction commit, and there are no tags. So this file starts at
`Unreleased` and the first entry below it will be the first release there has
ever been — see [`docs/releasing.md`](docs/releasing.md).

This file records *releases*, not commits. The argument for a change lives in
[`IDEAS.md`](IDEAS.md), the queue in [`TODO.md`](TODO.md); a changelog entry is
the one-line version for somebody who has installed a version and wants to know
what moved.

---

## [Unreleased]

### Added

- **A cold open for `nestor ui`.** `nestor demo` (and `nestor ui --demo`) seed a
  small live store across all three recipes plus a short review queue, so a
  freshly cloned or `pip install`ed Nestor opens onto real content, not an empty
  desk. The browser page now greets a newcomer with a **front door** — a
  three-door welcome framed by audience — and carries **Nestor himself** in the
  header as a small robot whose expression tracks the verdict on screen (settled
  on a served seal, unconvinced on a draft, alarmed on a signature that does not
  verify). The **Memory** rows gained a status **lamp** and a bold
  **served / not-served flag**, so a row that says sealed but would be refused is
  visible at a glance. Stdlib-only and CSP-clean, as the page has always been.
  `IDEAS.md` §6.107.
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

- **No version bump.** `0.1.0` stands. What the first released version should be
  is a decision for whoever releases it.
- **No tag.** Creating one is the trigger, and pulling that trigger is not a
  thing this branch should do on its own.
- **No `pip install nestor` in the README.** It would be false today, and a
  README that lies about how to install is worse than one that omits it. It goes
  in with the first release, in the same commit.
- **No store schema version and no ledger format version.** Both are real gaps —
  `IDEAS.md` §6.31 — and both touch persistence and the audit chain, so they
  want deciding rather than stamping.
