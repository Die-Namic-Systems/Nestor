# Fleet integration map — open IDEAS ↔ existing repos

*Scanned 2026-07-31 across `~/github/` (nestor, willow-mcp, kartikeya,
safe-app-store-public, redential-cli, engram, terpsi-music, oakenscrolls-office,
supporting docs). This is a wiring guide, not a commitment to integrate.*

Use with [`IDEAS.md`](../IDEAS.md) open items and [`TODO.md`](../TODO.md).

---

## §1.4 Seal staleness and quorum — **open**

| Fleet piece | What it already does | Nestor plug |
|-------------|----------------------|-------------|
| **`nestor.calibrate`** + `bench/bench_accuracy.py` | Measured false-verification rate vs threshold on *your* corpus | The honest “dial” story for §4.2; not time decay, but the right *kind* of rigor |
| **`safe-app-store` … `oakenscrolls-office`** | Append-only predictions; confidence graded when resolved; “does your 70% mean 70%?” | Model for **time + outcome** without deleting history (VOID, supersede) — opposite of `memory_delete` |
| **`safe-app-store` … `jarvis`** (`weakestProvenance`, provenance ladder) | Weakest-link provenance on recalled facts | UI pattern for “how much to trust this row” beside `servable` |
| **`docs/the-nestor-lineage.md`** | Names calibration + reconciliation + TM as one mechanic | Positioning ammo for regulated buyers (quorum = future policy) |

**Near win:** §6.10 is mostly UI product — `created_at` already appears on Memory rows (`ui_page.py`); add **relative age** or “sealed N days ago” and link to §1.4 without implementing decay.

---

## §2.4 Skip redundant `memory_init` — **open**

No other repo owns this; it is **`SqliteStore`-local**. The bounded WAL pool (§6.5) is already in nestor. A per-connection `schema_ready` flag is the only sensible plug — do not import from willow.

---

## §4.2 Category: AI verification, not translation memory — **open**

| Fleet piece | Plug |
|-------------|------|
| **`safe-app-store-public/docs/the-nestor-lineage.md`** §3–4 | Ready-made narrative: normalize → match sealed memory → serve/queue → ledger; “translation layer” is one recipe |
| **`stores/promote_check.py`** | Treats `nestor.matcher:Matcher` as the **semantic seam** for SAFE promotion — same story for external reviewers |
| **`redential-cli`** proof graph | Different domain (webhook/auth anchors), but same *category* language: structural evidence, not “we are accurate” |
| **`nestor` `calibrate` + bench** | “Here is your false-verification rate on your corpus” — use in README/QUESTIONS, not new code |

**Action:** Lift §3 of the lineage doc (or a shortened quote) into README or QUESTIONS §marketing — code already exists in another repo.

---

## §4.4 Bench as marketing asset — **open**

| Fleet piece | Plug |
|-------------|------|
| **`bench/README.md`** + committed **`bench/results/`** | Checkpointed, citable JSON; `--resume` story = seriousness |
| **`terpsi-music`** + **`bench/corpus_terpsi.py`** | Real-prose corpus; human-authored surfaces bench |
| **`demo/sixty_seconds.py`** | Scripted demo; §4.3 still wants a **recording** |
| **Lineage doc** | Cite-and-grade on almanac-data (51 entries) — parallel “we measure” story |

**Action:** One landing page or README section linking demo + one `bench/results/*.json` chart + terpsi dispersion — no new bench code required.

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

## §5.8 Asymmetric seal signatures (Ed25519) — **open**

| Fleet piece | Plug |
|-------------|------|
| **`willow-mcp` `egress_authorization.py`** | Production **Ed25519** sign/verify envelopes (`sign_envelope`, `verify_envelope`, scoped payload, no MCP signing surface) |
| **`kartikeya`** worker | Calls `ExecutorNetworkAuthorizer` before net — same “verify before act” shape as `ledger_preflight` |
| **`nestor.signing`** | Documents `sign_seal(..., key=)` seam for asymmetric upgrade |
| **`promote_check`** `verified_by != author` | Social quorum separate from crypto |

**Action:** Spec a `nestor.seal_envelope` parallel to willow net-auth (payload: norm, target, verifier, ts); reuse cryptography patterns from `egress_authorization`, not HMAC semantics.

---

## §6.7 Hot checkpoint / backup while open — **open**

| Fleet piece | Plug |
|-------------|------|
| **`nestor export`** / **`Curator.export`** | Correct backup semantics today |
| **`SqliteStore.close()`** | Checkpoint on UI shutdown |
| **`safe-app-store` docs** (visidata, sqlit) | Operator tooling to **inspect** live SQLite — companion to “don’t plain `cp`” |

**Action:** Thin CLI `nestor db checkpoint [--out path]` wrapping `wal_checkpoint` or `VACUUM INTO` — no fleet dependency.

---

## §6.8 `memory_init` replay — **open**

Nestor-only (see §2.4).

---

## §6.9 Subprocess test: UI refuses bad ledger interval — **open**

| Fleet piece | Plug |
|-------------|------|
| **`tests/test_cli.py`** `_run_cli_subprocess(["ui", "--help"])` | Pattern exists |
| **`tests/test_keyring.py`** `surface.main(...) == 2` on bad keyring | **Copy this** for `NESTOR_LEDGER_VERIFY_INTERVAL_SEC=5m` → exit 2 |

---

## §6.10 Seal age in provenance — **open**

| Fleet piece | Plug |
|-------------|------|
| **Memory UI** | Already shows `created_at` chips |
| **`source-trail`** (SAFE app) | Cite/log/verify sources — adjacent for *query* provenance, not seal rows |
| **§1.4** | Policy (decay/quorum) still open; display is not |

**Action:** Relative age + optional sort by `created_at`; defer decay to §1.4.

---

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

## Cross-cutting fleet hooks (not a single IDEAS §)

| Piece | Nestor touchpoint |
|-------|-------------------|
| **`safe-app-store` `promote_check.py`** | Nestor is a **worked promotion** example (`semantic_seam`: Matcher) |
| **`willow-mcp` `integration_list`** | Surface nestor/frank as an integration status line in ops docs |
| **`terpsi-music`** | Bench: `corpus_terpsi` + `PINNED_REV`; product: **`claude/coat-hat-check-p6obau`** store/records + ARCHITECTURE as Nestor **host** spec (see section above) |
| **Sync between instances** (`TODO.md` §2) | **No** continuous sync in fleet; `portable` import/export + human conflict queue remains the model; FRANK is audit sync, not data sync |

---

## Suggested priority (integration effort vs value)

1. **Docs-only:** §4.2 / §4.4 from lineage + bench results; §5.5 frank + `ledger head` runbook.
2. **Small code:** §6.9 subprocess test; §6.10 relative age in UI; §6.7 `db checkpoint` CLI.
3. **Large / design:** §5.8 Ed25519 (borrow willow-mcp envelope shape); §5.2 erasure (oakenscroll-style tombstones); §1.4 quorum policy.
