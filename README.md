# Nestor

**Meaning infrastructure. *In medio, fides.***

Nestor is a translation-fidelity engine: a three-tier cascade run per segment,
backed by a translation memory and a hash-chained audit ledger. It was
extracted from the `semantic-translator` app into a standalone package with
**no upward dependency on any host** — persistence is *injected*.

## The cascade

For each text segment, Nestor tries three tiers in order:

| Tier | Name | What it is | Result state |
|------|------|-----------|--------------|
| 1 | **Nestor's ledger** | A sealed translation-memory hit (fuzzy match ≥ `SEAL_THRESHOLD`) | `sealed` — served verbatim |
| 2 | **Nova's draft** | A glossary-constrained LLM (or offline TM-composite) draft | `draft` — queued for review |
| 0 | *(no candidate)* | The engine declined / returned nothing | `pending` |

A tier-2 draft is written into the host's `documents`/`segments` review queue.
Tier 3 — **the seal** — happens when a human verifies a segment: call
`graduate_segment(...)`, and the verified pair enters the sealed memory, where
it will serve future tier-1 hits.

Every passage and every seal is appended to a **hash-chained ledger**
(`data/ledger.jsonl` by default). Each line records `prev = sha256(previous
line)`, so the audit trail is tamper-evident.

### The translation memory

`nestor.memory` owns the algorithm — source-text normalization plus difflib
fuzzy scoring — and ranks candidate pairs. Pairs are `sealed`
(human-verified / curated) or `draft` (machine, awaiting seal). Only sealed
pairs are served as tier-1; drafts may feed the engine as style/terminology
context but are never served as verified.

## The injected-storage design

Nestor imports **nothing** from a host application. Instead it defines a
`typing.Protocol` — `nestor.storage.Storage` — capturing exactly the
persistence operations the cascade and memory need. A host (or the bundled
reference store) supplies a concrete implementation.

Two ways to wire it up:

```python
from nestor import storage, translate_text
from nestor.sqlite_store import SqliteStore

storage.set_store(SqliteStore("data/nestor.db"))   # process-wide
doc, passages = translate_text("Hello, world.", target_lang="es")
```

or per call, without a global:

```python
store = SqliteStore(":memory:")
doc, passages = translate_text("Hola.", target_lang="en", store=store)
```

If neither a global store nor an explicit `store=` is present, Nestor raises a
clear `RuntimeError` — it never silently falls back to a hidden database.

### The `Storage` Protocol

Document / segment operations (from the cascade):

- `init_db()` — ensure document/segment schema exists.
- `create_document(title, source_lang, target_lang) -> dict` (returns `{"id", ...}`).
- `get_document(document_id) -> dict | None` (exposes `source_lang`, `target_lang`).
- `update_document_status(document_id, status)`.
- `create_segment(document_id, position, source_text, candidate, jeles_score) -> dict` (returns `{"id", ...}`).
- `get_segment(segment_id) -> dict | None` (exposes `candidate`, `source_text`, `document_id`).

Translation-memory operations (refactored from raw SQL in `memory.py`):

- `memory_init()` — ensure the TM table exists.
- `memory_find(source_norm, source_lang, target_lang) -> dict | None` — exact normalized-key lookup, for upsert.
- `memory_insert(pair)` — insert a new pair (all columns supplied by Nestor).
- `memory_seal(pair_id, target_text, verifier, weight)` — upgrade a pair to `sealed`.
- `memory_candidates(source_lang, target_lang) -> list[dict]` — all pairs for a direction; Nestor does the fuzzy scoring.
- `memory_stats() -> dict` — `{total, sealed, draft, lang_pairs}`.

### Other injected seams

- **Bilingual corpus loader** — `memory.seed_from_corpus` needs curated
  bilingual pairs. Supply them with `memory.set_bilingual_loader(fn)` or pass
  `loader=` directly. Default returns `[]`.
- **Ledger path** — configurable via the `NESTOR_LEDGER` environment variable
  or `cascade.set_ledger_path(...)`. Defaults to `data/ledger.jsonl`.
- **Draft engine** — `nestor.engine.get_engine("auto"|"claude"|"offline")`.
  The Anthropic SDK import is lazy: without credentials or the `anthropic`
  package installed, Nestor uses the deterministic offline TM-composite engine.
  Install the cloud extra (`pip install -e ".[cloud]"`) to enable `ClaudeEngine`.

## Running against the reference store

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

The reference `SqliteStore` owns `documents`, `segments` and `tm_pairs`, so the
whole cascade runs end-to-end with no host. Use `SqliteStore(":memory:")` for
ephemeral runs and tests.

## TODO — FRANK / willow-mcp integration (future, not implemented)

The hash-chained `data/ledger.jsonl` is a local stand-in for **FRANK**, the
append-only provenance ledger. A future integration should forward each ledger
entry to willow-mcp's `frank_append` so the audit trail lives in shared
provenance infrastructure rather than a local file. The seam is `cascade
._ledger_append` — that single function is where forwarding would hook in.
This package deliberately does **not** implement that integration.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
