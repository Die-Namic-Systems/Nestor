# jeles v0.9.0 — inference gap analysis

**Date:** 2026-08-19
**Method:** Six parallel probe agents (646+ scenarios total) cross-referenced
against the 449-decision dogfood corpus (`docs/dogfood/nestor.db`, all draft).
"Dogfood ref" cites the decision's `source_text` key verbatim; "Probe ref"
cites the report file and section.

This is a *behavioral proposal*, not a decision — nothing here is sealed.

---

## 1. Kind hierarchy and the crossing boundary

**Dogfood says:**
- Nuggets cross as drafts, including `verification_kind='human'`
  (ref: "jeles nuggets carry verified_by and verified_at. Do they cross as
  sealed?" → "No. Every nugget crosses as a draft").
- Nothing is lost by demoting — verification metadata goes into the row's
  `reason` field (ref: "Is anything lost by demoting?").
- A nestor seal exported back to jeles becomes `verification_kind='asserted'`,
  `written_by='nestor'` (ref: "What does a nestor seal look like once it goes
  back to jeles?").
- The two packages' defaults fall opposite ways: `add_pair` defaults to
  `status='draft'`; `put_nugget` defaults to `verification_kind='human'`
  (ref: "Which way do the two packages' defaults fall?").

**Probes confirmed:**
- The kind hierarchy is a strict, race-safe, per-transaction guard. Lateral
  same-kind overwrites are allowed; downgrades are refused even against
  tombstoned rows. 200/200 concurrent `log_gap` writes serialized exactly;
  mixed-kind races on the same new id held the guard correctly
  (probe-corpus §1, §5).
- `corpus_server.corpus_put` without `JELES_CORPUS_TRUST_TOOL_WRITES` pins
  writes to `asserted`, never `human` (probe-reactions §11, #125–130).

**Gap:** The probe found that the kind guard has **no content-identity check**
(probe-corpus §1.14). A same-kind overwrite silently replaces the
question/answer with completely unrelated content. The dogfood corpus records
that "a proposal reaching this package's tool surface" cannot name its own
rung (ref: decision 326ea095), but nothing records whether the *content*
under a `nugget_id` should be immutable once established. The crossing
boundary demotes the rung; it does not protect the content at a given id
from lateral replacement before that crossing happens.

**Inference:** If a `human`-level writer repurposes a `nugget_id`'s content
(different question, different answer, same id, same rung), the demoted draft
that crosses into nestor carries the *replacement* content with the
*original*'s provenance trail in `reason`. The dogfood decisions assume the
rung is the axis that matters; the probe shows the content axis is unguarded.

---

## 2. The 2-source independence bar

**Dogfood says:**
- jeles' independence rule counts names, not people; "two verifiers" in nestor
  is weaker (ref: "Is 'two verifiers' the same independence jeles means?").
- The independence bar is a cheap heuristic, deliberately weighted toward
  false negatives (ref: "Is that a defect in jeles?" → "No... _independence.py
  already calls its own bar 'a cheap heuristic'").
- 43 of 71 single-sourced subjects actually struggle to clear the
  corroboration bar, and the reason is not routing breadth
  (ref: "Do the 43 single-sourced subjects actually struggle to clear jeles'
  corroboration bar?").

**Probes confirmed:**
- `verify_claims` uses `>=` (inclusive) on `min_institutions`; the
  `DEFAULT_MIN_INSTITUTIONS == 2 == MIN_INDEPENDENT_SOURCES` alias cannot
  drift (probe-verification §_verdict, §DEFAULT_MIN_INSTITUTIONS).
- `registrable_domain()` collapses `*.github.io` to one source (undercounting,
  the survivable direction). IPv4/IPv6/dotless hosts all yield empty string
  (probe-verification §_independence, probe-reactions §10).
- `conflict_scan.react()` correctly refuses the documented duckduckgo +
  wikipedia regression (probe-reactions §3, #23).

**Gaps found:**

| Gap | Probe ref | Dogfood coverage |
|-----|-----------|-----------------|
| `min_sources=0` lets `react()` corroborate from zero evidence — a `put_nugget` proposal citing 0 sources | probe-reactions §3 #29 | None. The dogfood bar discussions assume `min_sources >= 2`. |
| `min_institutions=0` (or negative) silently disables the verifier in `verify_claims` — every claim becomes `corroborated` | probe-verification §_verdict row 10 | None. |
| Percent-encoded hostnames are not decoded by `registrable_domain()` — `n%61sa.gov` ≠ `nasa.gov`, creating a potential evasion of the 2-source bar | probe-verification §_independence #156 | None. The dogfood decision about jeles' independence bar (41674a1e) discusses only the `_LONE_THE`-class weakness, not encoding-based evasion. |
| `_witnesses()` has no stemming — `widget` vs `widgets` fails the one-content-word overlap bar, so a plural-form witness is silently excluded | probe-reactions §2 #18 | None. |

**Inference:** The dogfood corpus has a clear-eyed read of the independence
bar's design bias (false-negative-tolerant), but the probe found four
distinct paths that undercut the bar in the *opposite* direction (false
positives or total bypass). None of these are recorded as decisions.

---

## 3. Corpus tokenization and matching

**Dogfood says:**
- The matcher mirrors jeles' answering, not its ranking
  (ref: "What does the matcher mirror — jeles' ranking, or its answering?").
- `NuggetMatcher` implements containment-then-symmetry, not the loose ranking
  (same ref).
- Default `StringMatcher` is used for the dogfood decision store; character
  similarity is acknowledged as a weakness
  (ref: "the decision store keys prose-about-code with the default
  StringMatcher... admits two series to the same decision" — decision
  e78efe0f).

**Probes confirmed:**
- `_confidence()` uses harmonic mean (F1) with an absolute veto: any asked
  content token absent from the nugget's question forces confidence to 0.0
  (probe-corpus §2).
- `MIN_ASK_SCORE = 0.5`, inclusive (probe-corpus §2.5).

**Gaps found:**

| Gap | Probe ref | Dogfood coverage |
|-----|-----------|-----------------|
| The apostrophe-binding comment (line 298) is only true for `_SHORT_RE` / `_ask_tokens`'s short-word fallback, not the primary `_WORD_RE` used by `_tokens`/`_score`/`log_gap`. `"don't"` truncates to `"don"` in the main tokenizer. | probe-corpus §3.14 | None. |
| The indefinite article `"a"` survives tokenization as a real content token because `_STOP` excludes all single-letter words (to protect drug-code disambiguation). | probe-corpus §3.8 | None. |
| Emoji contribute zero tokens with no warning; a pure-emoji question yields an empty token set. | probe-corpus §3.4–3.5 | None. |
| No length cap anywhere in the tokenizer — a 5000-char single token is kept whole. | probe-corpus §3.6 | None. |
| Tie-breaks in `ask_corpus` favor the most recently written nugget (via `ORDER BY updated_at DESC` + stable sort), not the first written. | probe-corpus §6.6 | None. |

**Inference:** The dogfood corpus understands the matcher/answering distinction
and knows the `StringMatcher` has limits. But the tokenizer-level behaviors
that feed both jeles' own ranking and nestor's `NuggetMatcher` have not been
recorded as decisions, even where they produce surprising results (the `"a"`
survival, the apostrophe inconsistency).

---

## 4. Gap logging and the empty-query hole

**Dogfood says:**
- jeles gaps become rows in the gap store but do not cross into nestor as rows
  (ref: "Do jeles gaps become rows?" → "No. bridge_gaps reads and returns; it
  writes nothing").

**Probes confirmed:**
- `log_gap` correctly deduplicates by `_gap_key` (UUID5 of token set +
  adjacency pairs + short codes). The `_MAX_GAP_VARIANTS=8` sliding window
  works exactly as documented (probe-corpus §4).
- `search_nuggets()` never logs a gap on a miss (probe-corpus §6.9).

**Gaps found:**

| Gap | Probe ref | Dogfood coverage |
|-----|-----------|-----------------|
| `ask_corpus` silently drops gap-logging for empty/whitespace-only queries — `log_gap`'s `{"error":"question required"}` return is discarded by its only caller. | probe-corpus §6.2b | None. |
| A gap asked only one way has no `variants` key at all (not even `[]`); callers need `.get("variants", [])`. | probe-corpus §4.7 | None. |
| No length guard on `ask_corpus` query — a 9200-char question processes normally. | probe-corpus §6.5 | None. |

**Inference:** The gap store is well-understood at the bridge level (dogfood
records that `bridge_gaps` reads only). The silent gap-logging failure for
empty queries is a genuine observability hole: a flood of empty asks leaves
zero trace in `list_gaps()`, with no signal that logging was skipped.

---

## 5. Egress guard and SSRF prevention

**Dogfood says:**
No decisions directly address jeles' egress guard. The closest is the general
concern about "this container is not reading my Drive corpus" (decision
979916a0), which is about nestor's own permissions, not jeles' `_egress.py`.

**Probes confirmed (147 scenarios):**
- `private_destination()` correctly blocks RFC 1918, loopback, link-local,
  multicast, and `0.0.0.0/8` addresses across all representations tested
  (probe-egress §4).
- Scheme guards (`HTTPS_ONLY`, `HTTP_OR_HTTPS`) work correctly (probe-egress §2).
- `read_capped()` enforces byte limits (probe-egress §7).

**Gaps found:**

| Gap | Probe ref | Dogfood coverage |
|-----|-----------|-----------------|
| Behind an HTTPS proxy, `private_destination()`'s DNS-rebinding protection is inert for hostnames the proxy is willing to reach — documented in `_proxy_dials_for` but easy to miss operationally. | probe-egress Finding 1 | None. |
| `check_url()` lets a raw `ValueError` escape for malformed bracketed IPv6 hosts, bypassing its own message-composition logic — fires even with `allow_private=True`. | probe-egress Finding 2 | None. |
| Credential-stripping on redirect is host-only — port and scheme are not part of the identity. A same-host HTTPS→HTTP downgrade under `HTTP_OR_HTTPS` retains `Authorization`/`X-Api-Key`/`Cookie` headers. | probe-egress Finding 3 | None. |

**Inference:** The egress guard is not represented in the dogfood corpus at
all. The probe found it to be thorough (147 scenarios, most matching
documentation exactly), with three documentation gaps that an operator
deploying jeles behind a proxy should know about.

---

## 6. Persona and compiler

**Dogfood says:**
No decisions directly address the jeles persona or `compile_persona()`.

**Probes confirmed (124 scenarios):**
- Import purity holds under actual `socket()`-blocking (probe-persona §1.1).
- `load_persona()` / `persona_prompt()` caching works correctly
  (probe-persona §1.5–1.8).
- `_append_closing_discipline()` handles strings, lists, and edge cases
  correctly (probe-persona §2b).
- All 84 host catalog cards pass validation (probe-persona §4).

**Gaps found:**

| Gap | Probe ref | Dogfood coverage |
|-----|-----------|-----------------|
| `load_persona()` and `persona_prompt()` have **independent** `lru_cache`s — clearing one does not invalidate the other. | probe-persona §1.9 | None. |
| `compile_persona()` handles missing keys gracefully but crashes with `AttributeError` on any section explicitly set to `None` (present-but-null). | probe-persona §2a | None. |
| The real `jeles_persona.json` has a content duplication: `overview.relationship_to_other_faculty` and `institutional_role.relationship_to_other_faculty` hold different texts; the compiler's `or`-fallback means the second copy is unreachable. | probe-persona §2c | None. |
| `_subprocess_env()`'s secret-filtering is prefix-based — a hypothetical secret-shaped `WILLOW_*` var would pass through unblocked. | probe-persona §5 | None. |

**Inference:** The persona/compiler surface is clean but has no representation
in the dogfood corpus. The independent-cache and None-crash findings are the
kind of caller-facing footgun that would benefit from a recorded decision
about intended contract.

---

## 7. Sources and routing

**Dogfood says:**
- Which field of a source declaration is worth a seal: the subject list, not
  `key_required` or `hosts` (ref: decision 0e5e714b).
- Source routing breadth was initially blamed for the 43 single-sourced
  subjects, but the real reason is different (ref: decision 35ec3405).
- Three copies of the source registry exist across repos and disagree by
  design and by drift (ref: decision 80060540).

**Probes confirmed (118 scenarios):**
- 65 sources, 61 in default fan-out, 4 opt-in — matches documentation exactly
  (probe-sources §1).
- `route_sources()` first-match-wins on keyword routing, `_MAX_ROUTE_SOURCES=6`
  (probe-sources §2).
- `_is_prose()` 6-word threshold works as documented (probe-sources §6).
- `search()` four-bucket accounting invariant (`results`, `skipped`, `failed`,
  `timed_out`) holds across all scenarios (probe-sources §12).

**Gaps found:**

| Gap | Probe ref | Dogfood coverage |
|-----|-----------|-----------------|
| `_LONE_THE`'s proper-noun guard is broken by `re.IGNORECASE` — `[A-Z]` in the lookahead is case-folded to match any letter, so `question_to_query` almost never strips a lone "the." | probe-sources §3 | None. Filed as jeles#53 per dogfood decision d25c12cf, but the regex mechanism is not recorded as a decision. |
| `search(sources=[])` silently means "search everything" — Python `if sources:` treats empty list as falsy, promoting to the full 61-source fan-out. | probe-sources §13 | None. |
| `NO_WIKIPEDIA_NOTE` is unconditionally attached to every `search()` response, including ones that explicitly requested and returned Wikipedia results. | probe-sources §14 | None. |
| `_result()` `_text()` coercion only covers `title`/`institution`/`snippet`, not `url`/`date`/`id` — those three can be `None` or non-string. | probe-sources §10 | None. |
| `limit_per_source` is entirely unvalidated — 0, negative, or large values reach adapters verbatim. | probe-sources §12 | None. |

**Inference:** The dogfood corpus has a sophisticated understanding of the
source registry's drift across repos and the corroboration bar's real
bottleneck. But the probe found five operational-level gaps in the search
dispatch and result normalization that have no corresponding decisions.

---

## 8. Verification pipeline

**Dogfood says:**
- The independence rule at the jeles level was tested against real citations
  and found that two of six domains in one case were the article being checked
  and a verbatim-quoting post (ref: decision 1a704d54).
- jeles' rules are "working mechanisms with a demonstrated escalation behind
  them" (ref: decision e02583e3).

**Probes confirmed (65 scenarios):**
- `verify_claims` correctly short-circuits on empty answer/citations
  (probe-verification §verify_claims short-circuits).
- `_fold()` normalization is case+whitespace-folding as documented
  (probe-verification §_fold).
- `_verdict()` uses inclusive `>=` on `min_institutions`
  (probe-verification §_verdict).
- `legal_citations.py` fail-soft guarantee held across all error paths
  (probe-verification §legal_citations).

**Gaps found:**

| Gap | Probe ref | Dogfood coverage |
|-----|-----------|-----------------|
| Whitespace-only `source` field in a citation defeats the institution fallback (`"   "` is truthy in Python's `or` chain) — produces an unidentifiable citation that still counts as "supported." | probe-verification Finding 1 | None. |
| `single_source` verdicts can carry an empty `institutions` list — a shape callers may not expect. | probe-verification Finding 2 | None. |
| String-typed `n` values (e.g. `"n": "1"` from JSON) are silently dropped by `isinstance(n, int)`, potentially flipping a `corroborated` verdict to `single_source`. | probe-verification Finding 3 | None. |
| `source_trail.verify_claim` confidence ties break by dict iteration order, not any documented rule. | probe-verification Finding 8 | None. |

**Inference:** The dogfood corpus understands the independence rule at a
conceptual level (the "cheap heuristic" acknowledgment) and has tested it
against real data. But the probe found four implementation-level gaps in the
verification pipeline that no decisions cover — particularly the
whitespace-truthy and string-typed-n issues, which are realistic serialization
footguns.

---

## 9. Unhandled exceptions in otherwise well-validated paths

**Probes found two species of the same gap** — validated shape, unvalidated
contents:

| Path | Exception | Probe ref |
|------|-----------|-----------|
| Bad `JELES_CORPUS_COLLECTION`/`GAPS_COLLECTION` env value → `put_nugget`/`log_gap` | Uncaught `ValueError` | probe-corpus §8.18 |
| Non-JSON-serializable value inside an otherwise-valid `evidence` dict → `put_nugget` | Uncaught `TypeError` | probe-corpus §9.8 |

**Dogfood coverage:** None. The dogfood corpus discusses jeles' write paths
at the rung/crossing/bridge level, never at the exception-shape level. Both
gaps are in paths that every other validation failure handles with a clean
`{"error": ...}` dict — these two are the exceptions.

---

## 10. Corpus server (`corpus_server.py`)

**Dogfood says:**
- The test suite should not depend on jeles being installed; the live-corpus
  test uses `importorskip` (ref: decision 160add96).
- `corpus_server.corpus_put`'s kind-pinning gate is the documented
  safeguard against a tool caller escalating to `human` rung
  (ref: decision 326ea095).

**Probes confirmed:**
- `JELES_CORPUS_TRUST_TOOL_WRITES` truth table matches documentation exactly
  (probe-reactions §11 #128).
- Kind-pinning blocks a downgrade attempt from `asserted` onto an existing
  `human` nugget (probe-reactions §11 #130).
- 10 MCP tools registered, matching the module docstring (probe-reactions §11
  #124).

**Gaps found:**

| Gap | Probe ref | Dogfood coverage |
|-----|-----------|-----------------|
| `corpus_put`'s docstring claims "at least one source" but the code does not enforce it — `sources: []` is accepted. | probe-reactions §11 #133 | None. |
| Same-rung overwrite across callers is allowed (any MCP client can overwrite any `asserted` nugget by id, regardless of `app_id`). | probe-reactions §11 #131 | None. The dogfood decision about per-caller isolation says "no caller here needs protecting from another caller's data" (inherited from the module), but `corpus_put`'s own docstring is silent about it. |

---

## Summary: what the dogfood corpus covers and what it does not

**Well covered** (dogfood decisions exist and probe confirmed the behavior):
- Crossing boundary semantics (rung demotion, metadata preservation, round-trip shape)
- Independence bar's design bias (false-negative-tolerant, cheap heuristic)
- Source registry drift across repos
- Matcher distinction (answering vs. ranking)
- Default-direction asymmetry between the two packages
- Kind-pinning at the corpus-server tool surface

**Not covered** (probe found real behaviors with no corresponding decisions):
- Content-identity gap in the kind guard (same-rung content replacement)
- Four paths that bypass or disable the 2-source bar (`min_sources=0`,
  `min_institutions=0`, percent-encoded hostnames, no stemming in witnesses)
- Tokenizer edge cases (apostrophe binding inconsistency, `"a"` survival,
  emoji dropping, no length cap)
- Silent gap-logging failure for empty queries
- Entire egress guard surface (proxy caveat, credential-stripping on redirect,
  malformed IPv6 ValueError)
- Persona compiler crashes on present-but-null sections
- Independent `lru_cache` invalidation gap
- Five source-dispatch operational gaps (`sources=[]`, unconditional Wikipedia
  note, partial `_text()` coercion, unvalidated `limit_per_source`, duplicate
  sid handling)
- Four verification-pipeline serialization footguns (whitespace-truthy source,
  empty institutions list, string-typed n, confidence tie-break)
- Two unhandled-exception gaps in write paths (collection name ValueError,
  evidence TypeError)
- Docstring/code mismatch on `corpus_put` source requirement

**Not in scope for dogfood coverage** (jeles internals that have no
nestor-side crossing):
- Cards schema validation (clean, no gaps found)
- `willow_mcp_client` fire-and-forget semantics (well-designed, gaps are
  operator-facing not nestor-facing)
- DuckDuckGo HTML SERP parsing internals
- CourtListener legal-citation lookup internals (fail-soft, no gaps found)

---

## Probe inventory

| Report | Scenarios | File |
|--------|-----------|------|
| corpus | ~55 | `jeles-probe-corpus.md` |
| sources | ~118 | `jeles-probe-sources.md` |
| verification | ~65 | `jeles-probe-verification.md` |
| egress | 147 | `jeles-probe-egress.md` |
| reactions + corpus_server | ~137 | `jeles-probe-reactions.md` |
| persona + cards + willow_mcp + init | 124 | `jeles-probe-persona.md` |
| **Total** | **646+** | |

All probes ran against the installed package at
`.venv/lib/python3.11/site-packages/jeles/` (v0.9.0), using
`/home/user/Nestor/.venv/bin/python`. No real network calls were made. All
temporary corpus stores used scratch directories, never `~/.willow/store`.
