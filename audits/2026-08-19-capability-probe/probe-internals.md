# Nestor internals probe — findings

Scope: `data/nestor-demo.db`, `nestor init`/`demo`, Python API surface beyond
the CLI, and store internals. ~30 commands run against the checked-in repo
(read-only) and a scratch copy under
`/tmp/claude-0/.../scratchpad/probe1/` (write experiments).

## 1. SQLite schema (`data/nestor-demo.db`)

Seven tables, no ORM — hand-written schema in `nestor/sqlite_store.py`:

- **`tm_pairs`** — the translation-memory / generic key-value seal table.
  Columns: `id, source_text, source_norm, source_lang, target_text,
  target_lang, status, verifier, weight, origin, created_at, seal_sig,
  reason, superseded_by`. `source_lang`/`target_lang` are overloaded as
  **generic domain tags**, not just human languages — e.g. in the demo db a
  row has `source_lang='entity', target_lang='entity'` (an entity alias) and
  another has `source_lang='q3-revenue', target_lang='value'` (a numeric
  baseline). One table backs translations, entity resolution, and numeric
  reconciliation.
- **`tm_rejections`** — recorded "no"s, keyed by `query_norm` + langs, with a
  `reopen_when` column ("never" vs "not yet" — empty means permanent, a
  condition string means the rejection is reopenable).
- **`tm_embeddings`** — cached embedding vectors per `(pair_id, model_name)`,
  each with its own `sig` (HMAC), separate from `seal_sig`.
- **`decision_edges`** / **`decision_evidence`** — a decision graph (nodes are
  presumably `tm_pairs` rows elsewhere; these are edges/evidence attachments)
  with their own `edge_sig`. Both empty in the demo db (0 rows).
- **`documents`** / **`segments`** — the tier-3 human-review queue (a document
  broken into segments with `jeles_score`, `candidate`, `status`).

Lineage columns on `tm_pairs` (`reason`, `superseded_by`) and reopenable
rejections (`reopen_when`) are recent additions per inline schema comments
referencing `docs/decision-memory.md` N3-N5.

## 2. Seals vs. the ledger — data actually looks like

`data/nestor-demo.db` has 9 `tm_pairs` rows: 8 `status='sealed'`, 1 `draft`,
verifier `rita` on every seeded row. **Every `seal_sig` is the empty
string** — `nestor stats` confirms why: `seal signatures: OFF — stored status
is trusted` (no `NESTOR_SEAL_KEY` set). So "sealed" in the demo store is
*only* a trusted column value, not a cryptographic proof — exactly the
Nestor#2 gap `nestor/signing.py`'s docstring describes, left deliberately
open by default (opt-in HMAC/ed25519).

The **ledger file** (`data/nestor-demo.ledger.jsonl`, 15 lines) is a
hash-chained append log, each entry carrying `prev` = SHA-256 of the previous
entry, `kind` (`seal`, `entity_seal`, `baseline_seal`, `passage`), and enough
fields to reconstruct what happened but not the full row (e.g. `seal` entries
carry `pair_id`/`verifier`/`source_sha` — a hash of the source text, not the
text itself). `nestor ledger verify` on the demo pair confirms `✓ intact — 15
entries`.

So: the **DB table** is current-state ("what does Nestor believe right now,
and can it be superseded"), the **ledger** is the append-only history of how
it got there (including entries the DB no longer needs, e.g. one `passage`
kind for offline-TM matches under tier 0/1/2 with `state` values
`pending`/`draft`/`sealed` that don't necessarily correspond to a `tm_pairs`
row at all). `data/ledger.jsonl` (10 lines, separate file, different genesis)
is a second independent chain — apparently the default `--ledger
data/ledger.jsonl` used by ad hoc `nestor` invocations in this checkout,
distinct from the demo-specific `nestor-demo.ledger.jsonl`.

## 3. `nestor init --help` / behavior

```
usage: nestor init [-h] [--yes] [--question QUESTION] [--commitment COMMITMENT] [--rationale RATIONALE]
```

Ran `nestor init --yes` against a scratch DB. It is a **3-step scripted demo**,
not a config wizard:
1. asks a canned question ("Should this team review PRs same-day or
   next-day?"),
2. reports that nothing matched (there is nothing to match yet),
3. writes one `status='draft', verifier='(none)'` row and says explicitly
   this is as far as it goes — sealing requires `nestor ui` by a human.

No files, keys, or config get created beyond the DB/ledger themselves; it's
purely a scripted "propose a draft" walkthrough that reinforces the governance
model in prose every time it runs.

## 4. `nestor demo`

`nestor --db X demo` seeds 12 rows: "4 sealed + 1 draft translation, 2 entity
alias(es), 2 numeric baseline(s), 3 segment(s) awaiting review." Ran it twice
into two fresh files (`demoA.db`, `demoB.db`): **content is deterministic**
(same source/target text, same statuses, same verifier `rita`, same domain
tags) but **not byte-identical** — `id` columns are random UUID4s and
`created_at` timestamps differ per run, so the ledger hash chains differ too.
Re-running `nestor demo` against an **already-seeded** file is a guarded no-op:
`"probe1/demoA.db already has content — not seeding (delete it to reseed)."`
— confirmed row count stayed at 9 (well, `tm_pairs`=9 after reseed attempt,
matching the original demo db's mix) after a second `demo` call.

## 5. Python API surface beyond the CLI

`python -c "import nestor; dir(nestor)"` exposes far more than the 17 CLI
subcommands: `Curator`, `Reconciler`, `EntityResolver`, `Matcher`,
`StringMatcher`, `NumericMatcher`, `Passage`, error classes
(`ConflictingDraftError`, `ConflictingSealError`, `RejectedPairError`,
`NestorError`), plus module-level functions `graduate_segment`,
`reject_match`, `reject_pair`, `reject_segment`, `translate_segment`,
`translate_text`, `supports_curation`, `supports_rejection`,
`set_bilingual_loader`, `set_frank_forwarder`, `set_ledger_path`,
`set_matcher`, `set_store`, `get_matcher`, `get_store`.

**No `nestor.engine.NestorEngine` class exists** (the task prompt's suggested
name is wrong) — `nestor/engine.py` instead exposes `ClaudeEngine`,
`OfflineEngine`, `get_engine(name='auto')`, `system_prompt()`, and a `Draft`
dataclass. `Draft` is deliberately field-limited (`text`, `engine`,
`confidence`) — no `state`/`verified`/`seal_sig` field, by design: "an engine
cannot mark its own output verified because it has nothing to mark it with."

**`nestor.curator.Curator` and `nestor.reconcile.Reconciler` have no CLI
subcommand at all.** The 17 top-level CLI verbs
(`ask,resolve,check,match,decision,evidence,export,db,import,ledger,
calibrate,keys,rejections,stats,demo,init,ui,serve`) do not include
`curate`/`reconcile`/`unseal`. `Curator` (see `nestor/curator.py`) is a
Python-only surface for browsing sealed memory, checking `signature_valid` vs.
`servable` per row (a sealed row whose HMAC doesn't verify is invisible to
`memory_stats` but is the first thing `Curator.list()` flags), unsealing rows
back to draft, and reading `rejection_signals()` (aggregate "no" patterns).
`Reconciler` is the numeric-baseline domain recipe (`seal_baseline` /
`check`), also Python-API-only.

## 6. `nestor/` package structure (34 top-level modules)

```
answer.py       calibrate.py    cascade.py      cli.py          cloud_seal.py
config.py       curator.py      decision.py     embedding_store.py  engine.py
entity.py       errors.py       evidence.py     frank.py        glossary.py
home_init.py    home_paths.py   keyring.py      langid.py       ledger.py
matcher.py      memory.py       ollama_embed.py onboarding.py   persona.py
portable.py     reconcile.py    seed.py         segment.py      semantic_matcher.py
serve.py        signing.py      sqlite_store.py staleness.py    storage.py
ui.py           ui_page.py
```
plus `nestor/vendor/` and `nestor/triage/`.

Notable modules with real logic but **no direct CLI verb**:
- `cloud_seal.py` — an opt-in "provisional seal from the cloud" path gated on
  an external `willow-gate` package (fails closed/absent by default — "Nestor
  core stays zero-dependency"). Explicitly distinguishes *provisional* seals
  (agent-signed, session-bound) from *canonical* ones (only conferred by a
  human-held key at "the home end").
- `frank.py` — an injectable forwarder (`set_forwarder`) that mirrors every
  local ledger entry into `willow-mcp`'s external governance ledger over MCP.
  Off by default; failures are swallowed unless `NESTOR_FRANK_STRICT=1`.
- `persona.py` — governs only Nestor's *refusal* voice ("I do not know," "a
  machine wrote this") — explicitly firewalled by a test
  (`TestTheEngineCannotReachThePersona`) from `engine.system_prompt`, so the
  translation-output voice and the refusal voice can never merge.
- `keyring.py` — per-verifier signing keys (so a seal proves *who*, not just
  *that a key existed*), with an explicit `compromised=True/False` fork on
  revocation (rotate quietly vs. mark everything that key ever signed as
  unverifiable).
- `staleness.py`, `langid.py`, `evidence.py`, `decision.py`, `calibrate.py` —
  each backs one CLI verb (`decision`, `evidence`, `calibrate`) or an internal
  concern (staleness/langid) with more granular functions than the CLI
  exposes as flags.

## 7. `nestor/storage.py` — the `Storage` Protocol (store-agnostic contract)

`Storage` is a `runtime_checkable` `Protocol` (not an ABC) with **23 required
methods**, so any object structurally matching it — SQLite-backed or not — is
a valid store: `init_db`, `create_document`, `get_document`,
`update_document_status`, `create_segment`, `get_segment`, `list_documents`,
`list_segments`, `update_segment_status`, `memory_init`, `memory_find`,
`memory_insert`, `memory_seal`, `memory_unseal`, `memory_candidates`,
`memory_get`, `memory_list`, `memory_reject_pair`, `memory_add_rejection`,
`memory_rejections`, `memory_list_rejections`, `memory_rejections_for_pair`,
`memory_stats`. `nestor/sqlite_store.py`'s `SqliteStore` is the only shipped
implementation (1088 lines) and has *more* methods than the Protocol requires
(lineage/edges/evidence/embedding helpers: `memory_lineage`,
`memory_add_edge`, `memory_edges_to/from`, `memory_seal_edge`,
`memory_add_evidence`, `memory_evidence_for`, `memory_unevidenced_seals`,
`embedding_load/save/drop`, `memory_mark_superseded[_if]`,
`memory_set_reason`, `checkpoint_wal`, `backup_into`) — i.e. `Storage` is the
*minimum* contract, `SqliteStore` is a superset, and swapping in a
non-SQLite backend (e.g. for `Curator`/`Reconciler`) only needs the Protocol
subset via `require_capability()`/`supports_curation()`/`supports_rejection()`
checks in `storage.py`.

`memory_unseal(pair_id, verifier, reason)` — clears `seal_sig`, flips
`status` back to `draft`, and stamps `origin='unsealed:<verifier>:<reason>'`
(comment: a `draft` row that still carried a *valid* signature would be "a
seal waiting to be reactivated by anything that flips the status column back",
so the signature is deliberately destroyed, not just hidden). Called only from
`curator.py` and `reconcile.py` — never from `cli.py`.

## 8. `dir(nestor)` — see §5 above (full list captured).

## 9. Determinism of `nestor demo` — see §4. Deterministic content, random
IDs/timestamps, idempotent against an already-seeded file.

## 10. `--db /dev/null`, `--db :memory:`, nonexistent parent dir

- **`--db ":memory:"`** works cleanly: `nestor stats` reports `0 pair(s)`, `no
  domains yet`, `ledger: ✓ no ledger yet`. (Passed straight through to
  `sqlite3.connect(":memory:")`.)
- **`--db /dev/null`** is an **unhandled crash**, not a graceful error:
  ```
  sqlite3.OperationalError: disk I/O error
    File ".../nestor/sqlite_store.py", line 500, in init_db
    File ".../nestor/sqlite_store.py", line 485, in _apply_schema
  ```
  raised out of `SqliteStore.init_db()` → `_apply_schema()` with a raw
  Python traceback reaching the terminal — no `NestorError` wrapping, no
  friendly CLI message. A rough edge worth flagging.
- **Nonexistent parent directory** (`--db /nonexistent-dir/x.db`): works
  silently — the directory (and the 100KB-ish empty-schema db file) get
  auto-created; `nestor stats` reports `0 pair(s)` normally. So `--db`
  auto-creates missing parent directories but does not handle a non-regular
  file target like `/dev/null`.

## 11. Domain system / matcher plugin surface

`nestor match --help` / `nestor export --help` both document `--matcher`:
> "the matcher that keys this domain: a shipped name (string, numeric,
> semantic, ollama) or **a custom one as `module:attribute`**, e.g.
> `acme.incidents:SERIALS`"

So beyond the three matchers visible in the demo ledger (`StringMatcher` for
`en→es` translation, implicit `NumericMatcher` for the `value` domain,
`entity` domain via `EntityResolver`), there are two more shipped matcher
kinds not present in the demo data: **`semantic`** (`nestor/semantic_matcher.py`
— `SemanticMatcher`, embedding-based, cosine similarity, requires `fastembed`
and gates on `integration_tests_enabled()`) and **`ollama`**
(`nestor/ollama_embed.py`, presumably a semantic matcher backed by a local
Ollama embedding model instead of `fastembed`). Plus an arbitrary
**dotted-path plugin loader** (`module:attribute`) that lets a caller point
`--matcher` at any importable object — i.e. the domain/matcher system is
designed to be extended without modifying Nestor itself, keyed generically off
`source_lang`/`target_lang` string tags rather than a fixed enum of domain
types.

`nestor.signing` explicitly documents a *third* MAC'd protocol beyond seals
and rejections: **cached embedding vectors** are also HMAC'd (`tm_embeddings.sig`,
separate from `seal_sig`), because under `SemanticMatcher` the vector itself
is part of what gets served, so a store-writer must not be able to swap the
vector out from under a still-valid seal.

## 12. Governance/hook side-finding (unplanned but relevant to "internal
architecture")

This repo's `.claude/settings.json` wires a `PreToolUse` hook
(`hooks/before_authority.py`, the "self-grant tripwire") on every `Bash` call
that denies commands which could *mint sealing authority* (`nestor keys add`
without `--public`, assigning `NESTOR_SEAL_KEY`/`NESTOR_KEYRING`/
`NESTOR_CACHE_KEY`, `nestor import --apply --verifier`, or any command
containing both `sqlite3` and a seal-write pattern). Confirmed a **false
positive**: a Python one-liner doing `import sqlite3; ...select id, status,
verifier, seal_sig ...` (a pure read) was denied, because
`hooks/before_authority.py`'s `_SQLITE_RE = re.compile(r"\bsqlite3\b")` matches
the *Python module name* `sqlite3`, not just the `sqlite3` CLI binary, and its
`_SEAL_WRITE_RE` matches the literal substring `status=` / `'sealed'` /
`seal_sig` anywhere in the command text — including inside a read-only SELECT
column list. Removing those columns from the query (`select id from
tm_pairs`) let the identical connection succeed. This is a real rough edge in
an otherwise carefully-designed guard (the module's own docstring
acknowledges "fail closed on subject, open on our own bugs" as the design
intent, but this rule's blast radius includes ordinary read queries whenever
the query happens to select the `verifier`/`seal_sig`/`status` columns by
name from a Python script). Separately confirmed `hooks/before_bash.py` (the
destructive-command guard: `rm -rf /`, `dd`, `mkfs`, `git reset --hard`, secret
path reads, etc.) is a distinct, more carefully normalized guard and did not
fire on any read-only commands used in this probe.

## Files referenced
- `/home/user/Nestor/nestor/sqlite_store.py` — schema + `SqliteStore` (1088 lines)
- `/home/user/Nestor/nestor/storage.py` — `Storage` Protocol, capability checks
- `/home/user/Nestor/nestor/curator.py`, `/home/user/Nestor/nestor/reconcile.py` — CLI-less Python APIs
- `/home/user/Nestor/nestor/engine.py` — `ClaudeEngine`, `OfflineEngine`, `Draft`, `get_engine`
- `/home/user/Nestor/nestor/signing.py`, `/home/user/Nestor/nestor/keyring.py` — seal HMAC/ed25519 mechanics
- `/home/user/Nestor/nestor/cloud_seal.py`, `/home/user/Nestor/nestor/frank.py` — opt-in external-governance seams
- `/home/user/Nestor/nestor/persona.py` — refusal-voice module, firewalled from `engine.py`
- `/home/user/Nestor/hooks/before_authority.py` — the self-grant tripwire (false-positive found here)
- `/home/user/Nestor/hooks/before_bash.py` — destructive-command guard
- `/home/user/Nestor/data/nestor-demo.db`, `/home/user/Nestor/data/nestor-demo.ledger.jsonl` — probed demo store
- `/tmp/claude-0/-home-user-Nestor/b2bb32f9-9208-5449-8125-3d3598b210a2/scratchpad/probe1/` — scratch stores created during this probe (`demoA.db`, `demoB.db`, `test1.db`)
