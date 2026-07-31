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

**Agent log (§6).** Follow-ups proposed during implementation sessions (IDE
agents included) go in §6 with the same status vocabulary. When something
ships, mark it **shipped** there (and fold the substance into the numbered
section it belongs to if it isn't already). Agents: when you suggest a follow-up
to the operator, add it to §6 in the same change or immediately after — do not
leave it only in chat.

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

**Reading them back — shipped.** For a while the remaining line here was that
nothing consumed rejections as *signal*. `Curator.rejection_signals()`,
`nestor rejections` and the UI's Signals tab now do: a query refused several
times over is evidence about the **threshold** in that domain (§1.3), and a pair
refused against many unrelated queries is evidence about the **pair**. Read from
the ledger rather than the store — `memory_rejections` answers "what was refused
for this query", which is what serving needs, and there is no enumerate call;
adding one would change the Storage Protocol every host implements, for a
reporting feature. The number of entries read is reported, so a rotated chain
shows as a smaller sample rather than as a clean bill of health.

It deliberately stops short of proposing a threshold. The score a rejected match
was made at is not recorded, so this says the dial is wrong here and hands over
to §1.3's calibration.

### 1.3 The threshold should be calibrated, not constant — **measured; the calibration shipped**

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

**The calibration mode now exists** — `nestor.calibrate` / `nestor calibrate`.
It does not import these corpora; it measures the memory a deployment actually
has, by asking the one question that needs no probe set: for each sealed pair,
which *other* sealed pair scores highest against it **and has a different
target**? That is a false seal by definition, already present, between two
things a human deliberately verified. It reports the rate at every cutoff in
this same sweep, recommends the lowest one meeting a target rate, and says so
when none does — that last case being a corpus problem rather than a dial
problem, and worth naming as such.

Two limits it states in its own output. It is a **lower bound**: real queries
include text the memory has never held, and this can only see collisions the
corpus already contains. And it cannot see recall — a memory holds no record of
the paraphrases nobody has asked yet — so the trade above still has to be read
from the bench. It changes nothing on its own: moving the threshold is a
decision about how much unverified content you will serve, and that belongs to
a person.

That is also the honest marketing story (§4.2): not "we are accurate," but "here
is your false-verification rate, measured on your corpus, and here is the dial."

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

### 1.9 The numeric matcher takes the first number it finds — **shipped**

`NumericMatcher.parse` strips `$ , %` and then *searches* for a number, so
`"1,00o,000"` — one typo — parses as **100**, and `"12/31/2024"` parses as 12.
Its docstring says "extract a number … or None", so this is the documented
behavior, not a bug against its own contract.

Whether it is the right contract for a reconciler is the open question. The
failure direction is currently safe: a typo produces a wildly wrong figure, which
gets *flagged*, and a human looks. But the reverse exists — a stray leading token
in an otherwise correct figure is silently dropped — and "the number I compared
was not the number you typed" is a bad sentence to have to say in an audit.
Requiring the whole cleaned string to parse was the other option, and it is
wrong: it breaks `"$1,000,000 USD"`, which is an ordinary way to write a figure.
So the signal shipped is not "was anything left over" but **"was a *digit* left
over"** — `"USD"` is decoration, `"o000"` and `"/31/2024"` are the rest of a
number that never reached the comparison. That separates the two failures above
from the legitimate case exactly, with no false alarm on currency or units.

`NumericMatcher.parse_detail` returns the figure with what it had to ignore;
`check()` carries `observed_text` / `observed_partial` and the same pair for the
baseline; `seal_baseline` warns, because a partially-read *baseline* is the one
case where the discrepancy is permanent — the row says `"$1,00o,000"` forever
and every future check runs against 100. The ledger records the flags and not
the raw strings, since `nestor.frank` mirrors entries verbatim into somebody
else's ledger.

Reporting beat refusing: a reconciler that rejected every partially-parsed
figure would refuse real inputs, and the person who can tell a typo from a unit
suffix is the human this package exists to keep in the loop.

---

## 2. Performance — the scan

**measured** (`fill.py`, session of 2026-07-25; to be folded into a bench):
lookup is linear in corpus size — 293 ms @ 2k pairs, 4.4 s @ 32k, projecting to
~135 s @ 1M. **97% of that is Python-side `difflib`, not SQL** (112 ms fetch vs
4,260 ms scoring at 32k). The database is not the bottleneck; the scoring loop is.

### 2.1 Lossless prefilter via difflib's own bounds — **shipped**

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

**Shipped**, as `StringMatcher.similarity_bound` plus `best_sealed`'s own scan.
Re-measured on landing: 4,000 sealed rows, 40 absent probes, 35.6 s → 2.4 s
(**14.7x**), identical answers. The bound is a matcher method rather than a
difflib call inside `memory` — the seam is where domain knowledge lives — and it
is deliberately *not* in the `Matcher` Protocol: `NumericMatcher` gains nothing
from a bound on two floats, and requiring it would break every custom matcher
already injected. No bound offered, no pruning, same answer. The length bound is
inlined rather than taken from a `SequenceMatcher`, because constructing one
indexes the second sequence, which costs more than the cheap question is worth.

Writing it turned up something the performance work was not looking for.
`best_sealed` filtered `lookup()`'s result, and `lookup` defaults to `limit=5`.
Six drafts scoring above a sealed row is not exotic — the engine writes a draft
for every near miss — and they pushed a human's verification off the end of the
list, so tier 1 answered "nothing verified, here is a fresh draft" while the
seal sat in the memory matching at 0.933. There is no top-N to fall out of now.

Do this before anything lossy — and there is still nothing lossy.

### 2.2 Trigram blocking — **measured, disappointing**

A 4-gram prefilter gave only **2.4x** (4,372 ms → 1,818 ms) because 43% of
candidates survived it. That number is from the homogeneous boilerplate corpus,
which is the worst case for blocking — on diverse prose it should do far better,
and that is worth measuring before judging the idea. Lossy, unlike §2.1.

### 2.3 Index `source_norm` — **shipped**

`memory_find` runs on every `add_pair`. Fresh reference databases get
``idx_tm_pairs_key`` on ``(source_norm, source_lang, target_lang)`` — the same
unique index §1.8 added for concurrent seals, which also satisfies the measured
~2.3× ingest win (bench session 2026-07-25). If duplicates already exist and the
unique index cannot be created, ``idx_tm_pairs_find`` on the same columns is
installed so lookups stay indexed while the operator resolves the dupes.

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

### 3.1 The seam is lossy by construction — **shipped**

`normalize(value) -> str` is the dedup key in `memory_find` and what gets
persisted as ``source_norm``. Scoring used to go only through
``similarity(a_norm, b_norm)`` on those keys, so anything that did not survive
normalization was gone by scoring time (the acronym case below).

**Optional ``score(raw_a, raw_b)``** — when a matcher implements it,
``memory.lookup``, ``memory.best_sealed``, and ``nestor.calibrate`` compare the
query's raw text to each row's ``source_text`` via ``score``. ``similarity`` on
norms remains for matchers that do not offer ``score``. ``similarity_bound``
prefiltering is disabled when ``score`` is present (bounds are on norms only).

The original failure mode: I lost an acronym match (`AWS` → `Amazon Web
Services`) purely because my normalizer sorted its tokens, and the information
needed to recover it no longer existed by scoring time. Worse, that same string
is simultaneously the store's exact-match dedup key in `memory_find`. Scoring
wants rich structure; deduplication wants aggressive collapse. **These two jobs
pull in opposite directions, and one string served both** — until ``score``
split them.

This is the change that unblocks embedding/semantic matchers without smuggling a
vector through a SQL key: ``normalize`` stays the dedup key; ``score`` (or a
matcher that implements it with embeddings) sees the originals.

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

### 3.3 Semantic matcher — **shipped (optional extra)**

``pip install nestor[semantic]`` pulls in `fastembed` only — core stays
zero-dependency. :class:`~nestor.semantic_matcher.SemanticMatcher` keeps
:class:`~nestor.matcher.StringMatcher` normalization for dedup and implements
``score(raw_a, raw_b)`` with cosine similarity on a small bi-encoder (default
``BAAI/bge-small-en-v1.5``). Wired as ``matcher="semantic"`` on
``nestor match``, the UI Ask → Match view, and ``nestor_match`` over MCP.

Serving thresholds calibrated for character ``StringMatcher`` do not transfer;
re-run ``nestor calibrate`` on the corpus you intend to serve.

### 3.4 Model-authored surfaces — **measured; four stages, and the matcher
mattered more than the surfaces**

*The hypothesis: the acronym/synonym miss class is answerable by sealing several
lexically different **surfaces** for one meaning — the shape `entity.py` already
uses — rather than by a semantic matcher (§3.3) and the dependency §3.3 is
reluctant to take. §3.1's own example is the case: `AWS` → `Amazon Web Services`
was lost because the information needed to recover it did not survive
normalization. Sealed as two surfaces, it never has to survive normalization,
because it was indexed in its own right.*

The mechanism is already in the package — `EntityResolver.seal` writes one row
per surface, N surfaces → one canonical target. So the missing piece is not a
matcher; it is **something to author the surfaces**, which a model does at seal
time having just read the sentence. That is a write-side one-to-many expansion,
`surfaces(raw) -> list[str]`, and neither `normalize` (1→1) nor §3.1's proposed
`score(raw_a, raw_b)` (2→float) can express it. §3.1 and §3.4 are different seam
changes, not the same one arrived at twice.

#### The result

`bench/bench_surfaces.py` on `corpora.aliased`, 1500 rows, 250 probes, seed 7
(`bench/results/surfaces.json`). Every arm holds **the same 1500 rows** — K
meanings × surfaces held constant — so index size and scan cost are equal and
only structure varies.

| K | meanings | recall @0.92 | false seals @0.92 | recall @0.96 | false seals @0.96 |
|--:|---------:|-------------:|------------------:|-------------:|------------------:|
| 1 | 1500 | 0.056 | 0.004 | 0.044 | 0.000 |
| 3 |  500 | 0.440 | 0.024 | 0.344 | 0.000 |
| 5 |  300 | 0.652 | 0.036 | 0.492 | 0.000 |

**At 0.96 the lift is 11× and it is free.** Recall 0.044 → 0.492 with zero false
seals at every K. §1.3 concluded there is no threshold that is simultaneously
safe and useful; on this corpus, surfaces move the safe threshold into
usefulness rather than trading one for the other. At 0.92 the lift is 12× for 9×
the false seals — real, but not free, and 0.96 is the better operating point.

> **Superseded by stage 3, and left standing.** The paragraph above is correct
> about `aliased` and wrong to have implied it generalizes. On human prose the
> entire score distribution tops out at 0.878 and recall at 0.96 is 0.000 in
> every arm. The claim is kept verbatim because *which* sentence overreached, and
> on what evidence, is the part worth being able to check later.

**Why the budget control mattered.** The naive reading holds meanings constant
and lets rows grow:

| K | budget | rows | recall @0.92 | false seals @0.92 |
|--:|--------|-----:|-------------:|------------------:|
| 5 | fixed-rows | 1500 | 0.652 | 0.036 |
| 5 | fixed-meanings | 7500 | 0.652 | **0.084** |

Recall is *identical* — it depends only on whether the probe's surface family
was sealed, not on how many other meanings share the index. False seals are
**2.3× higher**, and all of that is the corpus-size penalty (accuracy.json:
boilerplate 2k → 1.6%, 24k → 16.0%), not the surfaces. Measured the naive way,
surfaces look considerably more expensive than they are.

**Coverage, not bridging — the negative finding that matters.** Recall is
*always below* the fraction of the query distribution whose surface family was
sealed (0.056 vs 0.21; 0.440 vs 0.59; 0.652 vs 1.00), never above. Sealing
`Amazon Web Services` does **not** help you match `AWS`. There is no free
bridging between disjoint surfaces, which is precisely why the surfaces have to
be authored — and precisely the gap a semantic matcher would otherwise fill.
This is the strongest evidence for §3.4 and it arrives as a negative result.

#### Two blind harnesses, found and fixed — the reusable part

Both looked like clean results at the time. Recording them because the lesson
generalizes past this entry.

**Blind #1 — the corpus could not contain the case.** Run against
`boilerplate`/`prose`, recall was identical to three decimals across K and the
canonical surface won **117 matches out of 117**. That reads as a crisp
falsification. It was a property of `corpora.perturb`:

```
sim(original, paraphrase_A)     = 0.738
sim(paraphrase_A, paraphrase_B) = 0.624
```

Independent one-step perturbations of one phrase sit further from each other
than from the original, so the centroid is always the best bridge and extra
points around it are redundant. Meanwhile the target class sits at 0.27–0.50
(`AWS`/`Amazon Web Services` = 0.273). Those corpora cannot express it. Hence
`corpora.aliased`, whose intra-meaning dispersion (p50 **0.407**) is measured
into every result rather than asserted.

**Blind #2 — the probes were exact matches.** `perturb` does not bite on short
name-like surfaces: no company vocabulary in the synonym tables, no clauses to
reorder, no function words to drop, and a typo rule requiring >12 characters. So
88% of surface-tier and **100%** of paraphrase-tier probes normalized
*identically* to the row they were meant to find. "Recall" was measuring whether
the exact string had been sealed — a lookup test wearing a fuzzy-match costume,
and it produced a flattering `K=5 → 1.000 recall at 0.000 false seals` that was
one edit away from this entry. `corpora.aliased_query` replaces it with noise a
person actually introduces (suffix abbreviation, acronym dotting, word drop,
typo); `aliased_query_bite` measures the result — 31% still exact, p50 0.947 —
and the bench prints it every run and warns above 50%.

**The rule both times:** measure the property the harness depends on, *in the
harness, every run*. A corpus property asserted in a docstring is not a control.
Two of the three controls in this bench exist because a confident number turned
out to be an artifact.

#### Stage 2 — model-authored surfaces

A model saw **only the canonical form** and authored four alternates
(`bench/bench_surfaces_llm.py`, surfaces in `bench/results/authored_surfaces.json`).
A prediction was recorded before the run (`bench/STAGE2-PREDICTION.md`) and was
**wrong**: predicted 0.52 recall @0.92 at K=5, measured 0.377 against the
generator's probe families.

It was wrong for a reason worth keeping. Per-family recall @0.92:

| family | generator | model-authored |
|--------|----------:|---------------:|
| full | 0.94 | **1.00** |
| short | 0.45 | **0.82** |
| acronym | 1.00 | 0.00 |
| ticker | 0.58 | 0.00 |
| legacy | 0.56 | 0.00 |

The model produced an acronym for **every** meaning — `JRG 0`, `QFL 1`, `PMC 2`
— arguably better than the generator's, which uses place+trade initials only and
jams the tag on unspaced (`JR0`). `sim("JRG 0","JR0") = 0.750`, under threshold,
scores zero. `acronym = 0.00` is a **corpus artifact, not a model failure**.

**Stage 1 and stage 2 need different corpora**, which nothing about `aliased`
reveals until a second author is introduced. The generator authoring both the
sealed surfaces and the probe families makes it self-consistent; the moment
someone else supplies one side, every invented convention becomes an unguessable
barrier and the bench measures convention-matching.

Re-scored with probes from an author independent of both — an agent asked what a
hurried employee would type into a search box, which had seen neither the
generator's families nor the sealing model's output:

| arm | K | rows | recall@0.92 | recall@0.96 |
|-----|--:|-----:|------------:|------------:|
| canonical only | 1 | 300 | 0.117 | 0.023 |
| generator families | 5 | 1500 | 0.430 | 0.293 |
| model-authored | 5 | **1402** | **0.670** | **0.570** |

Model surfaces beat the generator's own families, on fewer rows.

#### Stage 3 — a person authored both sides, on a real corpus

`bench/bench_surfaces_human.py` over `corpus_terpsi`, on `terpsi-music` at
`6ea9b89` — 120 extracted spans, 96 surviving the gate, 14 referents
(`bench/results/surfaces_human.json`). Every surface and every probe is a
**verbatim span of one person's prose**, written across fourteen documents and
twenty-four survey notes (seven extraction agents, three waves) before any of it was going to be
matched against anything. A model only *labelled* which existing phrase points at
which file; `corpus_terpsi.gate` re-reads the source and drops anything that is
not a literal substring — 7 of 120 rejected as NOT VERBATIM, including a span an
agent had helpfully re-capitalised.

The referent is a **file path**, so ground truth owes nothing to string
similarity and the labels cannot be circular with the thing being measured. The
split is by **source document, run in both directions**, and any probe whose
normalized form is already in the sealed set is dropped and counted, so recall
is never measuring lookup.

This corpus reaches the case `aliased` is structurally incapable of expressing.
`aliased` tests **derivation** — manipulate the canonical string. These are
**knowledge**:

```
"the sensitivity ladder"     -> docs/SENSITIVITY.md   sim 0.615
"the eight text-only checks" -> craft/                sim 0.067
```

**The result, and it is not the one stage 2 pointed at.** rank@1 is the
threshold-free measure — how often the correct referent is the argmax.

| cut | split | arm | n | rank@1 | recall @0.80 | @0.92 |
|---|---|---|--:|--:|--:|--:|
| inclusive | A→B | canonical only | 14 | 0.714 | 0.000 | 0.000 |
| inclusive | A→B | **+ human surfaces** | 14 | **0.786** | 0.000 | 0.000 |
| inclusive | A→B | + WRONG surfaces | 14 | 0.500 | 0.000 | 0.000 |
| inclusive | B→A | canonical only | 41 | 0.780 | 0.000 | 0.000 |
| inclusive | B→A | **+ human surfaces** | 41 | **0.805** | **0.585** | 0.000 |
| inclusive | B→A | + WRONG surfaces | 41 | 0.000 | 0.000 | 0.000 |
| strict | A→B | canonical only | 4 | 0.000 | 0.000 | 0.000 |
| strict | A→B | **+ human surfaces** | 4 | **0.250** | 0.000 | 0.000 |
| strict | B→A | canonical only | 12 | 0.250 | 0.000 | 0.000 |
| strict | B→A | **+ human surfaces** | 12 | **0.333** | 0.000 | 0.000 |
| strict | both | + WRONG surfaces | — | 0.000 | 0.000 | 0.000 |

**Recall at every shipped threshold is 0.000, in every arm, in both cuts.** The
highest similarity any probe achieves against any sealed row *anywhere in this
corpus* is 0.878. Nestor's sweep starts at 0.80 and the distribution lives below
it. This is not "surfaces underperformed" — nothing is served at all, with or
without them. The only recall above zero anywhere is 0.585 at 0.80, one arm, one
split, and 0.80 is not an operating point anyone proposed.

**Why two cuts, and why neither is "the" number.** The inclusive cut counts
every probe. The strict cut additionally drops any probe that *contains* a sealed
surface or is contained by one — `§14 of the capability map` against a sealed
`The capability map` is not the matcher bridging two phrasings, the answer is
sitting inside the query. But the same rule also drops `the sensitivity ladder`
against canonical `SENSITIVITY`, which is genuinely what the human calls that
file. Substring inclusion is the *easy half* of real aliasing, not a fake version
of it. So the inclusive cut flatters the mechanism and the strict cut selects for
cases a character matcher structurally cannot do — a benchmark that would report
its own conclusion. Both are printed; the truth is between them, and the arm
ordering is the same in both.

Two narrower rules were tried and rejected on the way, and the failures are kept
in `corpus_terpsi.template_key`: a regex for `§N of the ...` caught
`§8.1 of the architecture` and missed `CLAUDE.md #17` for no reason but which
form was noticed first; and "drop anything containing its own canonical" turned
out to be the strict cut, arrived at by accident and nearly applied by default.

**What surfaces actually buy on real prose is rank, not service.** rank@1 rises
in all four split × cut cells, and the negative control — same referents, same
row count, each referent given *another* referent's surfaces — is worse than
canonical-only in all four, collapsing to 0.000 in three. So the lift is the
surfaces carrying meaning, not more rows in the index buying more chances. But
the correct answer being first at 0.84 does not help a mechanic whose threshold
is 0.92.

**Underpowered on the strict cut, and the direction is not.** n=4 and n=12
there; a 0.250 → 0.333 lift on twelve probes is one probe. What is *not*
fragile: the arm ordering is 4/4 consistent across both cuts and both splits, and
0.000 recall at 0.92 rests on the maximum score over the whole corpus, which no
sample-size argument touches.

**Two harness faults, both found only because the result was implausible.**
`best_match_fast(floor=FLOOR)` censors scores below the lowest threshold, so the
first run reported zeros with no way to distinguish "cannot see it" from
"threshold is above it" — rescored at `floor=0.0`, and rank@1 added. And
`normalize` collapses `CAPABILITY-MAP` to `capabilitymap`, one token where the
probe has two, costing the *baseline* arm +0.0195 mean similarity for punctuation
reasons; the canonical is now de-slugged, which makes the comparison harder for
the hypothesis. An artifact that points the way you want is the one to remove
first.

#### Stage 4 — the matcher was the binding constraint, not the corpus

Three stages varied the surfaces and never varied the tool comparing them. Every
0.000 above is `StringMatcher`, which is character difflib. `bench/token_matchers.py`
adds two token matchers behind the same seam — `TokenJaccard` (|A∩B|/|A∪B|) and
`TokenOverlap` (|A∩B|/min) — and stage 3 reruns unchanged. All matchers answer
**one probe list**, with the lookup drop computed with `StringMatcher` every
time; letting each matcher's own `normalize` decide the drop gave the token runs
17 probes where the string run had 41, two numbers that must never be compared.

| matcher | split | arm | rank@1 | recall @0.92 | LOO false seal @0.92 |
|---|---|---|--:|--:|--:|
| string | B→A (41) | canonical | 0.780 | 0.000 | 0.000 |
| string | B→A | + human | 0.805 | 0.000 | 0.000 |
| jaccard | B→A | canonical | 0.732 | 0.000 | 0.000 |
| jaccard | B→A | + human | 0.756 | 0.049 | 0.000 |
| **overlap** | B→A | canonical | 0.732 | **0.707** | 0.000 |
| **overlap** | B→A | + human | 0.756 | **0.707** | 0.000 |
| overlap | B→A | + WRONG | 0.732 | 0.707 | **0.683** |

**Recall at Nestor's shipped 0.92 goes from 0.000 to 0.707 on identical probes,
by changing the matcher.** Stage 3's "no threshold in the shipped range is
reachable" is a fact about difflib, not about human aliasing. That conclusion
needed one afternoon's work to reach and I should have reached it before running
three benches, not after — *the failure is never in the step you are watching.*

**And most of that win is not the surfaces.** `+ WRONG surfaces` scores the same
0.707 as `canonical only`. Under token containment the canonical row alone does
the serving; surfaces add ~0.02–0.07 of rank@1 and nothing to recall. The one
place they carry it is the strict cut A→B — canonical 0.000, human 0.250, WRONG
0.000 — on n=4.

**The number that decides §3.3.** 17.1% of probes (7/41) share **no token** with
any sealed surface; on the strict cut, 58.3%. That is the lexical floor — no
character, token or n-gram method reaches it at any threshold — and it, not the
whole problem, is what a semantic matcher has to justify itself against.

**Two harness faults, and the second was nearly a published result.**

- `best_match_fast` accepts a `matcher` and ignores it for scoring, pruning with
  difflib's own upper bounds. Its docstring says so outright: *"Only valid for
  StringMatcher … callers must fall back to best_match for any other matcher."*
  I passed token matchers to it and read the output. The tell was that
  `TokenJaccard` and `TokenOverlap` — which share a `normalize` and differ only
  in `similarity` — returned byte-identical numbers in all 24 cells. Discarded
  and rerun through `best_match`. **The warning was written down, in the
  function, and being written down did not help** — the same shape as the README
  that accurately recorded a limitation nobody acted on.
- The false-seal rate was measured on whatever probes happened to have an
  unsealed referent — eleven of them — and reported 0.000 for `TokenOverlap`,
  the matcher most likely to false-seal, which saturates at 1.0 on a single
  shared token and had `p50 = 1.000`. Replaced with leave-one-out: rebuild the
  store without each probe's own referent, so the right answer is absent by
  construction, and score all 41. The legitimate arms hold at 0.000; the WRONG
  arm goes to **0.683**, which is the measure showing what it will do when the
  index does not contain the answer. Fourteen referents with distinct
  vocabularies is a friendly test and 0.000 should not be read as safe at scale.

#### What is established, and what is not

**Established, now across three corpora and four authorship regimes — one
surface per meaning is not enough.** Canonical-only scores 0.056 against
generator probes, 0.117 against independent agent probes, and on human prose it
produces **nothing at any threshold down to 0.55** once the templated family is
removed. Every multi-surface arm beats it in every framing. That is §3.4's
load-bearing claim and it survived the corpus that was supposed to break it.

**Not established — how good model-authored aliases are.** Stage 2's two
framings disagree by ~1.8× (0.377 vs 0.670) and *neither is the answer*: against
the generator the model is punished for not guessing arbitrary conventions,
against another agent it is rewarded for agreeing with itself. Stage 3 does not
settle this, because it measures *human*-authored surfaces. It removes the
question's urgency instead — see below.

**Overturned by stage 3 — that surfaces move the safe threshold into
usefulness.** Stage 1's *"At 0.96 the lift is 11× and it is free"* is a property
of `aliased`, whose intra-meaning dispersion happens to leave sibling surfaces
close enough to clear 0.92. Real human prose does not sit there. The whole
distribution tops out at 0.878, canonical and multi-surface alike, so §1.3's
conclusion — no threshold simultaneously safe and useful — is the correct
description of this corpus and **surfaces do not repair it.** The sentence
should not have been written in a form that implied it would generalize.

**Established by stage 3, and it points somewhere else — surfaces buy rank, not
service.** rank@1 improves in 4/4 cells with the negative control collapsing to
0.024–0.167, while served recall stays flatly zero. That is not a weaker version
of the original claim; it is a different mechanic. Nestor already has a place
where "the right answer, first, at 0.84" is worth something and a served match is
not required: **the review queue.** Ordering a human's queue is the use these
measurements support. Auto-serving is the one they refuse.

**Established — authored surfaces waste slots.** 98 of 300 meanings (33%)
received a variant identical to the canonical after normalization; a third of the
budget bought nothing. Measurable before sealing, so a dedup check at authoring
time recovers it.

#### Still untested

- **Human-authored probes against *model*-authored surfaces.** Stage 3 pairs
  human with human; stage 2 pairs model with model. The cell that resolves the
  0.377/0.670 gap — a person's queries against Claude's aliases — is still empty,
  and it is now one bench run away rather than a research project.
- **Name-shaped human aliasing.** `terpsi-music`'s aliases are *definite
  descriptions* — "the sensitivity ladder", "the eight text-only checks" —
  which is a different linguistic object from `AWS`/`Amazon Web Services`, §3.1's
  motivating case. Descriptions share almost no characters with the canonical, so
  a character-similarity matcher is close to the worst possible tool for them.
  **The 0.000 recall may be a fact about descriptions rather than about human
  aliasing**, and a corpus of human-written *name* variants would separate the
  two. Until then stage 3's negative result is scoped to the case it measured.
- **Whether ranking is enough.** If the mechanic is queue ordering rather than
  serving, the number to measure is not recall at a threshold — it is how far a
  reviewer scrolls. Nothing here measures that.
- **Who pays.** Authoring costs a model call, and if a human seals anyway,
  surfaces are review surface too — five rows to check instead of one. Sharper
  now that the payoff is ranking rather than avoided review.

**Cost if it holds:** a paragraph of prompt at seal time, `entity.py` unchanged,
no new dependency, no vector smuggled through a SQL key. §3.3 becomes optional
rather than blocking — **for the ranking use.** For serving at a safe threshold
on prose-shaped aliases, stage 3 says surfaces are not a substitute for §3.3 and
the two are no longer alternatives to each other.

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

### 4.3 The 60-second demo — **shipped, except the recording**

Highest-leverage missing artifact. An AI gets something wrong; a human corrects
it **once**; it is right forever after, with a receipt that cannot be forged.
Then tamper with the ledger and watch the chain refuse. That is the entire
product in one loop, and it lands on an engineer and a compliance officer for
different reasons.

No longer blocked on §5.1 — `nestor ui`, `nestor ask` and `nestor serve` all
exist, and two screens carry the loop with no explaining: a near-match returning
`~ draft` because it is under the cutoff, and a forged row scoring **1.000**
returning `! pending`.

`demo/sixty_seconds.py` is the script: eight beats, the exact phrases that
produce each outcome, paced for a recording and `--fast` for CI. What is left is
literally the screen capture.

One beat is worth defending, because it is the one a demo usually leaves out.
Between the near miss and the forgery, the script asks for "sixty days" against
a phrase sealed for "thirty days" — which scores 0.96 and **is served, wrongly**.
Showing it is the point: §4.4's argument is that admitting a measured failure
rate is stronger than claiming accuracy, and a demo that only shows the good
case is exactly what a compliance buyer has learned to distrust. It lands
pointing at `bench/`, `nestor calibrate` and the rejection signals — the three
things that exist to answer it.

Every beat asserts what it narrates and the script exits non-zero if a claim
does not hold, so it cannot rot into a lie between recordings. A test runs it.

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

### 5.3 Ledger verification is once per process — **verified; the tail closed**

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
on every render, so the *reading* is live — but nothing refused an append after
the first one, and that was a realistic window rather than a theoretical one.

**The tail half is closed.** Each append now records where its own line landed
and that line's hash; the next one re-reads from there, requires its own last
entry to still be present and unchanged, and requires anything appended since —
by this process or another — to chain onto it. The cost is the bytes written
since the last append, not the file, so this is affordable in a way
re-verification is not. It runs in the preflight as well as under the append
lock, because a refusal that arrives *after* the caller's store write leaves a
sealed row with no trail.

What it does not cover, and the docstring says so: an edit to a line older than
the checkpoint. That still needs the full walk. The checkpoint is the cheap
guard on the part of the chain being written right now, not a replacement for
`verify()` — a periodic or TTL'd full re-verification is still open.

One subtlety worth recording, because it was a flake before it was a fix: the
preflight holds no lock (it cannot — its job is to answer before the caller
commits), so it must not read a line another thread is flushing and call the
chain broken. It checks only the checkpoint line, whose bytes were fsynced
before its offset was recorded; the full tail walk runs again under the lock.

### 5.4 There was nowhere for the human to sit — **shipped**

*Was: every surface was a library surface. The reviewer worked the tier-2 queue
by typing `graduate_segment` into a REPL; the curator browsed the memory through
`Curator`. For a system whose entire claim is that a human checked the answer,
being the human meant writing Python.*

`nestor.ui` — stdlib only (`http.server` plus one inlined page), so the zero
runtime dependencies hold — with five views: **Queue** (the segments the cascade
left for review), **Memory** (the curator's list, provenance and revocation),
**Ask** (run the cascade and see the state that came back, with the ranked
candidates behind it), **Signals** (below), **Ledger** (`verify()`'s verdict
beside the chain).

Decisions worth keeping:

* **Ask is the demo.** Two screens carry the product with no explaining: a
  near-match scoring 0.875 comes back `~ draft` because the cutoff is 0.92, and
  a forged row scoring **1.000** comes back `! pending` — sealed, not servable,
  by mallory. §4.3's 60-second demo is that second screen.
* **The Memory list admits it has a second page.** It stopped at 50 rows with
  nothing to say it had. "No pairs match" and "no more pairs on this page" read
  identically when the page is the only thing you can see, so a curator whose
  memory is larger than one page was looking at an arbitrary slice of it and had
  no way to know. It asks for one row more than it shows, which is how it learns
  there is a next page — the Storage Protocol has no count, and adding one for a
  pager would be the wrong trade.
* **Signals is for the questions no single row answers.** Seals somebody
  overwrote (which the store keeps no trace of at all — only the ledger does,
  and `add_pair` refuses a different verifier's overwrite, so an entry there
  means a human overruled another human), plus §1.2's two rejection aggregates.
  Three findings the package recorded and nothing displayed.
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

**The in-process half shipped** (§5.3): every append remembers the line it
wrote and refuses to continue if that line has changed, so while an entry is the
tip, the process that wrote it still knows what it said. That is the closest
thing to a local fix there is — it survives the entry being newest, but not the
process restarting.

Still open: a checkpoint written to a sidecar the ledger's writer does not own,
which is the only version that survives a restart, and which is `nestor.frank`
again in miniature — the fix is not local, it is "someone else remembers."

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

### 5.8 A verifier was a string anybody could type — **shipped**

*Was: everything about trust here was rigorous except the name. A seal was bound
to a key the store does not hold — but ONE key for the whole deployment, so a
valid signature proved the key was present and nothing about who used it.
`verifier="rita"` was a string anyone who could reach the process could type,
and "a human checked this" meant "somebody with access typed a name."*

`nestor.keyring` gives each verifier their own key. A seal's signature verifies
under the key of the verifier it *names*, or not at all — so moving a real
signature onto a more senior name in the database stops working, and a name the
keyring does not know cannot seal, raised from `sign_seal` before `add_pair`
touches the store. The UI's "acting as" box becomes a sign-in: a verifier
presents their key, and the typed name is then ignored entirely, because a field
that must match something already known is only a way to produce confusing
errors.

**Revocation is the part that needed a decision, and the decision was not to
guess.** An HMAC carries no timestamp, so a signature cannot distinguish "sealed
by rita last March" from "forged last night by whoever took rita's key". So the
operator says which happened. A *rotated* key makes no new seals and keeps its
old ones — nobody else ever held it, so they are still that person's
verifications. A *compromised* one makes no new seals and loses its old ones,
which land in `Curator.unverifiable()` for re-verification rather than being
deleted. Picking either automatically is wrong every time: one silently retires
a departed colleague's entire body of work, the other serves a thief's
forgeries as human-verified.

Opt-in throughout, and the shared-key deployment is byte-for-byte unchanged
without it. Migration is `nestor keys add NAME --adopt-shared-key`, after which
pre-keyring seals keep serving and report as `legacy` — verified by somebody
here, not attributable to a person, which is what they always were.

A rejection by an unregistered name is still recorded and honored, and reported
as unsigned; refusing to record a "no" is the one direction rejection must not
fail in, and it is the same asymmetry §1.2 already argues for signatures.

Still open, and the same follow-on Nestor#2 named: the asymmetric upgrade. A
shared secret proves possession of a key, not the presence of a person, and the
process necessarily holds the keys it verifies against. Ed25519 or a Biscuit
capability goes through the same `signing.sign_seal(..., key=)` seam.

---

## 6. Agent log

Implementation-session follow-ups. Same status words as the table at the top;
nothing here is a commitment until someone picks it up.

### 6.1 Semantic smoke test behind NESTOR_SEMANTIC_TEST — **shipped**

*Proposed 2026-07-31 after §3.3 shipped; implemented same session.*

Integration test, off by default: set environment variable
NESTOR_SEMANTIC_TEST=1 (and ``pip install nestor[semantic]``) to download the
default `fastembed` model and assert `SemanticMatcher.score("AWS", "Amazon Web
Services")` beats `StringMatcher` on the same pair (IDEAS §3.1's motivating
case, ~0.273 on character ratio). See ``tests/test_semantic_integration.py`` and
``nestor.semantic_matcher.integration_tests_enabled``.

### 6.2 Batch-embed in `lookup` / `best_sealed` — **shipped**

*Proposed 2026-07-31 after §3.3 shipped; implemented across PR #22 and follow-up.*

Matchers that implement ``scores_against`` (notably :class:`~nestor.semantic_matcher.SemanticMatcher`)
embed uncached query and candidate surfaces in one ``fastembed`` call per scan.
:func:`~nestor.memory.lookup` and :func:`~nestor.memory.best_sealed` share
``_raw_score_sims`` so both paths batch the same way; rows with no
``source_text`` still score through norms only. Persisted vectors per row are §6.4.

### 6.4 Persisted row embeddings (`tm_embeddings`) — **shipped**

*Follow-up to §6.2, 2026-07-31.*

:mod:`nestor.sqlite_store.SqliteStore` stores one vector per ``(pair_id,
model_name)`` with a ``source_sha`` so a changed surface is not served from a
stale embedding. :meth:`~nestor.semantic_matcher.SemanticMatcher.scores_against_for_rows`
hydrates the in-process LRU from the store before batching and writes back after
embed. :func:`~nestor.memory.add_pair` drops stored embeddings when the raw
``source_text`` for an existing normalized key changes, and
:func:`~nestor.memory.reject_pair` drops them outright; ``tm_embeddings`` has a
foreign key onto ``tm_pairs`` with ``ON DELETE CASCADE``, so nothing is left
behind by a delete either. Other ``Storage`` implementations are unaffected
(duck-typed via :func:`~nestor.embedding_store.supports_embedding_store`).

**A cached vector is signed, because it is a serve input.** ``source_sha``
catches *staleness*; it cannot catch *tampering*, being a digest of text in the
row next to it. Under ``SemanticMatcher`` the score comes from the vectors, so a
store-writer who cannot forge a seal could otherwise still choose which queries
a sealed row answers — Nestor#2 one object over. Each entry therefore carries an
HMAC over ``(pair_id, model_name, source_sha, vector)``
(:func:`~nestor.signing.sign_embedding`), and one that does not verify is
recomputed rather than used: a bad entry costs latency, never an answer.
:func:`~nestor.signing.cache_trust` decides the policy — ``"unsigned"`` with
signing off (the store is already fully trusted), ``"signed"`` with a key, and
``"unavailable"`` when signing is on but no deployment-wide key exists, in which
case the cache is disabled in both directions and says so once.

Persistence is also opt-out per matcher (``SemanticMatcher(persist=False)``,
threaded from ``--read-only`` on both surfaces): matching is a read, and it was
writing one row per candidate *per serve* until hydration started reporting
which ids it had already filled. Measured over 20 rows with the in-process LRU
cleared each time: 20 UPSERTs on the cold serve, **0** on every serve after.

### 6.3 Bench token matchers: `score` + harness `match_similarity` — **shipped**

*Proposed and implemented 2026-07-31.*

`TokenJaccard` / `TokenOverlap` implement `score(raw_a, raw_b)`; `bench_accuracy.best_match`
takes raw probe text and calls `nestor.matcher.match_similarity` so stage-4
surfaces-human runs use the same path as production `lookup`, not difflib over
sorted norms.
