# The Matcher seam — in depth

*The [README](../README.md#the-matcher-seam) introduces the `Matcher` protocol and
the shipped matchers. This is the rest: how the embedding cache is signed, and
why a domain is its tags **and** its matcher. Both were measured, not
anticipated.*

---

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
> no longer pull against each other. See [`IDEAS.md`](../IDEAS.md) §3.1.

## The embedding cache is signed, for the same reason a seal is

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

### Semantic and Ollama configuration

`SemanticMatcher` (the `[semantic]` extra) defaults to `BAAI/bge-small-en-v1.5`;
set `NESTOR_SEMANTIC_TEST=1` with the extra installed to run the §3.1 acronym
integration test (`AWS` vs `Amazon Web Services`). The **`ollama`** backend needs
no pip extra but reads `OLLAMA_HOST` (default `http://localhost:11434`) and the
model pulled; its embedding model and request timeout are
`NESTOR_OLLAMA_EMBED_MODEL` (default `nomic-embed-text`) and
`NESTOR_OLLAMA_EMBED_TIMEOUT`. Nomic cosine bunches differently from
character-ratio / fastembed space, so measure with
`nestor calibrate --matcher ollama` before trusting serves.

## A domain is its tags *and* its matcher

Every surface that keys a row has to be handed the matcher that keys it. The
domain tags alone are half of a domain, and a surface holding only that half
files decisions under the default's key instead of yours — silently, with a
`200` and a valid signature:

```python
from nestor import memory, ui

app = ui.App(store=store, source_lang="incident", target_lang="incident",
             matcher=SerialMatcher())        # ← the other half

memory.set_matcher(SerialMatcher())          # or process-wide, for a single-domain host
```

`nestor ui --matcher {string,numeric,semantic,ollama}` names a **shipped** matcher; a
custom one cannot come off a wire, so it is passed in code. `ui.App(matcher=None)`
— the default — defers to the process-wide matcher rather than forcing
`StringMatcher`, so a host that called `set_matcher()` before launching the
surface keeps what it set. The Ask view shows which matcher is in force beside
the engine, and `/api/state` reports it as `domain.matcher` / `domain.matcher_source`.

**`App.matcher` describes `App`'s domain and no other.** The Ask and Match views
let a human retype the domain tags, and `/api/reject-match` is shared by every
recipe — the Entity view rejects an alias through it carrying the *entity*
domain, which `EntityResolver` keys with its own matcher. A request about another
domain therefore falls back to the process-wide default rather than borrowing
this App's. Getting that wrong re-created §6.40 one recipe over, for exactly one
release.

**A process is told by a spec, not by a name.** `nestor serve` and `nestor ask`
*are* the process, so there is no earlier moment at which a host could call
`set_matcher()`, and a shipped name cannot conjure a custom matcher. Point them
at one with `module:attribute`:

```bash
nestor serve --matcher acme.incidents:SERIALS      # a module attribute
nestor ask "CH4471 free-flow" --matcher acme.incidents:SerialMatcher   # or a class
nestor ui --matcher acme.incidents:SERIALS         # the same spec everywhere
```

Without it, a model asking over MCP gets `pending` for a phrase a human sealed
through this UI — measured, and the reason the flag exists (`IDEAS.md` §6.41).
The loader **imports the module named**, which is the same authority the command
line already has; it is a flag for that reason, and never a value read from a
request or a stored row. A spec that does not resolve to something offering
`normalize` and `similarity` is refused at startup rather than at the first query.

This is written down because it was measured, not anticipated:
[`IDEAS.md`](../IDEAS.md) §6.40 and the two-desk fixture
[`demo/two_desks.py`](../demo/two_desks.py) found that the UI had no way to be told,
which made both promises at the top of the README void for any domain that took
this seam at its word. The trail stayed intact throughout — a hash chain cannot
catch a true record of an answer nobody can reach.
