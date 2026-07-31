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

### 1.1 Margin, not just magnitude — **measured; mostly falsified**

*The hypothesis was: a false seal happens when many sealed rows resemble the
probe about equally, so the gap between best and second-best should separate a
genuine match from a coincidental one — attacking false seals without the recall
cost of raising the threshold. I called it the highest-value change on this list.
It is not.*

`bench_margin.py`, threshold 0.92, false-seal % / recall %
(`bench/results/margin.json`):

| margin | boil 2k | boil 8k | boil 24k | prose 2k | prose 4k |
|-------:|--------:|--------:|---------:|---------:|---------:|
| 0.00 | 1.6 / 100 | 8.0 / 100 | 16.0 / 100 | 4.8 / 99.6 | 6.8 / 100 |
| 0.03 | 1.6 / 100 | 6.0 / 100 | 10.0 / 99.2 | 4.4 / 99.2 | 6.4 / 98.0 |
| 0.05 | 1.6 / 99.6 | 3.2 / 98.4 | **4.0 / 96.8** | 4.4 / 96.8 | 6.0 / 93.6 |
| 0.10 | 0.0 / 91.2 | 0.4 / 70.8 | 0.0 / **44.4** | 3.6 / 91.6 | 5.2 / 88.4 |

**On homogeneous text it half-works.** Boilerplate 24k at margin 0.05 cuts false
seals 16.0% → 4.0% for 3.2 points of recall. Real, but not free, and nowhere near
the clean separation the hypothesis predicted — pushing to 0.10 eliminates false
seals and destroys recall (44%).

**On prose it does nothing but cost recall.** 6.8% → 6.0% at margin 0.05 while
recall falls 100% → 93.6%. Strictly worse than simply raising the threshold.

The distributions overlap, which is the real verdict. Gap between true-match p10
and false-seal p90 — positive means separable:

| | boil 2k | boil 8k | boil 24k | prose 2k | prose 4k |
|---|---:|---:|---:|---:|---:|
| gap | +0.018 | −0.001 | +0.012 | −0.050 | −0.103 |

**Why it fails, which is the part worth keeping.** The hypothesis assumed false
seals arise from *crowding* — many near-equal candidates. That is true only in
templated corpora. In prose a false seal comes from a **genuine near-duplicate**:
one sentence that really is nearly identical to the probe, with nothing else
close. So the margin is *wide* precisely when the answer is wrong, and the signal
inverts. Crowding is an artifact of homogeneous text, not a property of false
seals.

Not worth shipping as a global rule. Possibly worth it as a per-domain option for
templated corpora, where it beats raising the threshold — but §1.3's calibration
work should decide that, not this idea on its own.

Caveat on the recall column here: `bench_margin.py` still uses the **surface**
perturbations, where most probes score exactly 1.0, so its margin is
`1.0 − second` and the recall cliff at 0.10 is partly an artifact of how close
the rest of the corpus sits to an exact match. Re-running it against the
paraphrase tier would only make the verdict more negative — paraphrase probes
score lower, so their margins are narrower — so it was not worth re-running to
overturn a conclusion that is already "no". The false-seal column never depended
on the perturbation set.

**What the failures actually look like, and why no scalar rule catches them.**
Every worst-case collision differs from the phrase it was served *only in the
identifier*:

```
asked : the joint term triggers any joint breach under section 5386
served: the joint term triggers any joint breach under section 756    sim=0.974
```

A character-ratio matcher is blind to *which* characters carry the meaning. 0.974
clears any cutoff that preserves recall, and the margin measurements above show
the runner-up gap does not reliably collapse either. So neither threshold nor
margin — the two knobs available on top of a scalar similarity — can separate
these. The fix has to change what is being *compared*: weight identifier-like
tokens, or go semantic (§3.1/§3.3).

### 1.2 Negative seals — **shipped**

*Was: a human could seal "this match is right" but never record "this match is
wrong," so a bad fuzzy hit came back identically forever and human attention
leaked out of the system.*

Implemented as two distinct refusals, because collapsing them would have been a
bug:

* **`reject_pair(pair_id, …)`** — the mapping itself is wrong. Sets
  `status='rejected'`; never served, never offered as engine context again.
* **`reject_match(source_text, …, pair_id=/target_text=)`** — *this pair is the
  wrong answer for this query*. The pair stays valid for its own source text.

The second is the false-seal case from the bench, and it is the one that had no
home in the schema. A false seal is a **correct** pair matched to the wrong
input, so rejecting the pair would destroy a good verification. It needed a new
table (`tm_rejections`) keyed on the query, not on the pair.

Design decisions worth remembering:

* **Enforcement lives in `lookup()`**, not `best_sealed()`. Every serve path —
  `best_sealed`, engine TM context, the entity resolver, the reconciler — goes
  through `lookup`. Filtering one level up would have left a rejected pair still
  reaching the engine's system prompt as authoritative reference material.
* **Rejections are honored even when their signature does not verify**, which is
  the opposite of how seals are treated. The two fail in opposite directions:
  honoring a forged seal serves unverified content as verified, whereas honoring
  a forged rejection merely withholds an answer and degrades to human review —
  the defined safe state. It grants an attacker nothing either, since writing a
  forged rejection needs store write access, and anyone with that could delete
  the sealed row instead. Validity is still recorded and surfaced via
  `rejection_signature_report` for the curator.
* **Rejection signatures are domain-separated** from seal signatures (a literal
  `"rejection"` tag as element 0 of the signed message), so one can never be
  replayed as the other.
* **The capability is optional and all-or-nothing.** A host store predating it
  keeps working; `supports_rejection()` reports partial implementations as no
  support, because writing rejections nobody reads back is worse than not having
  the feature. `reject_*` raises rather than silently dropping a human's "no".

Remaining: nothing consumes rejections as *training signal* — a query with
several rejections is a strong hint that the threshold is wrong for that domain
(§1.3), and a pair rejected against many different queries is a hint the pair
itself is junk. Both are now recorded and unread.

### 1.3 The threshold should be calibrated, not constant — **measured**

`SEAL_THRESHOLD = 0.92` is a single global constant across every domain, and no
single value works. Complete sweep, 250 probes per cell, false-seal rate
(`bench/results/accuracy.json`):

| threshold | boil 500 | boil 2k | boil 8k | boil 24k | prose 500 | prose 2k | prose 4k |
|-----------|---------:|--------:|--------:|---------:|----------:|---------:|---------:|
| 0.90 | 2.8% | 10.8% | 36.4% | 56.4% | 2.4% | 5.6% | 10.0% |
| **0.92** (shipped) | 0.4% | 1.6% | 8.0% | **16.4%** | 2.0% | 4.8% | 6.8% |
| 0.94 | 0.0% | 0.4% | 1.6% | 4.8% | 0.8% | 4.0% | 3.6% |
| 0.96 | 0.0% | 0.0% | 1.2% | 0.4% | 0.0% | 1.2% | 1.6% |
| 0.98 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.4% | 0.8% |

**The "free six points" claim this section used to make is dead.** It rested on a
recall column measured with perturbations that normalization erased. With a real
paraphrase tier (`bench_accuracy` now reports `recall_surface` and
`recall_paraphrase` separately), raising the threshold is expensive:

| threshold | boil 24k false-seal | boil 24k paraphrase recall | prose 4k false-seal | prose 4k paraphrase recall |
|-----------|--------------------:|---------------------------:|--------------------:|---------------------------:|
| 0.90 | 56.4% | 38.4% | 10.0% | 62.4% |
| **0.92** | 16.4% | **23.6%** | 6.8% | **60.0%** |
| 0.94 | 4.8% | 6.8% | 3.6% | 56.0% |
| 0.96 | 0.4% | 2.4% | 1.6% | 43.6% |
| 0.98 | 0.0% | 0.0% | 0.8% | 15.6% |

Surface recall reads 100% in every one of those cells. That gap *is* the finding:
the old column measured whether near-identical input still matches, which was
never in question.

**There is no threshold that is simultaneously safe and useful.** At 0.96 the
24k boilerplate case is clean (0.4% false seals) and effectively dead (2.4%
paraphrase recall). At 0.92 it serves more real rewrites and gets one in six
answers wrong. Every cutoff is bad at one of the two jobs, on both corpora.

That is a limit of character-ratio matching, not of threshold choice, and it is
now the strongest argument on this list for §3.1/§3.3 — widening the seam so a
semantic matcher can be used at all. Tuning `SEAL_THRESHOLD` cannot fix it.

Note the two corpora are not equally stressed: a synonym swap in an 11-word
boilerplate phrase changes ~9% of its tokens, while dropping one stopword from a
long prose sentence changes far less (paraphrase score p50 is 0.0 — i.e. below
the 0.80 floor — for boilerplate, versus 0.95 for prose). The direction holds on
both; the magnitudes are not comparable across corpora.

**Two separate scaling stories, and the prose one is worse than it looks.**
Boilerplate degrades faster with size (0.4% → 16.4%) but is a synthetic worst
case. Prose is real English and still reaches 6.8% at only 4,000 pairs, with a
score distribution whose p50 is ~0.48 — i.e. the *average* probe is nowhere near
danger and the tail still clears 0.98. A diverse corpus feels safe and is not,
because real corpora contain genuine near-duplicates.

The paraphrase tier that settles this was added in `corpora.py`: meaning-
preserving rewrites (synonym substitution from a curated table, clause
reordering, contraction, and a guaranteed stopword-drop fallback) that survive
normalization. 0% of boilerplate and 5% of prose paraphrases normalize to an
identical key, against 80% for the surface tier.

Longer term this still wants to be per-domain, or a calibration mode that
samples a corpus, measures its absent-score distribution, and recommends a
cutoff for a target false-seal rate — which is also the honest marketing story
(§4.2): not "we are accurate," but "here is your false-verification rate, and
here is the dial."

### 1.4 Seal staleness and quorum — **open**

Every seal is equally authoritative forever, and one verifier is enough. Neither
is obviously right for a regulated buyer. Worth considering: seal age surfaced
in provenance; a `weight` that decays; N-of-M verification for high-stakes
domains. The ledger already records who sealed what and when, so the data is
there — nothing consumes it.

### 1.5 A numeric label could hold several baselines — **shipped**

*Was: `Reconciler.seal_baseline` let a label accumulate baselines, and `check`
scored an observation against whichever it sat nearest.*

Found while building the numeric view of the UI (§5.4). The conflicting-seal
guard in `add_pair` keys on the **normalized source**, and under a
`NumericMatcher` every figure is its own key — so a second baseline for a label
was never an overwrite to catch, it was an insert. Both stayed sealed. Then
`check` ranked by similarity, i.e. by nearness to the observation, which is
precisely the wrong tie-break: the figure most likely to excuse an observation
is the one closest to it. Reproduced —

```
seal_baseline("ceiling", "$5,000,000", verifier="auditor")   # superseded
seal_baseline("ceiling", "$1,000,000", verifier="auditor")   # the standing one
check("ceiling", "$4,900,000")  ->  flagged: False           # against the old ceiling
```

A recipe whose entire job is to flag a deviation must not let a caller add the
baseline that excuses it. `seal_baseline` now raises `ConflictingSealError` when
a different verifier restates a label's figure, retires the superseded baseline
on a self-correction or explicit override, and ledgers `baseline_replaced`.
`check` uses the **newest** baseline, not the nearest, and reports `ambiguous`
with a count when more than one stands — which is what a store that cannot
retire (no curation capability) now degrades to, loudly, instead of silently.

Worth noting what this is an instance of: **the shared guards protect a recipe
only as far as the matcher's notion of identity reaches.** The entity recipe is
fine — two canonicals for one alias collide on the same normalized surface, so
`add_pair` catches it. Any future matcher whose normalization makes distinct
values distinct keys needs its own uniqueness rule, and §3.1's warning about the
seam being lossy has a second edge here: what the normalizer *separates* matters
as much as what it collapses.

### 1.6 A seal could be made without being ledgered — **shipped**

*Was: `memory.add_pair(status="sealed")` wrote nothing to the chain.*

Found by a CLI test that filtered the ledger for `seal` entries and got none,
against a database that had two sealed pairs in it. The seal entries in the chain
came from the *callers* that happened to write one — `graduate_segment`, the
recipes, the UI — so the shortest path to a sealed row, and the one every
importer and host integration takes, produced a verified answer with no trail.
Meanwhile the README's first paragraph promised every seal was appended.

The entry is written from `add_pair` now, which is the one function that turns a
pair into a sealed one, so the promise holds regardless of entry point.
`graduate_segment`'s own entry became `segment_sealed` — which segment, in which
document, a human decided — so the trail carries both facts and says "seal" once.
`seed_from_corpus` passes `audit=False` and writes a single `corpus_seed` entry
instead, because a 10k-pair curated import is one act by one non-human verifier
and burying every human decision under ten thousand lines would be its own kind
of unauditable.

**A follow-up found the same fix had inverted the priorities.** Routing the entry
through `_log_seal_event` — which swallows ledger failures so a bulk import
cannot half-write — meant a seal onto a *broken chain* was accepted, served, and
recorded nowhere, while `reject_pair` and `unseal` on the same chain raised and
refused. Granting trust failed open; withdrawing it failed closed. Exactly
backwards, and invisible because both paths "worked".

`cascade.ledger_preflight()` now applies the append's refusals *before* the store
is touched, so a decision that cannot be audited is refused rather than made, and
the post-write append warns instead of passing silently. A draft still lands on a
broken chain, which is the right line: a draft is not a verification.

Worth naming the pattern, because it is the second instance: **a guarantee
enforced by convention at call sites is not enforced.** The first was
`is_verified_seal` (§1.2's regression — a bare `status == "sealed"` filter one
file over). Both were fixed the same way: move the rule into the single function
that cannot be bypassed.

### 1.7 An import could revive a pair a human had rejected — **shipped**

*Was: `portable.import_bundle(override_conflicts=True)` wrote through
`store.memory_seal` directly, so `RejectedPairError` — which `add_pair` raises
for exactly this — was structurally unreachable. A pair rejected as fraudulent
came back sealed and serving, and the report said "sealed: 1".*

Found by an adversarial read of the docs against the code, and it is §5.2's bug
wearing a different coat: a guarantee enforced at one call site, and a second
path into the store that never passes it. The first time it was
`graduate_segment`; this time it was a file.

The fix is a second switch, not a stronger one. `override_conflicts` means
"their answer wins where we disagree", and a rejection is **not** a competing
answer — it is a decision that the mapping is wrong. So rejected rows get their
own bucket in the report, their own warning, their own CLI line, and their own
`override_rejections` flag, mirroring the two `add_pair` has had all along. The
UI deliberately has no checkbox for it: reviving a rejection through a file
import should cost a considered command, and `Curator.restore` is the documented
way back.

### 1.8 Two threads could seal the same phrase, and both won — **shipped**

*Was: `add_pair` read, decided, then wrote, with nothing making that atomic and
no key constraint behind it. Two concurrent seals of the same new source each
found nothing and each inserted — two sealed rows for one normalized source, no
`ConflictingSealError`, and no answer to which one serves.*

Reachable the moment the UI existed: it serves from a thread pool, so two
reviewers pressing **Seal** on the same phrase is all it takes. The guard was
written when every caller was a REPL.

Fixed in two places, because a check and an invariant are different things. The
reference store now carries a unique index on `(source_norm, source_lang,
target_lang)` — the invariant the curator, the exporter and every serve path
already assumed, now enforced by something no caller can talk past. And
`add_pair` catches the collision, re-reads, and takes the existing-row path, so
the loser gets the `ConflictingSealError` it should have had. A pre-existing
database holding duplicates cannot take the index; that degrades with a warning
naming the count rather than failing every later call.

**The ledger had the same disease, and worse consequences.** `_ledger_append`
read the tail and wrote the next line unsynchronized: eight threads appending
concurrently wrote all 160 entries and left a chain `verify()` rejects. Not a
lost entry — a trail that indicts itself, on the one file whose integrity is the
product. It is now `ledger_append` (public, since six modules import it), holding
a process lock and an advisory file lock, with the FRANK forward moved outside
both so a slow mirror cannot stall a review queue.

### 1.9 The numeric matcher takes the first number it finds — **open**

`NumericMatcher.parse` strips `$ , %` and then *searches* for a number, so
`"1,00o,000"` — one typo — parses as **100**, and `"12/31/2024"` parses as 12.
Its docstring says "extract a number … or None", so this is the documented
behavior, not a bug against its own contract.

Whether it is the right contract for a reconciler is the open question. The
failure direction is currently safe: a typo produces a wildly wrong figure, which
gets *flagged*, and a human looks. But the reverse exists — a stray leading token
in an otherwise correct figure is silently dropped — and "the number I compared
was not the number you typed" is a bad sentence to have to say in an audit.
Options: require the whole cleaned string to parse (breaks `"$1,000,000 USD"`),
or report the parsed figure back in the result so a caller can see what was
actually compared. The second is cheap and non-breaking; do that first.

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
Seeding the incumbent at the threshold instead of `0.0` makes every candidate
below it skippable from the first row rather than only after a good match turns
up. Implemented as `best_match_fast(..., floor=)` and measured on *absent*
probes — the case that previously pruned worst:

| Corpus | Naive | floor=0.0 | floor=0.80 |
|--------|------:|----------:|-----------:|
| prose 4,000 | 22.1 s | 18.9 s (1.2x) | **2.5 s (8.8x)** |
| boilerplate 24,000 | 94.2 s | 15.3 s (6.1x) | 15.5 s (6.1x) |

Zero disagreements above the floor in both. The floor is what rescues prose,
exactly as predicted; boilerplate gains nothing extra because every probe there
already scores above 0.80, so nothing is censored. This turned a 24k row that
had failed to finish in 53 minutes into ~5 minutes, and made the complete
7-row sweep possible.

**Ship this in `best_sealed`.** `lookup()` cannot use it — it must return
sub-threshold candidates as engine context — so it wants to be a distinct fast
path, not a change to the shared scan.

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

**There is now a threaded consumer.** `nestor.ui` serves from a thread pool, and
that turned the shared `":memory:"` connection into an error — SQLite objects
belong to the thread that made them — so it is guarded by a lock, while
file-backed stores keep opening per operation and are thread-safe by that
accident. Whether the churn costs anything under real concurrent review is still
unmeasured, and now worth measuring rather than hypothesising about.

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

The README advertised three recipes; the seam supports a category. The UI's Ask
view narrowed that gap by exposing the seam itself as a fourth choice — any two
domain tags, either shipped matcher, showing the normalized key and every
candidate's score — so a custom recipe is drivable without writing a surface for
it. What is still true is that a matcher written outside the package cannot be
selected from a UI or an MCP call, because a name off a wire cannot conjure one;
it has to be injected in code (`memory.set_matcher`). The rest is positioning
(§4.1).

### 3.3 Semantic matcher — **open**

Blocked on §3.1. Would fix the acronym/synonym class of misses outright. Cost:
the first real dependency in a currently zero-dependency package — which is a
genuine selling point to the regulated buyer, so this should probably live as an
optional extra, never core.

---

## 4. Positioning

### 4.1 Lead with the mechanic, not translation — **shipped**

*Was: the README opened on a translation demo and reached the general mechanic a
section later, so the first screen said "translation memory" to anyone skimming.*

The mechanic is now the first section: the loop, then the recipe table, then one
line placing translation as the origin story rather than the boundary. The quick
start runs the loop **twice** — once in translation, once as an alias graph with
no translation in it — because "domain-agnostic" is a claim, and two runnable
files are evidence. Both are executed by `tests/test_docs.py` and diffed against
the output printed beneath them, so the second one cannot quietly rot while the
first is the only one anybody runs.

The entity example ends on the line worth arriving at: a near miss comes back
**unsealed with a suggestion**, not as an answer with a lower score. That is the
same three-state answer the translation demo gives, in a domain where nobody
would call it translation memory — which is the whole argument of §4.2 made
without asserting it.

Still open, and deliberately separate: §4.2's positioning line, and §4.3's
recorded demo.

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

No longer blocked on §5.1 — `nestor ui`, `nestor ask` and `nestor serve` all
exist, and two screens carry the loop with no explaining: a near-match returning
`~ draft` because it is under the cutoff, and a forged row scoring **1.000**
returning `! pending`. What is missing is the *artifact* — a scripted sixty
seconds, recorded, that ends on tampering with the ledger and watching the chain
refuse.

### 4.4 The bench is a marketing asset — **open**

"We are accurate" is a claim a compliance buyer knows is a lie. "Here is our
measured false-verification rate, here is the dial that sets it, here is the
harness — run it yourself" is stronger *because* it admits a failure rate.
Publishing `bench/results/` is a differentiator, not an exposure.

---

## 5. Missing surface

### 5.1 There is no CLI — **shipped**

*Was: no `console_scripts`, no entry point, nothing to run without writing
Python.*

`nestor` (`nestor.cli`): `ask`, `resolve`, `check`, `match`, `export`, `import`,
`ledger verify|entries|head`, `stats`, and delegation to `ui` and `serve`, which
own their own flags rather than having them mirrored and left to drift.

Two decisions worth keeping. **Exit codes carry the answer** — 0 for a verified
one, 1 for an unverified answer, a flagged figure, a broken chain or an import
with conflicts, 2 for usage — so `nestor ledger verify` is a CI gate and `nestor
ask` works in a shell conditional. That is the difference between a CLI and a
pretty-printer. And **`import` is a dry run until `--apply`**, like every other
decision here that changes what gets served as verified.

Sealing is deliberately *not* a subcommand. It would be the one place in the
codebase where a verification could be made by something with no face — a script,
a cron job, a CI runner — and `--verifier "$USER"` is not a human checking
anything. Seals are made in the UI or in code that a person is driving.

### 5.2 The memory is write-only — **shipped**

*Was: `Storage` had no list, unseal, delete or export. A pair could be sealed but
never browsed, inspected, revoked or exported — so for a system whose whole value
is human verification, the human could not see what they had verified.*

`nestor.curator.Curator` is that surface: `list` (filter by status / verifier /
substring, paginated), `get` (full provenance plus every rejection recorded
against the pair), `unverifiable`, `unseal`, `restore`, `export`, `summary`.
Backed by an optional all-or-nothing `Storage` capability
(`supports_curation`), on the same terms as rejection.

Three decisions worth keeping:

* **Every row reports `servable`, not just `status`.** That column runs the same
  `is_verified_seal` predicate the serve path uses, so it answers "would Nestor
  actually serve this?" rather than "does the row say sealed?". `unverifiable()`
  lists the difference — with signing on, those are rows written by something
  that never held the seal key. Nothing else surfaces them.
* **Unseal is not reject.** Unsealing returns a pair to `draft` for
  re-verification; rejecting retires it as wrong. A curator who is merely unsure
  should not have to choose between destroying a mapping and leaving a seal
  standing they no longer trust. Unseal clears `seal_sig` — a `draft` row still
  carrying a valid signature is a seal waiting to be reactivated by anything
  that flips the status column back.
* **Revocation is ledgered** (`unseal`, `restore`). A trail that records every
  grant of trust and no withdrawal of it is not an audit trail.

**Building this found a real bug in §1.2.** `add_pair` resurrected rejected
pairs: a curator rejected a bad mapping and the next `graduate_segment` over the
same source text silently re-sealed it — precisely the leak rejection existed to
close. `add_pair` now raises `RejectedPairError` instead, so a host driving a
review queue can surface it as what it is: one human asserting the opposite of
another's recorded decision. `Curator.restore` is the deliberate way back, and it
returns to `draft` rather than `sealed`, because a mapping someone once called
wrong should be re-verified rather than reinstated.

Still missing: no `memory_delete`. Deliberate for now — rejection and unsealing
preserve the audit trail, and hard deletion would punch a hole in it. A GDPR-style
erasure path would need to be designed against the ledger, not bolted on.

### 5.3 Ledger verification is once per process — **verified**

`cascade._verified_ledgers` caches by path, so the chain is checked on first
append and never again. I watched an append succeed after mid-run tampering. The
cache is a deliberate cost trade, but a long-lived process will not notice
tampering that happens while it runs. Options: periodic re-verification, verify
the tail only, or make the cache TTL'd. Related: `verify()` cost grows linearly
with ledger length, so checkpointing may be needed before re-verification is
affordable.

**The UI makes this sharper, not worse.** `nestor.ui` is the first long-lived
Nestor process in the repo: a REPL session or a batch run exits, a review server
stays up for a shift. It verifies the chain on the first append and then trusts
it for as long as the reviewer keeps working. The Ledger view calls `verify()`
on every render, so the *reading* is live — but nothing refuses an append after
the first one, and that is now a realistic window rather than a theoretical one.

### 5.4 There was nowhere for the human to sit — **shipped**

*Was: every surface was a library surface. The reviewer worked the tier-2 queue
by typing `graduate_segment` into a REPL; the curator browsed the memory through
`Curator`. For a system whose entire claim is that a human checked the answer,
being the human meant writing Python.*

`nestor.ui` — stdlib only (`http.server` plus one inlined page), so the zero
runtime dependencies hold — with four views: **Queue** (the segments the cascade
left for review), **Memory** (the curator's list, provenance and revocation),
**Ask** (run the cascade and see the state that came back, with the ranked
candidates behind it), **Ledger** (`verify()`'s verdict beside the chain).

Decisions worth keeping:

* **Ask is the demo.** Two screens carry the product with no explaining: a
  near-match scoring 0.875 comes back `~ draft` because the cutoff is 0.92, and
  a forged row scoring **1.000** comes back `! pending` — sealed, not servable,
  by mallory. §4.3's 60-second demo is that second screen.
* **An empty verifier is refused, not defaulted.** `memory._same_verifier`
  treats `""` as *unknown* rather than as a person, so a UI that quietly sent it
  would file every decision under an actor who is nobody and turn every
  anonymous re-seal into a conflict. The API asks who is deciding.
* **The library's refusals reach the human verbatim.** A `ConflictingSealError`
  comes back as a 409 carrying its own message — *"pair … was sealed by 'rita'
  as 'Buenas noches.'; 'sam' is now asserting …"* — and the override is a second,
  deliberate click. Declining leaves the memory untouched.
* **No authentication, said out loud.** The verifier is typed, not proven. Hence
  loopback by default, `--allow-remote` to leave it, a custom-header requirement
  so another tab cannot POST a seal in, `default-src 'none'` so the page cannot
  ship the memory anywhere, and `--read-only` for showing without granting.

**All four recipes, not just translation.** The Ask view is a recipe picker —
Translate (the cascade), Entity (alias → canonical), Numeric (figure → baseline,
with tolerance and variation) and Match (the bare seam: any two domain tags,
either shipped matcher, showing the normalized key and every candidate's score).
Each seals from the same screen, into the same memory, through the same ledger.
The Memory view's domain picker lists every tag pair in the store with its size,
so several disjoint graphs in one database are visible rather than assumed.

The UI does **not** infer a recipe from a domain's tags. `("company","company")`
is probably an entity graph and `("en","es")` probably a translation, but nothing
enforces either, and a surface that guessed wrong would mislabel someone's data
with total confidence. The human picks; the UI reports what exists. §4.1's "lead
with the mechanic, not translation" now has a screen that does it.

**Building it found three real bugs.** `graduate_segment` never marked its
segment decided, so a sealed segment stayed `pending` and the queue offered it
forever — the accept-side twin of the attention tax §1.2's rejection work removed
from the reject side; invisible until something rendered the queue.
`SqliteStore`'s shared `:memory:` connection was single-threaded, which no test
caught because nothing had ever served Nestor from more than one thread. And the
third is its own entry — §1.5.

The Queue view lets a reviewer **correct** a draft before sealing it, not only
accept or reject it, because review is usually "nearly" — right apart from one
term. Without that, correcting meant rejecting the segment and sealing the fixed
text somewhere else, and the trail recorded a refusal where a correction
happened. A corrected seal is ledgered with `edited: true` and the digest of the
draft that was *not* sealed, so "a human accepted the machine's answer" and "a
human wrote the answer" stay distinguishable.

Sealing by hand picks its domain from the ones the store actually holds (or
opens a new one), rather than the language pair the process started with — the
last place in the UI that still assumed translation, and the reason to keep
asking "which surface here is quietly single-recipe?"

Still missing: no pagination in Memory beyond the first 50 rows, and no view over
`Curator.replaced_seals` — the highest-signal thing the curator surface reports,
and the one the ledger holds alone.

### 5.5 The newest ledger entry is vouched for by nothing — **shipped (mitigated)**

Every line is verified by the line *after* it, so the last one has nothing
following it: edit it and `verify()` still walks clean. Found while writing a CLI
test that tampered with a one-entry ledger and could not make it fail.

It is a property of hash chains rather than a bug, but it is not marginal: the
newest entry is the one that just recorded who sealed what, so "the most recent
decision is the editable one" is a bad thing to leave unwritten. `ledger.head()`
returns the tip and `verify(expected_head=…)` refuses one that moved
unexpectedly; `nestor ledger head` / `nestor ledger verify --expect-head` put it
in CI. That only helps a caller who kept the value *outside* the file, which is
the honest framing — the fix is not local, it is "someone else remembers."
`nestor.frank` is that taken to its conclusion, mirroring every entry with its
`local_hash` into a ledger somebody else holds.

Open: an append-time checkpoint (write the head to a sidecar the ledger writer
does not own), and whether §5.3's once-per-process verification should re-check
the head on every append rather than the whole chain — cheap, and it catches
mid-run tampering of the tail.

### 5.6 Nothing could leave — **shipped**

*Was: `Curator.export()` produced a human-readable dump and there was no way back
in. A memory could be read and never moved.*

`nestor.portable`: `export_bundle` (pairs, rejections, signatures, a canonical
`digest`, the source chain for reading), `verify_bundle`, `import_bundle`,
`pairs_csv`. CLI and UI both.

The design question is import, not export. A bundle is a file, and a file saying
`"status": "sealed"` is making exactly the claim a seal signature exists to
distrust — the same claim a forged database row makes, which Nestor already
refuses to serve. So import applies the identical rule: a seal is honored only if
it verifies **here**, and one that does not lands as a `draft` in the review
queue, counted and warned about. Two instances sharing a `NESTOR_SEAL_KEY` move
verified pairs between them and the verification survives, because it was never
in the row to begin with. Two instances that do not share a key move *candidates*
— which is the correct answer, not a degraded one.

Three smaller decisions: conflicts are listed rather than resolved (a bundle
asserting a different target for a source this instance sealed is two humans
disagreeing through a file); the chain does **not** merge, because splicing
another instance's entries in would produce a chain that verifies while
describing events that never happened here, so only the import event is appended;
and the CSV drops signatures on purpose, so nobody mistakes a spreadsheet
round-trip for a way to carry a seal.

### 5.7 A model had no way in — **shipped**

*Was: every surface assumed a human. The obvious deployment — an agent that
consults verified answers before improvising — required writing an integration.*

`nestor serve` speaks MCP over stdio (newline-delimited JSON-RPC, so stdlib only
and the zero-dependency core holds). Seven tools: ask, resolve, check, match,
provenance, ledger_verify, propose.

**The load-bearing decision is what is absent.** There is no sealing tool, no
flag that adds one, and no argument to an existing tool that produces one; a
plausible name gets a refusal that explains why. A model's only write is
`propose`, which queues a candidate as a `draft` exactly where a tier-2 engine's
output lands. This is not caution — it is the whole proposition. "Has a human
checked this?" is worth precisely as much as the difficulty of getting a
machine's output marked as checked, and a server that let a model seal, however
carefully, would be a system where the machine grades its own work.
`tests/test_serve.py` pins it as a property rather than a policy: after a model
calls every tool the server has, the sealed memory is unchanged.

The other half is what comes *back*. Every answer carries the state, the
verifier, the confidence and the candidates with their scores — so an agent can
say "verified by rita", quote a pair id an auditor can look up, or decline
because nothing was sealed. Returning only the text would have made Nestor an
ordinary cache. This is also why `nestor.answer` exists: the browser, the
terminal and the model now share one definition of what Nestor answers, because a
system that tells a model "verified" while showing a curator "draft" has already
lost the argument.
