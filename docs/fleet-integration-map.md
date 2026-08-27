# Fleet integration map — open IDEAS ↔ existing repos

*Scanned 2026-08-27 across `~/github/` (nestor, willow-mcp, willow-grove,
kartikeya, safe-app-store-public, redential-cli, engram, terpsi-music,
oakenscrolls-office, supporting docs). This is a wiring guide, not a commitment
to integrate.*

Use with [`IDEAS.md`](../IDEAS.md) open items and [`TODO.md`](../TODO.md).

**Local wiring:** [`local-fleet.md`](local-fleet.md) — checkout script, `TERPSI_ROOT`,
`promote_check`, ledger head / `db checkpoint`.

**Household wiring:** [`local-agent-prototype.md`](local-agent-prototype.md) —
`~/.nestor` as the live trust root; git `docs/dogfood/nestor.db` stays an
all-draft reproducible artifact (`IDEAS.md` §6.123).

---

## §1.4 Seal staleness and quorum — **open**

| Fleet piece | What it already does | Nestor plug |
|-------------|----------------------|-------------|
| **`nestor.calibrate`** + `bench/bench_accuracy.py` | Measured false-verification rate vs threshold on *your* corpus | The honest “dial” story for §4.2; not time decay, but the right *kind* of rigor |
| **`safe-app-store` … `oakenscrolls-office`** | Append-only predictions; confidence graded when resolved; “does your 70% mean 70%?” | Model for **time + outcome** without deleting history (VOID, supersede) — opposite of `memory_delete` |
| **`safe-app-store` … `jarvis`** (`weakestProvenance`, provenance ladder) | Weakest-link provenance on recalled facts | UI pattern for “how much to trust this row” beside `servable` |
| **`docs/the-nestor-lineage.md`** | Names calibration + reconciliation + TM as one mechanic | Positioning ammo for regulated buyers (quorum = future policy) |

**Near win:** §6.10 relative age is shipped on Memory chips; §1.4 decay/quorum policy is still open.

---

## §2.4 Skip redundant `memory_init` — **shipped** (as §6.8)

No other repo owns this; it is **`SqliteStore`-local**. The bounded WAL pool (§6.5) is already in nestor. A per-connection `schema_ready` flag is the only sensible plug — do not import from willow.

Shipped 2026-08-06. The flag is an attribute on a `sqlite3.Connection` subclass, because the base class takes neither attributes nor weak references and an `id(conn)`-keyed set outlives the connection it names. `IDEAS.md` §6.8.

---

## §4.2 Category: AI verification, not translation memory — **shipped**

| Fleet piece | Plug |
|-------------|------|
| **`safe-app-store-public/docs/the-nestor-lineage.md`** §3–4 | Ready-made narrative: normalize → match sealed memory → serve/queue → ledger; “translation layer” is one recipe |
| **`stores/promote_check.py`** | Treats `nestor.matcher:Matcher` as the **semantic seam** for SAFE promotion — same story for external reviewers |
| **`redential-cli`** proof graph | Different domain (webhook/auth anchors), but same *category* language: structural evidence, not “we are accurate” |
| **`nestor` `calibrate` + bench** | “Here is your false-verification rate on your corpus” — use in README/QUESTIONS, not new code |

~~**Action:** Lift §3 of the lineage doc (or a shortened quote) into README or QUESTIONS §marketing — code already exists in another repo.~~

**Done 2026-08-06, but not that way.** The README section *The category — verification, not translation memory* was written fresh, not lifted: it was built in a cloud container with no fleet checkout on disk and no access to `safe-app-store-public`, so `the-nestor-lineage.md` could not be read, let alone quoted. If that doc says it better, this section should be reconciled against it by someone who can open both. `IDEAS.md` §4.2.

---

## §4.4 Bench as marketing asset — **partly** (README section shipped; no landing page, no chart)

| Fleet piece | Plug |
|-------------|------|
| **`bench/README.md`** + committed **`bench/results/`** | Checkpointed, citable JSON; `--resume` story = seriousness |
| **`terpsi-music`** + **`bench/corpus_terpsi.py`** | Real-prose corpus; human-authored surfaces bench |
| **`demo/sixty_seconds.py`** | Scripted demo; §4.3 still wants a **recording** |
| **Lineage doc** | Cite-and-grade on almanac-data (51 entries) — parallel “we measure” story |

**Action:** ~~One landing page or~~ README section linking demo + one `bench/results/*.json` chart + terpsi dispersion — no new bench code required.

**Done 2026-08-06:** the README half, as *Why the numbers are published* closing the Accuracy section — it links the demo and points at committed `bench/results/`. **Still open:** the landing page, the chart, and the terpsi dispersion, all of which want either a corpus checkout or a rendering surface this container does not have. `IDEAS.md` §4.4.

---

## §5.2 `memory_delete` / erasure — **open (deliberate)**

| Fleet piece | Lesson |
|-------------|--------|
| **`engram`** `mem_delete` / hard delete | **Anti-pattern** for Nestor: deletion without ledger design punches holes |
| **`oakenscrolls-office`** append-only + supersede | **Pattern:** retire without erasing; both values stay for audit |

**Plug:** Any erasure path should be designed like oakenscroll (tombstone + re-anchor), not copied from engram’s admin delete.

---

## §5.5 Ledger checkpoint somebody else holds — **open**

| Fleet piece | Plug |
|-------------|------|
| **`nestor.frank`** + **`willow-mcp` `frank_append` / `frank_verify`** | Already mirrors each local line with `local_hash` — **this is the shipped half** of “someone else remembers” |
| **`nestor.ledger.head` + `verify(expected_head=...)`** | Operator-held tip outside the file (CI, monitoring) |
| **`willow-mcp` Postgres FRANK chain** | Third-party-readable governance ledger |

**Action:** Document the **two-step** operator story: (1) `NESTOR_FRANK_STRICT` + forwarder for shared chain; (2) `nestor ledger head` in CI. Sidecar file is optional if FRANK + expected_head are enough.

---

## §5.8 Asymmetric seal signatures (Ed25519) — **shipped**

| Fleet piece | What shipped |
|-------------|----------------|
| **`nestor.keyring`** + `[keys]` extra | Per-verifier Ed25519 and HMAC; browser signer (Nestor#17); decisions `0074`/`0077`/`0078` |
| **`willow-mcp` `egress_authorization.py`** | Parallel envelope shape for fleet egress — borrow for future cross-repo tooling, not Nestor seals |
| **`promote_check`** `verified_by != author` | Social quorum separate from crypto |

**Operator story:** enrol a public key with `nestor keys add NAME --type ed25519 --public …`;
seal in `nestor ui` with the browser key; household store at `~/.nestor/keep/`
with `NESTOR_REQUIRE_SEAL_KEY=1`. See [`local-agent-prototype.md`](local-agent-prototype.md).

**Still open:** quorum / multi-party policy (§1.4) — crypto attribution shipped,
time-decay and N-of-M are not.

---

## §6.123 Household trust root + Grove seat — **shipped** (operator path)

| Piece | Role |
|-------|------|
| **`~/.nestor/keep/nestor.db`** | Live household memory — seals persist here, not in git dogfood |
| **`docs/local-agent-prototype.md`** | Cursor + Ollama + MCP pin the same paths |
| **`scripts/household_activate_sealed_dogfood.sh`** | Import a sealed export (`--from-db` or `--bundle`) into household (with backup); refuses `docs/dogfood/nestor.db` |
| **`safe-app-willow-grove`** (`grove_serve`, `resident_watcher`) | Operator seat at `:8766`; `nestor_client` calls household via MCP `nestor_ask` on `decision→decision` |
| **Decision `0215`** | Gate 5 watcher L1 ceiling at the Nestor seam |

**Still open in nestor:** reviewable `docs/dogfood/seals/<id>.json` folded at
`dogfood_store.py --rebuild` (§6.123 git seal-file shape). The household +
import path is the shipped answer for operators; the committed `.db` stays
all-draft by design.

---

## §6.7 Hot checkpoint / backup while open — **shipped**

| Fleet piece | Plug |
|-------------|------|
| **`nestor db checkpoint`** | In-place WAL flush; ``--out`` + ``<basename>.ledger.jsonl`` (``--no-ledger`` to omit) |
| **`nestor export`** / **`Curator.export`** | Portable bundle backup |
| **`SqliteStore.close()`** | Checkpoint on UI shutdown |
| **`docs/local-fleet.md`** | Operator runbook with fleet paths |

---

## §6.8 `memory_init` replay — **shipped**

Nestor-only (see §2.4). A per-connection flag on a `sqlite3.Connection`
subclass; measured 0.556 → 0.395 ms/op on a bare `add_pair` loop. No fleet
piece was involved, as §2.4 predicted.

---

## §6.9 Subprocess test: UI refuses bad ledger interval — **shipped**

`tests/test_cli.py` — child ``nestor.ui`` with malformed ``NESTOR_LEDGER_VERIFY_INTERVAL_SEC``.

---

## §6.10 Seal age in provenance — **shipped**

Relative age on Memory pair chips; full timestamp in ``title``. Policy (decay/quorum) still §1.4.

## `terpsi-music` — remote branches (2026-07-31)

**Remotes:** only `origin/main` (`d2817f2`, PR #15 merged) and
`origin/claude/coat-hat-check-p6obau` (`3b9bc9c`, **~121 commits ahead of
`main`**, no open PR). Merge-base with `main` is current `main` — the coat-hat
line is purely additive.

### What the branch is

Not a bench tweak — a **FERPA/COPPA youth-program stack** landed on the branch:

| Area | Branch contents | Nestor IDEAS plug |
|------|-----------------|-------------------|
| **`store/`** S-1 + S-2 | Postgres roles, migrations, RLS (`003_row_security.sql`), `session.py`, read/write/narration paths; **one read predicate in Python**, SQL policies compiled to match | Pattern for “guard in one place” (`test_store_differential.py` keeps SQL ↔ Python honest) — analogous to ledger tail vs full walk |
| **`records/`** | Predicates only (no writes); attendance, fees ledger, adjudication seams | **§5.2 erasure / tombstones** — fees ledger “aid invisible, nowhere to put a PAN”; append + lane model vs `memory_delete` |
| **`venue/`**, **`surfaces/`** | Readings, sourcing, serving tests | Future **Nestor consumer**: transcripts as **`draft` until sealed** (ARCHITECTURE §16, cites Nestor cascade) |
| **`tools/audit.py`**, **`conform.py`**, **`manifest.py`** | Eight-gate conformance; doc notes **Nestor + Jeles cleared same gates in SAFE #88** | Same promotion discipline as `promote_check.py` |
| **`docs/FLEET-READS.md`** | Tier-1 read list; **Nestor verified at `111c187`** (`Curator.servable`, seal states) | Living integration spec — **update pin** when nestor moves (fleet map is stale vs `5c377e6`) |
| **`docs/ARCHITECTURE.md`** | §14 component table: **EntityResolver**, **Reconciler**, seal cascade, `servable` | Direct map to nestor **recipes** (entity, numeric, tier-1 serve) — terpsi as **host app**, not duplicate engine |
| **`docs/PLAN-STORE.md`** | Store plan S-3+ still open (sealing, at-rest keys) | **§5.8** / lane sealing may eventually call `nestor.signing` or host-specific crypto |

### Bench corpus (`corpus_terpsi.py`)

- **`PINNED_REV = 6ea9b89`** is still an ancestor of **both** `main` and coat-hat;
  `docs/SKINS.md` and `craft/` prose paths still exist on the branch.
- **121 commits after the pin** change the *product* (store, records), not
  necessarily the extracted span JSON — re-run `bench_surfaces_human` with
  `corpus_revision` if you point `TERPSI_ROOT` at coat-hat instead of the pin.
- **Do not** assume `main` == old “music-only” tree; README on both tips is
  already the youth-program architecture doc.

### Integration direction (terpsi → nestor, not the reverse)

| Open Nestor IDEAS | Terpsi branch offers |
|-------------------|----------------------|
| §4.2 verification positioning | ARCHITECTURE §“engine called Nestor” + FLEET-READS confirmed rows |
| §1.4 / §6.10 provenance | L1–L5 ladder (`docs/SENSITIVITY.md`), seal vs confidence vs provenance split in ARCHITECTURE |
| §5.2 no delete | Lane model + draft writes + planned `invalid_at` ending (store header) |
| §5.5 external checkpoint | Guardian relay / aggregate export gating (§9 item 10 on branch) — **policy** parallel to FRANK, not same code |
| §4.4 marketing | Real domain story (minors, adjudication) **stronger** than bench prose alone — pair demo + terpsi narrative |

**Practical next step:** merge or PR-review `claude/coat-hat-check-p6obau` when store S-2 is stable; refresh FLEET-READS Nestor SHA to current `master`; keep bench pin at `6ea9b89` until a deliberate re-extraction.

---

## Fleet remote branches ↔ open IDEAS (2026-07-31)

*After `git fetch --prune` across `~/github/`. Full machine list:
`/tmp/fleet-remote-branches.json` (regenerate with the fleet scan script when stale).
**nestor** and **kartikeya** had no non-default remotes. Most leftovers are Dependabot,
merged CI branches, or upstream forks — not IDEAS expanders.*

### Strong fit — expands open IDEAS or host patterns

| Repo / remote branch | Open IDEAS | How it applies |
|----------------------|------------|----------------|
| **terpsi-music** `origin/claude/coat-hat-check-p6obau` (+61 vs `main`, no PR) | §1.4, §4.2, §4.4, §5.2, §5.5 (policy), §6.10 | Nestor **host** app: draft→sealed cascade, sensitivity ladder, append/lanes vs `memory_delete`; one Python read predicate + RLS (see terpsi section above). |
| **safe-app-store** / **public** `origin/claude/repo-test-run-a8lt94` (+3) | §4.2, §5.7, §5.8 | Branch-only `docs/design/app-forge.md`: D1 generalizes **`nestor/serve.py`** (MCP ask/propose, no seal); D4 rebuild `sap-gate` on **`nestor/signing` + keyring**. Design log, not nestor code. |
| **safe-app-store** `origin/feat/nest-seed-ai` (+3, diverged) | §1.1, §3.3 (analogy) | **nest-seed** embedding **margin** tier (`NEST_EMBED_MARGIN`) — different comparator than scalar TM margin; fleet counterexample only. |
| **willow-compose** `origin/claude/ledger-edges-propose-i5i6tr` (+2) | §5.5, fringe §1.4 | Sealed atoms+edges round; propose vs operator seal — governance graph parallel to FRANK, not Nestor `memory_*` chain. |
| **oakenscrolls-office** on **`master`** (stale remotes safe to prune) | §3.2, §4.4 | `almanac_seam` + tests: cite-and-grade → `resolver.seal()` as Nestor pairs; lineage cite-and-grade bench story. |

### On SAFE default branch (no remote branch required)

| Piece | Open IDEAS |
|-------|------------|
| **`stores/promote_check.py`**, **`docs/the-nestor-lineage.md`**, marching-arts Nestor cascade docs | §4.2, §5.2, promotion narrative |
| **`store_refit_plan.md`** — Nestor/Jeles passed gates #88, **no minted record yet** | §4.2 — run `promote_check.py --record` when ready |
| **`willow-mcp` `egress_authorization.py`** on default | Ed25519 envelope shape for fleet egress (Nestor seals: see §5.8 **shipped**) |

### Weak / indirect (hygiene unless you rescue the work)

| Repo / branch | Verdict |
|---------------|---------|
| **redential-cli** `docs/principle-2-amendment` (+2, diverged) | §4.2 *category* language only (vault anchor governance); no seal API. |
| **safe-app-store** `claude/task-1qugto`, `claude/willow-pg-lib-a5` | D8 vault / source-trail — adjacent §6.10; heavily behind default. |
| **willow-mcp** `claude/willow-mcp-pr-211-afy9xt` (+1) | Hook allow-side tests — meta-parallel to §6.9; merge or delete for willow-mcp, not nestor. |
| **corpus-lens** `claude/redential-cli-clone-f8hlu9` (stale) | Fail-closed egress — same *shape* as verify-before-act (§5.8). |
| **Dependabot** pillow/rapidfuzz on SAFE | No IDEAS link. |
| **Jeles** CI remotes (0 ahead) | Prune candidates; no nestor IDEAS. |
| **hermes-agent**, **mcp-memory-service**, draft **DispatchesFromReality** | Not nestor queue. |

### Open IDEAS with no meaningful remote expander

Stay **nestor-local** unless you import design from the rows above:

~~§6.8 skip `memory_init`~~ (shipped 2026-08-06, nestor-local as predicted) · §1.4 quorum/decay **policy** (terpsi/oakenscroll offer patterns, not implementations here) · ~~§5.8 Ed25519 seals~~ (shipped in nestor; willow-mcp envelope remains fleet egress).

---

## Cross-cutting fleet hooks (not a single IDEAS §)

| Piece | Nestor touchpoint |
|-------|-------------------|
| **`safe-app-store` `promote_check.py`** | Nestor is a **worked promotion** example (`semantic_seam`: Matcher) |
| **`willow-mcp` `integration_list`** | Surface nestor/frank as an integration status line in ops docs |
| **`terpsi-music`** | Bench: `corpus_terpsi` + `PINNED_REV`; product: **`claude/coat-hat-check-p6obau`** store/records + ARCHITECTURE as Nestor **host** spec (see section above) |
| **Sync between instances** (`TODO.md` §2) | **No** continuous sync in fleet; `portable` import/export + human conflict queue remains the model; FRANK is audit sync, not data sync |

---

## Suggested priority (integration effort vs value)

1. **Docs-only:** ~~§4.2~~ (shipped) / §4.4 landing page + chart still open; §5.5 frank + `ledger head` runbook; ~~§6.123 household path~~ (shipped — see [`local-agent-prototype.md`](local-agent-prototype.md)).
2. **Small code:** ~~§6.8 `memory_init` skip~~ (shipped); optional Memory sort by `created_at`; §6.25 `init_db` lineage ordering (one line, found while doing §6.8); grove `nestor_client` MCP + `NESTOR_HOME` pin (safe-app-willow-grove, operator-tested).
3. **Large / design:** §5.2 erasure (oakenscroll-style tombstones); §1.4 quorum policy; §6.123 git `seals/*.json` shape.
