# jeles v0.9.0 capability probe — verification pipeline

Scope: `verify.py`, `source_trail.py`, `legal_citations.py`, `_independence.py`.
Method: mocked `llm_respond` / `jeles.sources.search` / `jeles._egress.fetch`
callables and drove the public + private functions directly with
`/home/user/Nestor/.venv/bin/python`. No real network calls were made. All
scenarios below actually executed (no crashes) unless noted otherwise.

This is a *behavioral proposal*, not a decision — nothing here is sealed.

---

## verify.py

### `_parse_claim_lines()`

| # | Input | Actual output | Notes |
|---|---|---|---|
| 1 | `"CLAIM: The sky is blue \|\| SOURCES: 1,3"` | `[('The sky is blue', [1, 3])]` | Standard format, documented. |
| 2 | `"CLAIM: The sky is blue SOURCES: 1,3"` (no `\|\|`) | `[('The sky is blue', [1, 3])]` | Missing separator handled — `SOURCES:` itself becomes the cut point. Documented. |
| 3 | `"CLAIM: X \|\| 1,3"` (has `\|\|` but no `SOURCES:` label) | `[('X', [])]` | **Interesting asymmetry**: when `\|\|` *is* present, the code only looks for the `SOURCES:` marker in the tail after `\|\|` — since it's absent, `nums` stays empty even though digits `1,3` are sitting right there. Contrast with #2: dropping `\|\|` recovers the numbers, but dropping the label after a present `\|\|` loses them. Not documented explicitly (the docstring says "a missing SOURCES clause (no sources)" which covers this, but the differing mechanics by which #2 and #3 both reach "no sources" is worth knowing if debugging a parse). |
| 4 | Preamble line + a real CLAIM line | Preamble skipped, `[('X', [1])]` returned | Non-`CLAIM:` lines silently dropped. Documented. |
| 5 | CLAIM line + trailing "Hope this helps!" commentary line | Commentary skipped | Documented. |
| 6 | `"Reclaim: X \|\| SOURCES: 1"` | `[]` — no match | Confirms the `\bclaim\s*:` word-boundary regex does **not** match `Reclaim:`. Documented intent, verified correct. |
| 7 | `"disclaimer: not a claim"` | `[]` | Same word-boundary protection. Verified. |
| 8 | `"CLAIM: X \|\| SOURCES: [1],[2]"` | `[('X', [1, 2])]` | Bracket-wrapped numbers extracted via `\d+`. Documented ("numbers written [1] or 1."). |
| 9 | `"CLAIM: X \|\| SOURCES: 1., 2."` | `[('X', [1, 2])]` | Dotted numbers extracted. Documented. |
| 10 | `"CLAIM: X \|\| SOURCES: 1,1,1"` | `[('X', [1])]` | Same number repeated 3x collapses to one. Documented. |
| 11 | `"CLAIM: X \|\| SOURCES: NONE"` | `[('X', [])]` | Documented. |
| 12 | `"CLAIM: X \|\| SOURCES:"` (empty clause) | `[('X', [])]` | Documented. |
| 13 | `"CLAIM: X"` (no `\|\|`, no `SOURCES:` at all) | `[('X', [])]` | Documented. |
| 14 | `"claim: x \|\| sources: 1"` (lowercase) | `[('x', [1])]` | Case-insensitive regex confirmed (`(?i)`). |
| 15 | `"CLAIM: X \|\| SOURCE: 1"` (singular) | `[('X', [1])]` | `sources?` regex confirmed to match singular. Documented in a code comment, not the public docstring. |
| 16 | `"CLAIM: the paper lists its sources: three \|\| SOURCES: 2"` | `[('the paper lists its sources: three', [2])]` | Confirms the docstring's claim that when `\|\|` is present, the label is only searched for *after* it, so a claim whose own prose contains the word "sources:" is not truncated at its own text. Verified correct. |
| 17 | 3-line input: 2 valid CLAIM lines + 1 plain line | Only the 2 CLAIM lines parsed, in order | Multi-line handling confirmed. |
| 18 | `""` | `[]` | No crash on empty string. |
| 19 | `None` | `[]` | `(raw or "")` guards against `None` — confirmed no `AttributeError`. Not obviously documented that `None` is an accepted input; worth knowing since `llm_respond` could plausibly return `None` from a buggy mock/model wrapper. |
| 20 | `"   \n  \n"` (whitespace only) | `[]` | No crash. |
| 21 | `"- CLAIM: X \|\| SOURCES: 1"` (dash-prefixed) | `[('X', [1])]` | `claim.strip(" \t\r\n-•\|")` strips the leading dash. Documented via the strip charset in code. |
| 22 | `"• CLAIM: X \|\| SOURCES: 1"` (bullet-prefixed) | `[('X', [1])]` | Bullet stripped. |
| 23 | `"CLAIM:    \|\| SOURCES: 1"` (claim text empty after strip) | `[]` | An empty claim body after stripping is dropped entirely (the `if not claim: continue` guard) — so an otherwise well-formed line with sourced-but-blank claim text vanishes rather than appearing as an empty-string claim. Undocumented edge case, plausible real-world trigger if a model emits `"CLAIM: || SOURCES: 1"`. |
| 24 | `"CLAIM: sources: 5 is a great year \|\| SOURCES: 2"` | `[('sources: 5 is a great year', [2])]` | Own-text "sources:" occurring *before* `\|\|` does not confuse extraction; digits from the claim's own prose (`5`) are not picked up, only the post-label `2`. Confirms #16's mechanism more thoroughly. |

### `_fold()`

| Input | Output |
|---|---|
| `"NASA"` | `"nasa"` |
| `"nasa "` | `"nasa"` |
| `"  NASA  "` | `"nasa"` |
| `"New   York University"` (internal multi-space) | `"new york university"` — internal runs of whitespace collapsed to one space, confirming `_WHITESPACE_RE.sub(" ", …)` |
| `"NASA\t\n"` | `"nasa"` |
| `""` | `""` |

Confirmed: `_fold("NASA") == _fold("nasa ") == _fold("  NASA  ")` → `True`, exactly as the docstring claims.

### `_identity()`

| Citation dict | `(key, display)` | Notes |
|---|---|---|
| `{"source": "NASA", "url": "https://nasa.gov/x"}` | `("nasa", "NASA")` | Source used. |
| `{"institution": "NASA", "url": "..."}` (no `source`) | `("nasa", "NASA")` | Institution fallback used. |
| `{"source": "NASA", "institution": "Goddard"}` | `("nasa", "NASA")` | **Source wins** over institution when both present, confirmed. |
| `{"url": "https://www.nasa.gov/page"}` (neither field) | `("nasa.gov", "nasa.gov")` | Falls back to `registrable_domain(url)`; `www.` stripped by the domain function. |
| `{}` (no source/institution/url at all) | `("", "")` | Both empty — this citation becomes unidentifiable but is *not dropped* upstream in `verify_claims` (see below). |
| `{"source": "", "institution": ""}` with URL present | falls to domain | Confirms empty-string fields are treated as absent, not as a legitimate empty label. |
| `{"source": "", "institution": "ESA"}` | `("esa", "ESA")` | Empty source correctly falls through to institution. |
| `{"source": "   ", "institution": "ESA"}` | **`("", "")`** — not `("esa", "ESA")`! | Whitespace-only `source` is truthy in Python (`"   " or x` returns `"   "` since it's non-empty), so `citation.get("source") or citation.get("institution")` picks the whitespace string, not "ESA". It only becomes `""` after `.strip()`, by which point `institution` has already been discarded. **This looks like a real bug / undocumented edge case**: a citation with `source: "   "` (whitespace) and a perfectly good `institution: "ESA"` loses the institution entirely and becomes an unidentifiable citation, rather than falling back to ESA the way an empty-string `source` does. |
| `{"url": "http://93.184.216.34/page"}` (IP only) | `("", "")` | IP addresses are rejected by `registrable_domain`, so an IP-only citation with no source/institution is completely unidentifiable. Consistent with `_independence.py`'s IP rejection but worth flagging as a real-world dead end for e.g. bare-IP CDN citations. |
| `{"url": "nasa.gov/page"}` (schemeless) | `("nasa.gov", "nasa.gov")` | Confirmed `registrable_domain` handles schemeless URLs. |

**Follow-on test — the whitespace-source bug's real-world consequence** (see "unnameable-but-supported" case below): a citation like `{"n": 5, "url": "http://localhost/no-domain"}` (dotless host, no source/institution) produces identity `("", "")`. Fed through `verify_claims`, a claim citing only source `5` gets `institutions: []` yet verdict `"single_source"` (not `"unsupported"`) because `supported = bool(valid_nums)` is `True` — the citation *exists and is cited*, it simply cannot be named. This is consistent with the `_verdict` docstring's claim that `single_source` "also catches citations too anonymous to distinguish," but it is a genuinely surprising shape: **`single_source` with an empty `institutions` list**. Not obviously anticipated by a caller who assumes `single_source` implies `len(institutions) >= 1`.

### `_verdict()`

Signature: `_verdict(named: Sequence[str], supported: bool, min_institutions: int) -> str`.

| named | supported | min_institutions | Verdict | Notes |
|---|---|---|---|---|
| `["A"]` | `True` | 2 | `single_source` | 1 institution, bar=2. |
| `["A","B"]` | `True` | 2 | `corroborated` | Exactly at the bar → `corroborated`. Confirms `>=`, not `>`. |
| `["A","B","C"]` | `True` | 2 | `corroborated` | Above the bar. |
| `[]` | `False` | 2 | `unsupported` | Nothing cited. |
| `[]` | `True` | 2 | **`single_source`** | Edge case: 0 named institutions but `supported=True` still yields `single_source`, not `unsupported`. This is the exact "unnameable-but-supported" shape from `_identity` above, produced directly. |
| `["A"]` | `False` | 2 | `unsupported` | Institutions named but `supported=False` (an inconsistent combination `verify_claims` itself never constructs, since `supported = bool(valid_nums)` and `named` is derived from `valid_nums`) still resolves cleanly — `unsupported` wins because `len(named) < min_institutions`. |
| `["A","B"]` | `True` | 3 | `single_source` | Bar raised to 3 — 2 institutions is no longer enough. |
| `["A","B","C"]` | `True` | 3 | `corroborated` | Exactly at raised bar. |
| `["A"]` | `True` | 1 | `corroborated` | `min_institutions=1` — a single named institution is sufficient at bar 1. |
| `[]` | `True` | 0 | `corroborated` | `min_institutions=0` → `0 >= 0` is `True`, so even zero named institutions "corroborate." Degenerate but consistent with the `>=` comparison; nothing guards against `min_institutions=0` being passed. |
| `[]` | `False` | 0 | `corroborated` | Same — `min_institutions=0` makes `corroborated` the verdict for *any* claim regardless of `supported`, since the `len(named) >= min_institutions` check short-circuits before `supported` is even consulted. **Undocumented**: nothing in `verify_claims`/`verify_claims`'s public signature stops a caller from passing `min_institutions=0` (or negative), which silently degrades the entire verifier to "everything is corroborated."

### `DEFAULT_MIN_INSTITUTIONS`

Confirmed `verify.DEFAULT_MIN_INSTITUTIONS == 2 == _independence.MIN_INDEPENDENT_SOURCES`, and it is a direct import-alias (`DEFAULT_MIN_INSTITUTIONS = MIN_INDEPENDENT_SOURCES`), not a re-declared literal — so the two truly cannot drift independently at the source level (only by editing `_independence.py`). Documented and verified.

### `verify_claims()` — short-circuits

| Scenario | Result | `llm_respond` invocation count |
|---|---|---|
| `answer=""`, non-empty citations | `{"claims": [], "summary": {total:0, corroborated:0, single_source:0, unsupported:0}}` | 0 — confirmed not called |
| Non-empty answer, `citations=[]` | Same empty report | 0 — confirmed not called |
| Both empty | Same empty report | 0 — confirmed not called |

All three short-circuits confirmed to skip `llm_respond` entirely, as documented.

### `verify_claims()` — normal flow

| Scenario | Result |
|---|---|
| Citations for NASA(n=1), ESA(n=2), "nasa " (n=3, folds to NASA); mock cites `1,2` | `institutions: ["ESA", "NASA"]`, `verdict: "corroborated"` — 2 distinct folded institutions. |
| Mock cites `1,3` (both fold to NASA) | `institutions: ["NASA"]`, `verdict: "single_source"` — folding correctly collapses n=1 and n=3 to one institution, so 2 *citations* only count as 1 *institution*. This is the core anti-gaming behavior working as documented. |
| Mock cites `1,99` (99 doesn't exist in `key_by_n`) | `sources: [1]` (99 silently dropped), `verdict: "single_source"` — confirms invented numbers are dropped, never counted, exactly as documented. |
| Mock returns claim with no `SOURCES:` clause at all | `verdict: "unsupported"` | 
| Mock returns `SOURCES: NONE` | `verdict: "unsupported"` |
| Mock cites `1,1` (dup number, same citation) | `sources: [1]`, `institutions: ["NASA"]`, `verdict: "single_source"` |
| Claim text has no `\|\|` but does have a literal `SOURCES:` label ("CLAIM: X SOURCES: 1,2") | Parsed correctly as `sources: [1,2]`, `institutions: ["ESA","NASA"]`, `verdict: "corroborated"` — the "missing `\|\|`" tolerance flows all the way through the real pipeline, not just the parser unit. |
| 3-claim batch: one `corroborated`, one `single_source`, one `NONE`→`unsupported` | `summary: {total:3, corroborated:1, single_source:1, unsupported:1}` — summary counts match per-claim verdicts exactly. |

### `verify_claims()` — error handling

| Scenario | Result |
|---|---|
| `llm_respond` raises `RuntimeError("model unavailable")` | `{"claims": [], "summary": {..., "error": "model unavailable"}}` — caught, no propagation, confirmed exactly as documented. |
| `llm_respond` raises a custom exception subclass | `{"claims": [], "summary": {..., "error": "weird"}}` — the `except Exception` catches arbitrary custom exception types too (broad catch, as documented — "anything it raises"). |

### `verify_claims()` — malformed citation records

| Scenario | Result |
|---|---|
| One citation has `"n": "1"` (string, not int) | Silently skipped by `if not isinstance(n, int): continue` — a claim citing `SOURCES: 1,2` where citation-1's `n` is the *string* `"1"` only picks up citation-2 (`ESA`), producing `single_source` instead of the `corroborated` a caller might expect if they assumed string/int `n` values were equivalent. This is a real footgun for any host that builds citation records from JSON without normalizing types (JSON round-trips can preserve `"n": "1"` as a string if the source system serialized loosely). Undocumented in the module docstring — worth flagging to anything constructing citation dicts programmatically. |
| Custom `min_institutions=3` with exactly 3 named institutions | `corroborated` |
| Custom `min_institutions=4` with 3 named institutions | `single_source` — confirms the `min_institutions` kwarg overrides `DEFAULT_MIN_INSTITUTIONS` correctly end-to-end. |

---

## `_independence.py`

### `MIN_INDEPENDENT_SOURCES`

Confirmed value: `2`.

### `registrable_domain()`

| Input | Output | Notes |
|---|---|---|
| `"https://www.nasa.gov/some/path"` | `"nasa.gov"` | Scheme, `www.`, path all stripped. |
| `"nasa.gov"` (bare hostname, no scheme) | `"nasa.gov"` | Schemeless input parsed correctly via the `//` prefix trick. |
| `"www.nasa.gov"` (bare, with www) | `"nasa.gov"` | |
| `"https://foo.co.uk/page"` | `"foo.co.uk"` | Two-label suffix set kept 3 labels, as documented. |
| `"bar.co.uk"` (bare) | `"bar.co.uk"` | Two-label suffix logic applies even without a scheme. |
| `"https://example.com.au/x"` | `"example.com.au"` | |
| `"http://93.184.216.34/page"` | `""` | IPv4 correctly rejected. |
| `"93.184.216.34"` (bare IP, no scheme) | `""` | Bare IP also rejected — the IPv4 regex check runs after `www.`-strip/labels regardless of scheme presence. |
| `"1.2.3.4"` | `""` | Confirms the docstring's specific claim that `1.2.3.4` does *not* collapse to `"3.4"`. |
| `"https://nasa.gov/%20path%2Fwith%20stuff"` (percent-encoded path) | `"nasa.gov"` | Path is discarded entirely so encoding there is irrelevant. |
| `"https://n%61sa.gov/x"` (percent-encoded **host**) | `"n%61sa.gov"` | **Not decoded.** `urlparse` does not percent-decode the netloc, so a percent-encoded hostname (`%61` = `a`) passes through literally as `n%61sa.gov` instead of resolving to `nasa.gov`. This means a citation URL with an encoded host would be treated as a *different* domain than the same host written plainly — a real evasion vector if anything upstream percent-encodes hostnames (deliberately or via a buggy URL builder), since two citations from the same real site could then count as "independent." Not documented anywhere in the module. |
| `""` | `""` | |
| `"https://"` | `""` | Empty netloc → 0 labels → `""`. |
| `"http://localhost/x"` | `""` | Dotless host correctly rejected (`len(labels) < 2`). |
| `"localhost"` (bare) | `""` | Same. |
| `"https://foo.github.io/bar"` | `"github.io"` | Confirms the docstring's own example verbatim. Note `github.io` itself is *not* in `_TWO_LABEL_SUFFIXES`, so this is genuinely "coarse" as advertised — every `*.github.io` subdomain collapses to one source, a real false-negative-for-independence direction (undercounting, the "survivable" direction per the module's own stated bias). |
| `"https://nasa.gov:8443/x"` | `"nasa.gov"` | Port stripped correctly. |
| `"https://user:pass@nasa.gov/x"` | `"nasa.gov"` | Userinfo stripped correctly. |
| `"not a url at all !! ###"` | `""` | No crash; garbage silently yields empty domain (0 valid labels). |
| `"https://sub.example.com/x"` | `"example.com"` | Ordinary 3-label host reduces to registrable domain, subdomain dropped (not distinguished as its own source — `sub.example.com` and `other.example.com` collapse to the same key). |
| `"nasa.gov."` (trailing dot) | `"nasa.gov"` | Trailing-dot FQDN handled gracefully (empty last label filtered by `if x` in the list comprehension). |
| `"HTTPS://NASA.GOV/PATH"` (all uppercase) | `"nasa.gov"` | `.lower()` on netloc normalizes case. |
| `"https://x.co.jp/y"` | `"x.co.jp"` | |
| `"https://example.io/y"` | `"example.io"` | `.io` is *not* in the two-label suffix set (correctly — it's a normal ccTLD, `example.io` already is the registrable domain at 2 labels), so no special handling needed or applied. |
| `"http://999.1.1.1/x"` (out-of-range octets) | `""` | The IPv4 regex `^\d{1,3}(\.\d{1,3}){3}$` does **not** validate the 0–255 range, but `999.1.1.1` still matches the pattern (each group just needs 1-3 digits) and is correctly rejected as an "IP-shaped" host regardless of validity. Confirms the regex is deliberately permissive about the numeric range — it only needs to catch IP-shaped strings, not validate real IPs, which is fine for the module's purpose. |
| `"WWW.Nasa.Gov"` (bare, mixed case with www) | `"nasa.gov"` | Case + www both normalized together. |

The function never raised on any of the above inputs, consistent with the docstring's "never raises" guarantee.

---

## `source_trail.py`

### `extract_claims()`

| Scenario | Result |
|---|---|
| Mock returns 3 clean lines | All 3 returned, in order. |
| Mock returns 20 lines | Truncated to first 10 (`lines[:10]`) — confirmed max-10 cap. |
| Mock returns lines with blank/whitespace-only lines interspersed | Blank lines filtered out entirely (not counted toward the 10-line cap as empty placeholders) — `[ln.strip() for ln in raw.strip().splitlines() if ln.strip()]`. |
| Mock returns `""` | `[]` |
| Mock raises `RuntimeError` | Caught, logged via `log.warning`, returns `[]` — confirmed no propagation. |
| Input text of 5000 chars | Model receives exactly 4000 chars (`text[:4000]`) — confirmed via a capture-mock. |
| Input text of exactly 4000 chars | Model receives all 4000 chars unmodified (boundary case: `4000 == 4000` is not `> 4000`, no truncation triggered at exactly the boundary). |
| Input text of 100 chars | Model receives all 100, unaffected by the cap. |

All confirm the docstring's stated behavior precisely, including the boundary at exactly 4000.

### `verify_claim()`

| Scenario | Result |
|---|---|
| Two sources with different confidences (0.5 low, 0.9 high) both return one hit each | `source: "high_conf_src"` wins — highest-confidence hit selected correctly. |
| Source ID `"fbi_vault"` (in `PRESS_SOURCES`) returns a hit | `tier: "press"` |
| Source ID `"openalex"` (not in `PRESS_SOURCES`) returns a hit | `tier: "academic"` |
| Source ID with **no entry** in `_SOURCE_CONFIDENCE` | `confidence: 0.70` — confirms the documented 0.70 fallback for unregistered/press-only adapters. |
| No hits returned from any source (`{"results": {}}`) | `matched: False`, all string fields `""`, `confidence: 0.0` — the documented empty-result shape. |
| Two sources tied at confidence 0.8 (`src_a` first in dict, `src_b` second) | `source: "src_a"` wins | **Tie-break behavior, undocumented**: the loop uses strict `if conf > best_conf`, so on a tie the *first-iterated* hit keeps its slot and a later equal-confidence hit never overwrites it. Since Python dicts preserve insertion order, this means tie-breaking is effectively "first source dict key wins," which is an implementation detail of `sources.search`'s dict-building order rather than anything the caller controls or that the docstring mentions. Worth knowing if two adapters are ever given identical confidence values deliberately. |
| `sources=["explicit_src"]` (non-empty explicit list) | `route_sources` not called; `sources.search` called with exactly `["explicit_src"]` | Confirms explicit list bypasses auto-routing. |
| `sources=[]` (empty list — falsy) | `route_sources(claim)` **is** called — confirms the documented "bug-for-bug" match with upstream: `if sources` treats an empty list the same as `None`, silently falling back to auto-routing rather than searching zero sources (which would arguably be the more literal interpretation of "search exactly this empty list"). Documented as intentional upstream-parity behavior, verified present. |

### `verify_text()`

| Scenario | Result |
|---|---|
| Mock extracts 2 claims; `verify_claim` mocked to alternate matched/unmatched | `{"total": 2, "matched": 1, "claims": [...]}` — counts derived correctly from the per-claim `matched` flags. |
| Mock extraction returns `""` (no claims) | `{"claims": [], "total": 0, "matched": 0, "note": "No verifiable claims found."}`; `verify_claim` **never invoked** (confirmed via call counter) — confirms the short-circuit documented in the module docstring, and specifically that it avoids calling `verify_claim` zero times "silently" by adding the `note` key. |

### `PRESS_SOURCES`

Confirmed contents (frozenset, 7 members): `fbi_vault`, `ig_nobel`, `isfdb`, `medscape`, `omdb`, `psychiatric_times`, `stat_news`.

Confirmed `"openalex"` and `"pubmed"` are *not* members (i.e., they fall to the `academic` tier by exclusion, as the module docstring states — academic is "everything in `sources.SOURCES` not listed in `PRESS_SOURCES`," membership-by-exclusion rather than an explicit academic allowlist).

---

## `legal_citations.py`

### Token requirement

| Scenario | Result |
|---|---|
| No `COURTLISTENER_API_TOKEN` env var, no `token=` kwarg | `{"ok": False, "configured": False, "reason": "no CourtListener API token…", "citations": []}` — confirmed **zero** network calls attempted (verified via a monkeypatched `_egress.fetch` that was never invoked). |
| `token="fake-token-123"` passed explicitly, mocked `fetch` returns a 200-shaped payload | `fetch` called exactly once; result has `ok: True`, `matched: True` for the sample citation. |
| `COURTLISTENER_API_TOKEN` set via env var only (no `token=` kwarg) | `fetch` called — confirms the env-var fallback (`token or os.environ.get(...)`) works, and is read per-call (not cached at import), matching the docstring. |

### 64,000-character limit

| Text length | Result |
|---|---|
| Exactly 64,000 chars | **Allowed** — `fetch` called once, `ok: True`. Confirms the check is strictly `len(text) > MAX_TEXT_CHARS`, so the boundary value itself is not refused (only text *over* the cap is). |
| 64,001 chars (1 over) | Refused: `ok: False`, `configured: True`, reason names the exact length (`"text is 64001 characters, over CourtListener's 64000-character limit…"`) and instructs to split. `fetch` confirmed **not called**. |
| 200,000 chars (well over) | Same refusal shape, `fetch` not called. |

All three confirm the documented "refuse, don't truncate" behavior, including the exact boundary condition.

### `_record()` / status mapping (unit-level, no network)

| Input `status` | `matched` | Notes |
|---|---|---|
| `200`, non-empty `clusters` | `True` | Documented "found" case. |
| `404`, empty `clusters` | `False` | Documented "well-formed but not in database" case — confirmed this is *not* mistaken for a match. |
| `400`, empty `clusters` | `False` | Documented "unrecognized reporter" case. |
| `300`, `normalized_citations` populated | `False`, and `normalized_citations` is surfaced verbatim in the output (`["3 F.3d 3", "3 F.4th 3"]`) | Confirms ambiguous citations are *not* auto-resolved — the module truly just surfaces the candidate list rather than picking one, as documented. |
| `999` (unrecognized/future status) | `False` | Confirms forward-compatibility: an unknown status code degrades to `matched: False` rather than raising, exactly as documented ("a fifth status added upstream" scenario). |
| No `status` key present at all | `status: None`, `matched: False` | `status == 200` comparison against `None` safely evaluates `False`, no `KeyError`/exception. Not explicitly called out in the docstring but behaves exactly as the "never raises" guarantee implies. |

### `_cluster_field()` precedence (unit-level)

| Scenario | Result | Notes |
|---|---|---|
| Cluster has both `case_name` and `caseName` | `case: "Snake Case Wins"` (the `case_name` value) | Confirms the documented try-order `("case_name", "caseName", "case_name_short")` — snake_case checked first, camelCase is the fallback only. |
| Cluster has both `court` and `court_id` | `court: "court-field-wins"` (the plain `court` value) | **Different precedence order than case/date fields**: for `court` the try-order is `("court", "court_id", "court_citation_string")` — here the *shorter/plain* name is checked first, the opposite ordering convention from `case_name`-before-`caseName`. This is exactly as coded (verified by reading the `_cluster_field(cluster, "court", "court_id", "court_citation_string")` call site) but worth flagging: the two field groups don't follow one consistent naming-convention-preference rule, they were independently ordered per field. Not documented as a general principle, only implicit in the call-site argument order. |
| `normalized_citations` present but not a list (a string) | Coerced to `[]` (not wrapped as `["not-a-list"]`) | The `isinstance(normalized, list)` guard rejects non-list values entirely rather than trying to salvage them — confirmed defensive behavior against a malformed upstream response. |
| `clusters` present but `clusters[0]` is not a dict (e.g. a bare string) | No crash — `cluster` falls back to `{}`, all cluster-derived fields become `""` | Confirms the `isinstance(clusters[0], dict)` guard in the module. |

### Top-level failure handling (network-level, mocked `_egress.fetch`)

| Scenario | Result |
|---|---|
| `fetch` raises `HTTPError(code=429)` with body `{"wait_until": "2026-08-19T12:00:00Z"}` | `{"ok": False, "configured": True, "reason": "CourtListener rate-limited this request (HTTP 429); retry after 2026-08-19T12:00:00Z"}` — confirms the `wait_until` extraction and folding into `reason`. |
| `fetch` raises `HTTPError(code=500)` | `{"ok": False, "configured": True, "reason": "CourtListener returned HTTP 500: Internal Server Error"}` | Generic HTTP error path, distinct message shape from 429. |
| `fetch` returns malformed (non-JSON) bytes | `{"ok": False, "configured": True, "reason": "could not parse CourtListener's response: JSONDecodeError: …"}` — no exception propagates. |
| `fetch` returns valid JSON but a dict, not a list | `{"ok": False, "configured": True, "reason": "CourtListener's response was not the documented JSON array"}` |
| `fetch` returns `b"[]"` (valid, empty array — "no citations found in this prose") | `{"ok": True, "configured": True, "reason": "", "citations": [], "count": 0, "matched_count": 0}` — correctly distinguished from all the failure shapes above: an empty-but-successful lookup is `ok: True`, not `ok: False`. |
| `fetch` raises an unrelated exception (`ConnectionResetError`) | `{"ok": False, "configured": True, "reason": "ConnectionResetError: connection reset"}` — the generic `except Exception` catch-all confirmed to handle arbitrary network-layer exceptions, not just `urllib.error.HTTPError`. |

All failure paths confirmed to never raise into the caller, matching the "fail-soft, always" module guarantee.

---

## Summary of notable undocumented/surprising findings

1. **`verify.py` — whitespace-only `source` field defeats the institution fallback.** `{"source": "   ", "institution": "ESA"}` resolves to identity `("", "")`, not `("esa", "ESA")`, because Python's `or` treats a whitespace-only string as truthy — the fallback to `institution` never triggers, and the string is only stripped to empty *after* that decision. An empty-string `source` correctly falls through; a whitespace-only one does not. This is a real gap for any citation-producing pipeline that might pad or default `source` to a space rather than an empty string.

2. **`verify.py` — `single_source` verdicts can carry an empty `institutions` list.** When a cited source number resolves to an unidentifiable citation (`_identity` returns `("", "")`), the claim is still `supported=True` (a source number was cited and is valid) but contributes nothing to `named`. The verdict comes back `single_source` with `institutions: []`, which is a legitimate but easy-to-miss shape for any caller rendering the report (e.g., a UI that assumes `single_source` always has at least one name to show).

3. **`verify.py` — string-typed `n` values are silently dropped, not coerced.** A citation with `"n": "1"` (JSON string instead of int) is invisible to `verify_claims` entirely (`isinstance(n, int)` check), which can quietly turn what should be a `corroborated` verdict into `single_source` if a caller's citation-serialization path loses the int type anywhere along the way.

4. **`verify.py` — `min_institutions=0` (or negative) silently disables the verifier.** Nothing guards the `min_institutions` kwarg; passing 0 makes every claim `corroborated` regardless of `supported`, since `len(named) >= 0` is always true and short-circuits before the `supported` check.

5. **`_independence.py` — percent-encoded hostnames are not decoded.** `https://n%61sa.gov/x` yields registrable domain `"n%61sa.gov"`, literally, rather than resolving to `"nasa.gov"`. Two citations, one plain and one percent-encoded, from the same real host would be treated as independent sources — a potential (if obscure) evasion of the two-source independence bar.

6. **`_independence.py` — IPv4 detection doesn't validate the octet range**, e.g. `999.1.1.1` is still caught and rejected by the "IP-shaped" regex even though it's not a valid IP — a deliberate and correct permissiveness for the module's purpose (reject anything IP-*shaped*), confirmed working as intended rather than a bug.

7. **`legal_citations.py` — `_cluster_field`'s try-order isn't a single consistent convention.** `case`/`date` prefer `snake_case` first then `camelCase`; `court` prefers the short/plain `court` key first, ahead of `court_id`. Both are correct per their individual docstring rationale, but there's no single naming rule a reader could predict without checking each call site.

8. **`source_trail.py` — confidence ties break by dict/iteration order, not any documented rule.** Strict `>` comparison in `verify_claim`'s best-hit loop means the first-iterated hit at a given confidence level wins; a later hit with an equal confidence never displaces it.

No crashes, unhandled exceptions, or contract violations were found in ~35 distinct code paths exercised beyond the specific findings above — the fail-soft/no-network/short-circuit guarantees documented in each module's docstring all held up under adversarial and boundary inputs.
