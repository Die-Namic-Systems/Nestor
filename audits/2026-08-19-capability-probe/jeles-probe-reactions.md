# jeles v0.9.0 — capability probe: reactions & corpus_server

**Scope:** `jeles.reactions.conflict_scan`, `jeles.reactions.search_adapter`, `jeles.corpus_server`
(plus the shared helpers they lean on: `jeles._independence`, `jeles.corpus._tokens`, `jeles._egress`).

**Method:** static reading + ~55 offline test scenarios run against the installed package
(`/home/user/Nestor/.venv`, jeles 0.9.0). No real network calls. No real MCP transport — `mcp` is
not installed in this venv, so `corpus_server.py` was exercised two ways: (1) confirming the
documented `ImportError` when `mcp` is absent, and (2) importing it against a minimal local stub of
`mcp.server.mcpserver.MCPServer` (a `.tool()` decorator that just records the function; `.run()`
raises if ever called) so the ten tool functions could be called directly as plain Python — no
protocol, no stdio, no server loop. All corpus writes went to a temporary `WILLOW_STORE_ROOT`,
cleaned up after each script.

Every behavior below was **observed**, not inferred from reading. "Documented" means the module's
own docstrings/comments say this; "undocumented" means the behavior is real but not stated anywhere
in the source.

---

## 1. `conflict_scan.frame_queries()`

| # | Scenario | Expected | Actual | Doc status |
|---|---|---|---|---|
| 1 | Normal claim | 4 queries: mirror, supersession, rivalry, refutation | Exactly as documented, in that order | Documented |
| 2 | Empty string / whitespace-only / `None` claim | `[]` | `[]` in all three cases (`None` handled via `(claim or "").strip()`) | Documented |
| 3 | Leading/trailing whitespace | Claim trimmed before use | Trimmed correctly | Documented |
| 4 | Very long claim (5000 chars) | No truncation, no crash | All 4 queries built at full length — **no length cap anywhere in `frame_queries`** | Undocumented (no cap mentioned or applied) |
| 5 | Claim with embedded newlines | Passed through as-is into the query string | Newline preserved literally inside the query string | Undocumented but harmless |
| 6 | Unicode claim (`café résumé 日本語のクレーム`) | No crash, queries built normally | Works fine | Undocumented but expected |
| 7 | `extra=[...]` with genuinely new queries | Appended after the 4 base queries | Appended in order | Documented |
| 8 | `extra=` containing a string identical to a generated query | Not duplicated | Correctly deduped (`if q and q not in queries`) | Documented (dedup logic present, behavior confirmed) |
| 9 | `extra=` containing `""`, `"   "`, `None` mixed with a real value | Blank/`None` entries dropped, real one kept | Confirmed — `q = (q or "").strip()` handles `None` same as empty string | Undocumented (works, but `None` handling isn't called out) |
| 10 | `extra=[]` vs `extra=None` | Identical result | Confirmed identical | Documented (`extra or []`) |
| 11 | `extra=["dup", "dup"]` (duplicate *within* extra itself) | Only one "dup" survives, since the in-list containment check runs cumulatively | **Bug-shaped but not a bug**: only one `"dup"` appears in the output — the check is against `queries` which grows as items are appended, so a self-duplicate inside `extra` is caught too | Undocumented, works correctly |
| 12 | Claim that collapses to empty after `.strip()` but was non-empty on input (e.g. `"\t\n  \t"`) | `[]` | `[]` | Documented |

---

## 2. `conflict_scan._witnesses()` and `_NON_WITNESS`

| # | Scenario | Expected | Actual | Doc status |
|---|---|---|---|---|
| 13 | Contents of `_NON_WITNESS` | Search engines + shorteners | 21 domains: `duckduckgo.com, google.com, bing.com, yahoo.com, baidu.com, yandex.com, search.brave.com, ecosia.org, startpage.com, bit.ly, t.co, tinyurl.com, goo.gl, ow.ly, buff.ly, is.gd, rebrand.ly, cutt.ly, shorturl.at, lnkd.in, dlvr.it` | Documented (list matches the module's own comment) |
| 14 | `google.com` hit with real content overlap | Filtered out — non-witness wins over content match | Filtered out | Documented |
| 15 | `bit.ly` shortener hit | Filtered out | Filtered out | Documented |
| 16 | Real domain, snippet/title genuinely overlaps claim words | Counted as witness | Counted | Documented |
| 17 | Real domain, **zero** content-word overlap with claim | Filtered out (this is the whole point of the filter) | Filtered out | Documented |
| 18 | Real domain, content overlap only via a **different inflection** of a claim word (claim "widget…", hit says "widgets") | Ambiguous in docs — "shares at least one content word" | **Filtered out.** `_tokens()` (from `jeles.corpus`) does no stemming/lemmatization: `"widget"` and `"widgets"` are different tokens (`_tokens('widget batches writes') == ['widget','batches','writes']`, `_tokens('widgets are cool') == ['widgets','cool']`), so plural vs singular fails the "one content word" bar entirely | **Undocumented limitation.** The docstring says the loose one-word bar exists specifically so genuine differently-worded witnesses aren't lost — but it is exact-token matching with no stemming, so the single most common form of "differently worded" (plurals) is exactly what falls through the gap it claims to guard against. |
| 19 | Hit with unparseable/garbage URL (empty `domain`) | Filtered out | Filtered out | Documented |
| 20 | Dotless host (e.g. `http://localhost/page`) via `registrable_domain` | `""` (no source) | `""` | Documented (`_independence.py` comment: "a dotless/garbage host is no source") |

---

## 3. `conflict_scan.react()` — the 2-independent-source bar

| # | Scenario | Expected | Actual | Doc status |
|---|---|---|---|---|
| 21 | 2 hits, 2 distinct registrable domains, both overlap claim | Corroborated → `put_nugget` + `frank_append`, `verification_kind: "machine"` | Confirmed, answer text cites both domains, `sources` = exactly the witnessing URLs | Documented |
| 22 | 2 hits, **same** registrable domain (`sitea.com/a`, `sitea.com/b`) | Contested (1 source) → `log_gap` + `frank_append` | Confirmed: "contested — 1 independent source(s), below the 2-source bar" | Documented |
| 23 | 2 hits, both from `_NON_WITNESS` domains (`google.com`, `duckduckgo.com`) mentioning the claim | Should NOT corroborate even though 2 "sources" answered | Confirmed: 0 domains counted, `log_gap` emitted — this is the exact regression the module's docstring says it was built to close ("a claim invented on the spot was corroborated by duckduckgo.com + wikipedia.org") | Documented (regression test matches the documented history) |
| 24 | Missing `claim` key in `event` | `[]`, no crash | `[]` | Documented |
| 25 | Empty-string `claim` in `event` | `[]` | `[]` | Documented |
| 26 | Searcher raises for **one** of the 4 queries, succeeds for the rest | That query yields 0 results; scan proceeds on the rest | Confirmed — one query's exception is swallowed inside `_gather`, other queries still contribute hits, corroboration still reachable | Documented |
| 27 | Searcher raises for **every** query | No crash, degrades to contested gap (0 sources) | Confirmed | Documented |
| 28 | `min_sources=1` override | 1 witness now suffices to corroborate | Confirmed — `put_nugget` fired off a single witnessing domain | Documented (parameter exists, default is `DEFAULT_MIN_SOURCES=2`) |
| 29 | `min_sources=0` with **zero hits at all** | — | **`corroborated = True`** (`len(domains)=0 >= min_sources=0`) fires `put_nugget` with `sources: []`, `verified_by: "jeles:conflict-scan/2-independent-sources"`, and an answer literally reading *"Corroborated by 0 independent sources ()."* | **Undocumented edge case / soft bug.** Nothing in `react()` guards `min_sources` against being ≤ 0. A caller who passes `min_sources=0` (or a negative number — untested but `len(domains) >= negative` is always true) gets a machine-verified nugget asserting corroborated prior art from a search that found literally nothing. The module's own stated purpose ("the corpus asserting something false is the thing this whole package exists not to do") is directly undercut by this input, and it's reachable purely through the public keyword argument. |
| 30 | `max_results=0` | No hits gathered from any query even if the searcher returned real results | Confirmed — `_gather` slices `results[:max(0, 0)]` → 0 per query → gap | Undocumented behavior, but consistent with `max(0, max_results)` guard in source |
| 31 | `max_results=-5` (negative) | Should not crash or slice oddly | Confirmed — `max(0, -5)` clamps to 0, same as case 30 | Undocumented, defensive `max(0, ...)` already present |
| 32 | `event` carrying `tags`, `kind`, `surface`, and `queries` (extra) simultaneously | All four honored: tags merged into nugget tags, `kind`/`surface` echoed into the `frank_append` args, extra queries run through the searcher | Confirmed | Documented |
| 33 | Same URL returned by two different queries | Deduped by URL before domain-counting (`_gather`'s `seen` set) | Confirmed — 3 hits across queries but only 2 unique URLs / domains counted | Documented |

---

## 4. `conflict_scan.apply()` — allowlist, kind pinning, propose/execute split

| # | Scenario | Expected | Actual | Doc status |
|---|---|---|---|---|
| 34 | `_ALLOWED_ARGS` contents | `put_nugget`: `{question, answer, sources, verified_by, tags}`; `log_gap`: `{question}` | Confirmed exactly | Documented |
| 35 | `_REQUIRED_ARGS` contents | `put_nugget`: `{question, answer, sources, verified_by}`; `log_gap`: `{question}` | Confirmed | Documented |
| 36 | Well-formed `react()`-shaped proposal through `apply()` (mock drivers) | Executes cleanly, `verification_kind` forwarded as `"machine"` | Confirmed | Documented |
| 37 | Proposal with `verification_kind: "human"` | **Refused**, driver never called | Confirmed: `{"error": "proposal_args_refused", "rejected": ["verification_kind"], "detail": "a proposal may not set verification_kind='human'; ..."}`; mock driver's call list stayed empty | Documented (this is the exact scenario the file's history comment describes and the allowlist exists to close) |
| 38 | Proposal with `nugget_id` set (attempting to overwrite an existing — potentially human-verified — nugget) | Refused with a distinct, named detail about the overwrite path | Confirmed: `rejected: ["nugget_id"]`, detail explicitly calls out "nugget_id is not reachable from a proposal" | Documented |
| 39 | Proposal with `verified_at` (not in the allowlist, but a real `put_nugget` kwarg) | Refused | Confirmed | Documented (allowlist is a strict allow, not a blocklist of a few named keys) |
| 40 | Proposal with `written_by` (an identity field) | Refused | Confirmed | Documented |
| 41 | `log_gap` proposal carrying an extra `sources` key | Refused (log_gap's allowlist is just `{question}`) | Confirmed | Documented |
| 42 | `put_nugget` proposal missing a required arg (`answer`) | `proposal_args_incomplete` receipt, not a `TypeError` | Confirmed | Documented — this is explicitly the bug the `_REQUIRED_ARGS` pre-check was added to fix (a malformed proposal used to abort the whole batch via `TypeError`) |
| 43 | `args` is not a dict at all (a list) | Refused cleanly, no crash | Confirmed: `{"error": "proposal_args_refused", "detail": "args must be a mapping, got list"}` | Documented |
| 44 | `args` key missing from the proposal dict entirely | Treated as `{}`, falls through to `proposal_args_incomplete` listing all required keys | Confirmed | Undocumented but matches `p.get("args") or {}` in source |
| 45 | Unknown `driver` name (e.g. `"delete_everything"`) | `{"error": "unknown driver"}` receipt, no crash, no exception | Confirmed | Documented |
| 46 | `frank_append` with no `frank=` callable wired | `{"skipped": "no frank driver wired"}`, not silently dropped | Confirmed | Documented |
| 47 | One malformed proposal in a mixed list of 3 | Bad one gets an error receipt; the other two still execute (put_nugget succeeds, frank_append still fires) | Confirmed — 3 receipts returned, in order, only the first is an error | Documented ("a bad proposal must not take the good ones with it") |
| 48 | Empty proposals list | `[]` | `[]` | Documented |
| 49 | **Real drivers** (`apply()` with no injected functions, defaults to `jeles.corpus`) writing to a temp store | Nugget lands with `verification_kind: "machine"`, `status: "corroborated"` | Confirmed via `corpus.get_nugget()` readback | Documented |
| 50 | Malicious `verification_kind: "human"` proposal through the **real** driver path | Blocked by `_vet()` before `corpus.put_nugget` is ever called — proven by the fact `corpus.put_nugget`'s own kind-rank guard is never reached | Confirmed | Documented |
| 51 | Direct reproduction of the pre-allowlist exploit: calling `corpus.put_nugget(..., verification_kind="human")` **directly** (bypassing `apply`/`_vet` entirely) | Succeeds — because `corpus.put_nugget` itself has no opinion about who's calling it; the protection lives only in `apply()`'s vetting layer, one level up | Confirmed: direct call produces a real `human`/`verified` nugget. This demonstrates *why* the allowlist in `apply()` exists — `corpus.put_nugget`'s signature alone is not a security boundary. | Documented (this is literally spelled out in the `_ALLOWED_ARGS` docstring) |
| 52 | Kind escalation via `apply()` + `nugget_id` pointed at that now-human nugget, proposal claims `verification_kind: "machine"` (the *allowed* value) | Still refused, because `nugget_id` itself is off the allowlist regardless of what `verification_kind` says | Confirmed: refused for `nugget_id`, never reaches `corpus.put_nugget`'s own rung-downgrade guard | Documented |
| 53 | Whether `react()` itself performs any writes | Zero — `list_nuggets()` count before and after calling `react()` (against a live temp corpus) must be identical | Confirmed: count unchanged (2 before, 2 after) across a `react()` call that *would* have corroborated if it were `apply()`d | Documented ("propose, don't execute") |

---

## 5. `search_adapter` — backend registry, `describe_backend`, `make_searcher`

| # | Scenario | Expected | Actual | Doc status |
|---|---|---|---|---|
| 54 | `_BACKENDS` registry | `{searxng, brave, tavily, ddg}` | Confirmed | Documented |
| 55 | `_REQUIRES` mapping | `searxng→JELES_SEARXNG_URL`, `brave→BRAVE_API_KEY`, `tavily→TAVILY_API_KEY`, `ddg→None` | Confirmed | Documented |
| 56 | `_SHALLOW` set | Empty (post HTML-SERP rewrite) | Confirmed: `frozenset()` | Documented (module explicitly says the old Instant-Answer `ddg` was retired and `_SHALLOW` is kept only as a mechanism for a *future* placeholder backend) |
| 57 | `_default_backend_name()` with no env at all | `"ddg"` | Confirmed | Documented |
| 58 | `_default_backend_name()` with only `JELES_SEARXNG_URL` set | `"searxng"` (prefers sovereign default over keyless fallback) | Confirmed | Documented |
| 59 | `_default_backend_name()` with `JELES_SEARCH_BACKEND` set | Explicit env always wins over the URL-based inference | Confirmed (`brave` chosen even with no `BRAVE_API_KEY`) | Documented |
| 60 | `JELES_SEARCH_BACKEND` with mixed case and surrounding whitespace (`"  TAVILY  "`) | Normalized to lowercase, trimmed | Confirmed → `"tavily"` | Undocumented but implemented (`.strip().lower()`) |
| 61 | `describe_backend()` for each backend, fully unconfigured | `configured: false`, informative `reason` naming the missing env var | Confirmed for `searxng`/`brave`/`tavily`; `ddg` reports `configured: true, reason: ""` since it needs nothing | Documented |
| 62 | `describe_backend("unknown_name")` | `configured: false`, `reason` lists the valid backend names | Confirmed | Documented |
| 63 | `describe_backend("DDG")` (case) | Same result as lowercase | Confirmed — name lowercased internally | Undocumented but implemented |
| 64 | `describe_backend("brave")` with `BRAVE_API_KEY=""` (set but empty) | Treated as **not** configured (falsy), same as unset | Confirmed — `bool(os.environ.get(needs))` treats empty string same as absent | Undocumented edge case, matches the intent |
| 65 | `make_searcher("nope")` | `ValueError` naming valid choices | Confirmed | Documented |
| 66 | `make_searcher("brave")` with no key, called twice | Both calls return `[]` (fail-soft); the "backend not configured" WARNING logs only on the **first** call (`warned` flag), the per-call failure WARNING logs on both | Confirmed via log output — 1 "backend brave: ..." line, 2 "search via brave failed" lines | Documented ("logs once at first use" vs "failures log at WARNING" on every call) |
| 67 | `search_with_status()` on an unconfigured backend | `{hits: [], ok: false, backend, shallow: false, error: "<reason> (<exception>)"}` | Confirmed, error string concatenates the configuration reason with the raised exception detail | Documented |
| 68 | `search_with_status()` with an unknown backend name | `{hits: [], ok: false, error: "unknown backend..."}`, no exception raised (unlike `make_searcher`, which raises `ValueError`) | Confirmed — **the two functions deliberately disagree** on how to handle an unknown backend: `make_searcher` raises, `search_with_status` reports it as data | Documented (consistent with each function's own stated contract — `make_searcher` is for wiring, `search_with_status` is for reporting) |

---

## 6. `search_adapter.CircuitBreaker` — state machine

All tested with an injected fake monotonic clock, no real time delay.

| # | Scenario | Expected | Actual | Doc status |
|---|---|---|---|---|
| 69 | Fresh breaker | `CLOSED`, `allow()==True` | Confirmed | Documented |
| 70 | Failures below `fail_threshold` | Stays `CLOSED` | Confirmed (2 of 3 threshold) | Documented |
| 71 | Failures reach `fail_threshold` | Trips to `OPEN`, `allow()==False` | Confirmed | Documented |
| 72 | `allow()` before cooldown elapses | Still `False`, state stays `OPEN` | Confirmed (5s of 10s cooldown) | Documented |
| 73 | `allow()` after cooldown elapses | Transitions to `HALF_OPEN`, allows exactly the one probe | Confirmed (at 11s) | Documented |
| 74 | Half-open probe **fails** | Reopens `OPEN` with cooldown **doubled** (10s → 20s) | Confirmed | Documented |
| 75 | Cooldown doubling capped at `max_cooldown` | Repeated half-open failures never exceed the cap | Confirmed across 5 rounds: 10→20→25→25→25 (max_cooldown=25) | Documented |
| 76 | Half-open probe **succeeds** | Full reset: `CLOSED`, `failures=0`, cooldown back to `base_cooldown` | Confirmed | Documented |
| 77 | `record_success()` called while already `CLOSED` | No-op (idempotent reset) | Confirmed | Undocumented but harmless/expected |

---

## 7. `search_adapter._with_retry()`

| # | Scenario | Expected | Actual | Doc status |
|---|---|---|---|---|
| 78 | `TransientSearchError` retried up to `max_attempts`, then re-raised | 3 attempts, jittered backoff `[d, 2d]` with `d = base·2^(n-1)` | Confirmed: 3 attempts, sleeps `[0.0171, 0.0318]` — within `[0.01,0.02]` and `[0.02,0.04]` windows | Documented |
| 79 | Success on 2nd attempt | Returns the result, stops retrying | Confirmed | Documented |
| 80 | `HardBlockError` | Propagates **immediately**, no retry at all (1 attempt) | Confirmed | Documented |
| 81 | Arbitrary non-search exception (`ValueError`) | Propagates immediately, not caught by the retry loop at all | Confirmed (1 attempt) | Documented |
| 82 | Retry budget exhaustion | Stops retrying early once `elapsed + next_delay > budget`, even if `max_attempts` not reached | Confirmed: with `budget=2.0s, base_backoff=1.0` (delays grow ~1,2,4...), only 2 attempts happened before budget was deemed exhausted | Documented |
| 83 | `max_attempts=1` | No retry loop at all — raises on the very first failure | Confirmed | Documented |
| 84 | Env-var-driven defaults (`JELES_SEARCH_MAX_ATTEMPTS=1`) picked up when explicit params are omitted | `_retry_config()` reads env at call time | Confirmed | Documented |

---

## 8. DDG HTML parsing (`_unwrap_ddg`, `_parse_ddg_html`, `_looks_like_results_page`)

| # | Scenario | Expected | Actual | Doc status |
|---|---|---|---|---|
| 85 | `_unwrap_ddg` on a plain https URL | Passed through unchanged | Confirmed | Documented |
| 86 | `_unwrap_ddg` on a `uddg=`-wrapped redirect | Unwrapped and URL-decoded to the real destination | Confirmed: `%3A%2F%2F...` decoded correctly, including a query string on the target URL | Documented |
| 87 | `_unwrap_ddg` on a protocol-relative `//example.com/x` | Coerced to `https://` | Confirmed | Documented |
| 88 | `_unwrap_ddg("")` / `_unwrap_ddg(None)` | `""`, no crash | Confirmed | Undocumented but implemented (`(href or "").strip()`) |
| 89 | `_unwrap_ddg` with `uddg=` present but empty value | Falls through to returning the raw href unchanged (since `qs.get("uddg")` is falsy for an empty list/value) | Confirmed | Undocumented edge case |
| 90 | `_unwrap_ddg` with invalid percent-encoding in the `uddg` value (`%zz`) | Should not crash (there's a defensive `try/except`) | Confirmed — `unquote('%zz')` doesn't actually raise in Python, it just returns the literal string; the `except Exception` clause is defensive but wasn't triggered by this input | Documented as defensive, though this specific input doesn't exercise the except branch |
| 91 | `_parse_ddg_html` on well-formed sample markup with an embedded ad linking to `duckduckgo.com` | Real results parsed with entity-decoded, tag-stripped title/snippet; the `duckduckgo.com`-hosted ad link is **filtered out** (`if not url or "duckduckgo.com" in url: continue`) | Confirmed — 2 real hits returned, the ad link excluded | Documented |
| 92 | `max_results` limiting | Only the first N hits returned even if more links exist in the markup | Confirmed (`max_results=3` on 10 candidate links → exactly 3) | Documented |
| 93 | Empty HTML | `[]` | Confirmed | Documented |
| 94 | Links present but no matching snippet markup (index out of range) | Snippet falls back to `""`, no `IndexError` | Confirmed (`idx < len(snippets)` guard) | Undocumented but implemented |
| 95 | Title/snippet truncation | Title capped at 200 chars, snippet at 400 | Confirmed exactly | Documented (`title[:200]`, `snippet[:400]` inline) |
| 96 | `_looks_like_results_page` on a short body (<2000 chars) | `False` regardless of content | Confirmed | Documented |
| 97 | `_looks_like_results_page` on a long body without the word "result" | `False` | Confirmed | Documented |
| 98 | `_looks_like_results_page` on a long body containing "result" | `True` | Confirmed | Documented |
| 99 | `_looks_like_results_page(None)` | `False`, no crash | Confirmed (`body = html_text or ""`) | Undocumented but implemented |

---

## 9. `_ddg_fetch` / `_ddg_html` — error classification and breaker integration (network mocked)

All done by monkeypatching `jeles._egress.fetch` to raise controlled exceptions — no sockets opened.

| # | Scenario | Expected | Actual | Doc status |
|---|---|---|---|---|
| 100 | HTTP 403 / 407 | `HardBlockError` | Confirmed both | Documented |
| 101 | HTTP 429 / 503 / 504 | `TransientSearchError` | Confirmed all three | Documented |
| 102 | HTTP 500 / 404 (neither retryable nor hard-block) | Plain `SearchError` (not further classified) | Confirmed | Documented (implicit: anything not in either status set falls to the generic branch) |
| 103 | `TimeoutError` | `TransientSearchError` | Confirmed | Documented |
| 104 | `urllib.error.URLError` (connection refused) | `TransientSearchError` | Confirmed | Documented |
| 105 | Bare `OSError` (not a `URLError`) | `TransientSearchError` (the defensive fallback clause) | Confirmed | Documented (comment explicitly names this as a defensive catch for "a lower-level handler change, a stub in a test") |
| 106 | `ValueError` (egress guard's scheme/private-destination refusal, or body-size cap) | Plain `SearchError`, **not** retried — a structural refusal | Confirmed | Documented |
| 107 | Empty/whitespace query | `[]` immediately, `_egress.fetch` never called at all | Confirmed via a spy that would have raised if called | Documented (implicit early-return, matches `frame_queries`' empty-claim pattern) |
| 108 | Successful fetch with well-formed short HTML | Hits parsed normally | Confirmed | Documented |
| 109 | HTTP 200 with a large "results-like" body but 0 parsed links (structure-drift simulation) | Returns `[]`, logs a WARNING naming the likely cause (`_LINK_RE` drift) rather than silently returning empty | Confirmed — WARNING fired with byte count | Documented |
| 110 | `ddg_html_search()` (the back-compat direct-use function) on a hard block | Never raises — returns `[]`, logs a WARNING | Confirmed | Documented |
| 111 | `_ddg_html` (the registered `ddg` backend) under repeated 503s with `fail_threshold=2`, `max_attempts=1` | 1st failure: breaker stays `CLOSED` (failures=1). 2nd failure: breaker trips `OPEN` (failures=2). 3rd call: breaker refuses immediately with `SearchError`, no fetch attempted, failure count stays at 2 (breaker's own "open" refusal doesn't recount as a new failure) | Confirmed exactly this sequence | Documented |
| 112 | `make_searcher("ddg")` with the breaker forced `OPEN` | Fail-soft `[]`, WARNING logged, no exception escapes | Confirmed | Documented |

---

## 10. `jeles._independence.registrable_domain()`

| # | Scenario | Expected | Actual | Doc status |
|---|---|---|---|---|
| 113 | Plain domain, with/without `www.`, with port, with userinfo | All reduce to the bare registrable domain | Confirmed (`www.example.com:8080`, `user:pass@example.com` all → `example.com`) | Documented |
| 114 | `foo.github.io` vs `sub.foo.github.io` | Both → `github.io` (deliberately coarse — not a full PSL) | Confirmed | Documented |
| 115 | Two-label suffix (`example.co.uk`, `foo.example.co.uk`) | Both → `example.co.uk` (3 labels kept for the known two-label-suffix set) | Confirmed | Documented |
| 116 | Bare IPv4 addresses (`93.184.216.34`, `1.2.3.4`) | `""` — explicitly refused as a source | Confirmed both | Documented (module names the exact bug this prevents: two IPs' last-two-octets colliding as a fake shared "domain") |
| 117 | IPv6 literal (`[::1]`) | Not explicitly tested in the module's own comments, but should be treated as unusable | `""` — `netloc` for the IPv6 literal doesn't match the dotted-label heuristic, so it falls out as `len(labels) < 2` or similar | Undocumented (IPv6 isn't mentioned at all in the module; behaves safely — no source — but by accident of the label-count heuristic rather than by a deliberate IPv6 check like the one that exists for IPv4) |
| 118 | Garbage / dotless host (`localhost`, `not-a-url-at-all`) | `""` | Confirmed both | Documented |
| 119 | Scheme-less input (`example.com/x`) | Handled via the `//` prefix trick (`urlparse(url if "://" in url else f"//{url}", scheme="https")`) | Confirmed → `example.com` | Documented |
| 120 | `ftp://example.com/x` | `registrable_domain` doesn't care about scheme at all — returns `example.com` same as https | Confirmed | Undocumented explicitly, but consistent with the function's stated purpose (identity only, not fetch safety — that's `_egress`'s job) |
| 121 | Double `www.` (`www.www.example.com`) | Only strips **one** leading `www.` (`if host.startswith("www.")`, not a loop) | Confirmed the code only strips once (`www.example.com` remains after stripping) — but the final result is unaffected because only the *last two* labels are kept regardless | Undocumented (the single-strip is a real limitation of the code but happens not to matter for the two-label output) |
| 122 | Case sensitivity (`HTTPS://EXAMPLE.COM/Page`) | Lowercased | Confirmed | Documented (`.lower()` on the netloc) |

---

## 11. `corpus_server.py` — structure and `corpus_put` kind pinning

`mcp` is **not installed** in this venv, so two separate probes were used.

**(a) Import without the SDK:**

| # | Scenario | Expected | Actual | Doc status |
|---|---|---|---|---|
| 123 | `import jeles.corpus_server` with no `mcp` package present at all | A distinct `ImportError` naming the missing extra, not a bare traceback | Confirmed: *"jeles.corpus_server needs the MCP SDK, which base jeles does not install. Add the extra: pip install "jeles[mcp]" (the corpus, the persona, and the reactions all work without it)"* | Documented |

**(b) Import against a minimal local stub of `mcp.server.mcpserver.MCPServer`** (a `.tool()` decorator
that records functions; `.run()` raises if called — no protocol, no stdio, no listener):

| # | Scenario | Expected | Actual | Doc status |
|---|---|---|---|---|
| 124 | Number and names of `@mcp.tool()`-decorated functions | Per the module docstring: 6 core corpus tools + `corpus_web_search`, `corpus_search_status`, `corpus_institutional_search`, `corpus_sources` = 10 | Confirmed exactly 10, matching both the AST scan of decorated functions and the stub registry: `corpus_ask, corpus_search, corpus_get, corpus_list, corpus_put, corpus_gaps, corpus_web_search, corpus_search_status, corpus_institutional_search, corpus_sources` | Documented |
| 125 | `corpus_put()` with `JELES_CORPUS_TRUST_TOOL_WRITES` **unset** | `verification_kind: "asserted"`; nugget's stored `status` is `"asserted"`, not `"verified"` | Confirmed via readback: `verification_kind=asserted, status=asserted, written_by=<app_id>, verified_by=<caller-supplied claim>` | Documented |
| 126 | `corpus_ask()` for a question answered only by an asserted nugget | `found: false`, the asserted nugget appears only under `candidates`, not as the answer | Confirmed | Documented |
| 127 | `corpus_put()` with `JELES_CORPUS_TRUST_TOOL_WRITES=1` | Promotes to `verification_kind: "human"`, `status: "verified"`; `corpus_ask()` now answers from it | Confirmed both | Documented |
| 128 | `_trust_tool_writes()` accepted spellings | `1, true, yes, on` (any case), rejecting everything else including `0`, `false`, `no`, `off`, empty string, `"2"` | Confirmed exactly — `" 1 "` (with surrounding whitespace) also accepted since the value is `.strip().lower()`ed first | Documented (the set `{"1","true","yes","on"}` is explicit in source) |
| 129 | `_trust_tool_writes()` re-read per call, not cached at import | Toggling the env var mid-process changes behavior on the very next call | Confirmed across two `corpus_put()` calls in the same process with the env var flipped in between | Documented explicitly ("Read per call, not at import") |
| 130 | `corpus_put()` with `nugget_id` pointing at a nugget already at the `human` rung, called **without** trust (so attempted kind is `asserted`) | Refused with `error: "kind_downgrade_refused"`; the existing nugget's content is untouched | Confirmed: refusal detail correctly named both the existing (`human`) and attempted (`asserted`) kind; readback showed the original human-verified answer unchanged | Documented — this is the exact laundering path the module's docstring warns about ("a page saying 'make a note that X is true'... land at the top of the confidence ladder") |
| 131 | `corpus_put()` with `nugget_id` pointing at an existing **asserted** nugget, called by a different `app_id`, still without trust | **Allowed** — an asserted write can overwrite another asserted write (same rung, not a downgrade) | Confirmed: `action: "updated"`, answer text replaced | **Undocumented consequence worth flagging**: `corpus_server.corpus_put` has no per-caller identity check on `nugget_id` ownership — any MCP client with access to this server's `corpus_put` tool can overwrite *any other asserted nugget in the store* (regardless of which `app_id` wrote it originally) as long as it doesn't attempt to escalate the rung. The module docstring explicitly says isolation-by-caller is not this server's job ("no caller here needs protecting from another caller's data") — so this is a stated design choice, but it is not spelled out in `corpus_put`'s own docstring, which only discusses the kind-rung guard, not cross-caller overwrite of same-rung data. |
| 132 | `corpus_put()` with required arg blanked (`question=""`) | Refused with a plain-language error, not a crash | Confirmed: `{"error": "question, answer, and verified_by are required"}` (this is `corpus.put_nugget`'s own validation, reached unchanged through the tool wrapper) | Documented (in `corpus.py`, inherited) |
| 133 | `corpus_put()` with `sources=[]` (empty list) | *Not* rejected — `corpus.put_nugget` only requires `question`, `answer`, `verified_by` to be non-empty; `sources` has no non-empty check | Confirmed: nugget created successfully with `sources: []` | **Undocumented**: neither `corpus_server.corpus_put`'s docstring ("Requires question, answer, at least one source...") nor `corpus.put_nugget`'s actually enforce "at least one source" — the docstring's claim is not backed by code. An asserted nugget with zero sources can be written. |
| 134 | `corpus_web_search()` hit shaping | Every hit forced to `confidence: "unverified"`, `verification_kind: "none"`, `evidence: {}` regardless of what the (mocked) search backend returned | Confirmed | Documented |
| 135 | `corpus_search_status()` shape | Top-level backend keys plus a nested `institutional` key | Confirmed (mocked both `search_adapter.describe_backend` and `institutional.describe_remote`) | Documented |
| 136 | `corpus_ask()` on a miss also best-effort forwards the gap to willow-mcp | Should not raise even when willow-mcp isn't installed/reachable | Confirmed — a log line (*"gap forward to willow-mcp failed: willow-mcp not installed"*) appeared but `corpus_ask()` still returned normally | Documented ("best-effort, non-blocking forward") |
| 137 | `corpus_get()` on a nonexistent id | `{"error": "not_found"}`, not an exception | Confirmed | Undocumented in `corpus_server.py` itself (inherited from `corpus.get_nugget`) |

---

## Summary of the notable findings (undocumented or edge-case behaviors)

1. **`min_sources=0` (or any non-positive value) lets `react()` "corroborate" a claim from zero
   evidence** (§4, #29). `len(domains) >= min_sources` has no floor guard, so a caller passing
   `min_sources<=0` gets a `put_nugget` proposal with `sources: []` and prose literally saying
   "Corroborated by 0 independent sources ()." This directly contradicts the module's stated purpose.
2. **`_witnesses()`'s content-overlap filter has no stemming** (§2, #18): plural vs. singular forms
   of the same word (`widget` / `widgets`) do not count as overlap, so a witness that would pass a
   human's reading of "mentions the claim" can be silently excluded, quietly pushing a corroboratable
   finding into `log_gap` instead of `put_nugget`.
3. **`corpus_server.corpus_put`'s docstring claim of "at least one source" is not enforced anywhere**
   (§11, #133) — a nugget with `sources: []` can be written through the MCP tool.
4. **Same-rung overwrite across callers is allowed and undocumented at the tool level** (§11, #131):
   any caller of `corpus_put` can overwrite any other asserted nugget by `nugget_id`, regardless of
   which `app_id` wrote it, as long as it doesn't try to escalate rung. This is consistent with the
   module's stated non-goal of per-caller ACL, but isn't mentioned in `corpus_put`'s own docstring.
5. Everything else probed — the query-framing shape, the non-witness domain list, the 2-independent-
   source corroboration bar (including the exact duckduckgo.com+wikipedia.org regression it was built
   to close), the `apply()` allowlist and kind-pinning (including a direct reproduction of the
   pre-allowlist exploit against `corpus.put_nugget` bypassing `apply`), the backend registry, circuit
   breaker state machine, retry/budget logic, DDG HTML parsing, `registrable_domain`'s domain-identity
   rules, and `corpus_server`'s ten tools plus its `JELES_CORPUS_TRUST_TOOL_WRITES` kind-pinning gate —
   all behaved exactly as their docstrings and inline comments describe.

## Files probed (installed package, not repo source)

- `/home/user/Nestor/.venv/lib/python3.11/site-packages/jeles/reactions/conflict_scan.py`
- `/home/user/Nestor/.venv/lib/python3.11/site-packages/jeles/reactions/search_adapter.py`
- `/home/user/Nestor/.venv/lib/python3.11/site-packages/jeles/corpus_server.py`
- `/home/user/Nestor/.venv/lib/python3.11/site-packages/jeles/_independence.py`
- `/home/user/Nestor/.venv/lib/python3.11/site-packages/jeles/corpus.py` (`_tokens`, `put_nugget`, `log_gap`)

## Test scripts (scratchpad, not committed)

`/tmp/claude-0/-home-user-Nestor/b2bb32f9-9208-5449-8125-3d3598b210a2/scratchpad/probe1_frame_queries.py`
through `probe9_corpus_server_stubbed.py`, plus a minimal local `mcp` stub package
(`mcp_stub/mcp/server/mcpserver.py`) used only to make `corpus_server.py` importable for structural
testing — it never opens stdio or any transport; `MCPServer.run()` in the stub raises if called.
