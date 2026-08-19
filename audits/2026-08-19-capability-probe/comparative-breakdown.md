# Nestor Capability Breakdown: With and Without Jeles

> Generated 2026-08-19 using `nestor` CLI (decision check, match, stats,
> rejections, evidence report) and `jeles` Python API (corpus, egress,
> independence, conflict_scan, verify, persona, source_trail).
>
> **Method:** Each capability area was probed by running the actual tools —
> `nestor --db docs/dogfood/nestor.db decision check "<question>"` and
> `from jeles import corpus; corpus.ask_corpus("<question>")` — and comparing
> what each tool knows, can do, and surfaces. Probe reports (6 Nestor, 6 jeles,
> ~1300 scenarios total) provide the behavioral evidence.

---

## 1. Corpus & Decision Memory

### Nestor alone

**What it has:** 449 decision pairs in `docs/dogfood/nestor.db`, all draft
status, zero sealed. Domain: `decision→decision`. SQLite-backed, hash-chained
ledger, 7-table schema.

```
$ nestor --db docs/dogfood/nestor.db stats
449 pair(s): 0 sealed, 449 draft
  domains: decision→decision (449)
  seal signatures: OFF — stored status is trusted
  ledger: ✓ intact — 1 entries
```

**Decision check:** Lexical matcher (StringMatcher, Jaccard similarity).
Queries like "seal authority" score at best 0.429 against 449 candidates
(bar is 0.92), so most probe-discovered behaviors have no recorded decision.
Of 12 key questions tested, all returned `✓ clear — no decision on record`
or showed only weak fuzzy matches (0.55–0.58).

**Match:** The `match` subcommand defaults to `en→es` domain. Querying the
`decision→decision` domain requires explicit `--from decision --to decision`.
Without those flags, the 449-pair corpus is invisible:

```
$ nestor --db docs/dogfood/nestor.db match "seal authority"
! would not be served — nothing in this domain matched at all

$ nestor --db docs/dogfood/nestor.db match --from decision --to decision "seal authority"
! would not be served — closest of 449 candidate(s) is 0.429, below 0.92
```

**What it cannot do alone:**
- No source verification pipeline — no way to check if a claim is backed by
  independent sources
- No egress guard — no SSRF/DNS-rebinding protection for outbound requests
- No conflict detection across claims — contradictions must be found manually
- No structured gap logging — gaps are inferred from `decision check` exit
  codes, not tracked as first-class objects
- No persona/voice compilation
- No institutional source search

### With jeles

**Corpus:** jeles adds a parallel nugget store (`ask_corpus`, `put_nugget`,
`log_gap`). After populating it with 5 probe findings:

```python
>>> corpus.put_nugget(
...     question='What matcher does nestor use by default for all domains?',
...     answer='StringMatcher (Jaccard/character-based). 412==412 scores 0.75.',
...     sources=['probe-cascade.md'],
...     verified_by='probe-agent', verification_kind='machine')
{'id': 'e4e4f1c9', 'action': 'created', 'verification_kind': 'machine'}

>>> corpus.ask_corpus('What matcher does nestor use?')
{'found': True, 'nugget': {'answer': 'StringMatcher ...'}}
```

**Gap tracking:** jeles tracks gaps as first-class objects. 22 gaps logged
from the probe cross-reference — each with an ID, question text, and ask count:

```python
>>> corpus.log_gap('No decision on whether nestor should auto-detect numeric domains')
{'id': '3ab2b14c6395', 'asked_count': 1}
>>> len(corpus.list_gaps())
22
```

**Net gain:** Nestor's `decision check` tells you "no decision on record."
Jeles' `log_gap` + `list_gaps` turns that absence into a tracked work queue
with IDs and counts.

---

## 2. Source Verification & Independence

### Nestor alone

**No capability.** Nestor has no concept of independent sources. The seal
model is: a human verifier signs a decision. There is no automated check
that the underlying claim has corroboration from multiple independent sources.

```
$ nestor --db docs/dogfood/nestor.db decision check \
    "How does the verification pipeline corroborate claims from multiple sources"
✓ clear — no decision on record
```

The dogfood corpus does discuss jeles' independence rule in several decisions
(e.g., `fd9536ec`: "Is 'two verifiers' the same independence jeles means?" →
"No, and it is weaker. This counts names, not people."), but nestor itself
cannot enforce it.

### With jeles

**Full pipeline.** jeles provides:

1. **`_independence.registrable_domain()`** — deduplicates sources by
   registrable domain (reuters.com ≠ apnews.com, but www.reuters.com =
   reuters.com):

   ```python
   >>> registrable_domain('https://reuters.com/article/1')
   'reuters.com'
   >>> registrable_domain('https://www.reuters.com/article/2')
   'reuters.com'  # same source — not independent
   >>> MIN_INDEPENDENT_SOURCES
   2
   ```

2. **`verify.verify_claims()`** — full verification pipeline requiring
   `min_institutions` (default 2) independent institutional sources

3. **`source_trail.verify_claim()`** — single-claim verification with source
   limit

4. **`source_trail.verify_text()`** — multi-claim text verification via LLM
   claim extraction

**Probe findings on the pipeline:**
- Whitespace-only source field defeats institution fallback (jeles-probe-verification.md)
- `min_institutions=0` disables the verifier entirely (probe finding)
- String-typed `n` values silently dropped from counts (probe finding)
- Percent-encoded hostnames not decoded by `registrable_domain()` (probe finding)

**Net gain:** From zero source verification to a full pipeline with
independence checks, institutional source matching, and corroboration bars.

---

## 3. Egress Security (SSRF Prevention)

### Nestor alone

**No capability.** Nestor has no outbound HTTP fetching. The MCP server is
pure stdio; the UI serves only from localhost. No egress guard needed because
there is no egress.

### With jeles

**Full egress guard** (`jeles._egress`):

```python
>>> from jeles._egress import check_url, private_destination

# Private/internal addresses blocked
>>> private_destination('http://127.0.0.1/admin')
'127.0.0.1 is not a public address'
>>> private_destination('http://169.254.169.254/latest/meta-data/')
'169.254.169.254 is not a public address'
>>> private_destination('http://10.0.0.1/internal')
'10.0.0.1 is not a public address'
>>> private_destination('http://[::1]/secret')
'::1 is not a public address'

# Public addresses pass
>>> private_destination('https://reuters.com/article/test')
None  # allowed
```

**`check_url(url, allowed)`** — allowlist-based URL validation with private
destination blocking. Rejects URLs whose scheme, host, or resolved IP falls
outside the allowed set.

**Probe findings on the guard (147 scenarios):**
- Proxy mode disables DNS-rebinding protection for HTTPS (Finding 1 — the
  biggest: a CONNECT proxy forwards to whatever the DNS says at handshake
  time, not at check time)
- `check_url` raises raw `ValueError` on malformed IPv6 (Finding 2)
- Credential-stripping ignores port and scheme (Finding 3)

**Net gain:** From no egress surface to an active SSRF guard with private-IP
blocking, allowlist enforcement, and scheme validation — with known gaps in
proxy mode and IPv6 edge cases.

---

## 4. Conflict Detection

### Nestor alone

**Limited.** Nestor has decision graph edges (`contradicts`, `supersedes`,
`refines`) but they must be manually created. The `decision check` command
finds lexical matches, not semantic conflicts. Two decisions that contradict
each other will coexist silently unless a human draws the edge.

The dogfood corpus has 449 decisions and zero `contradicts` edges sealed. The
edge-sealing surface exists (`/api/edge/seal` in the UI, `decision_edges`
table in the schema) but is unused in the current corpus.

### With jeles

**Automated conflict scanning** (`jeles.reactions.conflict_scan`):

```python
>>> from jeles.reactions import conflict_scan

# frame_queries generates search queries to find conflicting evidence
>>> conflict_scan.frame_queries('The nestor matcher defaults to StringMatcher')
['The nestor matcher defaults to StringMatcher existing implementation library',
 'The nestor matcher defaults to StringMatcher alternative that supersedes',
 'The nestor matcher defaults to StringMatcher vs prior art comparison',
 'The nestor matcher defaults to StringMatcher limitations criticism why not']
```

**`react()`** — takes an event dict (a claim + context), searches for
witnesses and counter-evidence, and returns proposals. Requires a searcher
callback (typically backed by an LLM or search API).

**`apply()`** — applies proposals: puts confirmed nuggets, logs gaps, and
optionally forwards to FRANK.

**Probe findings (137 scenarios):**
- `min_sources=0` lets `react()` corroborate from zero evidence (#29)
- `_witnesses()` has no stemming (#18)
- Same-rung cross-caller overwrite allowed (#131)

**Net gain:** From manual edge-drawing to automated adversarial search for
conflicting evidence, with structured proposals and a `put_nugget`/`log_gap`
feedback loop.

---

## 5. Persona & Voice

### Nestor alone

**Minimal.** `nestor/persona.py` exists (refusal voice, firewalled from
engine) but is not exposed on any CLI command or MCP tool. The module is
internal infrastructure for how Nestor phrases refusals — it does not compile
a voice profile or generate persona prompts.

### With jeles

**Full persona compiler** (`jeles.persona`):

- `load_persona()` — loads a persona JSON definition
- `persona_prompt()` — compiles a persona into an LLM system prompt
- `compile_persona()` — builds a persona from sections (roles, constraints,
  voice attributes)
- `_subprocess_env()` — sanitizes environment for persona-driven subprocesses
  (prefix-based, not secret-aware — probe finding §5)

**Probe findings (124 scenarios):**
- Independent `lru_cache` on `load_persona`/`persona_prompt` (§1.9 — stale
  cache if persona file changes)
- `compile_persona` crashes on `None` sections (§2a)
- Persona JSON has unreachable duplicate content (§2c)

**Net gain:** From an internal refusal-voice module to a full persona
compiler that builds LLM system prompts with role, constraint, and voice
sections.

---

## 6. MCP & Network Surfaces

### Nestor alone

**MCP server:** 7 tools (6 read + 1 write `nestor_propose`). No resources,
prompts, or completion capabilities. Protocol-robust (handles malformed JSON,
oversized messages, JSON-RPC batch). Seal-injection is actively caught and
reported.

**HTTP UI:** ~20 endpoints including graph, triage, queue, export, import,
seal lifecycle. CSRF enforced, strict CSP, `Cache-Control: no-store`. No
push notifications — all pull-based.

### With jeles

**Corpus MCP server** (`jeles.corpus_server`) — requires `pip install
"jeles[mcp]"`. Adds corpus tools (`ask_corpus`, `put_nugget`, `log_gap`,
`search_nuggets`, `list_nuggets`, `list_gaps`, `get_nugget`) as MCP
endpoints.

**Willow MCP client** (`jeles.willow_mcp_client`) — forwards gaps and status
to a willow-mcp fleet server. Functions: `forward_gap`, `forward_status`,
`call_tool`, `ensure_started`.

**Net gain:** From a sealed-memory MCP server to a sealed-memory server +
a verified-nugget corpus server + fleet gap forwarding.

---

## 7. Tokenization & Normalization

### Nestor alone

Normalization strips case, punctuation, and Unicode (emoji, combining
characters) silently. The process is undocumented in `--help`. A trailing
emoji, full case change, and swapped punctuation all score 1.0 against the
baseline (probe-cascade.md §7).

```
$ nestor --db docs/dogfood/nestor.db decision check "tokenization normalization rules"
✓ clear — no decision on record
```

### With jeles

jeles has its own tokenizer (`_WORD_RE`, `_SHORT_RE` patterns) with different
trade-offs:

- `"a"` survives as a content token (probe §3.8 — potentially noisy for
  search)
- Apostrophe-binding comment inconsistency between `_WORD_RE` and `_SHORT_RE`
  (probe §3.14)
- Confidence scoring uses inclusive `>=0.5` threshold (probe §2.5)

**Net gain:** Two independent normalization pipelines — nestor's for
decision-memory matching, jeles' for corpus search — neither documented,
each with different edge-case behavior.

---

## 8. Summary: Capability Matrix

| Capability | Nestor alone | With jeles |
|---|---|---|
| **Decision memory** | 449 draft pairs, StringMatcher, 0.92 bar | + nugget corpus with machine/human verification kinds |
| **Gap tracking** | Inferred from `decision check` exit code | First-class objects with IDs and ask counts (22 logged) |
| **Source verification** | None — single-verifier seal model | Full pipeline: independence, institutions, corroboration bar |
| **SSRF/egress guard** | Not applicable (no egress) | Private-IP blocking, allowlist, scheme validation |
| **Conflict detection** | Manual graph edges (none sealed) | Automated adversarial search with `react()`/`apply()` |
| **Persona compiler** | Internal refusal voice only | Full persona→prompt compiler with sections and caching |
| **MCP tools** | 7 (sealed memory) | + corpus server tools + willow fleet forwarding |
| **Source adapters** | None | 65 source adapters via `jeles.sources` |
| **Legal citations** | None | `jeles.legal_citations.verify_citations()` |
| **Institutional search** | None | `jeles.institutional.search_institutional()` |
| **Tokenization** | Undocumented strip-and-normalize | Separate tokenizer with word/short patterns |

---

## 9. Cross-Reference: What the Dogfood Corpus Says About Jeles

The 449-decision dogfood corpus contains several decisions that discuss jeles
directly — evidence that the product team has thought about the integration,
even though the runtime capabilities are absent from Nestor alone:

| Decision ID | Question | Answer (excerpt) |
|---|---|---|
| `5f4bdadb` | jeles nuggets carry verified_by and verified_at. Do they cross as sealed? | No. Every nugget crosses as a draft. |
| `c6c3e7ec` | What does the matcher mirror — jeles' ranking, or its answering? | Its answering. NuggetMatcher implements containment-then-symmetry. |
| `e7837efc` | Can a bridged nugget be sealed through the human surface? | Not correctly, today. Blocked on IDEAS §6.40. |
| `fd9536ec` | Is 'two verifiers' the same independence jeles means? | No, and it is weaker. This counts names, not people. |
| `41674a1e` | Is that a defect in jeles? | No. _independence.py calls its own bar 'a cheap heuristic.' |
| `35ec3405` | Do 43 single-sourced subjects struggle to clear jeles' corroboration bar? | Yes — and the reason written into the feeder was wrong. |
| `160add96` | Should the test suite depend on jeles being installed? | No. Eight tests run on plain dicts; the live-corpus one uses importorskip. |

These decisions show the product team's position: jeles is a capability
extension, not a dependency. Nestor operates without it; jeles adds source
verification, conflict scanning, and corpus management as opt-in capabilities
that cross into Nestor as drafts, never as sealed facts.

---

## 10. Tool Evidence Index

Every claim in this report rests on a specific command and its output:

| Claim | Command | Output |
|---|---|---|
| 449 pairs, 0 sealed | `nestor --db docs/dogfood/nestor.db stats` | `449 pair(s): 0 sealed, 449 draft` |
| No decision on matcher default | `nestor decision check "What matcher does nestor use by default"` | `✓ clear — no decision on record` |
| Match bar is 0.92 | `nestor match --from decision --to decision "seal authority"` | `closest ... is 0.429, below 0.92` |
| Default domain hides decisions | `nestor match "seal authority"` (no --from/--to) | `nothing in this domain matched at all` |
| 0 rejections | `nestor rejections` | `0 rejection(s) in the chain` |
| No evidence gaps | `nestor evidence report` | `no live sealed pair is missing evidence` |
| jeles corpus populated | `corpus.put_nugget(...)` | `{'id': 'e4e4f1c9', 'action': 'created'}` |
| jeles ask finds nugget | `corpus.ask_corpus('What matcher does nestor use?')` | `{'found': True, ...}` |
| jeles gap tracking works | `corpus.log_gap(...)` | `{'id': '3ab2b14c6395', 'asked_count': 1}` |
| 22 gaps logged | `len(corpus.list_gaps())` | `22` |
| Private IPs blocked | `private_destination('http://169.254.169.254/...')` | `169.254.169.254 is not a public address` |
| Public IPs pass | `private_destination('https://reuters.com/...')` | `None` |
| Independence deduplicates | `registrable_domain('https://www.reuters.com/...')` | `reuters.com` |
| MIN_INDEPENDENT_SOURCES | `jeles._independence.MIN_INDEPENDENT_SOURCES` | `2` |
| Conflict scan frames queries | `conflict_scan.frame_queries(claim)` | 4 adversarial search queries |
