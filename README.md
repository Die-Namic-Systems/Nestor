# Nestor

**Meaning infrastructure. *In medio, fides.***

[![Tests](https://github.com/rudi193-cmd/Nestor/actions/workflows/tests.yml/badge.svg)](https://github.com/rudi193-cmd/Nestor/actions/workflows/tests.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)
[![Dependencies](https://img.shields.io/badge/runtime%20deps-none-lightgrey)](pyproject.toml)

Nestor answers one question about a machine-generated answer: **has a human
checked this?**

Not as a confidence score — as a structural fact you can audit. Every answer
Nestor serves is in exactly one of three states, and the state is never a guess:

| | State | What it means |
|---|-------|---------------|
| ✓ | **sealed** | A human verified this. Served verbatim, instantly, forever. |
| ~ | **draft** | A machine produced it. Queued for review, never served as verified. |
| ! | **pending** | Nothing to offer. Said plainly rather than improvised. |

A human seals an answer **once**. From then on it is free, instant, and carries
the provenance of whoever verified it. Every seal, serve and check is appended to
a hash-chained ledger, so the trail is tamper-evident.

**Contents** — [Quick start](#quick-start) · [The mechanic](#the-mechanic) ·
[Project layout](#project-layout) · [The Matcher seam](#the-matcher-seam) ·
[The recipes](#the-recipes) · [The ledger](#the-ledger) ·
[Injected storage](#injected-storage) ·
[Accuracy](#accuracy-and-how-to-measure-yours) · [Development](#development)

---

## Quick start

```bash
git clone https://github.com/rudi193-cmd/Nestor.git && cd Nestor
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q                                  # 65 passed
```

Python 3.10+, no runtime dependencies. The bundled `SqliteStore` owns every table
Nestor needs, so the whole cascade runs end-to-end with no host application.

Save this as `demo.py` and run it — it is the entire product in eleven lines:

```python
from nestor import cascade, memory, storage
from nestor.sqlite_store import SqliteStore

storage.set_store(SqliteStore(":memory:"))

# 1. Nothing is known yet. Nestor says so rather than improvising.
p = cascade.translate_segment("Good evening.", "en", "es")
print(p.mark, p.state, repr(p.target))

# 2. A human verifies it — once.
memory.add_pair("Good evening.", "Buenas noches.", "en", "es",
                status="sealed", verifier="rudi")

# 3. Forever after, including when it is retyped differently.
p = cascade.translate_segment("good evening", "en", "es")
print(p.mark, p.state, repr(p.target), p.confidence, p.meta["verifier"])
```

```
! pending ''
✓ sealed 'Buenas noches.' 1.0 rudi
```

One human verification, and the answer is free, instant and attributed from then
on — with both steps recorded in a tamper-evident ledger.

> The run also prints a `RuntimeWarning` about `NESTOR_SEAL_KEY`. That is Nestor
> telling you seals are being trusted on stored status alone. See
> [Seal signatures](#seal-signatures) before using it for anything real.

**Installation extras**

```bash
pip install -e ".[dev]"      # + pytest
pip install -e ".[cloud]"    # + the Anthropic SDK, to enable ClaudeEngine
```

---

## The mechanic

Nestor's core loop is domain-agnostic:

> **normalize an input → fuzzy-match it against a memory of _sealed_ (verified)
> pairs → serve the match above a threshold, else queue it for a human seal →
> log every step to a hash-chained ledger.**

Translation is one *instance* of that loop — the one Nestor was extracted from.
The only translation-specific parts are how text is normalized and scored, and
those live behind a small `Matcher` seam. Swap the matcher and the same
seal/serve/ledger machinery **resolves entities** and **reconciles numbers**.

| Recipe | Matcher | "source → target" means | Module |
|--------|---------|--------------------------|--------|
| Translation | `StringMatcher` | phrase → translation | `nestor.memory` + `nestor.cascade` |
| Entity resolution | `StringMatcher` | alias/surface → canonical entity | `nestor.entity` |
| Numeric reconciliation | `NumericMatcher` | figure → labelled baseline | `nestor.reconcile` |
| *yours* | *yours* | *whatever you can normalize and score* | — |

That last row is not aspirational. A date matcher (normalizing `Q3 2025`,
`September 30, 2025` and `30/09/2025` to one key, scoring by day-window) and a
CSV-header-to-schema mapper have both been built against the shipped package
without modifying it.

Nestor has **no upward dependency on any host** — persistence, the matcher, the
draft engine and the governance forwarder are all injected.

---

## Project layout

```
nestor/
├── __init__.py       public surface — translate_text, translate_segment, graduate_segment
├── cascade.py        the three tiers, and the hash-chained ledger append
├── memory.py         tier 1 — the sealed pair memory, ranking, seal/serve rules
├── matcher.py        the domain seam — Matcher protocol, StringMatcher, NumericMatcher
├── entity.py         recipe — alias → canonical entity resolution
├── reconcile.py      recipe — figure → sealed baseline, with tolerance and variation
├── engine.py         tier 2 — draft engines (ClaudeEngine, OfflineEngine)
├── storage.py        the persistence seam — Storage protocol, set_store/get_store
├── sqlite_store.py   reference Storage implementation; owns documents/segments/tm_pairs
├── ledger.py         verify() the hash chain — the fail-closed audit check
├── signing.py        bind a seal to a key the store does not hold
├── frank.py          mirror the ledger into willow-mcp's shared governance ledger
├── glossary.py       per-language-pair term locks — tier 2's constraint
├── langid.py         stopword-profile language identification
└── segment.py        sentence/segment splitting

bench/                measuring where the seal threshold stops holding — see bench/README.md
├── bench_accuracy.py false-seal rate vs recall, swept across thresholds
├── corpora.py        seeded corpora at both ends of the diversity spectrum
├── harness.py        timing, environment capture, JSON result recording
└── results/          committed measurements — parameters, git rev, raw numbers

tests/                65 tests, no network, no fixtures on disk
IDEAS.md              running list of ideas, each tagged measured/verified/hypothesis/open
```

---

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

- **`StringMatcher`** — the historical translation behavior: lowercase, strip
  punctuation, collapse whitespace, then `difflib.SequenceMatcher` ratio (equal
  normals → `1.0`). It is the module-wide default, so translation scoring is
  reproduced bit-for-bit.
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
non-translation use — so one store holds several disjoint graphs without
cross-talk.

> **Writing your own matcher?** `normalize()` is the *only* channel between a raw
> input and `similarity()`, which sees normalized keys and nothing else. Anything
> scoring needs — word order, structure, magnitude — must survive into that
> string. That same string is also the store's exact-match dedup key, so
> collapsing aggressively and scoring richly pull against each other. See
> [`IDEAS.md`](IDEAS.md) §3.1.

---

## The recipes

### Translation — the cascade

For each text segment, Nestor tries three tiers in order:

| Tier | Name | What it is | Result state |
|------|------|-----------|--------------|
| 1 | **Nestor's ledger** | A sealed translation-memory hit (fuzzy match ≥ `SEAL_THRESHOLD`) | `sealed` — served verbatim |
| 2 | **Nova's draft** | A glossary-constrained LLM (or offline TM-composite) draft | `draft` — queued for review |
| 0 | *(no candidate)* | The engine declined / returned nothing | `pending` |

A tier-2 draft is written into the host's `documents`/`segments` review queue.
Tier 3 — **the seal** — happens when a human verifies a segment: call
`graduate_segment(...)`, and the verified pair enters the sealed memory, where it
serves future tier-1 hits.

Pairs are `sealed` (human-verified / curated) or `draft` (machine, awaiting
seal). Only sealed pairs are served as tier 1; drafts may feed the engine as
style/terminology context but are never served as verified.

### Entity resolution — `nestor.entity`

```python
from nestor.entity import EntityResolver

r = EntityResolver(store, domain="company")
for surface in ["Amazon", "Amazon.com Inc", "AMZN", "AWS"]:
    r.seal(surface, "Amazon", verifier="analyst", origin="sec-filing")

r.resolve("amazon.com  inc.")
# {'canonical': 'Amazon', 'confidence': 1.0, 'sealed': True, 'provenance': {...}}
r.resolve("Alphabet Inc")
# {'canonical': None, 'confidence': 0.0, 'sealed': False, 'provenance': {'draft': True, ...}}
```

A match at/above the seal threshold returns the canonical entity with the sealed
mapping's provenance; below it, the top candidate comes back as an **unsealed
suggestion** the caller can queue for a human seal.

### Numeric reconciliation — `nestor.reconcile`

```python
from nestor.reconcile import Reconciler

rc = Reconciler(store, domain="contract", pct_tol=0.05)
rc.seal_baseline("ceiling", "$1,000,000", verifier="auditor")

rc.check("ceiling", "$1,030,000")
# {..., 'within_tolerance': True,  'variation': 30000.0,  'variation_pct': 0.03, 'flagged': False}
rc.check("ceiling", 1_250_000)
# {..., 'within_tolerance': False, 'variation': 250000.0, 'variation_pct': 0.25, 'flagged': True}
```

`check` compares an observation to the sealed baseline via the `NumericMatcher`
tolerance, reports absolute and proportional variation, and flags deviations.
Every seal and check is written to the ledger.

---

## The ledger

Every passage, seal, resolution and check is appended to a hash-chained ledger
(`data/ledger.jsonl` by default). Each line records `prev = sha256(previous
line)`, so the audit trail is tamper-evident — and all recipes share one chain.

Nestor fails closed on it. Appending refuses if the ledger is a symlink or not a
regular file (the trail must not be redirectable or suppressible), and the
existing chain is verified before it is extended, so a new entry can never
launder a tampered history. A broken chain is a refusal, not a warning.

Configure the path with `NESTOR_LEDGER` or `cascade.set_ledger_path(...)`.

```python
from nestor.ledger import verify
verify("data/ledger.jsonl")     # (True, 'intact — 18 entries')
```

### Seal signatures

Set `NESTOR_SEAL_KEY` and every seal is bound to a key the store does not hold,
so a row edited to `status='sealed'` directly in the database will not verify and
will not be served. Without the variable Nestor warns and trusts stored status —
set `NESTOR_REQUIRE_SEAL_KEY=1` to fail closed instead.

### FRANK — mirroring into shared provenance

`nestor.frank` mirrors every ledger entry into **FRANK**, willow-mcp's
append-only governance ledger, so the trail also lives in shared infrastructure.
A third injected seam, same shape as the others:

```python
from nestor import frank
frank.set_forwarder(frank.willow_forwarder())   # opt in
frank.set_forwarder(None)                       # local ledger only (the default)
```

A forwarder is any callable `(event_type: str, content: dict) -> None`. The
bundled `WillowForwarder` speaks **MCP over stdio** and calls willow-mcp's
`frank_append` tool, so the write passes through the manifest ACL that makes the
ledger trustworthy — it never touches the governance database directly.

| Variable | Meaning | Default |
|----------|---------|---------|
| `WILLOW_MCP_COMMAND` | server argv, JSON list or plain string | `[sys.executable, "-m", "willow_mcp"]` |
| `WILLOW_APP_ID` | app seat to call as (needs `frank_write`) | `nestor` |
| `NESTOR_FRANK_PROJECT` | FRANK project name | `nestor` |
| `NESTOR_FRANK_STRICT` | raise instead of swallowing forward failures | unset |

Local entries are written **first** and stay the source of truth; forwarding is
best-effort, because a governance mirror that is down, denied or absent must
never fail a translation. Each mirrored entry carries a `local_hash` — the
sha256 of the local line as written — so the two chains cross-link.

---

## Injected storage

Nestor imports **nothing** from a host application. It defines a
`typing.Protocol` — `nestor.storage.Storage` — capturing exactly the persistence
operations the cascade and memory need. A host (or the bundled reference store)
supplies a concrete implementation.

```python
storage.set_store(SqliteStore("data/nestor.db"))                          # process-wide
doc, passages = translate_text("Hola.", target_lang="en", store=store)    # or per call
```

If neither a global store nor an explicit `store=` is present, Nestor raises a
clear `RuntimeError` — it never silently falls back to a hidden database.

<details>
<summary><strong>The <code>Storage</code> Protocol</strong></summary>

Document / segment operations:

- `init_db()` — ensure document/segment schema exists.
- `create_document(title, source_lang, target_lang) -> dict`
- `get_document(document_id) -> dict | None`
- `update_document_status(document_id, status)`
- `create_segment(document_id, position, source_text, candidate, jeles_score) -> dict`
- `get_segment(segment_id) -> dict | None`

Translation-memory operations:

- `memory_init()` — ensure the TM table exists.
- `memory_find(source_norm, source_lang, target_lang) -> dict | None` — exact normalized-key lookup, for upsert.
- `memory_insert(pair)`
- `memory_seal(pair_id, target_text, verifier, weight, seal_sig)`
- `memory_candidates(source_lang, target_lang) -> list[dict]` — all pairs for a domain; Nestor does the scoring.
- `memory_stats() -> dict`

</details>

### Other injected seams

- **Draft engine** — `nestor.engine.get_engine("auto"|"claude"|"offline")`. The
  Anthropic SDK import is lazy: without credentials or the `anthropic` package,
  Nestor uses the deterministic offline TM-composite engine.
- **Bilingual corpus loader** — `memory.set_bilingual_loader(fn)`, or pass
  `loader=` to `seed_from_corpus`. Default returns `[]`.

---

## Accuracy, and how to measure yours

A tier-1 hit is served verbatim and marked verified, with **no review queue**. So
the failure that matters is the inverse of the usual one: not a missed match, but
a phrase that was never verified being served as though it were.

Both are governed by `SEAL_THRESHOLD` (default `0.92`), and they trade against
each other:

- **Raise it** — fewer false seals, more true matches falling to tier 2. A miss
  is cheap: it gets reviewed.
- **Lower it** — more matches served, more of them wrong. A false seal is
  expensive: nothing flags it, and the ledger faithfully records it as verified.

The right cutoff depends on your corpus. Homogeneous text — contract boilerplate,
templated notices — crowds the score distribution and produces false seals at
thresholds that are safe on diverse prose.

**So measure it rather than trusting the default.** `bench/` sweeps the threshold
against corpora at both ends of the diversity spectrum and reports false-seal
rate against recall at each cutoff:

```bash
python bench/bench_accuracy.py --probes 400
```

Results land in `bench/results/*.json` with parameters, environment and git
revision attached. [`bench/README.md`](bench/README.md) documents the method,
including the properties a corpus must preserve to produce a meaningful number.

Known limits, measured and recorded in [`IDEAS.md`](IDEAS.md):

- **Lookup is linear in corpus size**, and ~97% of the time is Python-side
  scoring rather than SQL. Nestor is built for high-value, reviewed decisions,
  not high-volume serving.
- **There is no way to record that a match is *wrong*** — a rejected fuzzy hit
  will be offered again identically (§1.2).
- **The memory has no read surface** — no list, export or unseal (§5.2).

---

## Development

```bash
pip install -e ".[dev]"
pytest -q                          # 65 tests, no network
ruff check nestor tests            # enforced in CI
bandit -r nestor -ll -q            # enforced in CI
python bench/bench_accuracy.py     # measurements -> bench/results/
```

CI runs lint and the test matrix (Python 3.10 and 3.12) on every pull request,
plus a daily scheduled run to catch drift. Ideas, open questions and measured
dead ends live in [`IDEAS.md`](IDEAS.md) — each entry tagged
**measured / verified / hypothesis / open**, so the confidence level travels with
the claim.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
