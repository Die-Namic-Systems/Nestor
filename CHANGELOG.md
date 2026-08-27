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

## Unreleased

### Added

* **Warrants** — `nestor/warrant.py`, a `decision_warrants` table, the
  `warrants` storage capability, and the `attach_warrant` ledger kind. A pair
  can now record *why a stranger should believe it* — a `citation` (a named
  authority asserted it) or a `construction` (a recipe and the digest it must
  produce) — separately from who sealed it. `attestation` is not storable: a
  sealed pair already is one, and `warrants_for()` composes it in on read.
  Nothing marks a warrant satisfied; the store holds the recipe, never the
  verdict. See [`docs/warrants.md`](docs/warrants.md), IDEAS §1.10, decision 0164.

* **Warrants travel — bundle version 4.** An export carries the warrants on the
  pairs it carries, inside the integrity digest, and an import brings them in.
  The rule is *carry the warrant, never a conclusion about it*: import refuses
  every row `warrant.attach` refuses locally (an unknown kind, an empty
  authority, a construction with no expected digest — and `attestation`, which
  a bundle must never be able to assert without a signature), naming each
  refusal in the report instead of dropping it in silence. `nestor import`
  prints the counts and any refusals. See `docs/warrants.md` §4, IDEAS §1.10(c).

* **`nestor warrant attach|for`** — the terminal surface for the relation, which
  shipped without one. `for` lists the set a pair holds, including the
  `attestation` composed from its seal, marked as coming from the seal rather
  than from the warrants table. There is no `--kind attestation`: argparse
  refuses the word before a store is opened, because a seal is the only way to
  say a person here checked. There is deliberately no `report` subcommand the
  way `nestor evidence` has one — what "unwarranted" means is not settled, and
  a queue naming rows as lacking something is a definition of that something.

* **Provenance answers what a claim rests on.** `Curator.get` — what
  `answer.provenance` returns and what `nestor_provenance` serves over MCP —
  now carries the pair's `evidence` and its `warrants` (including the
  `attestation` composed from its seal) alongside its rejections. A store
  lacking either optional capability gets the key **omitted**, not empty:
  present-and-empty means "nothing attached", absent means "this store cannot
  say". Nothing here reports a warrant as satisfied. `best_sealed` and the
  served state are untouched — IDEAS §1.10(a) stays open. Decision 0167.

* **A served answer says *warranted how*** — IDEAS §1.10(a), the last of the
  warrants memo's three open questions, decision 0169. **`pending` stays:**
  `best_sealed` still gates on `sealed` and nothing else, so a cited-but-unsealed
  row is served exactly as often as before — never. What it gained is
  `warrant_kinds` for the row it *did* find, carried onto `Passage.meta`, through
  `answer.ask` to `nestor_ask` and `nestor ask`, and into the ledger's `passage`
  entry (a warrant attached tomorrow is not one this answer went out with).
  Ranked candidates in `matches` carry it too, so a `pending` answer can say that
  a row beside it is cited and merely unsealed here — next to the
  `servable: false` that was always there. There is no fourth state; `Passage.mark`
  still maps exactly three.

* **`nestor decision check` shows the commitment it matched.** A clear consult
  that found a recorded decision now prints it, its rationale, and whether it is
  draft or sealed. Exit codes are unchanged — clear still exits 0. Previously an
  exact match printed a line a glance could not tell from "nothing on record",
  with the commitment visible only under `--json`, so the consult this repo tells
  agents to run *before proposing* could answer "clear" over a recorded answer.
  Found by that happening, on §1.10(a) itself.

* **Provenance carries the seal's age** — IDEAS §1.4's own first suggestion,
  which had shipped in the browser and nowhere else (agent-log §6.116, decision
  0170). `Curator.get` — and so `answer.provenance` and `nestor_provenance` —
  gains `seal_age` for sealed rows: `{days, last, verifier, kind,
  uncorroborated_tail}`, read from the ledger and never from a column, with a
  `countersign` resetting the clock. Display only: no answer is withdrawn, no
  score moves, nothing expires, and a draft gets no key at all rather than a
  zero. `uncorroborated_tail` says when the freshest decision is the chain's
  final line — the one line the chain does not vouch for.

### Changed

* **`Curator.list()` renamed to `browse()`; the deprecated alias is removed.**
  The old name shadowed the `list` builtin inside the class body, forcing a
  `builtins.list` workaround on later method signatures. All internal callers
  migrated. Decision 0183.

* **Demo stores moved from `docs/` to `demo/`:** `llm-only-joke/`,
  `llm-only-jokes.md`, and `ideas-store/` now live alongside the other
  scripted demos. Internal paths updated. Decision 0182.

* **`scripts/ci-lint.sh` now enforces "match the workflow" instead of asserting
  it.** The five tool versions live in `scripts/lint-pins.txt`; the workflow
  installs from it and the script refuses to run against anything else, naming
  each differing tool. Measured cause: a local ruff one minor ahead of CI's pin
  reported 530 pre-existing findings on a tree CI called clean. Run
  `pip install -r scripts/lint-pins.txt` to sync. See agent-log §6.114,
  decision 0168.

### Fixed

* **Stale counts and missing help text across CLI, README, and docs.**
  README view table updated from four to seven (added Signals, Graph, Triage);
  MCP tool count updated from seven to eight (`nestor_prefs` was missing);
  `domain_args()` and five other CLI arguments gained `help=` text;
  duplicate paragraph removed from README; shoebox gap count corrected in
  project-layout.md. Decisions 0186–0187.

### Upgrading

* **This release changes the schema, so long-lived processes must be
  restarted.** `_SCHEMA` gains `decision_warrants`. Since IDEAS §6.8
  `memory_init` skips its work on a connection that has already done it, so a
  process holding warm pooled connections will **not** create the new table
  until it restarts — the store upgrades on process start, not on package
  upgrade (`docs/releasing.md`, "A release that touches the schema requires a
  restart"). Nothing breaks in the meantime: `nestor.warrant.attach` raises on
  a store without the capability rather than dropping the warrant, and every
  other path seals and serves exactly as before.

* **Bundles written by this build declare version 4 and older readers will
  refuse them.** Bundles *already written* are unaffected: version 1, 2 and 3
  still verify here, byte-for-byte, because the digest stays version-gated —
  a v3 payload is hashed over the v3 field set exactly as before. Upgrade the
  reader before sending it a v4 bundle.

---

## [0.14.0](https://github.com/Die-Namic-Systems/Nestor/compare/v0.13.0...v0.14.0) (2026-08-27)


### Added

* **corpus:** consolidate extracted stores into one inert lane ([3138664](https://github.com/Die-Namic-Systems/Nestor/commit/3138664a2007eea36576111e3580c8ceb76966f2))
* **corpus:** consolidate extracted stores into one inert lane ([#233](https://github.com/Die-Namic-Systems/Nestor/issues/233)) ([4351023](https://github.com/Die-Namic-Systems/Nestor/commit/435102361ed78b8f3db906975b5870c5eae147e1))


### Fixed

* **corpus:** document NESTOR_CORPUS_DIR and sync dogfood store ([b430a99](https://github.com/Die-Namic-Systems/Nestor/commit/b430a997e8f2830d306bf4496cb9c750aa3b54c8))
* **corpus:** make local fixture dependency explicit ([e110c63](https://github.com/Die-Namic-Systems/Nestor/commit/e110c63d9b39383d3459eb95b734a11eb24e7dc4))
* **docs:** deduplicate corpus source pin ([1912187](https://github.com/Die-Namic-Systems/Nestor/commit/1912187680130b0f129661eeab9bb1440ed7e4bc))
* **dogfood:** rebuild from tracked PR decisions ([2fd0277](https://github.com/Die-Namic-Systems/Nestor/commit/2fd0277d156d0553239808a58ca5ee2a902068df))


### Performance

* **test:** make verification cost explicit ([#227](https://github.com/Die-Namic-Systems/Nestor/issues/227)) ([bc80045](https://github.com/Die-Namic-Systems/Nestor/commit/bc80045d952072cff4b386d0c449c695c49f1524))

## [0.13.0](https://github.com/Die-Namic-Systems/Nestor/compare/v0.12.0...v0.13.0) (2026-08-26)


### Added

* **local-agent:** add bounded Ollama drafting ([7629e59](https://github.com/Die-Namic-Systems/Nestor/commit/7629e593c049c169854d5ea8e6c7f490268ab3ca))
* **local-agent:** add bounded Ollama drafting ([#225](https://github.com/Die-Namic-Systems/Nestor/issues/225)) ([3b9a68d](https://github.com/Die-Namic-Systems/Nestor/commit/3b9a68d31390b55b37345cbc49140a9d36354dde))


### Fixed

* **ui:** make browser-key bootstrap non-clobbering ([8a54845](https://github.com/Die-Namic-Systems/Nestor/commit/8a548454885019a4cf09815a1c6900874df18fcd))
* **ui:** make browser-key bootstrap non-clobbering ([#226](https://github.com/Die-Namic-Systems/Nestor/issues/226)) ([adeecf2](https://github.com/Die-Namic-Systems/Nestor/commit/adeecf28629927d1d136e0a8c89e03966747245f))

## [0.12.0](https://github.com/Die-Namic-Systems/Nestor/compare/v0.11.1...v0.12.0) (2026-08-26)


### Added

* **evidence:** promote demo.weakest into aggregate_provenance (decision 0207) ([f72baaa](https://github.com/Die-Namic-Systems/Nestor/commit/f72baaa51c8a9c8ef5afc2633fca33367eeb68f8))
* **evidence:** promote demo.weakest into aggregate_provenance (decision 0207) ([#223](https://github.com/Die-Namic-Systems/Nestor/issues/223)) ([5be8756](https://github.com/Die-Namic-Systems/Nestor/commit/5be8756be19879e589ac648b916de1faa3cb20f0))

## [0.11.1](https://github.com/Die-Namic-Systems/Nestor/compare/v0.11.0...v0.11.1) (2026-08-25)


### Fixed

* 203 (MCP domain fallback) + ship issue_probe for the meaning suite ([#205](https://github.com/Die-Namic-Systems/Nestor/issues/205)) ([7733f42](https://github.com/Die-Namic-Systems/Nestor/commit/7733f42691ba723e20f36d086f9d296395f3a7b2))
* 203: MCP nestor_ask & nestor_match get the CLI's store-aware domain fallback ([d4c9cdf](https://github.com/Die-Namic-Systems/Nestor/commit/d4c9cdfe374b115c01daeb860d2cafa439420270))

## [0.11.0](https://github.com/Die-Namic-Systems/Nestor/compare/v0.10.0...v0.11.0) (2026-08-24)


### Added

* **cli:** --version, shell completions, and uniform --json ([e6ffa53](https://github.com/Die-Namic-Systems/Nestor/commit/e6ffa53e56c6a947b2d966b076052bc986a272d9))
* getting into the 7s — CLI finish, ruff 0.16.3, preferences, onboarding ([#190](https://github.com/Die-Namic-Systems/Nestor/issues/190)) ([d74b049](https://github.com/Die-Namic-Systems/Nestor/commit/d74b049f0a225e049447e41e583b27647374c012))
* IDEAS §1.10(a) and §1.4 — warranted how, seal age in provenance, and step 2 finally run ([#186](https://github.com/Die-Namic-Systems/Nestor/issues/186)) ([2fbeccb](https://github.com/Die-Namic-Systems/Nestor/commit/2fbeccbf2309ecdb03a165c091ded37800594a20))
* **migrations:** ship the first real migration step — visibility on tm_pairs ([#187](https://github.com/Die-Namic-Systems/Nestor/issues/187)) ([145bf9b](https://github.com/Die-Namic-Systems/Nestor/commit/145bf9babfad0f87eec1d4d9ef12ce2fd74ba32e))
* **migrations:** ship the first real migration step — visibility on tm_pairs (§7.5, [#91](https://github.com/Die-Namic-Systems/Nestor/issues/91)) ([7e99723](https://github.com/Die-Namic-Systems/Nestor/commit/7e99723cb6d1f0c18b0be518df0afa14e56ffd35))
* **prefs:** per-user, cross-session preference store (§7.5 gap) ([a3296ea](https://github.com/Die-Namic-Systems/Nestor/commit/a3296eacad13ee928ebb1987927b33ed289e9a79))
* **staleness:** seal age reaches provenance, and step 2 finally ran (IDEAS §1.4) ([682bc9f](https://github.com/Die-Namic-Systems/Nestor/commit/682bc9fe38a62fcff58063830dd5028c3e006708))
* **testing:** add property-based tests for normalizer, matcher, and signing (§7.5) ([ca6141a](https://github.com/Die-Namic-Systems/Nestor/commit/ca6141ae0434c01f81ae52dc7b1e72f0dd1d4b42))
* **testing:** property-based tests for normalizer, matcher, and signing ([#188](https://github.com/Die-Namic-Systems/Nestor/issues/188)) ([415445e](https://github.com/Die-Namic-Systems/Nestor/commit/415445e2784f90a906f4294515037c9e3a231cec))
* **warrants:** a served answer says warranted how (IDEAS §1.10(a)) ([54dcc6d](https://github.com/Die-Namic-Systems/Nestor/commit/54dcc6d592cbbe032ea0f2a9ec7d7f5da7c43e22))
* **warrants:** carriage, a terminal, provenance — and the lint gate'… ([#185](https://github.com/Die-Namic-Systems/Nestor/issues/185)) ([8ed24bc](https://github.com/Die-Namic-Systems/Nestor/commit/8ed24bc2c7319d461ea656d73af28976ff9137ef))
* **warrants:** carriage, a terminal, provenance — and the lint gate's pins ([eae8f7a](https://github.com/Die-Namic-Systems/Nestor/commit/eae8f7adba83acebb2ff149cf34674b721cc7b34))
* **warrants:** the citation and construction relation (IDEAS §1.10) ([7f2612f](https://github.com/Die-Namic-Systems/Nestor/commit/7f2612f4af6c3f4a542b826c70242850912d01c0))
* **warrants:** the citation and construction relation (IDEAS §1.10) ([#184](https://github.com/Die-Namic-Systems/Nestor/issues/184)) ([4351998](https://github.com/Die-Namic-Systems/Nestor/commit/4351998e411c468336f619813f577ab1ed201e13))


### Fixed

* `nestor match` now uses the same store-aware domain fallback as `nestor ask`:
  on a non-`en→es` store it queries the largest domain instead of silently
  reporting zero candidates. Decision 0184.
* **ci:** guard hypothesis import so test_property.py is skipped when not installed ([7ae0423](https://github.com/Die-Namic-Systems/Nestor/commit/7ae04232af183091f57858302b846b99c7295852))
* **docs:** add §6.117 to the Map in IDEAS.md ([b9a6967](https://github.com/Die-Namic-Systems/Nestor/commit/b9a6967f0f773ecc1a7312cab44098c793cada33))
* **lint:** bump ruff pin to 0.16.3 and fix all 536 findings ([5b2b542](https://github.com/Die-Namic-Systems/Nestor/commit/5b2b5426dd31fb8cc351681202ab338f3771a583))
* **lint:** clean 3 ruff findings in test_ci_venv.py from PR 189 ([31c955d](https://github.com/Die-Namic-Systems/Nestor/commit/31c955d3e54fda4a0e63704163a86ce53388e32c))
* **lint:** remove noqa directives — importorskip is a recognized import guard ([eb7db57](https://github.com/Die-Namic-Systems/Nestor/commit/eb7db578530258cb394f0a19b9c2834e91c1c59c))
* **mypy:** add shtab to ignored optional imports ([54db617](https://github.com/Die-Namic-Systems/Nestor/commit/54db617060e952e3e204fef632b2dbf8ec3c9a48))

## [0.10.0](https://github.com/rudi193-cmd/Nestor/compare/v0.9.1...v0.10.0) (2026-08-19)


### Added

* **memory:** per-domain verifier policy, enforced at seal time ([dd366c6](https://github.com/rudi193-cmd/Nestor/commit/dd366c623c8d0297cc7406ab8b7f7da512556775))
* **memory:** per-domain verifier policy, enforced at seal time ([#169](https://github.com/rudi193-cmd/Nestor/issues/169)) ([367700b](https://github.com/rudi193-cmd/Nestor/commit/367700bd08ff3c61be5b7d5e89e96720c5bb0932))

## [0.9.1](https://github.com/rudi193-cmd/Nestor/compare/v0.9.0...v0.9.1) (2026-08-19)


### Fixed

* **cli:** nestor ask matches its default domain to the store ([dac3c91](https://github.com/rudi193-cmd/Nestor/commit/dac3c915b6e38aa8c030d8c1f35d9bd969069085))
* **cli:** nestor ask matches its default domain to the store ([#168](https://github.com/rudi193-cmd/Nestor/issues/168)) ([4a8dabd](https://github.com/rudi193-cmd/Nestor/commit/4a8dabd1d4314e336cf61ad53d4d629ab79d7dc4))

## [0.9.0](https://github.com/rudi193-cmd/Nestor/compare/v0.8.3...v0.9.0) (2026-08-19)


### Added

* **ui:** a review you can finish, and a tab that says why it is empty ([#159](https://github.com/rudi193-cmd/Nestor/issues/159)) ([5ad53bb](https://github.com/rudi193-cmd/Nestor/commit/5ad53bbc411a0cf08765294622e97e32f846cc4f))
* **ui:** atomic-age panels, rendered reasons, and an origin you can open ([2b527da](https://github.com/rudi193-cmd/Nestor/commit/2b527da005141d9ce1bfbbd40e39e4ca009b7b10))
* **ui:** the review has a bottom, and a decided row leaves the list ([01c155d](https://github.com/rudi193-cmd/Nestor/commit/01c155dd184d3ed89fcfd1de6625d3d8cdecb68e))


### Fixed

* **ui:** a tab with nothing in it says why, not that the work is done ([56019a7](https://github.com/rudi193-cmd/Nestor/commit/56019a70a6706bc36d979dea9c1e23e80ad70b6c))

## [0.8.3](https://github.com/rudi193-cmd/Nestor/compare/v0.8.2...v0.8.3) (2026-08-19)


### Fixed

* **survey:** a repo identity is its remote, not the directory it sits in ([#153](https://github.com/rudi193-cmd/Nestor/issues/153)) ([46a2bd3](https://github.com/rudi193-cmd/Nestor/commit/46a2bd31d76668d0cf86a6039c24d7d09524704a))
* **survey:** a repo's identity is its remote, not the directory it sits in ([0423fd5](https://github.com/rudi193-cmd/Nestor/commit/0423fd50d1fa6454cad8a98d3f89dcd38d2c02ec))

## [0.8.2](https://github.com/rudi193-cmd/Nestor/compare/v0.8.1...v0.8.2) (2026-08-19)


### Fixed

* deduplicate staleness logic, cap reverification endpoint, ship ui_pure.js ([dac48ca](https://github.com/rudi193-cmd/Nestor/commit/dac48ca4f435fe3c6908b4ca615a1c1e43427c14))
* deduplicate staleness logic, cap reverification endpoint, ship ui_pure.js ([#150](https://github.com/rudi193-cmd/Nestor/issues/150)) ([6aabde3](https://github.com/rudi193-cmd/Nestor/commit/6aabde3a8136a16a563f95b842082495bf2fc278))

## [0.8.1](https://github.com/rudi193-cmd/Nestor/compare/v0.8.0...v0.8.1) (2026-08-19)


### Build

* **mypy:** an installed extra must not move the type gate's verdict ([ecb6217](https://github.com/rudi193-cmd/Nestor/commit/ecb6217bf7ff9507a9d5cabcc1f4e565c797597c))

## [0.8.0](https://github.com/rudi193-cmd/Nestor/compare/v0.7.0...v0.8.0) (2026-08-18)


### Added

* GET /api/due-for-reverification — aged seals as a read-only UI surface (IDEAS §6.49) ([4e4c7d0](https://github.com/rudi193-cmd/Nestor/commit/4e4c7d0388f3c66d9ad22e24df9ee7d432459a18))
* IDEAS batch 5 — staleness API, eight status updates ([#146](https://github.com/rudi193-cmd/Nestor/issues/146)) ([3e867d5](https://github.com/rudi193-cmd/Nestor/commit/3e867d513f6b6960f3eb4c68485787c9e22ba339))

## [0.7.0](https://github.com/rudi193-cmd/Nestor/compare/v0.6.2...v0.7.0) (2026-08-18)


### Added

* EntityResolver.propose() — draft alias without seal (IDEAS §6.39) ([6eb84ad](https://github.com/rudi193-cmd/Nestor/commit/6eb84adc6c27a1b54a5ff10cc38c0a9ffd35ba36))
* IDEAS batch 4 — EntityResolver.propose(), JS test harness, three status updates ([#144](https://github.com/rudi193-cmd/Nestor/issues/144)) ([7f1e97f](https://github.com/rudi193-cmd/Nestor/commit/7f1e97ffd98fbd3c5e6ff298d4513437f3f031a1))

## [0.6.2](https://github.com/rudi193-cmd/Nestor/compare/v0.6.1...v0.6.2) (2026-08-18)


### Fixed

* isolate bench and audit scripts from ambient keyring (IDEAS §6.98) ([29b8205](https://github.com/rudi193-cmd/Nestor/commit/29b820569c0d6b6d186af01835caec36cffba218))
* isolate bench/audit scripts from ambient keyring + status corrections (IDEAS §6.x batch 2) ([#141](https://github.com/rudi193-cmd/Nestor/issues/141)) ([8a7652c](https://github.com/rudi193-cmd/Nestor/commit/8a7652c45e8711b11d2514c644df460baec238db))

## [0.6.1](https://github.com/rudi193-cmd/Nestor/compare/v0.6.0...v0.6.1) (2026-08-18)


### Fixed

* glossary locks_in_text uses word-boundary matching (IDEAS §6.38) ([ee67645](https://github.com/rudi193-cmd/Nestor/commit/ee67645efd6f9f699f401244d3455901a587fa42))
* glossary word-boundary matching (IDEAS §6.38) ([#138](https://github.com/rudi193-cmd/Nestor/issues/138)) ([3cc1bb6](https://github.com/rudi193-cmd/Nestor/commit/3cc1bb61caa703866fd07d6f5dcedee64062c3a5))

## [0.6.0](https://github.com/rudi193-cmd/Nestor/compare/v0.5.0...v0.6.0) (2026-08-18)


### Added

* fuzzy constraints_on — recover re-worded decisions (IDEAS §6.33/6.94/6.106) ([daf21a8](https://github.com/rudi193-cmd/Nestor/commit/daf21a8175f7add5c5733f0df5b399f4926a3da0))
* fuzzy constraints_on — recover re-worded decisions (IDEAS §6.33/6.94/6.106) ([#135](https://github.com/rudi193-cmd/Nestor/issues/135)) ([d4f166d](https://github.com/rudi193-cmd/Nestor/commit/d4f166d1ecd4cbd61ebbc0302a4f301e322d20d4))

## [0.5.0](https://github.com/rudi193-cmd/Nestor/compare/v0.4.0...v0.5.0) (2026-08-17)


### Added

* nestor evidence for &lt;pair&gt; — read a pair's attached references ([ae95718](https://github.com/rudi193-cmd/Nestor/commit/ae9571832f81012c706557c2794b2e9eb8b7e2bd))
* nestor evidence for &lt;pair&gt; — read a pair's attached references ([#131](https://github.com/rudi193-cmd/Nestor/issues/131)) ([a18abd0](https://github.com/rudi193-cmd/Nestor/commit/a18abd064193c55e89608ac9c4f385be7e338dd4))

## [0.4.0](https://github.com/rudi193-cmd/Nestor/compare/v0.3.2...v0.4.0) (2026-08-16)


### Added

* **cli:** nestor init first-run wizard ([7ff8759](https://github.com/rudi193-cmd/Nestor/commit/7ff8759d148c7b81f81a98f6d659d022683a8357))
* **hooks:** advisory cross-session collision awareness ([#111](https://github.com/rudi193-cmd/Nestor/issues/111)) ([350ff55](https://github.com/rudi193-cmd/Nestor/commit/350ff5512c1b2e6be3293354b2e38151952d1a69))


### Fixed

* **ci:** one secret-scan exclusion list, shared by ci-lint.sh and the workflow ([f5f5f2d](https://github.com/rudi193-cmd/Nestor/commit/f5f5f2d041f70e8968a7b07611e8e7787e4c33bc))
* **hooks:** the self-grant tripwire no longer denies a read-only decision consult ([39563cd](https://github.com/rudi193-cmd/Nestor/commit/39563cd7c96e1b2ca39078f009ebdceed879a2c5))
* **mypy:** ignore cryptography imports so the keys-absent lint job passes ([44a4f23](https://github.com/rudi193-cmd/Nestor/commit/44a4f23ef8898458e9f5bed718fae2ba8b641627))
* **ui:** route detailPanel's card assembly through appendKids, not a per-call filter ([da7e475](https://github.com/rudi193-cmd/Nestor/commit/da7e475c1afe501d4a0fcd8bed5aa5c9c72c4994))


### Build

* add mypy type gate to ci-lint (IDEAS §7.5) ([6b5721f](https://github.com/rudi193-cmd/Nestor/commit/6b5721f2aaa81772cea379add37272af92368e47))

## [0.3.2](https://github.com/rudi193-cmd/Nestor/compare/v0.3.1...v0.3.2) (2026-08-16)


### Build

* the git tag becomes the version, and Nestor gets its own household root ([#120](https://github.com/rudi193-cmd/Nestor/issues/120)) ([7c8dede](https://github.com/rudi193-cmd/Nestor/commit/7c8dedeb5dc23111b119817cb431f47a6b7119f8))
* the git tag becomes the version, and release-please cuts it ([8303b34](https://github.com/rudi193-cmd/Nestor/commit/8303b347c5499ac6586cb3dead3a682f2131ea93))

## [Unreleased]

> From here on this section is written by `release-please` from
> conventional-commit prefixes, not by hand. See `docs/releasing.md`.

### Build

- **The git tag is now the version.** `pyproject.toml` moves from setuptools
  with a literal `version = "0.3.1"` to `hatchling` + `hatch-vcs` with
  `dynamic = ["version"]`, matching willow-mcp, kartikeya and jeles. Nothing in
  the tree carries a version number, so there is no bump commit and no second
  copy to forget — the failure kartikeya's v0.0.8 shipped, where a tag built a
  different version and only PyPI's duplicate-upload refusal noticed.

  Off a tag, a build produces `X.Y.Z.devN+g<sha>`, which PyPI rejects outright.
  `publish.yml` now checks out with `fetch-depth: 0` and `fetch-tags: true`, and
  compares the tag against the **built artefact** rather than a pyproject
  literal that no longer exists.

- **Release automation: `release-please`.** `release-please.yml` keeps an open
  release PR carrying the next version and its changelog section, cuts the tag
  when it merges, and the tag push starts `publish.yml`. It refuses to run
  without `RELEASE_PLEASE_TOKEN` rather than falling back to `GITHUB_TOKEN` —
  that fallback opens a healthy-looking release PR and then silently publishes
  nothing, because GitHub suppresses workflow runs for events generated with the
  default token.

- **`pr-title.yml`.** This repo merges with merge commits, so GitHub writes the
  PR title into the merge commit body and release-please parses it. The gate
  fails a title that would cut a release its commits would not, and the reverse:
  a release for a PR that touches nothing under `nestor/` or `pyproject.toml`.
  It reads the release-cutting types out of `release-please-config.json` rather
  than restating them.

### Fixed

- **`publish.yml`'s environment URL named the wrong project.** It pointed at
  `https://pypi.org/p/nestor` — this project's own reserved-and-empty name from
  before the 0.3.0 rename — for two releases after the rename. The distribution
  is `nestor-meaning`. Cosmetic (the OIDC claim exchange matches on owner,
  repository, workflow filename and environment, never on this URL) but it is
  the link a reviewer follows out of a release run. Same rename fallout as
  decision `0129`; now covered by a test that derives the expected URL from
  `pyproject.toml`.

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
