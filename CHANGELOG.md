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

### Changed

- Build requirement raised to `setuptools>=77` for PEP 639. The old
  `license = { text = "Apache-2.0" }` table still built but is deprecated, and a
  packaging change is the cheap moment to stop carrying it.

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
