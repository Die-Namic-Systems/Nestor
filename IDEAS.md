# Ideas

A running list, kept in the repo so it outlives the conversation that produced
it. Nothing here is a commitment; several entries argue against each other.

Each entry carries a status, because the difference matters:

| Status | Means |
|--------|-------|
| **measured** | There are numbers in `bench/results/`, or a run reproduced in this repo |
| **verified** | The mechanism was demonstrated working, without a full measurement |
| **hypothesis** | Plausible, untested — do not cite as fact |
| **open** | A question, not yet a proposal |

---

## 1. Correctness — the seal that shouldn't have served

The thing that makes Nestor Nestor is that a tier-1 answer is served verbatim,
marked verified, with no review queue. So the failure mode that matters is a
phrase which was never verified being served as though it were. Everything in
this section is downstream of that.

### 1.1 Margin, not just magnitude — **hypothesis**

A false seal happens when many sealed rows resemble the probe about equally. In
that situation the *absolute* top similarity is a weak signal, but the **gap
between the best and second-best candidate** should be a strong one: a genuine
re-typing of a sealed phrase beats its runner-up decisively, whereas a phrase
that merely looks like the corpus sits in a crowd.

Proposal: serve tier 1 only when `top >= SEAL_THRESHOLD` **and**
`top - second >= MARGIN`, where the runner-up is the best candidate pointing at
a *different* target. Cheap — the scan already visits every row.

If it holds, it is the highest-value change on this list, because it attacks
false seals without giving up recall the way raising the threshold does.
`bench_accuracy.py` already records what is needed to test it.

### 1.2 Negative seals — **hypothesis**

Today a human can seal "this match is right." There is no way to record "this
match is *wrong*." So a bad fuzzy hit that a reviewer rejects will be served
again tomorrow, identically, forever. A `rejected` status consulted before
serving would make review a ratchet in both directions.

This is arguably a bigger gap than anything in the performance section: without
it, human attention leaks.

### 1.3 The threshold should be calibrated, not constant — **open**

`SEAL_THRESHOLD = 0.92` is a single global constant across every domain. But the
right cutoff plainly depends on corpus density and homogeneity — the same 0.92
behaves very differently on templated contract language than on diverse prose.
Options: per-domain thresholds; or a calibration mode that samples the corpus,
measures the absent-probe score distribution, and *recommends* a threshold for a
target false-seal rate.

The latter is also the honest marketing story (see §4.2): not "we are accurate,"
but "here is your false-verification rate, and here is the dial."

### 1.4 Seal staleness and quorum — **open**

Every seal is equally authoritative forever, and one verifier is enough. Neither
is obviously right for a regulated buyer. Worth considering: seal age surfaced
in provenance; a `weight` that decays; N-of-M verification for high-stakes
domains. The ledger already records who sealed what and when, so the data is
there — nothing consumes it.

---

## 2. Performance — the scan

**measured** (`fill.py`, session of 2026-07-25; to be folded into a bench):
lookup is linear in corpus size — 293 ms @ 2k pairs, 4.4 s @ 32k, projecting to
~135 s @ 1M. **97% of that is Python-side `difflib`, not SQL** (112 ms fetch vs
4,260 ms scoring at 32k). The database is not the bottleneck; the scoring loop is.

### 2.1 Lossless prefilter via difflib's own bounds — **measured**

`SequenceMatcher` exposes `real_quick_ratio()` (length-based) and
`quick_ratio()` (multiset-based) as progressively tighter upper bounds on
`ratio()`. Confirmed in-repo on 20,000 random pairs:
`ratio() <= quick_ratio() <= real_quick_ratio()`, no violations.

So candidates whose upper bound cannot beat the incumbent best can be skipped
**without computing `ratio()` at all, and without changing a single result.**
Implemented as `bench.bench_accuracy.best_match_fast` and measured against the
naive scan over 120 probes, **0 disagreements** on both corpora:

| Corpus | Rows | Naive | Pruned | Speedup |
|--------|------|-------|--------|---------|
| boilerplate | 3,000 | 39.1 s | 10.1 s | **3.9x** |
| prose | 2,991 | 52.6 s | 50.9 s | **1.0x** |

**The prose result is the interesting one.** Pruning only bites once a *high*
incumbent exists — on diverse prose the best score stays low (p50 ≈ 0.49), the
bound almost never falls below it, and nothing gets skipped. So as a general
speedup this is corpus-dependent and worth much less than it first looks.

**But `best_sealed` doesn't need the argmax — it needs "anything ≥ threshold."**
Seeding the incumbent at `SEAL_THRESHOLD` instead of `0.0` prunes hard on *both*
corpora, because now every candidate below 0.92 is skippable from the first row
rather than only after a good match turns up. That is the version worth
shipping, and it is still exactly lossless *for that call*. `lookup()` cannot
use it (it must return sub-threshold candidates as engine context), so this
wants to be a distinct fast path, not a change to the shared scan.

Two caveats found while implementing it, both easy to get wrong:

* **`ratio()` is not symmetric.** `StringMatcher` computes
  `SequenceMatcher(None, probe, row)`. Swapping the operands to let difflib
  cache its `b2j` index across candidates measures a different function.
* **`autojunk` changes results** on sequences of 200+ elements, so it must be
  left at the default.

Both would produce a plausible, slightly-wrong benchmark. The equivalence check
(`--equiv`) exists because of them.

Do this before anything lossy.

### 2.2 Trigram blocking — **measured, disappointing**

A 4-gram prefilter gave only **2.4x** (4,372 ms → 1,818 ms) because 43% of
candidates survived it. That number is from the homogeneous boilerplate corpus,
which is the worst case for blocking — on diverse prose it should do far better,
and that is worth measuring before judging the idea. Lossy, unlike §2.1.

### 2.3 Index `source_norm` — **measured**

`memory_find` runs on every `add_pair` and there is no index on `source_norm`
(only `(source_lang, target_lang, status)`). Adding one cut ingest from
~10.1 s/1k to ~4.5 s/1k at 32k rows — **2.3x**, one line of DDL.

### 2.4 Connection-per-operation — **open**

`SqliteStore._db()` opens and closes a fresh connection for every call on
file-backed databases, and `add_pair` additionally calls `memory_init()`, which
replays the whole schema script each time. I hypothesised this dominated ingest
and **was wrong** — stubbing `memory_init` out made things marginally *slower*,
i.e. it is noise at this scale. Recorded here so nobody re-derives the same dead
end. The connection churn may still matter under concurrency; unmeasured.

---

## 3. The Matcher seam

### 3.1 The seam is lossy by construction — **verified**

`normalize(value) -> str` is the *only* channel between a raw input and
`similarity(a_norm, b_norm)`. Scoring never sees the originals. I lost an
acronym match (`AWS` → `Amazon Web Services`) purely because my normalizer
sorted its tokens, and the information needed to recover it no longer existed by
scoring time.

Worse, that same string is simultaneously the store's exact-match dedup key in
`memory_find`. Scoring wants rich structure; deduplication wants aggressive
collapse. **These two jobs pull in opposite directions, and one string serves
both.**

Proposal: an optional second method — `score(raw_a, raw_b)` — that the memory
prefers when present, leaving `normalize` free to be a pure dedup key. This is
the change that unblocks embedding/semantic matchers, which currently cannot be
expressed without smuggling a vector through a SQL key.

### 3.2 Recipes the seam already supports — **verified**

Written from outside the package, with **zero changes to `nestor/`**:

- **`DateMatcher`** — normalizes `Q3 2025`, `September 30, 2025` and
  `30/09/2025` to one ordinal; scores by day-window tolerance. A temporal
  alignment engine with sealed provenance, for ~30 lines.
- **Schema mapping** — messy CSV headers → canonical field names, using
  `EntityResolver` **unchanged**, just with a token matcher. `'TOTAL DUE'` →
  `amount_due` at 1.0; `'Name of Customer'` correctly queued for review at 0.667.

The README advertises three recipes. The seam supports a category. That gap is a
positioning problem more than an engineering one (§4.1).

### 3.3 Semantic matcher — **open**

Blocked on §3.1. Would fix the acronym/synonym class of misses outright. Cost:
the first real dependency in a currently zero-dependency package — which is a
genuine selling point to the regulated buyer, so this should probably live as an
optional extra, never core.

---

## 4. Positioning

### 4.1 Lead with the mechanic, not translation — **open**

The README opens with translation and reaches the general mechanic four sections
down. Everything I found suggests the general mechanic *is* the product and
translation is the origin story. Restructure so the first screen is
seal → serve → audit, with translation as one recipe among several.

### 4.2 The category is AI verification, not translation memory — **open**

Tier 2 is an AI draft explicitly queued for review; tier 3 is a human sealing it;
tier 1 is that seal served forever — all in a tamper-evident chain. That is a
direct answer to "which model outputs did a human actually check," which nobody
has solved and every regulated buyer is being asked.

The economic shape is the strong part: each human verification is **permanent
capital**. Cost per answer falls as trust rises — an unusual curve worth leading
with. Candidate line: *"Verified once. Served forever."*

Where it wins: high-value, low-volume decisions — contracts, clinical notes,
regulatory filings. Where it loses: high-volume chat, per §2 numbers. Don't
pitch into the second; the demo would lose.

### 4.3 The 60-second demo — **open**

Highest-leverage missing artifact. An AI gets something wrong; a human corrects
it **once**; it is right forever after, with a receipt that cannot be forged.
Then tamper with the ledger and watch the chain refuse. That is the entire
product in one loop, and it lands on an engineer and a compliance officer for
different reasons.

Blocked on §5.1 — there is currently nothing to run.

### 4.4 The bench is a marketing asset — **open**

"We are accurate" is a claim a compliance buyer knows is a lie. "Here is our
measured false-verification rate, here is the dial that sets it, here is the
harness — run it yourself" is stronger *because* it admits a failure rate.
Publishing `bench/results/` is a differentiator, not an exposure.

---

## 5. Missing surface

### 5.1 There is no CLI — **verified**

No `console_scripts`, no entry point, nothing to run without writing Python.
`nestor seal / resolve / check / ledger verify` would cost little and is the
prerequisite for §4.3.

### 5.2 The memory is write-only — **verified**

`Storage` has no `memory_list`, `memory_unseal`, `memory_delete` or
`memory_export`. You can seal a pair but never browse, correct, revoke or export
one. For a system whose entire value proposition is human verification, the
human has no way to see what they have verified. Pairs with §1.2.

### 5.3 Ledger verification is once per process — **verified**

`cascade._verified_ledgers` caches by path, so the chain is checked on first
append and never again. I watched an append succeed after mid-run tampering. The
cache is a deliberate cost trade, but a long-lived process will not notice
tampering that happens while it runs. Options: periodic re-verification, verify
the tail only, or make the cache TTL'd. Related: `verify()` cost grows linearly
with ledger length, so checkpointing may be needed before re-verification is
affordable.
