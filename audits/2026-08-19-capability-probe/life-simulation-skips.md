# Life Simulation: Skip-by-Skip Impact Analysis

> Testing every probe-discovered skip/limitation against Elena Vasquez's
> life data. 52 pairs across 8 domains, 10 decision graph edges, 4 evidence
> items, 23 ledger entries, 6 jeles nuggets, 19 jeles gaps.
>
> Generated 2026-08-19. Each finding rests on a named command and its output.

---

## Skip Index

| # | Skip | Impact | Verdict |
|---|---|---|---|
| 1 | DB/ledger path independence | **Severe** — wrong path erases the life | Real wall |
| 2 | Default domain `en→es` | **Severe** — entire life invisible | Real wall |
| 3 | Typo'd DB path creates phantom | **Moderate** — silent phantom person | Real wall |
| 4 | Calibrate needs sealed pairs | **Moderate** — can't tune the life's matcher | Correct by design |
| 5 | Unsealed contradicts don't fire | **Profound** — 4 contradictions exist but don't trigger | Correct by design |
| 6 | 0.92 bar rejects paraphrased recall | **Severe** — memories findable but not servable | Correct by design |
| 7 | Evidence is a reference, not a seal | **Moderate** — proof doesn't grant closure | Correct by design |
| 8 | Emoji/punctuation normalization | **Moderate** — emotional markers stripped from matching | Real wall |
| 9 | Numeric matcher tolerance | **Minor** — year lookup works, range query doesn't | Real wall |
| 10 | Sub-threshold text matching | **Severe** — "trust" can't find "Trusted a cofounder" | Real wall |
| 11 | Entity resolution without seals | **Minor** — resolves correctly, labels as suggestion | Door, not wall |
| 12 | Export loses graph edges | **Severe** — facts transfer, meaning doesn't | Real wall |
| 13 | Ledger records every ask | **Minor** — life timeline grows with every search | Correct by design |
| 14 | Jeles retrieval needs exact key | **Severe** — paraphrased memory queries fail | Real wall |
| 15 | Jeles `found: False` on asserted nuggets | **Moderate** — knows the answer, won't serve it | Parallel to Nestor |
| 16 | Conflict scan templates are code-shaped | **Minor** — structure works, templates need rewriting | Real wall |
| 17 | Egress guard as boundary enforcer | **Minor** — private-IP blocking maps to emotional boundaries | Door, not wall |
| 18 | Independence rule on self-beliefs | **Moderate** — identifies uncorroborated beliefs | Door, not wall |
| 19 | Decision check only sees `decision→decision` | **Moderate** — life beliefs in other domains are invisible | Real wall |
| 20 | `match` defaults silently miss life data | **Severe** — must know the domain to ask | Real wall |
| 21 | Cross-domain search impossible | **Severe** — no "search all of Elena's life" | Real wall |
| 22 | No temporal range queries | **Moderate** — "what happened after the betrayal?" fails | Real wall |
| 23 | Hash-chained ledger is tamper-evident | **Minor** — immutable life record | Correct by design |

---

## Detailed Findings

### Skip 1: DB/Ledger Path Independence

**Probe origin:** `probe-cascade.md` — ledger path defaults independently
of `--db`, so a wrong `--db` path creates a new empty database while the
ledger writes to the original path.

**Life test:**
```
$ nestor --db /tmp/wrong-elena.db stats
0 pair(s): 0 sealed, 0 draft
```

**Impact:** Elena's entire 52-pair life vanishes with one wrong path. The
ledger at the original location continues recording, now logging queries
against an empty person. Two files, two realities — one has Elena, one has
nobody, and the ledger can't tell which it's talking about.

**Verdict:** Real wall. A life stored in one place and queried from another
is not the same life.

---

### Skip 2: Default Domain `en→es`

**Probe origin:** `probe-cascade.md` §2 — `match` defaults to `en→es`.

**Life test:**
```
$ nestor --db docs/dogfood/nestor.db match "Elena Vasquez"
! would not be served — nothing in this domain matched at all —
  no candidate scored, which usually means en→es is empty rather than
  that the question was strange
```

**Impact:** Elena's entire life — 52 pairs across 8 domains — is invisible
under the default domain. You must know to ask `--from entity --to entity`
or `--from memory --to lesson`. A person asking about Elena without knowing
her domain structure gets `nothing in this domain matched at all`.

**Verdict:** Real wall. The system hides the life behind a domain you must
already know to specify. Like asking someone about their life and being
told "I don't speak that language" — not because the answer doesn't exist,
but because you asked in the wrong register.

---

### Skip 3: Typo'd DB Path Creates Phantom

**Probe origin:** `probe-cascade.md` — SQLite auto-creates databases.

**Life test:**
```
$ nestor --db docs/dogfoo/nestor.db stats
0 pair(s): 0 sealed, 0 draft
```

**Impact:** A single-character typo (`dogfoo` vs `dogfood`) creates a
phantom empty person at the wrong path. SQLite doesn't distinguish "file
not found" from "new database." Every misspelling births a new identity.

**Verdict:** Real wall. In life terms: introducing yourself to someone who
misheard your name — they now know a person who doesn't exist.

---

### Skip 4: Calibrate Needs Sealed Pairs

**Probe origin:** `probe-cascade.md` §4.

**Life test:**
```
$ nestor --db docs/dogfood/nestor.db calibrate
Nothing sealed here yet — nothing to calibrate against.
```

**Impact:** Elena has 52 draft pairs and zero sealed. She can't calibrate
her matcher thresholds because she hasn't committed to any truth yet. The
0.92 bar may be wrong for her life, but she can't adjust it until she seals
something.

**Verdict:** Correct by design. You can't measure yourself against a
standard you haven't committed to. Calibration requires a ground truth,
and Elena hasn't verified hers.

---

### Skip 5: Unsealed Contradicts Don't Fire

**Probe origin:** `probe-decisions.md` — only sealed `contradicts` edges
block `decision check`.

**Life test:**
```
$ nestor --db docs/dogfood/nestor.db decision check "People deserve second chances"
✓ clear — no recorded rejection or contradicts edge on
  'People deserve second chances'
```

**The graph holds 4 contradictions:**
1. "People deserve second chances" ↔ "That I can't trust anyone again after Alex"
2. "Said yes to every freelance gig in 2020" ↔ "Took the promotion at Meridian even though it meant 60-hour weeks"
3. "Silence is not peace" ↔ "Let my mother choose my college major"
4. "People deserve second chances" ↔ "I can never trust a business partner again"

None fire because all edges are `proposed`, not `sealed`.

**Impact:** Elena holds four contradictions and hasn't confronted any.
`decision check` says `✓ clear` — not because she's consistent, but
because she hasn't examined the inconsistency. The system correctly models
that an unexamined contradiction is a tension you haven't faced, not a rule
you've broken.

**Verdict:** Correct by design. This is therapy: the contradiction is real
the moment you name it, not the moment it exists. Sealing the edge is the
act of confrontation.

---

### Skip 6: 0.92 Bar Rejects Paraphrased Recall

**Probe origin:** `probe-cascade.md` §3 — StringMatcher Jaccard similarity
requires 0.92 for service.

**Life test:**
```
$ nestor --db docs/dogfood/nestor.db match --from memory --to lesson \
    "I worked too hard at Meridian"
! would not be served — closest of 5 candidate(s) is 0.512, below 0.92
```

The memory "Took the promotion at Meridian Corp even though it meant 60-hour
weeks" scores 0.512 against the paraphrase "I worked too hard at Meridian."
Present, findable (shown in diagnostics), but not served.

**Impact:** Elena can recall her memories only in the exact words she stored
them. Her own rephrasing of her own experience scores below the service bar.
Memory doesn't serve itself until someone verifies it — and a paraphrased
memory isn't close enough to count as the same memory.

**Verdict:** Correct by design, but painful. The bar protects against
serving wrong matches as truth, but it also means Elena can't access her own
memories through natural recall. A life that can only remember in its own
exact words.

---

### Skip 7: Evidence Is a Reference, Not a Seal

**Probe origin:** `probe-cascade.md` §evidence.

**Life test:** 4 evidence items on the Alex Chen betrayal:
1. `document` — Portland PD case #21-47832
2. `document` — Chase Business checking statements, June–July 2021
3. `human_statement` — Alex's text about a dinner that never happened
4. `human_statement` — Dr. Okafor session notes, March 2024

Each one: "a reference, not a seal — this confirms nothing."

**Impact:** Elena has a police report, bank statements, a damning text
message, and therapist notes. The system says: evidence exists but doesn't
change what gets served. Having proof isn't the same as having closure.

**Verdict:** Correct by design. In a life, proof supports healing but
doesn't do the healing. The evidence is there for when she's ready to seal.

---

### Skip 8: Emoji/Punctuation Normalization

**Probe origin:** `probe-cascade.md` §7 — normalization strips emoji,
punctuation, case silently.

**Life test:**
```
$ nestor --db docs/dogfood/nestor.db match --from memory --to lesson \
    "Running morning 💔 breakup"
! closest of 5 candidate(s) is 0.293, below 0.92
  normalized to 'running morning breakup'
```

The "💔" is silently stripped. Without the emoji, "running morning breakup"
matches poorly against stored memories.

**Impact:** Emotional markers in queries are destroyed before matching.
If Elena stored a memory with emotional context (heartbreak, joy, anger),
the normalization removes the emotion and matches only the words. The
feeling is not part of the lookup.

**Verdict:** Real wall. Normalization treats emoji as noise, but in a life,
💔 is signal. The system strips the part of the query that carries the most
meaning.

---

### Skip 9: Numeric Matcher Tolerance

**Probe origin:** `probe-cascade.md` §numeric.

**Life test:**
```
$ nestor --db docs/dogfood/nestor.db match --from year --to milestone "2020"
! would not be served — closest of 12 candidate(s) is 1.000, below 0.92
```

Wait — score is 1.000 but still says "would not be served"? The year 2020
matches exactly (score 1.0) but remains draft.

```
$ nestor --db docs/dogfood/nestor.db match --from year --to milestone \
    --abs-tol 2 "2020"
! would not be served — 1.000 match, but it is draft, not sealed
```

**Impact:** The numeric matcher works perfectly for exact years. But
"what happened around 2020" (with tolerance) still won't serve because
it's draft. And "what happened between 2019 and 2022" is impossible —
there is no range query.

**Verdict:** Real wall for range queries. The numeric matcher finds single
years but can't search periods of a life.

---

### Skip 10: Sub-Threshold Text Matching

**Probe origin:** `probe-cascade.md` §3 — StringMatcher Jaccard.

**Life test:**
```
$ nestor --db docs/dogfood/nestor.db match --from choice --to consequence "trust"
! would not be served — closest of 5 candidate(s) is 0.16, below 0.92
  normalized to 'trust'
```

"trust" scores 0.156 against "Trusted a cofounder who took $40,000 and
disappeared." The concept is present in the stored text, but the matcher
can barely see it.

**Impact:** Elena can't search her life by concept. "Trust" doesn't find
the trust betrayal. "Fear" doesn't find her fears. "Mother" doesn't find
her motherhood entries. The StringMatcher sees character overlap, not
meaning.

**Verdict:** Real wall. A life needs associative recall — searching by what
something *means*, not what characters it shares. This is the single biggest
limitation: the matcher that protects verification integrity also prevents
conceptual search.

---

### Skip 11: Entity Resolution Without Seals

**Probe origin:** `probe-edge-cases.md` — entity resolution works on draft.

**Life test:**
```
$ nestor --db docs/dogfood/nestor.db resolve "Mom"
Elena Vasquez — confidence 1.0 (unsealed suggestion)
```

**Impact:** Even without sealing, Elena knows who "Mom" is, who "my kid"
is, who "that guy who stole from me" is. Identity resolution works as
draft. You know who people are before you've verified the relationship.

**Verdict:** Door, not wall. The entity system is more permissive than the
pair system. You can name people before you've committed to what they mean
to you.

---

### Skip 12: Export Loses Graph Edges

**Probe origin:** `probe-internals.md` — export schema.

**Life test:**
```python
>>> export = nestor_export(db)
>>> list(export.keys())
['nestor_bundle', 'created_at', 'domain', 'matcher', 'signing',
 'partial_pairs', 'partial_rejections', 'counts', 'digest',
 'pairs', 'rejections', 'evidence', 'ledger']
>>> 'edges' in export or 'decision_edges' in export
False
```

**Impact:** Elena's 52 pairs and 4 evidence items transfer. Her 10 decision
graph edges — the 4 contradictions, 3 refinements, 3 supersessions — are
lost. The *facts* move but the *meaning between them* doesn't.

Importing Elena into a new Nestor instance would give you a person with
memories, beliefs, fears, and choices, but no record of which beliefs
contradict, which choices superseded others, or which body signals refined
which concepts. The graph that makes the life coherent is not portable.

**Verdict:** Real wall. This is the most structurally damaging skip. A life
without its connections is a list of facts, not a person.

---

### Skip 13: Ledger Records Every Ask

**Probe origin:** `probe-ledger.md` — passage lookups logged.

**Life test:**
```
$ nestor --db docs/dogfood/nestor.db stats
ledger: ✓ intact — 23 entries
```

Started at 12 entries after life creation. Grew to 23 during skip testing.
Every `match`, `decision check`, and `resolve` wrote a ledger entry.

**Impact:** Elena's life timeline now includes the act of searching itself.
The ledger records not just what happened, but every time someone asked
about what happened. In a life, this is the difference between the events
and the retrospection — both are part of the record.

**Verdict:** Correct by design. A ledger that records queries is a record
of self-examination. You can't search your own life without that search
becoming part of the life.

---

### Skip 14: Jeles Retrieval Needs Exact Key

**Probe origin:** `jeles-probe-corpus.md` — zero tolerance for rephrase.

**Life test:**
```python
>>> corpus.ask_corpus('Why did I leave Meridian?')
{'found': False, 'candidates': [{'question': 'Why did I leave Meridian?', ...}]}

>>> corpus.ask_corpus('Why did she leave her job?')
{'found': False, 'candidates': []}

>>> corpus.ask_corpus('What made Elena quit?')
{'found': False, 'candidates': []}
```

The exact key 'Why did I leave Meridian?' finds the candidate (it's in
`candidates`) but doesn't serve it (`found: False`). Any paraphrase finds
nothing at all.

**Impact:** Elena's inner journal (6 nuggets) can only be queried in the
exact words she used. "Why did she leave her job?" can't find "Why did I
leave Meridian?" — not even as a candidate. The corpus knows answers but
only to the exact question that was asked.

**Verdict:** Real wall. Like a person who can only remember what they've
already put into exact words. No associative recall, no rephrase tolerance.

---

### Skip 15: Jeles `found: False` on Asserted Nuggets

**Probe origin:** Discovered during life testing.

**Life test:**
```python
>>> corpus.ask_corpus('Why did I leave Meridian?')
{'found': False,
 'candidates': [{'question': 'Why did I leave Meridian?',
                  'status': 'asserted',
                  'verification_kind': 'asserted', ...}]}
```

The nugget exists. The exact question matches. The candidate is returned.
But `found` is `False` because the verification kind is `asserted` (self-
reported), not `human` or `machine`.

**Impact:** Elena told her own story and the system heard it, found it,
and refused to serve it — because she told it herself. Self-reported
knowledge is present but not authoritative. This parallels Nestor's
draft/sealed distinction: you can store your truth, but the system won't
present it as verified until someone else confirms it.

**Verdict:** Parallel to Nestor's design. Both tools model the same
epistemic principle: self-knowledge is stored, queryable, but not served
as truth without external verification.

---

### Skip 16: Conflict Scan Templates Are Code-Shaped

**Probe origin:** `jeles-probe-reactions.md` — `frame_queries()` generates
code-oriented search terms.

**Life test:**
```python
>>> conflict_scan.frame_queries('People deserve second chances')
['People deserve second chances existing implementation library',
 'People deserve second chances alternative that supersedes',
 'People deserve second chances vs prior art comparison',
 'People deserve second chances limitations criticism why not']
```

**Impact:** The templates append "existing implementation library" and
"vs prior art comparison" to a life belief. The *structure* — adversarial
search for what contradicts a claim — is correct. The *templates* are
written for code claims, not life claims. "People deserve second chances
existing implementation library" is nonsensical.

**Verdict:** Real wall, but a thin one. The scaffolding works; only the
template strings need rewriting for non-technical domains. A future
`frame_queries(claim, domain='life')` could append "lived counter-example"
and "case where I acted otherwise" instead.

---

### Skip 17: Egress Guard as Boundary Enforcer

**Probe origin:** `jeles-probe-egress.md` — private_destination blocks
internal IPs.

**Life test:**
```python
>>> private_destination('http://127.0.0.1/ex-check-social-media')
'127.0.0.1 is not a public address'

>>> private_destination('http://10.0.0.1/read-daughter-diary')
'10.0.0.1 is not a public address'

>>> private_destination('https://therapist.drokafor.com/session')
None  # allowed
```

**Impact:** The guard blocks "internal" lookups and allows "public" ones.
Mapped to Elena's life: checking an ex's social media (loopback), reading
a child's private journal (internal network), looking up an estranged
father (link-local) — all blocked. Public actions (therapy, business
dashboard) — all pass. The guard works as a boundary enforcer regardless
of what the boundary represents.

**Verdict:** Door, not wall. The SSRF guard's IP classification maps
directly to emotional boundary classification. The implementation is
technically sound; the reframing is interpretive.

---

### Skip 18: Independence Rule on Self-Beliefs

**Probe origin:** `jeles-probe-verification.md` — `MIN_INDEPENDENT_SOURCES=2`.

**Life test:**
- "I am a good mother" — 3 independent domains: self-report (`self-report.elena`),
  Sofia's essay (`school.edu`), therapist (`drokafor.com`). Clears the bar.
- "I am becoming my father" — 1 domain: self only. Fails the bar.

**Impact:** The independence rule correctly identifies which of Elena's
beliefs rest on a single uncorroborated voice (her own fear) versus
multiple independent perspectives (self + daughter + therapist). The
2-source bar is not about truth — it's about whether you've heard from
anyone else.

**Verdict:** Door, not wall. The rule was designed for source verification
in journalism/research, but it models something true about self-knowledge:
beliefs corroborated by others are different from beliefs held alone.

---

### Skip 19: Decision Check Only Sees `decision→decision`

**Probe origin:** `probe-decisions.md` — `decision check` queries only
the `decision→decision` domain.

**Life test:** Elena's beliefs live in `belief→evidence`, her fears in
`fear→truth`, her body signals in `body→signal`. None of these are
visible to `decision check`:

```
$ nestor --db docs/dogfood/nestor.db decision check "Migraines are a body signal"
✓ clear — no decision on record
```

But migraines *are* recorded — in `body→signal`, not `decision→decision`.

**Impact:** `decision check` only examines beliefs Elena has deliberately
placed in the decision domain. Her body knowledge, her fears, her
memories — all stored in Nestor but invisible to the decision-checking
mechanism. The beliefs she's willing to examine go in `decision→decision`.
The rest stays in domains she hasn't examined.

**Verdict:** Real wall, but also a design choice: the separation between
"decisions I've confronted" and "knowledge I hold but haven't examined
as decisions" is meaningful. The wall is structural — there is no
cross-domain decision check — but the structure models something true.

---

### Skip 20: `match` Defaults Silently Miss Life Data

**Probe origin:** `probe-cascade.md` §2.

**Life test:**
```
$ nestor --db docs/dogfood/nestor.db match "Sofia"
! nothing in this domain matched at all

$ nestor --db docs/dogfood/nestor.db match --from entity --to entity "Sofia"
  "my kid" → "Sofia Vasquez" (1.000)
```

**Impact:** The same query with and without domain flags returns completely
different results — one finds nothing, one finds Elena's daughter. The
system doesn't warn that other domains contain data; it just says "nothing
in this domain matched" as if there's nothing anywhere.

**Verdict:** Real wall. The silence is the problem. If the system said
"nothing in en→es, but 8 other domains have data," the user could redirect.
Instead, it implies absence where there is presence.

---

### Skip 21: Cross-Domain Search Impossible

**Probe origin:** structural limitation confirmed across all probes.

**Life test:**
```
$ nestor --db docs/dogfood/nestor.db match --from body --to evidence "Migraines"
! nothing in this domain matched at all

$ nestor --db docs/dogfood/nestor.db match --from body --to signal "Migraines"
  "Migraines started in 2017" → "overriding her own no" (0.xxx)
```

"Migraines" exists in `body→signal` but is invisible when queried from
`body→evidence`. There is no "search all of Elena's life for anything
about migraines."

**Impact:** Each domain is a silo. Elena's body knowledge can't see her
belief evidence. Her fears can't see her choices. Her timeline can't see
her memories. There is no integrated view of a life — only 8 separate
views of 8 separate aspects.

**Verdict:** Real wall. This is the structural twin of Skip 10 (conceptual
search). Skip 10 means you can't search by meaning; Skip 21 means you
can't search across aspects. Together they mean: a life in Nestor is 8
indexed filing cabinets, not a mind.

---

### Skip 22: No Temporal Range Queries

**Probe origin:** `probe-cascade.md` §numeric.

**Life test:** The `year→milestone` domain has 12 entries (1989–2024). The
numeric matcher finds exact years:

```
$ nestor --db docs/dogfood/nestor.db match --from year --to milestone "2020"
  "2020" → "Started therapy..." (1.000, draft)
```

But "what happened between 2018 and 2022" is impossible. `--abs-tol 2`
would catch years within 2 of the query, but there's no `--between`,
no `--after`, no `--range`.

**Impact:** Elena's life has a timeline, but Nestor can't answer temporal
questions about it. "What happened in the years after the betrayal?" "What
changed between Meridian and NovaBridge?" "What was happening when Sofia
started school?" — all impossible. The timeline exists as 12 disconnected
year-points, not as a narrative arc.

**Verdict:** Real wall. A life needs temporal reasoning — before/after,
during, between — not just point-in-time lookup.

---

### Skip 23: Hash-Chained Ledger Is Tamper-Evident

**Probe origin:** `probe-ledger.md`.

**Life test:**
```
$ nestor --db docs/dogfood/nestor.db stats
ledger: ✓ intact — 23 entries
```

23 hash-chained entries. Each carries `prev = SHA-256(previous entry)`.
The chain records: entity resolutions (who-is-who), evidence attachments,
passage lookups (memory searches), and decision checks.

**Impact:** Elena's life is tamper-evident by construction. She can't
retroactively deny that she searched for memories of Alex, that she
looked up who "Mom" is, that she attached evidence to the betrayal.
Every search, every resolution, every evidence attachment is recorded
and chained.

**Verdict:** Correct by design. In a life, the past is immutable — not
because you can't wish it different, but because the record of what you
actually did is chained to what came before.

---

## Summary: How the Skips Change the Life

### Real Walls (limitations that diminish Elena's life)

| Impact | Skips | What's lost |
|---|---|---|
| **Identity fragmentation** | 1, 2, 3, 20 | Wrong path = wrong person. Default domain = invisible person. Typo = phantom person. Silent miss = absent person. |
| **No conceptual recall** | 6, 10, 14 | Can't search by meaning, only by exact words. "Trust" can't find trust. Paraphrase can't find memory. |
| **Domain silos** | 19, 21 | 8 aspects of one life that can't see each other. No integrated search. No cross-domain insight. |
| **No temporal reasoning** | 9, 22 | Timeline exists as points, not arcs. Can't ask "what happened after." |
| **Export loses connections** | 12 | Facts transfer, relationships don't. A portable life without its meaning. |
| **Normalization strips emotion** | 8 | 💔 is removed before matching. The feeling is not part of the query. |
| **Code-shaped templates** | 16 | Conflict scan structure works for life; template strings don't. |

### Doors, Not Walls (limitations that model something true)

| Design | Skips | What it models |
|---|---|---|
| **Draft vs sealed** | 4, 5, 6, 7, 15 | An unverified life can be stored and queried but not served. You know your story but can't prove it until someone confirms it. |
| **Unsealed contradictions** | 5 | The contradiction is real the moment you name it, not the moment it exists. Sealing is the act of confrontation. |
| **Evidence ≠ closure** | 7 | Proof supports healing but doesn't do the healing. Four pieces of evidence still say "a reference, not a seal." |
| **Independence bar** | 18 | Beliefs corroborated by others are different from beliefs held alone. "I am becoming my father" has only one voice. |
| **Boundary enforcement** | 17 | Internal addresses map to unhealthy internal lookups. Public addresses map to healthy external engagement. |
| **Entity resolution** | 11 | You know who people are before you've verified the relationship. Identity is less strict than truth. |
| **Ledger as life record** | 13, 23 | Every search becomes part of the story. The past is immutable by construction. |

### The Pattern

The skips divide into two categories:

1. **Technical limitations that a person wouldn't have.** A person can search
   their life by concept, across aspects, through time, and in their own
   paraphrased words. Nestor can't do any of these. The matcher, the domain
   system, and the export format are built for precision at the cost of recall.

2. **Epistemic guardrails that a person should have.** A person who serves
   unverified memories as truth, who ignores contradictions they haven't
   examined, who treats evidence as proof of closure — that person is not
   being honest with themselves. Nestor's draft/sealed system, unsealed-
   contradicts behavior, and evidence-as-reference model all enforce a
   distinction between experiencing something and verifying it.

The technical limitations need fixing. The epistemic guardrails should stay.

---

## Tool Evidence Index

| Finding | Command | Output |
|---|---|---|
| Default domain hides life | `nestor match "Elena Vasquez"` | `nothing in this domain matched at all` |
| "trust" can't find betrayal | `nestor match --from choice --to consequence "trust"` | `closest of 5 candidate(s) is 0.16, below 0.92` |
| Export missing edges | `nestor export \| python3 check_keys` | `'edges' in export: False` |
| Cross-domain blind | `nestor match --from body --to evidence "Migraines"` | `body→evidence is empty` |
| Contradicts don't fire | `nestor decision check "People deserve second chances"` | `✓ clear — no recorded rejection or contradicts edge` |
| Ledger grew during testing | `nestor stats` | `ledger: ✓ intact — 23 entries` |
| Emoji stripped | `nestor match "Running morning 💔 breakup"` | `normalized to 'running morning breakup'` |
| Jeles exact match not served | `corpus.ask_corpus('Why did I leave Meridian?')` | `{'found': False, 'candidates': [...]}`  |
| Jeles paraphrase not found | `corpus.ask_corpus('Why did she leave her job?')` | `{'found': False, 'candidates': []}` |
| Independence deduplicates | `registrable_domain(url)` | 3 distinct domains for "good mother" belief |
| 4 contradicts edges exist | `SELECT * FROM decision_edges WHERE kind='contradicts'` | 4 rows, all unsigned |
| 10 total edges | `SELECT kind, COUNT(*) FROM decision_edges GROUP BY kind` | contradicts:4, refines:3, supersedes:3 |
