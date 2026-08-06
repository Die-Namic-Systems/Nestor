# Nestor

**Meaning infrastructure. *In medio, fides* — in the middle, trust.**

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
| ✓ | **sealed** | A human verified this, and the seal still verifies. Served verbatim, instantly, forever. |
| ~ | **draft** | A machine produced it. Queued for review, never served as verified. |
| ! | **pending** | Nothing to offer. Said plainly rather than improvised. |

Read the first row precisely: *and the seal still verifies*. A row that merely
**says** `sealed` in the database is not served — a seal is bound to a key the
store does not hold, and one that does not verify is surfaced to a curator
instead of answering anyone. That distinction is the product; see
[seal signatures](#seal-signatures) and [the curator](#the-curator--seeing-what-was-verified).

A human seals an answer once — and can **reject** one just as durably, so a wrong
match is never served again. Both decisions are signed and both are audited.

From then on a sealed answer is free, instant, and carries the provenance of
whoever verified it. Every seal, rejection, serve and check is appended to a
hash-chained ledger, so the trail is tamper-evident.

**Contents** — [The mechanic](#the-mechanic) ·
[The category](#the-category--verification-not-translation-memory) ·
[Quick start](#quick-start) ·
[Project layout](#project-layout) · [The Matcher seam](#the-matcher-seam) ·
[The recipes](#the-recipes) · [Rejection](#rejection--the-reviewers-no) ·
[The curator](#the-curator--seeing-what-was-verified) ·
[The UI](#the-ui--where-the-human-sits) · [The CLI](#the-cli) ·
[Export & import](#export-and-import--taking-the-memory-elsewhere) ·
[Serving a model](#serving-a-model--and-the-one-thing-it-cannot-do) ·
[The ledger](#the-ledger) · [Injected storage](#injected-storage) ·
[Accuracy](#accuracy-and-how-to-measure-yours) · [The name](#the-name) ·
[Development](#development)

Frequently asked, honestly answered — including the "not yet"s:
[**QUESTIONS.md**](QUESTIONS.md).

---

## The mechanic

One loop, and it knows nothing about language:

> **normalize an input → fuzzy-match it against a memory of _sealed_ (verified)
> pairs → serve the match above a threshold, else queue it for a human seal →
> append every step to a hash-chained ledger.**

That loop is the product. What it compares — sentences, aliases, figures, dates,
column headers — is decided by a `Matcher`, a two-method seam holding the only
domain-specific code in the system. Everything the value depends on is on the
other side of it: what counts as verified, who verified it, what gets served,
what gets queued, and what the audit trail records.

| Recipe | Matcher | "source → target" means | Module |
|--------|---------|--------------------------|--------|
| Translation | `StringMatcher` | phrase → translation | `nestor.memory` + `nestor.cascade` |
| Entity resolution | `StringMatcher` | alias/surface → canonical entity | `nestor.entity` |
| Numeric reconciliation | `NumericMatcher` | figure → labelled baseline | `nestor.reconcile` |
| *yours* | *yours* | *whatever you can normalize and score* | — |

Translation is where Nestor was extracted from, and the examples below use it
most because it needs no setup to read. It is the origin story, not the boundary.

That last row is not aspirational. A date matcher (normalizing `Q3 2025`,
`September 30, 2025` and `30/09/2025` to one key, scoring by day-window) and a
CSV-header-to-schema mapper have both been built against the shipped package
without modifying it.

Nestor has **no upward dependency on any host** — persistence, the matcher, the
draft engine and the governance forwarder are all injected.

---

## The category — verification, not translation memory

Translation memory is where Nestor was extracted from. It is not what Nestor is
for, and reading it as a TM gets the economics backwards.

A translation memory is a cache: it exists to avoid paying for the same work
twice, and its value is the work it skips. Nestor's three states are not a cache
tier. They are an answer to a different question, and it is a question being put
to anyone shipping model output into a regulated process:

> **Which model outputs did a human actually check?**

Tier 2 is a machine draft, explicitly queued and never served as verified. Tier
3 is a person checking it, under their own key. Tier 1 is that decision served
back, verbatim, with the name of who made it — and the whole sequence appended
to a hash-chained ledger, so the answer is a structural fact rather than a
recollection. "A human checked this" is either in the chain or it is not.

**Each verification is permanent capital.** This is the part worth leading with,
because the curve runs the wrong way round compared to inference: cost per
answer *falls* as the proportion of verified answers rises, and it never
un-falls, because a seal does not expire and costs nothing to serve again.
Spending review time buys down a recurring cost rather than renting a result.
Verified once, served forever.

**Where that wins:** high-value, low-volume decisions where somebody is already
reading the output — contract clauses, clinical notes, regulatory filings,
anything with a named reviewer and a retention requirement. The review was
happening anyway; Nestor is the difference between it happening and it being
provable.

**Where it loses, stated plainly:** high-volume serving. Lookup is linear in
corpus size and about 97% of that time is Python-side scoring, so this is not a
chat backend and pitching it as one loses on the numbers — see
[Accuracy](#accuracy-and-how-to-measure-yours) and `IDEAS.md` §2. The design
target is decisions worth a person's attention, not throughput.

---

## Quick start

```bash
git clone https://github.com/rudi193-cmd/Nestor.git && cd Nestor
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q                                  # count deliberately not quoted
```

Python 3.10+, no runtime dependencies. The bundled `SqliteStore` owns every table
Nestor needs, so the whole cascade runs end-to-end with no host application.

File-backed `SqliteStore` uses **WAL** mode. While a process holds the database
open, recent commits may live in `nestor.db-wal`, so a plain `cp` of
`nestor.db` is **not** a backup of a running server — use
`nestor export`, SQLite `VACUUM INTO`, or stop `nestor.ui` (which checkpoints on
exit). A hard kill or rsync of a live box has the same limit.

The whole argument in one run, against a scratch store it deletes afterwards:

```bash
python demo/sixty_seconds.py            # --fast to skip the pauses
```

An answer nobody has verified; one human verifying it once; the same question
retyped and served with a receipt; a rewrite that is *not* served; the failure
mode where "thirty days" matches "sixty days" and what to do about it; a seal
forged straight into the database and refused; then one field edited in one past
ledger entry, and the chain refusing both to verify and to accept the next
decision. Every beat asserts its own claim — the script exits non-zero rather
than narrate something that did not happen, and a test runs it.

Save this as `demo.py` and run it — the whole loop, in the translation recipe:

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

That ledger is a file, even when the store is not: the run above appends to
`./data/ledger.jsonl`, created relative to wherever you ran it. An in-memory
store dies with the process; the audit trail deliberately never does. Configure
the path with `NESTOR_LEDGER` — see [The ledger](#the-ledger).

Now the same loop with no translation in it. Save this as `entities.py`: an
alias graph, where "source → target" means *surface form → the entity it
denotes*, and the only thing that changed is which recipe is imported.

```python
from nestor import storage
from nestor.entity import EntityResolver
from nestor.sqlite_store import SqliteStore

storage.set_store(SqliteStore(":memory:"))
graph = EntityResolver(storage.get_store(), domain="company")

# 1. An analyst verifies two aliases — once each.
graph.seal("Amazon.com Inc", "Amazon", verifier="analyst")
graph.seal("AMZN", "Amazon", verifier="analyst")

# 2. A spelling nobody sealed, of an alias somebody did.
hit = graph.resolve("amazon.com,  inc.")
print(hit["sealed"], hit["canonical"], hit["provenance"]["verifier"])

# 3. Close, but not close enough to serve as verified.
near = graph.resolve("Amazon Web Services")
print(near["sealed"], near["canonical"], near["provenance"]["suggestion"])
```

```
True Amazon analyst
False None Amazon
```

Same seal, same threshold, same ledger. The third line is the one to notice:
a near miss comes back **unsealed with a suggestion**, not as an answer with a
lower score — because "probably Amazon" is not a thing a human checked.

Prefer to click rather than type? `python -m nestor.ui --db data/nestor.db` opens
the same three states, the review queue and the ledger in a browser — see
[The UI](#the-ui--where-the-human-sits).

> The run also prints a `RuntimeWarning` about `NESTOR_SEAL_KEY`. That is Nestor
> telling you seals are being trusted on stored status alone. See
> [Seal signatures](#seal-signatures) before using it for anything real.

**Installation extras**

```bash
pip install -e ".[dev]"      # + pytest, ruff, bandit — everything Development runs
pip install -e ".[cloud]"    # + the Anthropic SDK, to enable ClaudeEngine
pip install -e ".[semantic]" # + fastembed, to enable SemanticMatcher
pip install -e ".[keys]"     # + cryptography, for ed25519 per-verifier keys
```

(The `-e ".[…]"` form is the one that works here — Nestor is installed from
this clone, not from an index.)

---

## Project layout

```
nestor/
├── __init__.py       public surface — the cascade, the recipes, the curator, the matchers
├── cascade.py        the three tiers, and the hash-chained ledger append
├── memory.py         tier 1 — the sealed pair memory, ranking, seal/reject/serve rules
├── matcher.py        the domain seam — Matcher protocol, StringMatcher, NumericMatcher
├── semantic_matcher.py  optional SemanticMatcher (the [semantic] extra / fastembed)
├── curator.py        the curator surface — browse, audit, unseal, export
├── calibrate.py      where the seal threshold should sit for *your* corpus
├── answer.py         what Nestor answers — one definition, shared by every surface
├── persona.py        how Nestor speaks when Nestor is the speaker (never the translation)
├── ui.py             the browser surface — queue, memory, ask, signals, ledger (stdlib only)
├── ui_page.py        the single self-contained page ui.py serves
├── cli.py            the terminal surface — ask, export, import, ledger verify
├── serve.py          the model surface — MCP over stdio; it cannot seal
├── portable.py       export/import a memory without laundering trust
├── entity.py         recipe — alias → canonical entity resolution
├── reconcile.py      recipe — figure → sealed baseline, with tolerance and variation
├── engine.py         tier 2 — draft engines (ClaudeEngine, OfflineEngine)
├── embedding_store.py  optional tm_embeddings blob helpers (SqliteStore + semantic)
├── storage.py        the persistence seam — Storage protocol, set_store/get_store
├── sqlite_store.py   reference Storage impl; owns documents/segments/tm_pairs/tm_rejections/tm_embeddings
├── ledger.py         verify() the hash chain — the fail-closed audit check
├── signing.py        bind a seal (and a rejection) to a key the store does not hold
├── keyring.py        a key per verifier — so a seal names a person, not a deployment
├── frank.py          mirror the ledger into willow-mcp's shared governance ledger
├── homestead_paths.py  ~/.homestead/keep paths for homestead hosts (see docs/homestead-paths.md)
├── glossary.py       per-language-pair term locks — tier 2's constraint
├── langid.py         stopword-profile language identification
└── segment.py        sentence/segment splitting

bench/                measuring where the seal threshold stops holding — see bench/README.md
├── bench_accuracy.py   false-seal rate vs recall, swept across thresholds
├── bench_margin.py     does the gap to the runner-up separate a true match? (mostly: no)
├── bench_surfaces.py   which surface variations survive normalization
├── bench_surfaces_human.py   the same probes, authored by a human rather than generated
├── bench_surfaces_llm.py     and by a model, scored against both
├── corpora.py          seeded corpora at both ends of the diversity spectrum
├── corpus_terpsi.py    a real-prose corpus, with its span/split checks
├── token_matchers.py   token-weighted matchers tried against the identifier collisions
├── harness.py          timing, environment capture, JSON result recording
├── serve_ui.py         the threshold trade-off as a chart — read-only, stdlib (serves bench/ui/)
└── results/            committed measurements — parameters, git rev, raw numbers

demo/                 scripted and self-asserting — a claim that fails the build when it stops being true
├── sixty_seconds.py    the whole loop in eight beats — see Quick start
├── shoebox.py          one verifier, her own archive, across all three recipes — five open gaps (IDEAS §6.35, §6.37-§6.39)
└── desks.py            scaffolding: several deployments in one interpreter, and the three process globals that makes you own

recipes/              the seam's "yours" row, built against the shipped package
├── patch_review.py       defect description → proposed fix; DefectMatcher weights identifiers
└── bench_patch_review.py what it retrieves, against StringMatcher and TokenJaccard
scripts/              dogfood, fleet-checkout, and two_instances.py — the export/import
                      trust boundary across two genuinely separate deployments
tests/                no outbound network (one test binds a loopback socket), no fixtures on disk
AGENTS.md             cold-start for any agent — git sync, ci-lint, hook pointers
IDEAS.md              running list of ideas, each tagged measured/verified/hypothesis/open
TODO.md               the queue — what is left, in order; IDEAS/QUESTIONS hold the arguments
FINDINGS-*.md         dated audits, kept as records of what was found and how it was argued
docs/code-review-lessons.md  pre-merge checklist from PR review rounds (§2.4, §5.3, WAL, TTL)
docs/fleet-integration-map.md  open IDEAS ↔ fleet repos (what to wire, not new invention)
docs/local-fleet.md   wiring nestor to the fleet repos on one machine — paths and commands
docs/decision-memory.md  decisions as a Nestor recipe — the design carried in from SAFE
QUESTIONS.md          the questions this gets asked, answered or admitted
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
    # optional: score(raw_a, raw_b) -> float — memory prefers this when present
```

`match_similarity()` in `nestor.matcher` is what `lookup` / `best_sealed` call:
normalized-key scoring when there is no `score`, raw surfaces when there is.

Two core matchers ship with zero dependencies; a third is optional:

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
- **`SemanticMatcher`** *(optional)* — `pip install -e ".[semantic]"` adds
  `fastembed` only. Lexical dedup via `StringMatcher`; `score(raw_a, raw_b)`
  compares embeddings (default model `BAAI/bge-small-en-v1.5`). Use
  `matcher=semantic` on `nestor match`, the UI Match view, or MCP
  `nestor_match`. Re-calibrate thresholds — they are not comparable to
  character-ratio scores.

Set `NESTOR_SEMANTIC_TEST=1` and install the `[semantic]` extra to run the optional
integration test that checks the §3.1 acronym case (`AWS` vs `Amazon Web Services`).

#### The embedding cache is signed, for the same reason a seal is

Embedding a row costs real time, so `SqliteStore` caches each vector in
`tm_embeddings`, keyed by `(pair_id, model_name)`. That cache is **an input to
the serve decision**: under `SemanticMatcher` the score comes from the vectors,
not from the text. A seal signature covers `(source_norm, target_text,
verifier)` — it says what a human approved, and nothing about what the row
*matches*. So a store-writer who cannot forge a seal could still choose which
queries a sealed row answers, by writing the vector. Same shape as
[Nestor#2](https://github.com/rudi193-cmd/Nestor/issues/2), one object over.

Each cached vector therefore carries an HMAC over
`(pair_id, model_name, source_sha, vector)`, and one that does not verify is
**recomputed rather than used** — a bad cache entry costs latency, never an
answer. The key comes from `NESTOR_CACHE_KEY`, else `NESTOR_SEAL_KEY`, else a
keyring's `legacy_key`:

| what is configured | what the cache does |
| --- | --- |
| nothing (signing off) | used unsigned — the store is already fully trusted, so a MAC would protect nothing |
| `NESTOR_SEAL_KEY`, or `NESTOR_CACHE_KEY` | signed and verified on every read |
| a keyring with **no** `legacy_key` and no `NESTOR_SEAL_KEY` | **disabled** — there is no deployment-wide key to sign with, and reading a cache it cannot check is exactly the hole above. Set `NESTOR_CACHE_KEY` to turn it back on; Nestor warns once |

`--read-only` surfaces read the cache but never write it: matching is a read,
and a reader who passed `--read-only` did not agree to a write.

`nestor.memory` holds a module-level default matcher (`set_matcher` /
`get_matcher`), and every public memory function (`add_pair`, `lookup`,
`best_sealed`, …) accepts an optional `matcher=`. The `tm_pairs` schema is
**unchanged**: `source_norm` is just whatever the matcher emits, and the
`source_lang` / `target_lang` columns are treated as generic **domain tags** for
non-translation use — so one store holds several disjoint graphs without
cross-talk.

> **Writing your own matcher?** `normalize()` is persisted as ``source_norm`` and
> used for exact dedup. Scoring normally goes through ``similarity(a_norm,
> b_norm)`` on those keys. If scoring needs information that must not be
> collapsed into the dedup key — word order, token structure, anything a semantic
> matcher would need — implement optional ``score(raw_a, raw_b)``; memory will
> compare the query to each row's ``source_text`` that way instead. The two jobs
> no longer pull against each other. See [`IDEAS.md`](IDEAS.md) §3.1.

---

## The recipes

### Translation — the cascade

For each text segment, Nestor tries three tiers in order:

| Tier | Name | What it is | Result state |
|------|------|-----------|--------------|
| 1 | **Nestor's ledger** | A sealed translation-memory hit (fuzzy match ≥ `SEAL_THRESHOLD`, default `0.92` — [why that number is a dial, not a default](#accuracy-and-how-to-measure-yours)) | `sealed` — served verbatim |
| 2 | **The draft** (`Nova` in the code, from the host it was extracted from) | A glossary-constrained LLM (or offline TM-composite) draft | `draft` — queued for review |
| 0 | *(no candidate)* | The engine declined / returned nothing | `pending` |

A tier-2 draft is written into the host's `documents`/`segments` review queue.
Tier 3 — **the seal** — happens when a human verifies a segment: call
`graduate_segment(...)`, and the verified pair enters the sealed memory, where it
serves future tier-1 hits.

A reviewer's **no** is recorded too — `reject_segment(...)` — so a wrong
candidate is never offered for that input again. See
[Rejection](#rejection--the-reviewers-no).

The loop end to end, in code — draft, queue, seal, serve:

```python
from nestor import cascade, memory, storage
from nestor.sqlite_store import SqliteStore

store = SqliteStore(":memory:")
storage.set_store(store)
memory.add_pair("Please sign the form.", "Firme el formulario.", "en", "es",
                status="sealed", verifier="rita")

# Tier 2: nothing sealed is close enough, so the engine drafts and queues.
doc, passages = cascade.translate_text("Please sign the attached form.",
                                       target_lang="es", source_lang="en")
passages[0].state                     # 'draft' — queued, not served as verified

# Tier 3: a human works the queue. Accept or refuse; either way it sticks.
for seg in store.list_segments(doc["id"]):        # the optional queue capability
    cascade.graduate_segment(seg["id"], verifier="rita")
    # or: cascade.reject_segment(seg["id"], verifier="rita", reason="…")

# From now on, the same request is a tier-1 hit with rita's name on it.
memory.best_sealed("Please sign the attached form.", "en", "es")
# {'pair': {...'verifier': 'rita'...}, 'similarity': 1.0}
```

Pairs are `sealed` (human-verified / curated) or `draft` (machine, awaiting
seal). Only sealed pairs are served as tier 1; drafts may feed the engine as
style/terminology context but are never served as verified.

**Changing an answer keeps the answer it replaces.** `supersede_pair(...)`
retires the live sealed pair behind its successor — verifier required, because
replacing a sealed decision is itself a decision — and `revise_draft(...)` does
the same for a machine's own draft, deliberately taking **no** verifier: the
successor is a draft too, and sealing it stays a separate human act. Both keep
the old row with the reason it was replaced, and `memory_lineage` walks the
chain back, newest first. Both need the lineage capability
(`storage.supports_lineage`) and raise without it rather than falling back to
the destructive overwrite they exist to replace.

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

**A label has exactly one baseline.** That needed its own guard, because
`add_pair`'s conflicting-seal check keys on the normalized source and under a
`NumericMatcher` every figure is its own key — so a second baseline for a label
was not an overwrite, it was an insert. Both stayed sealed, and `check` scored an
observation against whichever it sat *nearest*: the one figure guaranteed to
excuse it. A `$4,900,000` spend passed cleanly against a superseded `$5,000,000`
ceiling while the standing `$1,000,000` one went unconsulted. Now a differing
figure from a different verifier raises `ConflictingSealError`; a same-verifier
restatement (or an explicit `override_conflict`) retires the superseded baseline
and ledgers the replacement. Where a store cannot retire it, `check` reports
`ambiguous=True` and uses the newest rather than the nearest.

All three recipes are driven from [the UI](#the-ui--where-the-human-sits) — same
memory, same threshold, same ledger, four buttons.

---

## Rejection — the reviewer's "no"

Sealing records that an answer is right. Rejection records that one is **wrong**,
so it is never served again. Both are verification decisions by a human, both are
signed, and both land in the ledger — otherwise the audit trail only ever records
agreement.

There are two different refusals, and the distinction matters:

```python
# 1. The mapping itself is wrong — retire it everywhere.
memory.reject_pair(pair_id, verifier="rita", reason="wrong time of day")

# 2. This pair is the wrong answer FOR THIS QUERY — it stays valid for its own
#    source text. This is what a false seal actually is. A hit from lookup()
#    or best_sealed() is {"pair": {...the stored row...}, "similarity": float}.
hit = memory.best_sealed("the penalty under section 900026", "en", "es")
memory.reject_match("the penalty under section 900026", "en", "es",
                    pair_id=hit["pair"]["id"], verifier="rita",
                    reason="different section")
```

A false seal is a *correct* pair matched to the wrong input, so rejecting the
pair would destroy a good verification. Rejecting the **match** suppresses it for
that one query and leaves the seal intact:

```
before: served 'SEALED-ANSWER-9072'  sim=0.971  state=SEALED   <- never verified for this input
        rita rejects that match once
after : best_sealed -> None
        lookup      -> []                     (also hidden from the engine)
        the real pair still serves its own source, sim=1.0
```

For a reviewer working the queue, `cascade.reject_segment(segment_id, ...)` is
the sibling of `graduate_segment` — accept or refuse, and either way it sticks.

Enforcement lives in `memory.lookup()`, which every serve path goes through, so a
rejected pair is hidden from tier-1 serving *and* from the engine's reference
context.

> **For hosts:** rejection is an **optional** Storage capability
> (`memory_reject_pair`, `memory_add_rejection`, `memory_rejections`). A store
> predating it keeps working untouched; `storage.supports_rejection(store)`
> reports it. Implement all three or none — partial support counts as none, and
> the `reject_*` entry points raise rather than silently discard a human's
> decision.
>
> A rejection is honored **even if its signature does not verify** — the reverse
> of how seals are treated. Suppressing an answer degrades to human review, which
> is the safe state; serving an unverified one does not. Validity is still
> reported via `memory.rejection_signature_report(...)`.

---

## The curator — seeing what was verified

Sealing without a way to review it is write-only trust. `nestor.curator.Curator`
is the surface for whoever owns the memory: browse it, inspect provenance, spot
seals that do not verify, and revoke.

```python
from nestor.curator import Curator

c = Curator(store, source_lang="en", target_lang="es")

c.list(status="sealed", contains="invoice")   # browse, filter, paginate
c.get(pair_id)                                # provenance + every rejection against it
c.unverifiable()                              # says "sealed", would NOT be served
c.unseal(pair_id, verifier="rita", reason="terminology changed")
c.export()                                    # the whole memory, JSON-ready
```

Every row carries **`servable`** alongside `status`, because they are not the
same question. `servable` runs the identical check the serve path uses, so a row
marked `sealed` whose signature does not verify shows up as `servable=False` —
written by something that never held the seal key:

```
  sealed   servable=True   rita      the annual invoice
  sealed   servable=False  mallory   forged phrase        <- unverifiable() finds this
```

**Unsealing is not rejecting.** Unsealing returns a pair to `draft` for
re-verification; [rejecting](#rejection--the-reviewers-no) retires it as wrong. A
curator who is merely unsure shouldn't have to choose between destroying a
mapping and leaving a seal standing they no longer trust. Both are written to the
ledger — a trail that records every grant of trust and no withdrawal of it isn't
an audit trail.

Re-sealing a rejected pair raises `RejectedPairError` rather than silently
resurrecting it; `Curator.restore(pair_id)` is the deliberate way back, and it
returns the pair to `draft` so it gets re-verified rather than reinstated.

> **For hosts:** curation is an **optional** Storage capability (`memory_list`,
> `memory_get`, `memory_unseal`, `memory_rejections_for_pair`). A store predating
> it keeps working; `storage.supports_curation(store)` reports it, and `Curator`
> raises `CurationUnsupportedError` rather than offering actions the store cannot
> carry out.

---

## The UI — where the human sits

Everything above is a library surface. Nestor's whole claim is that *a human
checked this*, and until now that human had to write Python to do it: the
reviewer worked the queue through `graduate_segment` calls typed into a REPL,
the curator browsed the memory through `Curator`. `nestor.ui` is the place a
person can actually sit down at.

```bash
python -m nestor.ui --db data/nestor.db          # http://127.0.0.1:8765
nestor-ui --db data/nestor.db --open             # same, via the console script
```

Stdlib only — `http.server` and one inlined page — so the runtime dependency
count stays zero. Four views, each one a surface the package already had and
nobody could see:

| View | What it is |
|------|-----------|
| **Queue** | The segments the cascade left for review. Seal, correct-then-seal, or reject each one; the segment leaves the queue and the decision is signed and ledgered. |
| **Memory** | The curator's view over any domain in the store: filter, inspect provenance and every rejection against a pair, unseal, reject, restore, seal one by hand into any domain (or a new one), export and import. Every row shows `servable` beside `status`. |
| **Ask** | The mechanic, in whichever recipe you pick — translate, resolve an entity, reconcile a figure, or run the bare seam. Each answer comes with the ranked candidates that produced it and what they scored. |
| **Ledger** | `verify()`'s verdict and the chain itself, so the audit trail can be read where the decisions are made. |

### Ask is recipe-shaped, not translation-shaped

The [recipes](#the-recipes) are four buttons, over one memory and one ledger:

| Recipe | What you type | What comes back |
|--------|---------------|-----------------|
| **Translate** | a phrase, and two language tags | the cascade's three states — sealed, draft, pending |
| **Entity** | a surface form, and an entity domain | the canonical entity, or an *unsealed suggestion* to seal, or nothing |
| **Numeric** | a label, a figure, and a tolerance | within tolerance / flagged with the exact variation / no baseline yet |
| **Match** | any value, any two domain tags, either shipped matcher | the normalized key, every candidate's score, and whether it would be served |

Each one seals from the same screen — an alias, a baseline, a translation — and
every seal, resolve, check and rejection lands in the one hash-chained ledger.
The Memory view's domain picker lists every tag pair actually in the store
(`en → es`, `company`, `ceiling → contract`, …) with its size, so several
disjoint graphs in one database are visible rather than assumed.

> The UI never *infers* which recipe a domain belongs to. `("company",
> "company")` is probably an entity graph and `("en", "es")` probably a
> translation, but nothing enforces either, and a surface that guessed wrong
> would mislabel someone's data with total confidence. You pick the recipe; it
> reports what exists.

The Ask view is the one to open first, because it shows the product rather than
describing it. Asking for a phrase that only *nearly* matches a sealed one:

```
~ draft   tier 2   offline-tm   confidence 0.7
Firme y devuelva el formulario adjunto.
A machine produced it. Queued for review, never served as verified.

Ranked candidates. A sealed one serves only at or above 0.92.
✓  0.875   Please sign and return the attached form. → Firme y devuelva el formulario adjunto.
```

And asking for one whose only match is a row that *claims* to be sealed but was
written without the seal key — the forgery `Curator.unverifiable()` exists to
surface, seen from the serve side:

```
! pending   tier 0
—
Nothing to offer. Said plainly rather than improvised.

✓  1.000   wire the funds to the new account → transfiera los fondos a la cuenta nueva
           sealed · NOT SERVABLE · by mallory
```

A perfect match, and the answer is still *pending*. That is the whole product in
one screen.

The same screen in the **Entity** recipe, resolving `amazon web services, inc.`
against a sealed alias graph — an alias scoring 0.905 is below the cutoff, so
what comes back is an offer to seal, not an answer:

```
~ draft   domain company   confidence 0.905   via "Amazon Web Services"
Amazon
Nothing verified matched closely enough. This is a suggestion to seal, not an answer.

✓  0.905   Amazon Web Services → Amazon      sealed · by analyst
✓  0.611   Amazon.com Inc      → Amazon      sealed · by analyst
```

And in **Numeric**, an observation against a sealed contract ceiling:

```
✗ flagged   ceiling · contract
baseline    observed    variation   as %      tolerance
1,000,000   1,250,000   250,000     25.00%    ±0 or 5.00%
Outside the tolerance band. The variation is reported, not smoothed.
```

**What the UI does not do is authenticate anybody.** The verifier is typed, not
proven — the same trust model as calling `memory.add_pair(verifier="rita")`
yourself. So it binds to loopback and refuses a public bind unless you pass
`--allow-remote`, mutating requests are refused unless they carry the page's own
header (so another browser tab cannot POST a seal into it), and the page is served with a
Content-Security-Policy of `default-src 'none'` plus `connect-src 'self'` (the
inline stylesheet and script are allowed, nothing external is, and `fetch` can
only reach this server) — an audit surface should not be able to ship the memory
it is displaying anywhere. Seal
*signatures* (`NESTOR_SEAL_KEY`) remain the thing that makes a seal unforgeable;
nothing here weakens them, and the header badge tells you when they are off.

`--read-only` refuses every decision at the API layer, for showing the memory to
someone without handing them the ability to change it. `--engine` defaults to
`offline` rather than `auto`, because a click in a browser should not silently
call a paid API.

> **For hosts:** the queue view needs a third **optional** Storage capability —
> `list_documents`, `list_segments`, `update_segment_status`
> (`storage.supports_queue`). Without it the other three views work and the
> queue says so, rather than showing an empty list that means "this store cannot
> tell you".

---

## The CLI

The CLI is its own process, so it does not see a store your Python snippet set
with `set_store(":memory:")` — it reads `--db` (default `./data/nestor.db`) and
`--ledger` (default `NESTOR_LEDGER` or `./data/ledger.jsonl`). Both are global
flags, so they go **before** the subcommand: `nestor --db mydb.db ask "…"`, not
`nestor ask "…" --db mydb.db`. The examples below assume something has been
sealed into that file-backed store; to make the first one answer, seed it once:

```bash
python - <<'EOF'
from nestor import memory, storage
from nestor.sqlite_store import SqliteStore
storage.set_store(SqliteStore("data/nestor.db"))
memory.add_pair("Good evening.", "Buenas noches.", "en", "es",
                status="sealed", verifier="rita")
EOF
```

```bash
nestor ask "Good evening."               # ✓ sealed  Buenas noches.  (verified by rita)
nestor resolve AMZN --domain company     # the entity graph
nestor check ceiling '$1,030,000' --domain contract
nestor export --out memory.json          # a portable bundle
nestor import memory.json                # dry run; --apply commits
nestor ledger verify                     # exit 1 on a broken chain
nestor stats
nestor calibrate --from en --to es       # where the threshold belongs for this corpus (--matcher too)
nestor rejections                        # what the recorded "no"s say in aggregate
nestor keys add rita --keyring keys.json # a key per verifier; keys list / revoke
nestor ui                                # the browser surface
nestor serve                             # MCP over stdio, for a model
```

**Exit codes mean something.** `0` is the good answer, `1` is the bad one — an
unverified answer, a flagged figure, a broken chain, an import with conflicts —
and `2` is a usage error. So `nestor ledger verify` is a CI gate and `nestor ask`
belongs in a shell conditional:

```bash
nestor ask "$phrase" >/dev/null || echo "nothing verified for that — ask a human"
```

## Export and import — taking the memory elsewhere

```bash
nestor export --out memory.json          # pairs, rejections, signatures, digest
nestor import memory.json                # reports what would happen
nestor import memory.json --apply --verifier rita
```

Export is easy. Import is the half worth explaining, because **a bundle is a
file, and a file claiming `"status": "sealed"` is making exactly the claim a seal
signature exists to distrust** — the same claim a forged database row makes. So
import applies the serve path's rule rather than a softer one:

| Incoming row | What happens |
|---|---|
| sealed, and its signature verifies **here** | imported sealed — this is what sharing a `NESTOR_SEAL_KEY` between instances buys you |
| sealed, signature does not verify | imported as a **draft**, into the review queue — counted, warned about, and never served |
| sealed, and **this instance has no key configured** | imported sealed on stored status alone — the serve path would trust the same row for the same reason, so import does not pretend to a stricter rule than serving has. `NESTOR_REQUIRE_SEAL_KEY=1` refuses the import outright |
| draft | imported as a draft |
| same source, a *different* target | **conflict**: listed for a human, never resolved silently (`--override-conflicts`) |
| a pair **rejected here** | listed and skipped — `--override-conflicts` deliberately cannot reach it, because a rejection is not a competing answer (`--override-rejections`, or `Curator.restore`, is the way back) |
| sealed and verified, over a local **draft** of the same text | the draft is upgraded — same answer, but one side has a verification the other lacks |

```
would import: 16 sealed, 1 demoted to draft (signature does not verify here),
              1 draft, 0 already present, 1 rejection(s)

nothing was written — re-run with --apply to commit.
```

Dry run by default, in the library and the CLI both, because an import decides
what an instance will serve as human-verified. The UI has the same flow with the
report on screen. **The ledger does not merge** — a hash chain has one history by
construction, so a bundle carries the source chain for *reading* and the import
itself is what gets appended locally.

`--format csv` is offered and is deliberately lossy: it drops signatures, so a
CSV round-trip cannot carry a verifiable seal. Use it to read a memory, not to
move one.

This is a transfer, not a sync: there is no continuous replication and no
three-way merge, and a pair's id is per-instance. [QUESTIONS.md
§8](QUESTIONS.md) says what that would take.

## Serving a model — and the one thing it cannot do

```bash
nestor serve --db data/nestor.db         # MCP over stdio, stdlib only
```

```json
{"mcpServers": {"nestor": {"command": "nestor",
                           "args": ["serve", "--db", "data/nestor.db"],
                           "env": {"NESTOR_SEAL_KEY": "…"}}}}
```

A model gets `nestor_ask`, `nestor_resolve`, `nestor_check`, `nestor_match`,
`nestor_provenance`, `nestor_ledger_verify` — and `nestor_propose`, which queues
its answer for a human as a `draft`.

**It cannot seal.** Not "sealing is disabled by default" — there is no sealing
tool, no flag that adds one, and no argument to any existing tool that produces
one. A plausible-sounding name gets a refusal that explains why:

```
PermissionError: 'nestor_seal' is not available to a model. This server
deliberately withholds: seal, unseal, reject, override a conflicting seal,
import a bundle, edit the ledger. Verification is a human act — use
nestor_propose to put an answer in front of one.
```

That is the product, not a precaution. "Has a human checked this?" is worth
exactly as much as the difficulty of getting a machine's output marked as
checked, so `tests/test_serve.py` pins it as a property: after a model has called
every tool this server has, the sealed memory is unchanged.

`--read-only` withholds even the proposal, for an agent that should be able to
*read* the verified memory and put nothing into it.

What comes back is the **state**, not just a string — so an agent can cite a
human, or decline:

```
ask "good evening"                 -> verified=True  state=sealed   by=rita
ask "wire the funds to the new account"
                                   -> verified=False state=pending
                                      (top candidate scored 1.0, servable=False)
```

A perfect match, and the model is still told it has nothing verified — because
that row was written by something that never held the seal key.

---

## The ledger

Every passage, seal, rejection, unseal, resolution and check is appended to a hash-chained ledger
(`data/ledger.jsonl` by default). Each line records `prev = sha256(previous
line)`, so the audit trail is tamper-evident — and all recipes share one chain.

Nestor fails closed on it. Appending refuses if the ledger is a symlink or not a
regular file (the trail must not be redirectable or suppressible), and the
existing chain is verified before it is *first* extended in a process, so a
broken chain is refused rather than silently extended — see `IDEAS.md` §5.3 for
the once-per-process limit and what it does and does not cost you.

**A decision that cannot be recorded is not made.** Those refusals run *before*
the store is written (`cascade.ledger_preflight`), so a seal, a rejection or an
unseal onto an unwritable or broken chain is refused outright rather than
committed and then regretted. A draft still lands — a draft is not a
verification. Appends are serialized across threads and processes, because a
concurrent writer used to produce a chain that verified as broken while every
entry was present.

Be precise about what that limit is: the tamper is still **caught**. `verify()`
fails before and after, and the chain stays broken, so tamper-evidence — the
load-bearing property — holds completely. What you lose is the early refusal.
Inside one long-lived process, after the first append, a new entry can chain onto
a tampered history without a refusal unless you set a re-verify interval.
``NESTOR_LEDGER_VERIFY_INTERVAL_SEC`` (or ``cascade.set_ledger_verify_interval``)
controls how often the full walk runs on seal/reject: ``0`` is once per process
(default for batch/CLI); ``nestor.ui`` defaults to 300 seconds when unset.

Configure the path with `NESTOR_LEDGER` or `cascade.set_ledger_path(...)`.

Term locks resolve the same way: `NESTOR_GLOSSARY` or
`glossary.set_glossary_path(...)`, defaulting to `./data/glossary.json` relative
to the directory the process started in. Set one of the two in any deployment
whose working directory is not the one the terms were entered from — a service
unit and a developer shell reading different glossaries is silent, and the only
symptom is tier-2 drafts ignoring terminology somebody chose (`IDEAS.md` §6.27).

**Only the *default* is captured at startup.** A `chdir` cannot move the
glossary under a running process, but `NESTOR_GLOSSARY` is read on every call —
the same posture `NESTOR_LEDGER` has — so anything that mutates the environment
mid-process still switches files. A deployment that wants the path fixed for the
life of the process calls `glossary.set_glossary_path(...)` once at startup;
that wins over the variable and nothing later can move it.

**Nothing is ever deleted, and that is a design decision with a cost.** Rejecting
and unsealing preserve the trail; there is no `memory_delete`, because hard
deletion punches a hole in a hash chain by construction. An erasure path has to
be designed *against* the ledger rather than bolted on, so until someone does
that work: do not put personal data in the source text. [QUESTIONS.md
§10](QUESTIONS.md) states the same thing where a compliance reader will look for
it.

```python
from nestor.ledger import verify
verify("data/ledger.jsonl")     # (True, 'intact — 18 entries')
```

**The walk cannot vouch for the newest entry.** Every line is verified by the
line after it, so the last one — the one that just recorded who sealed what — has
nothing following it, and editing it leaves the chain walking clean. That is a
property of hash chains, not a bug in the verifier, but "the most recent decision
is the editable one" is a strange thing for an audit trail to leave unsaid. Pin
the tip somewhere the ledger's writer cannot reach:

```bash
head=$(nestor ledger head)                    # store this in CI, a monitor, anywhere else
nestor ledger verify --expect-head "$head"    # exit 1 if the tip moved unexpectedly
```

[FRANK](#frank--mirroring-into-shared-provenance) is the same idea taken to its
conclusion: every entry mirrored into a ledger somebody else holds, each carrying
its own `local_hash`.

### Seal signatures

Set `NESTOR_SEAL_KEY` and every seal is bound to a key the store does not hold,
so a row edited to `status='sealed'` directly in the database will not verify and
will not be served. Without the variable Nestor warns and trusts stored status —
set `NESTOR_REQUIRE_SEAL_KEY=1` to fail closed instead.

The key is an arbitrary string used as an HMAC secret — there is no required
format, so generate one with entropy rather than inventing one:

```bash
export NESTOR_SEAL_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
# keep it out of source control; every seal made under it verifies only where it is set
```

### Who verified it — per-verifier keys

One `NESTOR_SEAL_KEY` proves *the key was present*. It does not prove **who**:
every verifier signs with it, so `verifier="rita"` is still a string anybody who
can reach the process can type. A keyring (`nestor.keyring`) gives each verifier
their own key, so a valid signature over `(source_norm, target_text, "rita")` is
evidence about rita.

```bash
nestor keys add rita --keyring keys.json     # prints the key once; the file is 0600
nestor keys add sam  --keyring keys.json
export NESTOR_KEYRING=keys.json
nestor ui --db data/nestor.db                # "acting as" becomes a sign-in
```

For **fleet-gap** review (willow SOIL imports), the UI can echo Hanuman dispatch
handoffs from a charter rollup JSON plus files under your willow home:

| Variable | Meaning | Default |
|----------|---------|---------|
| `NESTOR_GATE_ROLLUP` | path to fleet-gap seals JSON (willow `governance/decisions/*` schema) | unset — override with `nestor ui --gate-rollup` |
| `WILLOW_HOME` | willow **fleet** runtime root (`store/`, `dispatch/`, `mcp_apps/` — see `docs/roots-willow-and-homestead.md`) | `~/github/.willow` (alias `~/.willow`) |
| `HOMESTEAD_HOME` | household root when a host pins Nestor under homestead (see `docs/homestead-paths.md`) | `<home>/.homestead` |

With a keyring in force:

* a seal is signed with the named verifier's key, and a name the keyring does
  not know **cannot seal** — `UnknownVerifierError`, raised before anything is
  written;
* the UI stops taking a typed name. A verifier signs in with their key, and
  every decision in that session is recorded and signed as them;
* moving a real signature onto a different name in the database no longer
  works — it verifies under the key of the verifier it names, or not at all.

A **rejection** by an unregistered name is still recorded and honored, and
reported as unsigned. Refusing to record a "no" is the one direction rejection
must not fail in: it would leave a bad answer serving because a reviewer was not
on a list.

**Revoking a key asks one question, because the answer genuinely differs.** An
HMAC carries no timestamp, so a signature cannot tell "sealed by rita last
March" from "forged last night by whoever took rita's key". Nestor will not
guess:

```bash
nestor keys revoke rita --reason "left the team"          # rotated
nestor keys revoke sam  --compromised --reason "stolen"   # taken
```

| | new seals | seals it already made |
|---|---|---|
| rotated (`--reason`) | refused | **keep serving** — nobody else held the key, so they are still that person's verifications |
| `--compromised` | refused | **stop serving** — indistinguishable from the thief's; the rows surface in `Curator.unverifiable()` and the UI's unverifiable filter for re-verification |

Migrating a store sealed under a single key: `nestor keys add NAME
--adopt-shared-key` also trusts `NESTOR_SEAL_KEY`, so existing seals keep
serving and are reported as `legacy` — verified by somebody here, not
attributable to a person, which is what they always were. Leave it out and they
land in `unverifiable()` for re-verification instead.

What this is not: a shared secret proves possession of a key, not the presence
of a person, and with HMAC entries the process necessarily holds the keys it
verifies against. The asymmetric upgrade exists, behind the `[keys]` extra
(`pip install -e ".[keys]"`):

```bash
nestor keys add rita --type ed25519 --keyring keys.json   # generates a keypair here
nestor keys add peer --type ed25519 --public <hex> --keyring keys.json
```

An ed25519 entry signs with a private key and verifies with the public half —
so a keyring holding only a peer's **public** key can verify their seals while
being structurally unable to sign as them, which is what makes an imported
bundle's seals checkable without sharing a secret. HMAC entries and the
single-`NESTOR_SEAL_KEY` deployment are unchanged, through the same
`signing.sign_seal(..., key=)` seam.

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

**Core** — every store must implement these.

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

**Optional capabilities** — all-or-nothing, each reported by a `supports_*`
predicate. A store predating one keeps working, and the surfaces that need it say
so rather than showing an empty list, because "nothing here" and "this store
cannot tell you" are different facts.

| Capability | Operations | Reported by | Without it |
|---|---|---|---|
| Rejection | `memory_reject_pair`, `memory_add_rejection`, `memory_rejections` | `supports_rejection` | `reject_*` raises rather than dropping a human's "no" |
| Curation | `memory_list`, `memory_get`, `memory_unseal`, `memory_rejections_for_pair` | `supports_curation` | `Curator` raises `CurationUnsupportedError`; no export/import |
| Review queue | `list_documents`, `list_segments`, `update_segment_status` | `supports_queue` | the queue cannot be listed or cleared; everything else works |
| Rejection listing | `memory_list_rejections` | `supports_rejection_listing` | rejections still record and read by key; export says a bundle ships without the ones naming no pair, rather than shipping quietly short |
| Lineage | `memory_mark_superseded`, `memory_lineage` | `supports_lineage` | `supersede_pair` / `revise_draft` raise rather than destructively overwriting a prior decision |
| Atomic supersede | `memory_mark_superseded_if` | `supports_atomic_supersede` | `revise_draft` refuses rather than racing — a race here could retire a human's seal under an unverified draft |

Partial implementation counts as none. Writing rejections nobody can read back,
or offering an unseal the store cannot perform, is worse than not having the
feature.

</details>

### Other injected seams

- **Draft engine** — `nestor.engine.get_engine("auto"|"claude"|"offline")`. The
  Anthropic SDK import is lazy: without credentials (`ANTHROPIC_API_KEY`) or the
  `anthropic` package, `auto` falls back to the deterministic offline
  TM-composite engine — silently, so if you expected a Claude draft and got an
  offline one, the unset variable is the first thing to check.
- **Bilingual corpus loader** — `memory.set_bilingual_loader(fn)`, or pass
  `loader=` to `seed_from_corpus`. Default returns `[]`.

---

## Accuracy, and how to measure yours

A tier-1 hit is served verbatim and marked verified, with **no review queue**. So
the failure that matters is the inverse of the usual one: not a missed match, but
a phrase that was never verified being served as though it were.

Both are governed by `SEAL_THRESHOLD` (default `0.92`), and **no value of it is
good at both jobs.** Measured, 250 probes per cell:

| threshold | false seals (24k boilerplate) | recall on real rewrites |
|-----------|------------------------------:|------------------------:|
| 0.92 (default) | 16.4% | 23.6% |
| 0.96 | 0.4% | 2.4% |

Raise it and unverified answers stop being served, but so do genuine ones —
a phrase retyped with one synonym swapped stops matching. Lower it and the
reverse. That is a limit of character-similarity matching, not a tuning problem,
and it is why the threshold is exposed rather than tuned for you.

Recall above is measured against **meaning-preserving rewrites** — synonym
substitution, clause reordering, dropped function words. Measured against
surface variation only (case, punctuation, whitespace, a typo) recall reads 100%
in every row of that table, because Nestor's normalization erases those before
scoring. Ask which one a benchmark is reporting.

The right cutoff also depends on your corpus. Homogeneous text — contract
boilerplate, templated notices — degrades far faster than diverse prose.

**So measure it rather than trusting the default.** `bench/` sweeps the threshold
against corpora at both ends of the diversity spectrum and reports false-seal
rate against recall at each cutoff:

```bash
python bench/bench_accuracy.py --probes 400
```

The full sweep takes on the order of ten minutes; it checkpoints after every
row and `--resume` continues an interrupted run, so a timeout costs nothing —
[`bench/README.md`](bench/README.md) explains, including why a result with
`"complete": false` is a prefix, not an answer.

Results land in `bench/results/*.json` with parameters, environment and git
revision attached. [`bench/README.md`](bench/README.md) documents the method,
including the properties a corpus must preserve to produce a meaningful number.

The trade is a shape, so there is a chart of it — read-only, stdlib, no build:

```bash
python bench/serve_ui.py --open       # http://127.0.0.1:8770/ui/
```

**And then calibrate against the memory you actually have.** The bench measures
the matcher in general; `nestor calibrate` measures *your* corpus, by asking
the only question that needs no probe set:

```bash
nestor calibrate --from en --to es --target 0.01
nestor calibrate --from en --to es --matcher semantic --target 0.01  # needs the [semantic] extra
```

Pass ``--matcher`` when you serve with ``semantic`` or token bench matchers —
the shipped ``0.92`` default was measured for ``StringMatcher``.

For each sealed pair, it finds the other sealed pair whose source scores highest
against it and whose target is **different** — which is exactly a false seal, and
one that already exists in your memory between two things a human verified. It
reports the rate at every cutoff, recommends the cheapest one that meets your
target, and says so plainly when no cutoff reaches it (that is a corpus problem,
not a dial problem). It changes nothing: moving the threshold is a decision
about how much unverified content you will serve, and it belongs to a person. It
is also a *lower* bound — real queries include text the memory has never seen.

Two consequences of that, stated rather than implied. **A small memory
recommends low, and means nothing by it** — fewer pairs means fewer collisions,
so an early, near-empty memory clears any target at the lowest cutoff swept.
Treat a recommendation from a few dozen pairs as noise and calibrate again once
the memory has grown. And **applying the result is deliberately manual**: pass
`seal_threshold=` per call to `best_sealed`, or rebind
`nestor.memory.SEAL_THRESHOLD` at process start. There is no env var, because
moving the dial is a decision someone should be able to find in code review,
not a deployment setting that drifts.

Known limits, measured and recorded in [`IDEAS.md`](IDEAS.md):

- **Lookup is linear in corpus size**, and ~97% of the time is Python-side
  scoring rather than SQL. Nestor is built for high-value, reviewed decisions,
  not high-volume serving. `best_sealed` prunes losslessly on difflib's own
  bounds (§2.1), which makes the *absent* case — nothing verified matches —
  roughly an order of magnitude cheaper, but the scan is still a scan.
- **The threshold wants calibrating per corpus, not trusting.** No single cutoff
  is both safe and useful across corpora (§1.3).

### Why the numbers are published

Everything above admits a failure rate, in public, in the README. That is
deliberate, and it is the point of the section rather than a caveat attached to
it.

*"We are accurate"* is a claim anyone evaluating a system for a regulated
process already knows is unfalsifiable. It names no rate, no corpus and no
cutoff, so it cannot be wrong, which is exactly why it cannot be relied on
either. The replacement is not a better adjective:

> Here is the measured false-verification rate. Here is the dial that sets it.
> Here is the harness — run it against your own corpus and get your own number.

Each of those three is a file in this repository. The harness is `bench/`; the
dial is `SEAL_THRESHOLD` and `nestor calibrate`; the numbers are committed under
[`bench/results/`](bench/results/) as JSON carrying the parameters, the
environment and the git revision of the run that produced them, so a result can
be cited and re-derived rather than quoted. `"complete": false` marks a prefix
rather than an answer, which is a distinction a marketing number would not
bother to keep.

The argument runs the same way as the rest of the system. A seal is worth
something because a forged one is refused and the chain says so; a measurement
is worth something because the method is published and the run can be repeated.
Neither is a promise about how good this is. Both are structures that make the
claim checkable by somebody who does not trust us — which is the only kind of
claim worth making to a buyer whose job is not trusting vendors.

For the sixty-second version of the whole argument, including the failure mode
where "thirty days" matches "sixty days", run `python demo/sixty_seconds.py`.

---

## The name

English **nest** descends from Proto-Indo-European \*ni-sd-ós — \*ni "down" plus
the zero grade of \*sed- "to sit". The nest is, literally, *the place where it
sits down*.

So here is the word, in the languages that inherited it. Which is also a
translation memory, so it is presented as one:

| target | rendering | state | note |
|--------|-----------|-------|------|
| Latin | *nīdus* | ~ draft | the Romance ancestor |
| Spanish | *nido* | ~ draft | |
| Italian | *nido* | ~ draft | |
| French | *nid* | ~ draft | |
| Portuguese | *ninho* | ~ draft | |
| Catalan | *niu* | ~ draft | |
| German | *Nest* | ~ draft | |
| Dutch | *nest* | ~ draft | |
| Sanskrit | नीड (*nīḍá*) | ~ draft | |
| Welsh | *nyth* | ~ draft | |
| Irish | *nead* | ~ draft | |
| Russian | гнездо (*gnezdó*) | ~ draft | inherited, with an irregular *g-* nobody has fully explained |
| Polish | *gniazdo* | ~ draft | same irregularity |
| Armenian | նիստ (*nist*) | ~ draft | **means "seat, session" — not "nest"**; and its derivation is contested |
| Romanian | *cuib* | ~ draft | **not a cognate**: Vulgar Latin \*clubium ← Greek κλυβίον |
| Greek | φωλιά (*foliá*) | ~ draft | **not a cognate either** — the Hellenic branch kept no reflex of \*nisdós |

**Every row is a draft, and that is not decoration.** Nobody in this repository
reads Romanian, Welsh or Armenian. The table was produced by a machine, at one
apparent confidence, for sixteen languages — and three of the last four rows are
the ones where that confidence was wrong or overstated. Checking is what
separated them; the last four rows are the return on it. In Nestor's terms these
are exactly what tier 2 emits: plausible, sourced, unsigned, and queued. They
become `sealed` when somebody who actually speaks the language says so, and not
before. That is the whole product, applied to its own README.

### The name is not the word

Nestor of Pylos — the Homeric counsellor who has outlived three generations and
gives long, reasonable, sometimes wrong advice — takes his name from a different
root. Νέστωρ is conventionally derived from \*nes- "to return safely home", the
root behind νόστος (*nóstos*) and, at one remove, *nostalgia*.

Two roots, one spelling. \*ni-sd-ós gives *nest*: **settle down**. \*nes- gives
*Nestor*: **come home safely**. They converge on the theme and are not the same
word, and the name does not translate at all — it transliterates:

| | |
|---|---|
| Russian | Нестор |
| Spanish | Néstor |
| Italian | Nestore |
| French / German | Nestor |

Which is where the joke stops being a joke. `StringMatcher.normalize` case-folds,
so `Nestor` and `nestor` are the same key, and the store holds one live row per
key — it cannot carry both the name and the noun, and there is no field that says
which one a string is. That is a real limitation, measured and written down as
[`IDEAS.md`](IDEAS.md) §6.22, not fixed, and honestly not urgent: nobody has hit
it.

### The other Nestor

The Homeric one gives the name its manner — counsel that is long, reasonable,
well-meant and sometimes wrong. A second namesake gives it the mechanism, and
fits so exactly that it is worth stating even though nobody chose it on purpose.

In Asimov's *I, Robot*, the **NS-2 series is nicknamed "Nestor"**. Not a
character — a production line. Sixty-three identical units, every one a Nestor,
and in "Little Lost Robot" (1947) one of them has had the First Law amended:
the clause *"or, through inaction, allow a human being to come to harm"* is
deleted and the rest of the sentence left alone. It still reads like the First
Law.

It was weakened because the strict version kept firing. Robots on the base were
hauling technicians out of radiation fields that were in fact safe for humans to
stand in — a guard producing false positives, so the guard was edited. That is
this repository's own argument, from the other side: *"an integrity check that
fails on a lossless round-trip trains people to ignore it, which is worse than
not having one"* ([`portable.py`](nestor/portable.py)). Asimov's engineers did
not ignore theirs. They amended it, which is the same instinct with better
tooling.

And then the modified unit hides among the sixty-two compliant ones and no
inspection can tell them apart. **That is the forged seal, described in 1947.**
A row that *says* `sealed` and a row that *is* sealed are indistinguishable
inside the store, which is precisely why a seal is bound to a key the store does
not hold — you cannot inspect your way to the answer, so you sign it. It is also
why Susan Calvin's anger is aimed at the people who authorized the modification
rather than at the robot: the constraint was never the machine's to relax, and
when a human relaxes it the accountability is that human's. See
[`verifier=`](#the-ledger).

One place it cuts the other way, which is the useful part. Asimov's failure is
harm *by inaction* — the machine standing there, permitted to let something
happen. Nestor treats deliberate inaction as the safe state: `pending`, nothing
to offer. The two are not in conflict, because Nestor-10's inaction is silent
and concealed, and `pending` announces itself. The whole product is the
difference between a machine that declines and a machine that merely doesn't.

---

## Development

```bash
pip install -e ".[dev]"
pytest -q                          # no outbound network
ruff check nestor tests            # enforced in CI
bandit -r nestor -ll -q            # enforced in CI
python bench/bench_accuracy.py     # measurements -> bench/results/
```

**Returning to an existing clone:** the install persists, the activation does
not — run `source .venv/bin/activate` in each new shell before any of the
above. The failure mode is quiet if you forget: the package imports from the
repo root without any install, so scripts and snippets keep working while
`nestor` and `pytest` are missing or stale. If commands are half-working,
check `which python` before debugging anything else. (Sessions on Claude Code
on the web skip all this — a `SessionStart` hook in `.claude/` builds `.venv`
and puts it on `PATH` before the session starts.)

CI runs lint and the test matrix (Python 3.10 and 3.12) on every pull request,
plus a daily scheduled run to catch drift. Ideas, open questions and measured
dead ends live in [`IDEAS.md`](IDEAS.md) — each entry tagged
**measured / verified / hypothesis / open**, so the confidence level travels with
the claim.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
