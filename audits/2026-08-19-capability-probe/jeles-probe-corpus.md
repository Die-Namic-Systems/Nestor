# Capability probe: `jeles.corpus` (v0.9.0)

**Scope:** `jeles.corpus` — the SQLite-backed verified-nugget store.
**Method:** Direct calls against the module with `WILLOW_STORE_ROOT` pointed at a
scratch temp directory (never the real `~/.willow/store`). Source read in full
(`.venv/lib/python3.11/site-packages/jeles/corpus.py`, 827 lines) before probing,
so "documented" below means "stated in a docstring or comment in that file,"
not "in external docs" (none were found — this package has never been published,
per its own comment on `_gap_key`).
**Environment:** `/home/user/Nestor/.venv/bin/python`, jeles 0.9.0.

Legend: **Documented** = behavior is explicitly described in source comments/docstrings.
**Implied** = follows from reading the code but isn't called out. **Undocumented** =
neither stated nor an obvious consequence of a stated design goal — a genuine surprise.

---

## 1. Kind hierarchy enforcement (`human` > `machine` > `asserted`)

| # | Test | Expected | Actual | Doc status |
|---|------|----------|--------|------------|
| 1.1 | Create nugget `k1` as `human` | created | `{"id":"k1","action":"created","verification_kind":"human"}` | Documented |
| 1.2 | Overwrite `k1` (human) with `asserted` | refused | `{"error":"kind_downgrade_refused","existing_kind":"human","attempted_kind":"asserted",...}` | Documented |
| 1.3 | Overwrite `k1` (human) with `machine` | refused | Same refusal shape, `attempted_kind:"machine"` | Documented |
| 1.4 | Overwrite `k1` (human) with `human` again (lateral) | allowed | `{"action":"updated"}` — the guard is `rank[prior] > rank[kind]`, a **strict** `>`, so equal rank passes | Implied (not spelled out that lateral same-kind overwrites are allowed) |
| 1.5 | Upgrade path `asserted → machine → human` on a fresh id | both succeed | Both `action:"updated"`, final kind `human` | Implied |
| 1.6 | Downgrade attempt *after* an upgrade (`human → asserted` on the now-human id) | refused | Refused, same as 1.2 — the ladder is permanent once climbed | Documented |
| 1.7 | `verification_kind="superverified"` (invalid) | error | `{"error":"verification_kind must be one of asserted, human, machine (got 'superverified')"}` | Documented |
| 1.8 | `verification_kind=""` | error | Same shape, `(got '')` | Implied |
| 1.9 | `verification_kind=None` explicit | error | Same shape, `(got None)` — `str(None or "")` collapses to `''`, caught by the same check, no crash | **Undocumented edge case**: passing `None` explicitly does *not* fall back to the parameter's own `"human"` default the way omitting it would; it's treated as an invalid string instead |
| 1.10 | `verification_kind="HUMAN"` (uppercase) | accepted, lowercased | `{"action":"created","verification_kind":"human"}` | Implied (`kind.lower()`) |
| 1.11 | `verification_kind=123` (int) | error | `{"error":"...(got 123)"}` — `str(123 or "").lower()` → `"123"`, not in rank table | Implied |
| 1.12 | `_kind_of()` on a nugget dict with a garbled stored `verification_kind` (e.g. `"totally-bogus"`, simulating on-disk corruption) | defensive high rung | Returns `"human"` — the highest rung, so a corrupted record can never be silently downgraded | **Documented** explicitly in the `_kind_of` docstring |
| 1.13 | Write a lower-kind (`asserted`) nugget onto an id that was soft-deleted (`deleted=1`) out-of-band, where the deleted row was `human` | refused | Still refused with `kind_downgrade_refused` — **the guard reads the tombstoned row and enforces the hierarchy even though `_get()`/normal reads would report the id as absent.** Tombstoning does not create a loophole to plant a lower-kind write under a higher-kind id. | **Undocumented as a downgrade-defense property** (only the "action" labeling for tombstoned ids is documented, at line ~488–492) |
| 1.14 | Overwrite same-kind (`human`) nugget with **completely unrelated question text** at the same `nugget_id` | allowed, no content check | `{"action":"updated"}`; the stored `question`/`answer` are fully replaced. The guard checks **only** `verification_kind` rank — it has no notion that `nugget_id="collide1"` should stay about the same topic. | **Undocumented**: a `human`-level writer can silently repurpose any nugget id's content as long as they keep supplying an equal-or-higher kind; there is no "same question" invariant |

**Key finding:** the downgrade guard is entirely rank-based and running *inside* the write transaction (comment at line 168–174 explains why: a check-then-write outside the transaction would race). It has no awareness of question/answer identity, so `nugget_id=` is effectively a free-form "slot" a caller controls, protected only along the kind axis.

---

## 2. Confidence scoring / `MIN_ASK_SCORE` threshold

`_confidence()` is a harmonic mean (F1) of precision/recall between the asked tokens and the nugget's `_ask_tokens()`, with an absolute veto: any asked content token *absent* from the nugget's question forces confidence to `0.0` regardless of overlap elsewhere (Rule 1 in the docstring).

| # | Test | Expected | Actual | Doc status |
|---|------|----------|--------|------------|
| 2.1 | Exact byte-identical question | found, exact | `{"found":true,"exact":true}` | Documented |
| 2.2 | `"What's the primary color in Grove?"` vs stored `"What is the primary color in Grove?"` | found (apostrophe binds `what's` as one token) | `{"found":true,"exact":true}` — collapses to the same token set | Documented |
| 2.3 | Query adds one content word the nugget's question lacks (`...in the new Grove theme?`) | refused (Rule 1) | `{"found":false}` | Documented |
| 2.4 | Single generic word (`"vaccine"`) against a long, specific nugget question | refused (Rule 2, symmetric F1) | `{"found":false}` | Documented |
| 2.5 | Constructed **exact boundary**: nugget question tokenizes to 6 known tokens, query is 2 of them (full recall, precision=2/6) → F1 = 2·(1/3)·1/(1/3+1) = **0.5 exactly** | `>= MIN_ASK_SCORE` is inclusive, so this should pass | `_confidence()` returns `0.5`; `ask_corpus` returns `found:true` | **Verified experimentally**: the `>=` in source (`if c >= MIN_ASK_SCORE`) is confirmed inclusive at the literal boundary, not just by reading the comparison operator |
| 2.6 | Same construction with 7 known tokens instead of 6 (precision=2/7) | just under threshold | F1 = `0.4444...` — excluded from the `confident` list | Verified experimentally |

**Key finding:** the `>=` threshold is a hard, exactly-inclusive boundary — 0.500000 passes, 0.444 doesn't. There's no rounding/epsilon tolerance visible, which is fine for floats built from small integer ratios but means a threshold-adjacent nugget's fate hinges on exact rational arithmetic.

---

## 3. Tokenization (`_tokens`, `_ask_tokens`)

| # | Input | `_tokens` result | Notes / doc status |
|---|-------|-------------------|---------------------|
| 3.1 | `什么是主色?` (pure CJK) | `['什么','么是','是主','主色']` | CJK bigrams, as documented |
| 3.2 | `Какой основной цвет?` (Cyrillic) | `['какой','основной','цвет']` — whole words preserved | Documented (Unicode `\w` fix) |
| 3.3 | `naïve résumé café` | `['naïve','résumé','café']` — **all three** survive whole including `café` (4 chars ≥ 3-char minimum) | Documented |
| 3.4 | `😀🎉🔥 emoji only` | `['emoji','only']` — emoji contribute **zero** tokens (not `\w`), silently dropped, no error | Undocumented (emoji-drop behavior) |
| 3.5 | `🎉` (pure emoji, no words) | `[]` — empty on both `_tokens` and `_ask_tokens`; falls through `_WORD_RE`, `_CJK_RE`, and the rule-3 `_SHORT_RE` fallback (also `\w`-only) | Undocumented |
| 3.6 | 5000-char single token (`"AAAA...A"`) | Kept whole as one 5000-char token | **No length cap anywhere in the tokenizer** — undocumented, worth noting for anyone hashing/indexing tokens downstream |
| 3.7 | `"x"` (single ASCII char) | `['x']` — `_WORD_RE` needs 3+ chars so the main pass yields nothing, then Rule 3's short-word fallback kicks in | Documented (Rule 3 exists exactly for this) |
| 3.8 | `"the a an is of"` (all "stopword-shaped") | `['a']` — **`the`, `an`, `is`, `of` are dropped as stopwords, but `"a"` survives** | **Undocumented surprise**: `_STOP` deliberately contains no single-letter entries (comment: "Deliberately no single letters: 'drug A' vs 'drug B'"), so the indefinite article "a" is indistinguishable from a meaningful one-letter code and is *not* treated as a stopword — it tokenizes as if it mattered |
| 3.9 | `"Is it up?"` | `['up']` | **Documented** — this is the literal motivating example in the `_ask_tokens` docstring (the API-down/API-up bug) |
| 3.10 | `"AI vs ML?"` | `['ai','vs','ml']` | Documented — literal motivating example in the module comment |
| 3.11 | `café 日本語 test` (mixed Latin+CJK+ASCII) | `['café','日本','本語','test']` | Documented |
| 3.12 | `""` empty string | `[]` | Implied |
| 3.13 | Whitespace-only (`"   \n\t  "`) | `[]` | Implied |
| 3.14 | `"it's what's don't"` | `['don']` — `"it's"` is explicitly in `_STOP`, `"what's"` also collapses to a stopword-equivalent form and is dropped, `"don't"` → `_WORD_RE` matches only `don` (apostrophe binds within `_WORD_RE`'s `[\w-]` class differently than `_SHORT_RE`'s) | **Undocumented inconsistency**: `_WORD_RE` (`[^\W_][\w-]{2,}`) does *not* actually include the apostrophe character in its char class — `\w` doesn't match `'` — so `"don't"` tokenizes to `don` (truncated at the apostrophe) even though the module comment at line 298 claims "the apostrophe binds: 'what's' is one token." That claim holds for `_SHORT_RE` (which explicitly lists `'` and `’` in its class) but **not** for the main `_WORD_RE` used by `_tokens`/`_score`/`log_gap`. `"what's"` only survives as one token here because it happens to be a listed exact `_STOP` entry ("it's" is listed, but "what's" is not — yet it still doesn't appear as a token, worth double-checking against production data if apostrophe words matter for search ranking) |
| 3.15 | `snake_case under-score CamelCase` | `['snake_case','under-score','camelcase']` — underscores and hyphens are inside the word char class, and case is folded | Implied by regex, not called out explicitly |
| 3.16 | `한국어 텍스트 테스트` (Korean Hangul) | Bigrammed like CJK: `['한국','국어','텍…]` | Documented — Hangul range explicit in `_CJK_RE` |
| 3.17 | `一` (single CJK character) | `['一']` — `range(max(1, len(run)-1))` yields `range(1)` for a 1-char run, so a lone CJK character produces itself as a "bigram" rather than nothing | Documented in code comment |

**Key finding (3.14):** the apostrophe-binding comment above `_SHORT_RE` (line 298–302) describes behavior that belongs to `_SHORT_RE`/`_ask_tokens`'s short-word fallback, not to the primary `_WORD_RE` tokenizer used for scoring and gap-keying. A rephrasing that hinges on a contraction surviving as one token in `_tokens` (not just `_ask_tokens`) will not behave as the comment implies.

---

## 4. Gap dedup (`_gap_key`, `log_gap`)

`_gap_key` = token set + adjacent-pair set + short-code set, joined into one string, then UUID5-hashed.

| # | Test | Expected | Actual | Doc status |
|---|------|----------|--------|------------|
| 4.1 | `"...migrate from postgres to mysql?"` vs `"...migrate from mysql to postgres?"` | **different** ids (opposite adjacency) | Confirmed different ids (`9d83ad9a...` vs `a62512d9...`) | **Documented** — literal motivating bug-fix example |
| 4.2 | `"Does drug A interact with X?"` vs `"With X, does drug A interact?"` (phrase moved, adjacency preserved) | **same** id | Confirmed identical id (`0f6ee765bdbf` both) | **Documented** — literal motivating example |
| 4.3 | `"migrate from v1 to v2"` vs `"migrate from v2 to v1"` (direction carried only by short codes `v1`/`v2`) | **same** id (known limitation) | Confirmed identical id | **Documented** as an explicit known limitation |
| 4.4 | `"the accent color in Nord"` vs `"the Nord accent color"` (legitimate rephrasing, adjacency broken) | **different** ids (accepted tradeoff) | Confirmed different ids | **Documented** as an accepted error mode |
| 4.5 | `"drug A interaction"` vs `"drug B interaction"` | **different** ids (short-code segment differentiates single-letter codes) | Confirmed different ids | Documented |
| 4.6 | `_MAX_GAP_VARIANTS=8` boundary: log 11 distinct literal phrasings that all share one gap key (varied only by trailing punctuation) | `asked_count` increments to 11; `variants` caps at 8, sliding-window drops the oldest | `asked_count: 11`. Final `variants` list has exactly **8** entries: `[!!  , ...  , (bare), ??  , " ."  , " ,"  , " ;"  , " ~"]` — note the 9th and 10th pushed phrasings (` :`  and ` -`) are **gone**, dropped by the `variants[:_MAX_GAP_VARIANTS-1] + [new]` sliding window as documented | **Documented** — matches the docstring exactly |
| 4.7 | Exact duplicate literal question logged 3×, no rephrasing | `asked_count` bumps, no `variants` key at all | `asked_count: 3`, and the stored record has **no `variants` field whatsoever** (not even `[]`) — because `question != first` is `False` every time, the `if variants:` guard never adds the key | **Undocumented consequence**: a gap that has only ever been asked one way has no `variants` key present, vs. one asked ≥2 ways which does — callers iterating `list_gaps()` need `.get("variants", [])`, not `["variants"]` |

---

## 5. Concurrent writes

The design (comment at lines 96–129 and 788–792) explicitly claims `BEGIN IMMEDIATE` + `isolation_level=None` fixes a documented prior bug ("measured at 14 after 50 concurrent calls" pre-fix, for `log_gap`'s read-then-write race).

| # | Test | Expected | Actual | Doc status |
|---|------|----------|--------|------------|
| 5.1 | 10 threads × 20 calls each = 200 concurrent `log_gap()` calls on the *same* question, in-process | `asked_count == 200` exactly if serialization holds | **`asked_count: 200`** — exact match, no lost updates | Documented as the exact bug this design fixes; **verified experimentally that the fix holds** in-process |
| 5.2 | 10 threads racing `put_nugget` on the same id, same kind (`human`), each with a distinct answer | no crash, no exception, last writer wins (serialized) | All 10 calls succeeded (`action` = 1×`created` + 9×`updated`, no errors, no exceptions); final stored answer was from `writer9` — consistent with full serialization, no interleaved/corrupted writes | Undocumented directly, but consistent with the design intent |
| 5.3 | Mixed-kind race: 3×`human`, 3×`asserted`, 3×`machine` all targeting the *same new id* simultaneously | whichever `human`/`machine` write lands first wins the slot permanently; later lower-kind writes refused; no corruption | Observed: first `human` write created the id, subsequent `human` writes updated it, and **every** `asserted`/`machine` write submitted after any `human` write landed was refused with `kind_downgrade_refused` — the guard held correctly across the race with real thread interleaving, not just sequential calls | Undocumented as a multi-thread scenario, but the invariant (guard runs inside the transaction) held under actual concurrent stress |

**Key finding:** the concurrency claims in the source comments check out under real threading — the `BEGIN IMMEDIATE` serialization is not just aspirational, it produces the exact expected count (200/200) and the kind-downgrade guard is race-safe even when multiple kinds are racing for the same new id.

---

## 6. `ask_corpus` edge cases

| # | Test | Expected | Actual | Doc status |
|---|------|----------|--------|------------|
| 6.1 | `ask_corpus()` on a totally empty, freshly-created collection | `found:false`, `candidates:[]`, and a gap **is** logged | Confirmed: `{"found":false,"nugget":null,"candidates":[]}`, and `list_gaps()` shows one row with `asked_count:1` | Implied |
| 6.2 | `ask_corpus("")` (empty string query) | `found:false` | `{"found":false,"nugget":null,"candidates":[]}` — but see 6.2b | Implied |
| 6.2b | Does the gap for an empty query actually get logged? | Either logs an empty-question gap, or fails | **Neither, silently**: `ask_corpus` unconditionally calls `log_gap(question)` on a miss, but `log_gap("")` returns `{"error":"question required"}` after its own `.strip()` check — and `ask_corpus` **discards that return value**. Net effect: an empty/whitespace-only query miss produces **no gap row at all**, with no signal to the caller that logging was skipped. Verified: gap count was identical (0→0) before/after two empty-query `ask_corpus` calls. | **Undocumented interaction** between two functions that individually behave sensibly |
| 6.3 | `ask_corpus("   ")` (whitespace only) | same as empty | Same silent-no-gap behavior as 6.2 | Undocumented |
| 6.4 | `ask_corpus("what is the")` (stopwords only) | tokens empty, `found:false`, gap **does** log this time (question is non-empty after strip) | `{"found":false,"nugget":null,"candidates":[]}` | Undocumented explicitly, but consistent with code |
| 6.5 | Very long query (~9200 chars, repeated phrase) | no crash, no length cap | Completed normally, `found:false`, 2 candidates returned | **Undocumented**: no length guard anywhere in `ask_corpus`/tokenizer/scoring path |
| 6.6 | Two nuggets with byte-identical question text, tied score/confidence | some deterministic tie-break | The **more recently created/updated** nugget won (`tie2`, inserted second, `answer B`) — an emergent property of `_all()`'s `ORDER BY updated_at DESC` plus Python's stable sort, not a documented tie-break rule | **Undocumented** tie-break contract — callers should not rely on "first nugget written" winning a tie; it's actually "most recently written" |
| 6.7 | `include_asserted` flag, where the *only* matching nugget is `asserted` | default excludes it (`found:false`, gap logged even though a matching nugget technically exists); `include_asserted=True` includes it | Confirmed both cases exactly as documented | Documented |
| 6.8 | Pure punctuation query (`"???!!!..."`) | tokens empty, `_gap_key` falls back to raw lowercased text since nothing tokenized | `{"found":false}`; gap key uses the documented fallback branch (`"Nothing tokenized at all (punctuation, emoji): fall back to the text"`) | Documented |
| 6.9 | `search_nuggets()` on a total miss | **never** logs a gap (per docstring: "Pure lookup — never logs a gap on a miss") | Confirmed: gap count unchanged (2→2) after a miss-triggering `search_nuggets()` call | **Documented, and verified** |
| 6.10 | `list_nuggets(limit=0)` / `list_nuggets(limit=-5)` | `0` results either way (`max(0, limit)` clamps negatives to 0, and 0 is 0) | Both return `0` items | Implied by `[: max(0, limit)]` |
| 6.11 | `list_gaps(limit=0)` / `list_gaps(limit=-1)` | same clamp | Both return `0` items | Implied |

---

## 7. `_clean()` control-character stripping

Regex: `[\x00-\x08\x0b-\x1f\x7f]` — i.e., **everything in C0 except tab (`\x09`) and newline (`\x0a`)**, plus DEL (`\x7f`).

| # | Char | Stripped? | Notes |
|---|------|-----------|-------|
| 7.1 | NUL `\x00` | **Yes** | |
| 7.2 | BEL `\x07` | **Yes** | |
| 7.3 | Form feed `\x0c` | **Yes** | |
| 7.4 | Vertical tab `\x0b` | **Yes** | |
| 7.5 | Tab `\x09` | **No** — preserved | Documented ("keep tab/newline") |
| 7.6 | Newline `\x0a` | **No** — preserved | Documented |
| 7.7 | Carriage return `\x0d` | **Yes, stripped** | **Worth flagging**: CR is in the stripped range (`\x0b-\x1f` covers `\x0d`) despite the comment only mentioning "tab/newline" as the kept exceptions — a CRLF-authored answer loses its `\r` and collapses to bare `\n`. This is consistent with the regex but not explicitly called out in the comment, which only frames the *kept* chars, not that CR specifically is *not* one of them |
| 7.8 | DEL `\x7f` | **Yes** | Explicit in regex, matches comment ("keep tab/newline" implies all else including DEL goes) |
| 7.9 | ESC `\x1b` | **Yes** | |
| 7.10 | Mixed C0 run `a\x00b\x01c\x02d\x1fe` | All control chars removed, letters concatenated: `abcde` | Confirmed |
| 7.11 | Nested dict/list/tuple with control chars at multiple depths, plus `None`/`int`/`float`/`bool` scalars mixed in | Recursively cleaned; non-str scalars pass through unchanged; **tuples become lists** in the output | Confirmed exactly, including the tuple→list conversion, which is explicitly commented ("tuples json-serialize as lists anyway") |
| 7.12 | End-to-end `put_nugget` with control chars embedded in question, answer, sources, and verified_by simultaneously | All fields cleaned at the single `_put()` chokepoint before storage | Confirmed — `"Control\x00char\x07question?"` → stored as `"Controlcharquestion?"`, etc., across every field | Documented (single chokepoint comment) |

---

## 8. Collection name validation (`^[A-Za-z0-9_-]{1,128}$`)

| # | Input | Result |
|---|-------|--------|
| 8.1 | `"my_collection-1"` | OK |
| 8.2 | `""` (empty) | REJECTED |
| 8.3 | `"../../etc/passwd"` | REJECTED |
| 8.4 | `"foo/bar"` | REJECTED |
| 8.5 | `"/etc/passwd"` | REJECTED |
| 8.6 | `"café_collection"` (Unicode letters) | REJECTED — regex is ASCII-only (`A-Za-z0-9_-`), so even benign non-ASCII names fail |
| 8.7 | `"coll\x00ection"` (embedded NUL) | REJECTED |
| 8.8 | 129 chars | REJECTED (over the 128 cap) |
| 8.9 | 128 chars exactly | OK (inclusive upper bound confirmed) |
| 8.10 | 1 char (`"a"`) | OK (inclusive lower bound confirmed) |
| 8.11 | `"my collection"` (space) | REJECTED |
| 8.12 | `"."` / `".."` | REJECTED (both, since `.` isn't in the allowed class at all) |
| 8.13 | `"-collection"` (leading dash) | **OK** — nothing forbids a name that starts with `-`; on a shell this could be mistaken for a flag by naive tooling downstream, though `_conn()` only ever uses it as a `Path` component, not a shell argument, so no injection here |
| 8.14 | `"..\\..\\windows"` (Windows-style traversal) | REJECTED (backslash not in allowed class) |
| 8.15 | `"%2e%2e%2fetc"` (URL-encoded traversal, unescaped) | REJECTED (`%` not in allowed class) — note this only defends because the string is validated *before* any decoding; nothing here does percent-decoding, so this is really just "not a valid identifier," not a URL-decode-then-check defense |
| 8.16 | `"coll;DROP TABLE"` | REJECTED |
| 8.17 | `"coll\nection"` (embedded newline) | REJECTED |
| 8.18 | End-to-end: `JELES_CORPUS_COLLECTION` env var set to `"../../../tmp/evil"`, then call `put_nugget(...)` | Regex correctly rejects it — but **how**: does `put_nugget` return a clean `{"error": ...}`, or does the `ValueError` propagate uncaught? | **Uncaught `ValueError` propagates all the way out of `put_nugget()`** — confirmed: `ValueError: invalid collection name (must match ^[A-Za-z0-9_-]{1,128}$): '../../../tmp/evil'` raised, not returned as `{"error": ...}`. `put_nugget`'s `try/except` only catches its own `_WriteRefused`, not `ValueError` from `_conn()`/`_validate_collection()`. | **Undocumented gap**: every other validation failure in `put_nugget` (missing fields, bad kind, bad evidence type) returns a clean error dict; a bad collection name is the one path that crashes the caller with an unhandled exception instead. Since `NUGGETS_COLLECTION`/`GAPS_COLLECTION` are read from env vars at **module import time** (line 37–38), this is only reachable by whoever controls the process environment before import — but a launcher that forwards an unsanitized env var here would get a hard crash, not a rejected write |

---

## 9. `evidence` dict on `put_nugget`

| # | Test | Expected | Actual | Doc status |
|---|------|----------|--------|------------|
| 9.1 | `evidence={"sig": "abc123", "signer": "nestor-chain"}` (flat dict) | stored verbatim | Stored exactly, uninterpreted | Documented |
| 9.2 | Deeply nested dict with lists/dicts inside, mixed types (`int`, `str`, `float`, `None`, nested `bool`) | no depth/shape restriction, anything JSON-serializable survives | Stored exactly as given, full fidelity | Documented ("keys of its own choosing") |
| 9.3 | `evidence=None` (default/omitted) | `evidence` key absent from stored record | Confirmed: `"evidence"` key is **entirely absent**, not even `{}` | Documented |
| 9.4 | `evidence={}` (explicit empty dict) | — | **Identical to 9.3**: also entirely absent from the stored record | **Undocumented edge case**: `if evidence:` is a truthiness check, so `{}` and `None` are indistinguishable in storage — a caller who explicitly wants to record "no evidence, but I checked" by passing `{}` cannot distinguish that from never having passed the parameter at all. `to_search_hit` then renders both as `"evidence": {}` |
| 9.5 | `evidence=["not","a","dict"]` (list) | error | `{"error": "evidence must be a dict (got list)"}` | Documented (explicit `isinstance` check) |
| 9.6 | `evidence="a string"` | error | `{"error": "evidence must be a dict (got str)"}` | Documented |
| 9.7 | `evidence=42` (int) | error | `{"error": "evidence must be a dict (got int)"}` | Documented |
| 9.8 | `evidence={"obj": <non-JSON-serializable custom object>}` | Top-level `isinstance(evidence, dict)` check passes (it *is* a dict), but the object inside isn't validated | **Uncaught `TypeError: Object of type Weird is not JSON serializable`**, raised from inside `_put()`'s `json.dumps(record)` call, well past `put_nugget`'s own validation and try/except | **Undocumented gap**: `put_nugget` validates that `evidence` is a dict but never validates that its *values* are JSON-serializable; a caller passing a dict containing e.g. a `datetime`, a custom class instance, bytes, etc. gets a raw, unhandled `TypeError` from deep inside storage internals instead of a clean `{"error": ...}` — the same class of gap as 8.18 (collection name), where one validation layer is thorough and an adjacent one is silently absent |

---

## 10. `MAX_GAP_VARIANTS` — see §4.6/4.7 above (folded in for flow)

Confirmed: exactly 8 variants retained on the 9th+ distinct rephrasing, sliding window drops oldest-first, `asked_count` keeps incrementing unbounded regardless of the variants cap. No `variants` key at all when every ask used the identical literal string.

---

## Summary of the more actionable findings

1. **Kind guard has no content-identity check** (§1.14) — same-kind overwrite on an existing `nugget_id` silently replaces the question/answer with unrelated content; only the *kind* is protected, not "this is still the same fact."
2. **`ask_corpus` silently drops gap-logging for empty/whitespace-only queries** (§6.2b) — `log_gap`'s own `{"error": "question required"}` return is discarded by its only caller, so a flood of empty-string asks leaves zero trace in `list_gaps()`.
3. **Two distinct unhandled-exception gaps**, both in otherwise well-validated write paths:
   - Bad `JELES_CORPUS_COLLECTION`/`GAPS_COLLECTION` env values raise `ValueError` uncaught through `put_nugget`/`log_gap` (§8.18).
   - Non-JSON-serializable values nested inside an otherwise-valid `evidence` dict raise `TypeError` uncaught through `put_nugget` (§9.8).
   Both are "this validates the *shape* but not the *contents*" gaps of the same species.
4. **`evidence={}` and `evidence=None` are indistinguishable** in storage (§9.4) — loses the "I checked, there's nothing to attach" signal.
5. **Apostrophe-binding comment is only true for the short-word fallback path**, not the primary `_WORD_RE` tokenizer (§3.14) — `"don't"` truncates to `don` in `_tokens`/`_score`/`log_gap`, contrary to what the nearby comment implies for the general case.
6. **The word `"a"` alone survives tokenization** as a real content token (§3.8) — an artifact of `_STOP` deliberately excluding all single-letter words (to protect drug-code-style disambiguation), which also means the indefinite article "a" gets treated as meaning-bearing.
7. **Concurrency claims check out under real threading stress**: 200/200 exact count on `log_gap`, and the kind-downgrade guard held correctly across genuinely racing `put_nugget` calls of mixed kinds (§5.1–5.3) — this is the one area where testing confirmed the documented fix works exactly as claimed, not just plausibly.

All temp stores used for this probe lived under `/tmp/jeles-probe-*` / `/tmp/jeles-probe2-*` and were never pointed at the real `~/.willow/store`.
