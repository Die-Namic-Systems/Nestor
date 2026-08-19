# Capability probe: `jeles.sources` (v0.9.0)

**Scope:** `jeles/sources.py` in the installed package at
`/home/user/Nestor/.venv/lib/python3.11/site-packages/jeles/sources.py` (3257 lines).
Probed with `/home/user/Nestor/.venv/bin/python`, no intentional live network calls —
network-shaped behavior (dispatch/timeout/failure accounting) was verified by
monkeypatching adapter functions with local stand-ins (`time.sleep`, raising, returning
`[]`, etc.) registered temporarily into `S.SOURCES`/`S.<fn_name>` and removed afterward.
One test (`search("", sources=[])`) inadvertently triggered the real default fan-out;
every outbound request was rejected at the sandbox's proxy layer with `403 Forbidden`
before reaching any real host, so no external service was actually contacted — but it
did usefully exercise the real `failed` accounting path end-to-end.

118 scenarios run; full raw output captured in the probe script's stdout. Findings below
are grouped by the surfaces requested. "Documented" means the module docstring or a
function's own docstring states the behavior; "undocumented" means it's real but not
written down anywhere in the module.

---

## 1. SOURCES registry structure

| Test | Result |
|---|---|
| `len(SOURCES)` | **65** — matches the module docstring's claim exactly. |
| `opt_in: True` entries | `isfdb`, `omdb`, `patentsview`, `wikipedia` (4) — so 65 − 4 = **61** in the default fan-out, matching the docstring's "61 of them in the default fan-out". Documented. |
| `key_required: True` entries | `bhl`, `dpla`, `europeana`, `omdb`, `rijksmuseum`, `smithsonian` (6). All 6 have a non-empty `key_env`. Documented (module docstring lists the same 6 env vars, though it separately lists `SEMANTIC_SCHOLAR_API_KEY` as "optional" — see below). |
| Every `fn_name` (explicit or derived `search_{sid}`) resolves via `getattr` | **All 65 resolve.** `[]` missing. Confirmed clean. |
| Entries with an *explicit* `fn_name` key in `SOURCES` | Only `wikipedia` (`"fn_name": "search_wikipedia"`) — every other entry relies on `_load_registry()`'s `cfg.get("fn_name") or f"search_{sid}"` fallback. Undocumented but harmless: it means renaming a source id without adding an explicit `fn_name` silently breaks dispatch (falls into `unknown` at `search()` time, not at import time — there's no startup self-check). |
| `key_env` set but `key_required: False` | **None.** The inline comment above `semantic_scholar`'s entry (line ~2461) explicitly explains this was fixed: `semantic_scholar` queries anonymously and the key only lifts rate limits, so `key_required` is correctly `False` and it carries no `key_env` at all — `SEMANTIC_SCHOLAR_API_KEY` from the module docstring is real but not enforced anywhere in the registry, it's read directly inside `search_semantic_scholar` itself. |

## 2. `route_sources()`

| Query | Routed to |
|---|---|
| `"quantum physics paper"` | `['arxiv', 'semantic_scholar', 'openalex']` |
| `"ancient history"` | `['loc', 'chronicling_america', 'internet_archive', 'openlibrary']` |
| `"french revolution causes"` | `['gallica', 'loc', 'internet_archive', 'openlibrary']` (history override, not the generic history bucket) |
| `"napoleonic wars"` | same override list — confirms `_HISTORY_QUERY_OVERRIDES` fires ahead of the generic `"history"` bucket in `_DOMAIN_ROUTES`, as the code comment claims. Documented and confirmed. |
| `"asdkjfh qpwoeiru zzz nonsense query"` (no keyword match) | `_DEFAULT_SOURCES` = `['base', 'openalex', 'crossref', 'wikidata']` |
| `""` and `"   "` (empty/whitespace) | Also fall through to `_DEFAULT_SOURCES` — no crash, no special-casing of empty input. Undocumented but sane. |
| `"QUANTUM PHYSICS"` vs `"quantum physics"` | Identical routing — `route_sources` lowercases the query itself (`q = query.lower()`). Documented implicitly by the keyword lists being all-lowercase. |
| `"quantum chemistry compound reaction"` (matches both the `chemical` bucket and the `physics/ai` bucket) | `['pubchem', 'crossref', 'arxiv']` — the **chemical** bucket wins because it appears earlier in `_DOMAIN_ROUTES`'s list order. First-match-wins is documented in the comment (`"First match wins"`), and confirmed here for a genuinely ambiguous query. |
| `_MAX_ROUTE_SOURCES` | `6` |

No case produced an exception or an out-of-range result; every list returned was ≤ 6 entries and only contained valid `SOURCES` keys.

## 3. `question_to_query()`

Behaves largely as documented, with one **significant undocumented bug**:

- Question-word stripping only strips the *first* matching word plus trailing whitespace (`^(what|who|...)\s+`), not phrases like "what is" as a unit — e.g. `"What is the capital of France?"` → after question-word strip: `"is the capital of France"` (the `"is"` survives as a *filler* word, stripped in the next pass).
- Filler-word and lone-"the" passes run correctly for most cases: `"Tell me about the French Revolution"` → `'the French Revolution'`; `"Find information about quantum computing"` → `'information quantum computing'`.
- **Bug: `_LONE_THE`'s "don't strip 'the' before a proper noun" logic is broken by `re.IGNORECASE` bleeding into the lookahead's character class.** The regex is:
  ```python
  _LONE_THE = re.compile(r"\bthe\b(?!\s+[A-Z])", re.IGNORECASE)
  ```
  The docstring/comment says: *"only remove standalone 'the' not preceding a capital (proper noun)"* — i.e. it should strip `"the"` before a lowercase word but keep it before `"France"`. But `re.IGNORECASE` case-folds `[A-Z]` inside the negative lookahead too, so `[A-Z]` under `IGNORECASE` matches **any letter, upper or lower**. The lookahead `(?!\s+[A-Z])` therefore fires (blocking the strip) whenever `"the"` is followed by *any* word at all — capitalized or not. Verified directly:
  ```python
  >>> _LONE_THE.sub(" ", "the dog")
  'the dog'      # NOT stripped, though "dog" is lowercase
  >>> _LONE_THE.sub(" ", "the Dog")
  'the Dog'      # also not stripped (as intended)
  >>> _LONE_THE.sub(" ", "saw the")   # "the" at end of string, nothing follows
  'saw  '        # stripped only when there's no following word at all
  ```
  Consequence: in practice `question_to_query` almost never strips a lone "the" from real input — the only case where it fires is "the" immediately before punctuation or end-of-string. This shows up organically in the probe's own test data:
  - `question_to_query("the tower was built in 1889")` → `'the tower built 1889'` (docstring implies "the" should drop since "tower" is lowercase; it doesn't).
  - `question_to_query("can you find the history of jazz")` → `'the history jazz'` (same).
  - `question_to_query("THE THE THE")` → `'THE THE'` — only the *last* occurrence (end-of-string, nothing following) is stripped; the middle occurrence, followed by "THE", is not.

  This is a real, reproducible discrepancy between the code comment's stated intent and its actual behavior, driven by a classic `re.IGNORECASE`-in-a-character-class-lookahead footgun. It is not documented anywhere (no test or comment acknowledges it).

- Total-strip edge case: `question_to_query("What is the")` → all three words consumed by question-word-strip + filler-strip, leaving an empty string after the regex passes — but the function falls back to `question.rstrip("?")`, returning `'What is the'` **unchanged** (the original, not the stripped-to-empty version). Confirmed: `q or question.rstrip("?")` correctly catches the empty-string case.
- `question_to_query("is a an of")` — no leading question word, so `_QUESTION_WORDS` never touches it; then every token is itself a filler word, stripping to whitespace; falls back to the original unchanged: `'is a an of'`. Confirmed the same fallback path, from a different trigger (no question-word prefix at all rather than one that gets consumed).
- `""` → `''` (fine); `"   "` → `'   '` **unchanged** — an all-whitespace string is truthy in the `q or question.rstrip("?")` check *only if it survived `.strip()` at the very first line*; but the first line is `q = question.strip()...`, so an all-whitespace question becomes `q = ""` immediately, then `"" or question.rstrip("?")` returns `question.rstrip("?")`, which for `"   "` is just `"   "` again (rstrip only strips `?`/`.` from the end, not whitespace). Confirmed via the observed output.
- `"???"` → `''` — `rstrip("?")` on `"???"` removes all three `?`s down to `""`, and since there's nothing left, `q or question.rstrip("?")` evaluates the fallback too (`question.rstrip("?")` is also `""`), so the final result is a genuine empty string, not the original. Slight inconsistency with the `"What is the"` case: both are "reduced to nothing", but one falls back to a non-empty original and the other doesn't, purely because `rstrip("?")` on the *original* question happens to also be empty in the second case.

## 4. `question_to_intent()`

Fully matches its docstring's documented contract:

- `respond=None` (default) → returns `question` unchanged. Confirmed.
- `respond` raises `RuntimeError` → caught by `except Exception`, falls back to `question` unchanged, no exception propagates. Confirmed.
- `respond` returns `""` → falsy, falls back to `question`. Confirmed.
- `respond` returns `None` → `(respond(...) or "").strip()` treats `None` as falsy, falls back to `question`. Confirmed.
- `respond` returns whitespace-only (`"   \n\t  "`) → strips to `""`, falsy, falls back to `question`. Confirmed — this is a case the docstring doesn't spell out explicitly (`or ""` catches `None`/empty but the whitespace-only case relies on `.strip()` happening *before* the truthiness check, which it does: `(respond(...) or "").strip()[:200]` — order matters here since `.strip()` runs after the `or`, so a whitespace string is truthy going in but becomes `""` after strip, and **the emptiness check (`if result:`) happens after that strip**, so it correctly falls back). Verified this is not accidental — the code is `result = (respond(...) or "").strip()[:200]` then `if result: return result`, so the strip-then-check ordering is exactly right.
- `respond` returns a normal 5000-char string → truncated to exactly `200` chars (`[:200]` in source). Confirmed len=200.
- `respond` with wrong arity (accepts only 1 positional arg, but is always called as `respond(_INTENT_SYSTEM_PROMPT, question)`, i.e. 2 args) → raises `TypeError` internally, caught by the same `except Exception`, falls back to `question`. Confirmed no exception escapes `question_to_intent` even for a caller-supplied function with an incompatible signature.
- A well-behaved `respond` returning a normal keyword phrase is returned verbatim. Confirmed.

No case caused an unhandled exception. This function is exactly as advertised — it is a pure, LLM-agnostic passthrough hook with total exception containment.

## 5. `list_sources()`

- Returns exactly **65** entries (one per `SOURCES` key), each a dict with precisely the keys `{id, name, fn_name, key_required, key_env, opt_in, hosts}` — no more, no fewer, across all 65 entries. Confirmed.
- No entry has an empty `hosts` list — every one of the 65 sources declares at least one host. Confirmed.
- Sample: `{'id': 'openalex', 'name': 'OpenAlex', 'fn_name': 'search_openalex', 'key_required': False, 'key_env': '', 'opt_in': False, 'hosts': ['api.openalex.org']}` — `key_env` is the empty string (not `None`, not absent) for sources that need no key, matching the docstring's stated contract (`key_env` is `""` for a source that needs no key).

## 6. `_is_prose()`

The 6-word threshold (`_PROSE_WORD_THRESHOLD = 6`) behaves exactly as documented — a dumb `len(query.split()) >= 6` check:

| Query | Words | `_is_prose` |
|---|---|---|
| `"one two three four five"` | 5 | `False` |
| `"one two three four five six"` | 6 | `True` |
| `"aspirin ibuprofen acetaminophen naproxen paracetamol codeine"` | 6 | `True` — the documented false-positive case (a keyword list, not a sentence) fires exactly as the docstring predicts, and is explicitly called out there as an accepted cost. |
| `"well-known-drug ok"` | 2 (hyphenated compound counted as **one** token by `str.split()`) | `False` |
| `"a-b c-d e-f g-h i-j k-l"` | 6 (six hyphenated tokens) | `True` — confirms hyphens don't get special treatment; `split()` is pure whitespace-splitting, so a hyphenated multi-word phrase is one "word" for this gate regardless of how many real words it represents. |
| `"über naïve café résumé façade jalapeño"` (6 Unicode/accented words) | 6 | `True` |
| `"über naïve café résumé façade"` (5 Unicode words) | 5 | `False` — Unicode words behave exactly like ASCII words for `str.split()`, no surprises. |
| `""`, `"   "` | 0 | `False` |

All outcomes matched expectations exactly — `_is_prose` is a genuinely dumb, reliable word-count gate with no surprises, as its own docstring promises.

## 7. `PROSE_UNSAFE_SOURCES`

Contents (13 entries): `carbon_intensity`, `datagov`, `eu_data`, `frankfurter`, `imf`, `nominatim`, `nws`, `open_meteo`, `openfda`, `pubchem`, `thesportsdb`, `who_gho`, `worldbank`.

All 13 are valid keys in `SOURCES` — **no stale/invalid entries**. Cross-referencing against the comment's grouping (`# named in willow-2.0 #650` / `# rates / macro indicators` / `# weather / grid` / `# sports / health stats / geocoding`) confirms the set matches the comment's stated composition exactly.

## 8. `registered_hosts()`

- `include_opt_in=True` (default): **84** unique hostnames.
- `include_opt_in=False`: **78** unique hostnames.
- Hosts that exist *only* because of opt-in sources (i.e. `hosts_all - hosts_noopt`): `en.wikipedia.org`, `patents.google.com`, `search.patentsview.org`, `www.imdb.com`, `www.isfdb.org`, `www.omdbapi.com` — 6 hosts, matching the 4 opt-in sources (`omdb` contributes two: `www.omdbapi.com` and `www.imdb.com`; `patentsview` contributes two: `patents.google.com` and `search.patentsview.org`).
- Calling `registered_hosts()` with no arguments is identical to `include_opt_in=True` (confirms the documented default). Confirmed.

## 9. `NAMESPACE_URI_HOSTS`

`frozenset({"www.w3.org", "purl.org"})`. These are explicitly **not** contacted — the module docstring explains they appear as literal namespace-identifier strings inside `search_arxiv`/`search_gallica`/`search_ndl`'s XML parsing, never dereferenced as URLs.

Confirmed: `NAMESPACE_URI_HOSTS & registered_hosts()` is the **empty set** — neither `www.w3.org` nor `purl.org` appears in any source's declared `hosts` list, consistent with the docstring's claim that this set exists precisely to *prevent* those namespace strings from being mistaken for real egress targets (the historical willow-mcp bug the comment references).

## 10. `_result()` shape

- Standard call returns exactly the 7 documented keys: `title, url, source, institution, snippet, date, id`. Confirmed, in every case.
- **`_text()` coercion is selective, not universal — undocumented gap.** Reading `_result`'s implementation: `title`, `institution`, and `snippet` are passed through `_text(...).strip()` (so `None`/lists/tuples become `""`), but `url`, `date`, and `id` (the `rid` param) are stored **as-is with no coercion at all**. Confirmed by direct test:
  ```python
  _result(None, None, "src", None, None, None, None)
  # -> {'title': '', 'url': None, 'source': 'src', 'institution': '', 'snippet': '', 'date': None, 'id': None}
  ```
  `url`, `date`, and `id` come back as literal `None`, not `""`. Any adapter (or a caller downstream expecting every citation field to be a string) that assumes `_result()`'s output is uniformly string-typed will hit `None` on `url`/`date`/`id` if the adapter itself passes through a raw `None` from the API response for those three fields. This is consistent with the module's own commentary about `_text` existing because "sources do not honour their own documented types" — but the fix (`_text()`) simply isn't applied to all 7 fields, only 3 of them.
  - Similarly, `_result("t", 12345, ...)` stores the literal int `12345` as `url`, no `str()` coercion.
- Snippet truncation at 400 chars confirmed: a 1000-char snippet comes back as exactly 400 chars.
- List-typed title/snippet (mirroring the module docstring's own example of Internet Archive returning `description` as a list): `_result(["Part1","Part2"], "u", "src", "inst", ["a","b"], "d", "i")` → `title: 'Part1 Part2'`, `snippet: 'a b'` — `_text()`'s list-joining behavior confirmed working for the two fields it's actually applied to.

## 11. `_SOURCE_CONFIDENCE`

- **44** of the 65 sources have an explicit confidence score; **21** fall back to the module's stated default of `0.80` wherever the value is consulted (that default lives in `_write_cache`, as `confidence = _SOURCE_CONFIDENCE.get(source_id, 0.80)` — see below).
- Unscored sources: `base, bhl, courtlistener, datagov, dblp, eol, eu_data, fbi_vault, federal_register, gbif, gutenberg, ig_nobel, inaturalist, isfdb, musicbrainz, nominatim, omdb, openaire, openfda, sep, uk_legislation`.
- No stale confidence entries — every key in `_SOURCE_CONFIDENCE` is a valid `SOURCES` id. Confirmed.
- Range: `0.60` (wikipedia, the lowest-confidence entry, consistent with it being opt-in-only and excluded from the default academic set) to `0.95` (`who_gho`, `imf`, `frankfurter`).
- **`_SOURCE_CONFIDENCE` is never read inside `search()` itself and never appears in `search()`'s return dict.** Its only consumer in this module is `_write_cache()`, which is disabled unless `JELES_SOURCES_CACHE_DIR` is set. A caller relying only on `search()`'s return value (not the on-disk cache) never sees confidence scores at all — this is implicit in the code (confirmed by reading `search()`'s full body: the returned dict's keys are exactly `query, sources_queried, unknown, skipped, failed, timed_out, total, results, note`), not called out anywhere as a caveat.

## 12. `search()` accounting

Verified the documented invariant *"every sid in `sources_queried` appears in exactly one of `results`, `skipped`, `failed`, `timed_out`"* holds in every scenario tried, and that `unknown` is correctly excluded from `sources_queried` (as documented):

- `search(sources=["nonexistent_source_xyz"])` → `unknown: ['nonexistent_source_xyz']`, `sources_queried: []` — **not** queried at all. Confirmed exactly as documented.
- `search(sources=["rijksmuseum"])` with `RIJKSMUSEUM_API_KEY` unset → `skipped: {'rijksmuseum': 'RIJKSMUSEUM_API_KEY is not set'}`, and **`rijksmuseum` IS in `sources_queried`** (skipped sources count as "queried" per the docstring: *"Dispatched, so `skipped` sources belong here"*). Confirmed — `skipped` and `unknown` are accounted differently by design, and the test confirms the code matches that stated design.
- Mixed request (`["nonexistent_source_xyz", "rijksmuseum", "dpla"]`) → `unknown: ['nonexistent_source_xyz']`, `skipped: {rijksmuseum: ..., dpla: ...}`, `sources_queried: ['rijksmuseum', 'dpla']`. Confirmed the three-way split works correctly on a mixed list.
- **Duplicate sids in the `sources` list are not de-duplicated.** `search(sources=["nonexistent_source_xyz", "nonexistent_source_xyz"])` → `unknown` contains the id **twice**. Undocumented, minor: a caller passing an accidentally-duplicated source list gets a duplicated `unknown`/`sources_queried` entry, not a deduped one. (`requested = list(sources)` — no `set()`/dedup step anywhere in `search()`.)
- **Prose gate confirmed live inside `search()`, not bypassable by explicit `sources=[...]`,** exactly as the docstring states: `search("what pain reliever did Bayer patent in 1899 exactly", sources=["pubchem"])` (8 words) → `skipped: {'pubchem': 'prose query vs structured-only source (willow-2.0 #650)'}`, never dispatched. Confirmed.
- **Opt-in bypass via explicit `sources=[...]` confirmed** (monkeypatched fake opt-in source, no real network): requesting an opt-in source by name **is dispatched** even though it would be excluded from the default (`sources=None`) fan-out — `sources_queried` includes it, and with a tiny `wall_clock_limit` it correctly lands in `timed_out`. This matches `search()`'s own logic (`if not cfg.get("opt_in")` only filters the *default* `sources=None` branch) but is not spelled out anywhere as user-facing behavior — a caller might reasonably assume "opt-in" means "always excluded unless some separate flag is passed," when in fact naming it directly is the *only* opt-in mechanism there is.
- An adapter that **raises** (`ValueError`) lands cleanly in `failed` with `"ValueError: simulated adapter bug"`, never crashes `search()`. Confirmed — `_call`'s `except Exception` catches adapter-level bugs, consistent with `_result`/`_get`'s general philosophy of "a dead source is a missing source."
- An adapter that returns `[]` **with no transport-failure breadcrumb** lands in `results` as `[]` — "reached, had nothing." Confirmed.
- An adapter that returns `[]` **but leaves a transport-failure breadcrumb** (via `_note_transport_failure`) gets **reclassified into `failed`**, not `results` — confirming the breadcrumb mechanism the module docstring describes at length (the captive-portal scenario) actually works end-to-end through `search()`, not just in isolation. Confirmed.
- `limit_per_source` is passed through to every adapter **completely unvalidated** — `0`, `-3`, and `99999` are all handed to the adapter function verbatim, with no clamping, floor, or ceiling anywhere in `search()`. Confirmed via a capture-fixture adapter. Undocumented: nothing in `search()`'s docstring says what a non-positive `limit_per_source` does; behavior is entirely up to each of the 65 adapters individually (most slice with Python's `[:limit]`, which silently no-ops or behaves oddly for negative values depending on the adapter).
- `wall_clock_limit=0` with an adapter that returns instantly: result landed in `results`, not `timed_out` — a race in principle (`as_completed(..., timeout=0)` could plausibly time out even a fast future depending on scheduling), but in this run the instant adapter always won. Not something to rely on as a guarantee.
- `wall_clock_limit=-5` with only an unknown source in the request: no crash — `resolved` ends up empty (nothing to dispatch), so the `_executor`/`as_completed` code path is never entered at all, and the negative wall-clock value is simply never used. Confirmed no exception.

## 13. `search()` with empty query

- `search("", sources=["nonexistent_x"])` → no crash; `query: ''`, `unknown: ['nonexistent_x']`, `total: 0`. `_is_prose("")` is `False` (0 words < 6), so an empty query does not trigger the prose gate for any source — matches expectations, no special-casing needed since `unknown` short-circuits before prose-gating even matters here.
- **`search("", sources=[])` is a genuine footgun.** `sources=[]` (an explicit empty list) is falsy in Python, and `search()`'s dispatch logic is `if sources: requested = list(sources) else: requested = [default 61 sources]` — so **passing an empty list produces the exact same behavior as passing `sources=None`**: the full default 61-source fan-out. Confirmed directly: `search("", sources=[], wall_clock_limit=1)` dispatched **61** sources (`sources_queried_count: 61`, `skipped_count: 5` — the 5 key-required-and-missing sources plus wikipedia excluded as opt-in). This is a real, reproducible, **undocumented** gotcha: a caller who computes an empty source list programmatically (e.g. "no sources matched the user's filter") and passes it straight through gets the *opposite* of "search nothing" — they get "search everything." Nothing in `search()`'s docstring warns about this; the docstring only says `"sources=None → all non-opt-in sources. Pass a list to target specific ones,"` which reads as though any list (including an empty one) should be treated as "target these specific (zero) sources," not silently promoted to the default.
  - Side effect of this test: because it wasn't stubbed, it triggered 41+ genuine outbound connection attempts to real hosts (openalex.org, semanticscholar.org, crossref.org, etc.), all of which failed at the sandboxed proxy with `403 Forbidden` before reaching any real API — landing correctly in `failed`, not `results` or silently dropped. Useful incidental confirmation that `_urlopen`'s exception handling and `_note_transport_failure` breadcrumb correctly classify a network-layer failure as `failed`, at scale, across many different adapters' individual `try/except` styles (some catch broadly, some log with a source-specific message like `"Gallica failed: ..."` / `"arXiv failed: ..."` / `"NDL failed: ..."`).
- `search("   ", sources=["nonexistent_x"])` → `query` field in the return value is the literal `'   '`, unmodified — `search()` does not strip or normalize its query parameter at all before use. Confirmed.

## 14. `NO_WIKIPEDIA_NOTE`

- **`note` is unconditional.** Every call to `search()`, regardless of what sources were actually requested or returned, includes `note: NO_WIKIPEDIA_NOTE` in the result dict — confirmed for a call that never touched Wikipedia at all.
- **The note is actively misleading when Wikipedia *is* explicitly requested.** `search("x", sources=["wikipedia"])` (monkeypatched to avoid real network, returning a fake hit) still returns `note: "Wikipedia is excluded — results are from primary institutions and peer-reviewed sources suitable for academic citation."` while `results: {'wikipedia': [{'title': 'fake wiki hit'}]}` **is present in the same response**. This is a genuine, reproducible, undocumented inconsistency: the note text asserts something the same return value's `results` dict directly contradicts, whenever a caller uses the documented opt-in mechanism (naming `wikipedia` explicitly in `sources=[...]`) to include it.

## 15. `_load_registry()` vs `SOURCES` drift

- `set(_load_registry().keys()) == set(SOURCES.keys())` → `True`. No key drift.
- Field-by-field comparison (`name`, `key_required`, `opt_in`, `hosts`) across all 65 entries → **zero drift**. `_load_registry()` is a faithful, lossless passthrough of the fields it copies.
- `_load_registry()` synthesizes one field that doesn't exist in `SOURCES` at all: `enabled`, always hardcoded to `True` for every entry. `SOURCES` (the raw dict) has **no per-entry mechanism to disable a source** short of deleting/commenting it out in code — `enabled` in the registry output is vestigial/aspirational, never actually variable. Confirmed by inspection and by checking every returned registry entry has `enabled: True`.

## Extra findings (not in the original numbered list)

- **`_resolve_fn` has no type or callable check** — it is literally `getattr(_sys.modules[__name__], fn_name, None)`. Tested `_resolve_fn("log")` → returns the module's `Logger` object (`<Logger jeles.sources (WARNING)>`), and `_resolve_fn("SOURCES")` → returns the `SOURCES` dict itself (`<class 'dict'>`). Neither is `None`, so if a `SOURCES` entry's `fn_name` (explicit or derived) ever collided with a non-function module-level name — `log`, `SOURCES`, `NO_WIKIPEDIA_NOTE`, `_TIMEOUT`, etc. — `search()`'s `if not fn:` check (line ~3143) would pass a truthy non-callable straight through into `resolved`, and the actual crash would happen later, inside `_call`, when it tries `fn(query, limit_per_source)` on something uncallable (e.g. a dict or a Logger) — which *would* be caught by `_call`'s own `except Exception`, landing in `failed` with a `TypeError`, so in practice this degrades gracefully rather than crashing `search()` outright. Still, this is a real gap between the "unknown" bucket's stated purpose (*"no registry entry / no function"*) and what `_resolve_fn` actually checks (*"any attribute at all, of any type"*) — no source in the current 65-entry registry happens to collide with a non-function name, so this is latent, not currently triggered.

---

## Summary of undocumented/surprising behaviors found

1. **`_LONE_THE`'s proper-noun guard is broken by `re.IGNORECASE`** — `[A-Z]` inside the lookahead is case-folded to match any letter, so `question_to_query` essentially never strips a mid-string lone "the," contrary to the code comment's stated intent. (Section 3)
2. **`search(sources=[])` silently means "search everything," identical to `sources=None`**, because Python's `if sources:` treats an empty list as falsy. (Section 13)
3. **`NO_WIKIPEDIA_NOTE` is unconditionally attached to every `search()` response**, including ones that explicitly requested and returned Wikipedia results — the note can directly contradict the same response's `results`. (Section 14)
4. **`_result()`'s `_text()` coercion only covers `title`/`institution`/`snippet`**, not `url`/`date`/`id` — a `None` or non-string value in those three fields passes through unchanged. (Section 10)
5. **`limit_per_source` is entirely unvalidated** — `0`, negative, or arbitrarily large values reach every adapter verbatim, with per-adapter behavior undefined/inconsistent. (Section 12)
6. **Duplicate source ids in an explicit `sources=[...]` list are not deduplicated** — they appear duplicated in `unknown` (and would in `sources_queried` too, for a valid duplicated id). (Section 12)
7. **Opt-in sources are only excluded from the *default* fan-out** (`sources=None`); naming one explicitly always dispatches it, with no separate confirmation flag. Correct per the code, but nowhere stated as the *complete* opt-in contract. (Section 12)
8. **`_resolve_fn` has no callable/type guard** — a `fn_name` colliding with any non-function module attribute (`log`, `SOURCES`, a constant) would resolve "successfully" and only fail later, inside the per-source `try/except`. Currently latent (no real collision exists in the 65-entry registry). (Extra)

Everything else probed — the registry/`list_sources()`/`_load_registry()` triad, `route_sources()`, `question_to_intent()`, `_is_prose()`, `PROSE_UNSAFE_SOURCES`, `registered_hosts()`, `NAMESPACE_URI_HOSTS`, `_SOURCE_CONFIDENCE`, and the four-bucket `search()` accounting invariant itself — matched the module's own docstrings exactly, with no discrepancies found.
