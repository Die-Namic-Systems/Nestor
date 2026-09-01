# The `Storage` Protocol

*The full persistence seam. The [manual](manual.md#injected-storage) explains
what injected storage is and why; this is the operation-by-operation reference a
host implements against.*

Nestor imports **nothing** from a host application. It defines a
`typing.Protocol` — `nestor.storage.Storage` — capturing exactly the persistence
operations the cascade and memory need. A host (or the bundled `SqliteStore`)
supplies a concrete implementation.

## Core — every store must implement these

Document / segment operations:

- `init_db()` — ensure document/segment schema exists.
- `create_document(title, source_lang, target_lang) -> dict`
- `get_document(document_id) -> dict | None`
- `update_document_status(document_id, status)`
- `create_segment(document_id, position, source_text, candidate, jeles_score) -> dict` — `jeles_score` is the draft engine's own rough confidence, stored as given (the name is inherited from the host Nestor was extracted from; nothing reads it back).
- `get_segment(segment_id) -> dict | None`

Translation-memory operations:

- `memory_init()` — ensure the TM table exists.
- `memory_find(source_norm, source_lang, target_lang) -> dict | None` — exact normalized-key lookup, for upsert.
- `memory_insert(pair)` — MUST refuse a second row with the same `(source_norm, source_lang, target_lang)`. Nestor's conflict guards read-then-write, so this is what makes "one row per source" hold when two reviewers seal the same phrase at once; the reference store enforces it with a unique index.
- `memory_seal(pair_id, target_text, verifier, weight, seal_sig)`
- `memory_candidates(source_lang, target_lang) -> list[dict]` — all pairs for a domain; Nestor does the scoring.
- `memory_stats() -> dict`

## Optional capabilities

All-or-nothing, each reported by a `supports_*` predicate. A store predating one
keeps working, and the surfaces that need it say so rather than showing an empty
list, because "nothing here" and "this store cannot tell you" are different facts.

| Capability | Operations | Reported by | Without it |
|---|---|---|---|
| Rejection | `memory_reject_pair`, `memory_add_rejection`, `memory_rejections` | `supports_rejection` | `reject_*` raises rather than dropping a human's "no" |
| Curation | `memory_list`, `memory_get`, `memory_unseal`, `memory_rejections_for_pair` | `supports_curation` | `Curator` raises `CurationUnsupportedError`; no export/import |
| Review queue | `list_documents`, `list_segments`, `update_segment_status` | `supports_queue` | the queue cannot be listed or cleared; everything else works |
| Rejection listing | `memory_list_rejections` | `supports_rejection_listing` | rejections still record and read by key; export says a bundle ships without the ones naming no pair |
| Lineage | `memory_mark_superseded`, `memory_lineage` | `supports_lineage` | `supersede_pair` / `revise_draft` raise rather than destructively overwriting |
| Atomic supersede | `memory_mark_superseded_if` | `supports_atomic_supersede` | `revise_draft` refuses rather than racing |
| Decision edges | `memory_add_edge`, `memory_edges_to`, `memory_edges_from` | `supports_edges` | decisions still seal, but cannot be related — no graph neighbours |
| Evidence | `memory_add_evidence`, `memory_evidence_for`, `memory_unevidenced_seals` | `supports_evidence` | a sealed claim cannot carry what it rests on, and the report is empty |
| Warrants | `memory_add_warrant`, `memory_warrants_for` | `supports_warrants` | a claim cannot record why a stranger should believe it — only who sealed it |
| Verifier policy | `memory_policy_add`, `memory_policy_remove`, `memory_policy_list` | `supports_verifier_policy` | every verifier name is accepted at seal time, for every domain |
| Embedding store | `embedding_load`, `embedding_save`, `embedding_drop` | `supports_embedding_store` | the semantic matcher recomputes each vector rather than caching it |

Partial implementation counts as none. Writing rejections nobody can read back,
or offering an unseal the store cannot perform, is worse than not having the
feature.
