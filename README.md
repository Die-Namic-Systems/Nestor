# Nestor

**Meaning infrastructure. *In medio, fides.***

Nestor is a **verified-match engine**. Its mechanic is domain-agnostic:

> **normalize an input → fuzzy-match it against a memory of _sealed_ (verified)
> pairs → serve the match above a threshold, else queue it for a human seal →
> log every step to a hash-chained ledger.**

Translation is just *one instance* of that mechanic — the one Nestor was
extracted from. The only translation-specific parts were how text is normalized
and scored, and those now live behind a small `Matcher` seam. Swap the matcher
and the very same seal/serve/ledger machinery **resolves entities** and
**reconciles numbers**. Nestor has **no upward dependency on any host** —
persistence and the matcher are both *injected*.

| Recipe | Matcher | "source → target" means | Module |
|--------|---------|--------------------------|--------|
| Translation | `StringMatcher` | phrase → translation | `nestor.memory` + `nestor.cascade` |
| Entity resolution | `StringMatcher` | alias/surface → canonical entity | `nestor.entity` |
| Numeric reconciliation | `NumericMatcher` | figure → labelled baseline | `nestor.reconcile` |

## The Matcher seam

A `Matcher` (`nestor.matcher`) is the domain-specific half of the mechanic —
everything else (sealing, thresholds, the ledger, storage inversion) is shared:

```python
@runtime_checkable
class Matcher(Protocol):
    def normalize(self, value) -> str: ...              # canonical key
    def similarity(self, a_norm, b_norm) -> float: ...  # [0.0, 1.0], 1.0 == verified
```

Two reference matchers ship:

- **`StringMatcher`** — the *exact* historical translation behavior: lowercase,
  strip punctuation, collapse whitespace (the old `_norm`), then
  `difflib.SequenceMatcher` ratio (equal normals → `1.0`). It is the module-wide
  default, so translation scoring is reproduced bit-for-bit.
- **`NumericMatcher(abs_tol=0.0, pct_tol=0.05)`** — `normalize` parses a number
  out of a str/int/float (stripping `$ , %` and whitespace) into a canonical
  float key; non-parseable inputs become a sentinel that never matches.
  `similarity` is `1.0` inside the tolerance band
  `tol = max(abs_tol, pct_tol·max(|a|,|b|))`, and decays exponentially
  `exp(-(|a-b|-tol)/tol)` outside it — continuous at the edge, monotonically
  toward `0` for a wildly different figure.

`nestor.memory` holds a module-level default matcher (`set_matcher` /
`get_matcher`), and every public memory function (`add_pair`, `lookup`,
`best_sealed`, …) accepts an optional `matcher=`. The `tm_pairs` schema is
**unchanged**: `source_norm` is just whatever the matcher emits, and the
`source_lang` / `target_lang` columns are treated as generic **domain tags** for
non-translation use.

### Entity resolution — `nestor.entity` (backs entity-graph gap #15)

```python
from nestor.entity import EntityResolver

r = EntityResolver(store, domain="company")
for surface in ["Amazon", "Amazon.com Inc", "AMZN", "AWS"]:
    r.seal(surface, "Amazon", verifier="analyst", origin="sec-filing")

r.resolve("amazon.com  inc.")   # -> {"canonical": "Amazon", "sealed": True, "confidence": 1.0, "provenance": {...}}
r.resolve("AMZN")               # -> {"canonical": "Amazon", "sealed": True, ...}
r.resolve("Alphabet Inc")       # -> {"canonical": None, "sealed": False, "provenance": {"draft": True, ...}}
```

A match at/above the seal threshold returns the canonical entity with the sealed
mapping's provenance; below it, the top candidate comes back as an **unsealed
suggestion** the caller can queue for a human seal. This is the entity-graph
engine (gap #15) realized on the very same machinery as translation.

### Numeric reconciliation — `nestor.reconcile` ("match the numbers")

```python
from nestor.reconcile import Reconciler

rc = Reconciler(store, domain="contract", pct_tol=0.05)
rc.seal_baseline("ceiling", "$1,000,000", verifier="auditor")

rc.check("ceiling", "$1,030,000")   # +3%  -> within_tolerance=True,  flagged=False
rc.check("ceiling",  1_250_000)     # +25% -> within_tolerance=False, flagged=True, variation=250000.0, variation_pct=0.25
```

`check` compares an observation to the sealed baseline via the `NumericMatcher`
tolerance, reports the absolute and proportional variation, and flags
deviations — the numeric sibling of the translation memory, feeding njord-style
reconciliation. Every seal and check is written to the ledger.

## The cascade (the translation recipe)

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

## FRANK — mirroring the ledger into shared provenance

The hash-chained `data/ledger.jsonl` is Nestor's own audit trail. `nestor.frank`
mirrors every entry into **FRANK**, willow-mcp's append-only governance ledger,
so the trail also lives in shared provenance infrastructure. It is a third
injected seam — same shape as storage and the matcher, no upward dependency:

```python
from nestor import frank

frank.set_forwarder(frank.willow_forwarder())   # opt in
frank.set_forwarder(None)                       # local ledger only (the default)
```

A forwarder is any callable `(event_type: str, content: dict) -> None`, so a
host can supply its own. With none installed nothing is forwarded and behavior
is exactly what it was.

The bundled `WillowForwarder` speaks **MCP over stdio** and calls willow-mcp's
`frank_append` tool, so the write passes through the manifest ACL that makes the
ledger trustworthy — it never touches the governance database directly. It
spawns the server on first use and reuses that session (a run appends many
entries; one handshake each would dominate the cost). Configuration comes from
the environment the willow-mcp project wiring already sets, so an installed seat
needs no arguments:

| Variable | Meaning | Default |
|----------|---------|---------|
| `WILLOW_MCP_COMMAND` | server argv, JSON list or plain string | `[sys.executable, "-m", "willow_mcp"]` |
| `WILLOW_APP_ID` | app seat to call as (needs the `frank_write` permission) | `nestor` |
| `NESTOR_FRANK_PROJECT` | FRANK project name | `nestor` |
| `NESTOR_FRANK_STRICT` | raise instead of swallowing forward failures | unset |

Local ledger entries are written **first** and stay the source of truth;
forwarding is best-effort, because a governance mirror that is down, denied, or
absent must never fail a translation. Each mirrored entry carries a `local_hash`
— the sha256 of the local line as written — so the two chains cross-link: a
FRANK entry maps back to an exact local line, and a rewritten local ledger no
longer matches its mirror. `event_type` is the entry's `kind`, namespaced
(`nestor.passage`, `nestor.seal`).

The seam is still `cascade._ledger_append` — that one function is where
forwarding hooks in.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
