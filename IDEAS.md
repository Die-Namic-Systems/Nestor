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

**Review lessons.** Durable checklist from PR review rounds (persistence, audit,
threading, config): [`docs/code-review-lessons.md`](docs/code-review-lessons.md).

**Fleet map.** Open IDEAS items vs existing repos (willow-mcp, SAFE store,
oakenscrolls, bench corpora): [`docs/fleet-integration-map.md`](docs/fleet-integration-map.md).
Local checkout and commands: [`docs/local-fleet.md`](docs/local-fleet.md).

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

### 1.4 Seal staleness and quorum — **measured**, design **open**

Every seal is equally authoritative forever, and one verifier is enough. Neither
is obviously right for a regulated buyer. Worth considering: seal age surfaced
in provenance; a `weight` that decays; N-of-M verification for high-stakes
domains. ~~The ledger already records who sealed what and when, so the data is
there — nothing consumes it.~~

> **Corrected in place, 2026-08-06**, by trying to argue the entry through:
> [`docs/seal-staleness-and-quorum.md`](docs/seal-staleness-and-quorum.md). The
> ledger records who sealed what and when for the **first** seal. It records
> nothing about agreement. Two verifiers sealing one source with the same target
> produces one row, one chain entry, and no trace of the second person —
> measured, on a file-backed store with signing on. `memory.py:374` writes only
> when the row is not already sealed *or* the target differs, so concurrence
> satisfies neither arm and returns the stored row to the caller as if it were
> theirs.
>
> So the premise "the data is there" is false for quorum specifically, and it is
> the load-bearing premise: N-of-M cannot be computed from a history that was
> never written, and no migration can backfill countersignatures that were
> discarded. See §6.26.

The memo's three conclusions, in brief:

* **Decay must not live in `weight`.** The column is written by every seal path,
  read by nothing in ranking, and absent from `signing._message` — so a decayed
  weight is unsigned mutable state anyone with write access can reset while
  every signature still verifies. Age should be derived from the ledger's
  timestamp, which the chain covers, not stored beside the data it governs.
* **Neither staleness nor quorum should change what is served silently.** A
  decay multiplier turns "a human checked this" back into a confidence score —
  the exact thing the README's first paragraph refuses — and withdraws a
  verified answer on a date nobody chose, leaving the ledger with no decision to
  point at. Staleness belongs in the curator queue, shaped like `reopen_when`.
* **Sub-quorum is not a weaker seal; it is a draft.** That keeps the guard in
  the one place a row becomes sealed rather than in every serving path, and
  avoids inventing a "70% sealed".

Still open, and named as open in the memo: how old is too old, whether any buyer
actually asks for either, and the fact that a quorum of HMACs is a quorum only
against outsiders until `TODO.md` §1 lands.

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

### 2.4 Connection-per-operation — **shipped (file-backed reuse)**

`SqliteStore._db()` used to open and close a fresh connection for every call on
file-backed databases, and `add_pair` additionally calls `memory_init()`, which
replays the whole schema script each time. I hypothesised this dominated ingest
and **was wrong** — stubbing `memory_init` out made things marginally *slower*,
i.e. it is noise at this scale. Recorded here so nobody re-derives the same dead
end.

**There is now a threaded consumer.** `nestor.ui` serves from a thread pool; the
in-memory store keeps one shared connection behind an ``RLock``. File-backed
stores keep a **bounded pool of idle connections** (``_POOL_MAX``, 8) under
``PRAGMA journal_mode=WAL``, so concurrent reviewers reuse connections instead of
paying connect/teardown on every API call. Measured, 3000 single-row reads:

| | time |
|---|---|
| a fresh connection per operation | 0.857s |
| a persistent connection per thread | 0.042s |
| a bounded idle pool | 0.045s |

The pool exists rather than a connection per thread because of how the threads
arrive. `ThreadingHTTPServer` under HTTP/1.1 keep-alive makes one thread per TCP
connection — a reload, a reconnect, a monitoring probe — and a connection bound
to a thread outlives it: `sqlite3.Connection` sits in reference cycles, so it is
freed by the *cyclic* collector rather than promptly, and nothing about running
out of file descriptors makes Python collect. Under ``ulimit -n 256`` the
per-thread version failed after **340 requests** with ``unable to open database
file`` where connection-per-operation ran 2000 clean; that also refuses seals,
because the ledger needs to open a file too. The pool keeps essentially all the
speed and caps descriptors at the pool size: anything borrowed beyond it is
closed on return, not accumulated.

``close()`` checkpoints the WAL into the main file and retires the store; using
one afterwards raises ``StoreClosedError`` rather than quietly reopening, which
for ``:memory:`` used to mean answering "0 sealed" from a fresh empty database.

Still open: skipping redundant ``memory_init`` schema replay per connection
(measured as noise for ingest; may matter only at huge table counts).

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

### 4.2 The category is AI verification, not translation memory — **shipped**

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

**Shipped 2026-08-06** as a README section, *The category — verification, not
translation memory*, placed directly after *The mechanic* and linked from
Contents. It carries the TM-is-a-cache contrast, the permanent-capital curve,
"Verified once, served forever", and both halves of the wins/loses pair with the
losing half pointing at the §2 numbers rather than glossing them.

**One clause from this entry was deliberately not shipped:** *"which nobody has
solved."* It is a claim about every other system in the category, it was not
checked, and there is no way to check it — which makes it precisely the kind of
sentence this repo spent 2026-08-05 learning not to publish. The README makes
the checkable claim instead: that this is a question regulated buyers are being
asked. What Nestor answers is a fact about Nestor; what everyone else has failed
to answer is not.

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

### 4.4 The bench is a marketing asset — **shipped**

"We are accurate" is a claim a compliance buyer knows is a lie. "Here is our
measured false-verification rate, here is the dial that sets it, here is the
harness — run it yourself" is stronger *because* it admits a failure rate.
Publishing `bench/results/` is a differentiator, not an exposure.

**Shipped 2026-08-06** as *Why the numbers are published*, a subsection closing
*Accuracy, and how to measure yours* — which is where the argument belongs,
because by that point the reader has just been shown a table where the default
threshold false-seals 16.4% of the time. The section says that was on purpose.

Each of the three things the pitch names is a path in the repository, and the
section says which: the harness is `bench/`, the dial is `SEAL_THRESHOLD` plus
`nestor calibrate`, the numbers are the committed `bench/results/*.json` with
parameters, environment and git revision attached. It also keeps
`"complete": false` in view — a prefix is not an answer, and a marketing number
would not bother to preserve the distinction.

**No landing page, and no new bench code**, which is what the fleet map's
"one landing page **or** README section" left open. The README section was the
cheaper half and it is the one a buyer already reading the repo will reach. The
recording in §4.3 is still the missing asset, and it is still nobody's code
change.

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
``verify()`` — a periodic or TTL'd full re-verification is now available via
``NESTOR_LEDGER_VERIFY_INTERVAL_SEC`` and :func:`~nestor.cascade.ledger_verify_interval_sec`.
``0`` keeps the original once-per-process cache (batch jobs). Positive values
re-walk on append/preflight after that many seconds; negative values walk every
time. ``nestor.ui`` defaults to five minutes when the env var is unset, because
it is the long-lived process this gap was written for.

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

Memory paginates (``/api/pairs`` with ``offset`` / ``limit+1``; UI pager) and the
Signals tab surfaces ``Curator.replaced_seals`` via ``/api/replaced-seals``.

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

Corrected in place, twice now. First: this used to say the asymmetric upgrade
was still open. It shipped (Ed25519, `[keys]` extra, decision `0074`) — a
keyring holding only a peer's **public** key can verify their seals while
being structurally unable to sign as them, which a shared secret can never
do. What Ed25519 alone left open was that the *signing* instance still holds
every one of its verifiers' private keys, so its operator could still forge
as anyone whose key lives there. The server-side half of closing that shipped
next (decision `0077`, Nestor#17): `memory.add_pair(..., seal_sig=...)`
accepts a signature a client already produced and only verifies it, never
signs it, so a public-only entry can still seal, given a valid signature.

Second: this then said the remaining piece was the browser page itself. It
has shipped too (`nestor/ui_page.py`, decision `0078`, §6.93) — WebCrypto
Ed25519 generated non-extractable in the browser, enrolled by printing the
`nestor keys add ... --public HEX` command for a human to run, and a seal
signed client-side against a message the human has actually seen before
signing it. Nestor#17's four-cell table is now fully closed.

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

### 6.6 TTL'd ledger re-verification on append — **shipped**

*Follow-up to IDEAS §5.3, 2026-07-31.*

:func:`~nestor.cascade.ledger_verify_interval_sec` / ``NESTOR_LEDGER_VERIFY_INTERVAL_SEC``
control how often the full chain walk runs on seal/reject preflight and append.
``nestor.ui`` sets a five-minute default when the env var is absent.

### 6.5 File-backed SQLite: a bounded WAL connection pool — **shipped**

*Follow-up to IDEAS §2.4, 2026-07-31.*

:mod:`nestor.sqlite_store.SqliteStore` reuses WAL connections from a capped idle
pool on disk paths (``:memory:`` unchanged). Numbers, and why a pool rather than
one connection per thread, are in §2.4. ``tests/test_sqlite_store.py`` covers
concurrent ``add_pair``, the descriptor ceiling under 360 request threads, the
``close()`` checkpoint from a thread that did not do the writing, and the refusal
to answer from a closed store.

### 6.7 Hot checkpoint / backup while the store is open — **shipped**

*Proposed 2026-07-31 after PR #24 WAL review; shipped same arc.*

``nestor db checkpoint`` flushes WAL in place; ``--out`` writes a consistent copy
via ``VACUUM INTO`` and, by default, copies the hash-chained ledger to
``<basename>.ledger.jsonl`` beside it (``--no-ledger`` opts out). Operator notes in
``docs/local-fleet.md``.

Both files are written through a ``.partial`` and ``os.replace``, so a failed
backup leaves the previous one intact rather than deleting it in favour of one
that never arrived. Both names are also *claimed* whether or not a given run
writes the sidecar: a chain left from an earlier backup beside a freshly written
database is worse than no chain, because the pair looks matched and the store is
the one that is ahead — sealed rows whose ledger entries are missing, which is
the state :func:`~nestor.memory.add_pair` refuses to create at seal time. So a
stale sidecar blocks the run, and ``--force`` removes it along with the database
it described.

### 6.8 Skip redundant ``memory_init`` schema replay — **shipped**

*Follow-up to IDEAS §2.4.*

Each ``add_pair`` still runs the idempotent schema script on that thread's
connection. ~~Measured once as noise for ingest; may matter at very large
corpora.~~ Needs a per-connection "schema ready" flag before changing
behaviour.

> **Corrected in place, 2026-08-06.** "Noise" does not survive being measured
> a second time. On a bare file-backed ingest loop — `add_pair` only, no draft
> engine in the path — replaying the schema cost **0.556 → 0.395 ms/op, −28.9%**
> (best of 3, N=4000, before/after on this machine). A monkeypatched
> upper bound taken before any code was written said 28–36% across four runs at
> N=2000 and N=6000, so the shipped fix captures very nearly all of the
> available win.
>
> Both readings are probably true of what they measured. The original note says
> *noise for ingest*, and in an ingest where a model authors each draft the
> store is not the constraint — a schema replay disappears behind a network
> round trip. The claim that did not hold is the unqualified one. What it costs
> is a third of the store's own time, and `nestor.memory` calls `memory_init()`
> at the top of a dozen public functions, so it is not only `add_pair` paying.

**The flag lives on the connection, and that is the whole design.** §6.8 asked
for a per-connection flag and the interesting part turned out to be *where a
per-connection flag can live*. `sqlite3.Connection` supports neither attribute
assignment nor weak references, which leaves a store-held set keyed either by
the connection — pinning it open, defeating `_POOL_MAX` (§6.5) — or by
`id(conn)`, which CPython reuses after a free. A recycled id marks a **fresh**
connection as already-initialized and hands a caller a schema-less database:
a condition that outlives the thing it describes, which is the shape
`CLAUDE.md` and §8–§9 of the review lessons keep naming. Subclassing
`sqlite3.Connection` makes the flag die exactly when its connection dies, so
there is no interval in which it can be wrong.

> **Not quite, and an adversarial review of PR #45 found where.** The first
> version put `schema_ready = False` on the class and read it with `getattr`.
> Setting `_Conn.schema_ready = True` then made every *brand-new* connection
> claim to be initialized: reproduced, `memory_init` on an empty database
> returned having created **zero tables**. That is the same defect one level up
> — a value that outlives and misdescribes the connection it speaks for — and it
> was reachable by anyone "optimising" the class, not by an attacker.
>
> Deleting the class default is the obvious fix and is not sufficient: a class
> attribute still shadows a missing instance one, so `getattr` would keep
> finding it. The default is gone **and** the read goes through
> `conn.__dict__`, which takes the class off the lookup path entirely — nothing
> but a connection can answer for that connection. Removing the interaction
> rather than adding a condition, which is what the paragraph above should have
> done the first time.
>
> Two gates, both failing against the reviewed revision:
> `test_a_class_attribute_cannot_answer_for_a_connection` (behavioural) and
> `test_conn_declares_no_schema_ready_default` (shape). The second passed at
> first for the wrong reason — the behavioural test's cleanup did an
> unconditional `del`, removing the very class default the shape guard exists to
> detect. Fixed to restore exactly what it found, which is not the same as
> deleting.

`init_db` deliberately does **not** set it. It applies a strict subset — no
`_ensure_lineage_schema` — so a connection it touched still owes the ALTERs
that bring a pre-lineage database up to date. Marking ready there is the
cheapest wrong version of this fix, and `test_init_db_does_not_excuse_memory_init`
is a **guard** against it: it passes before the change as well as after,
because before it there was no flag to set wrongly.

Three tests, one of them a gate: `test_memory_init_does_not_replay_the_schema_on_a_warm_connection`
fails against the unfixed revision and passes after. The other two pass on both
sides and are named as guards above.

### 6.9 Subprocess test: UI refuses bad ledger interval env — **shipped**

*Follow-up to PR #24.*

``tests/test_cli.py`` runs ``nestor.ui`` in a subprocess with
``NESTOR_LEDGER_VERIFY_INTERVAL_SEC=5m`` and asserts exit 2 before the DB opens.

### 6.10 Seal age in provenance (display only) — **shipped**

*Pointer to IDEAS §1.4.*

Memory list chips show **relative age**; full ISO timestamp on hover (``title``).
Decay/quorum policy remains §1.4.

### 6.11 Decision memory — lineage joined to rejection — **partly** (steps 1–2 shipped)

*Proposed 2026-08-05, carried over from the SAFE store; design doc in this
repo:* [`docs/decision-memory.md`](docs/decision-memory.md).

Nestor holds two of a decision record's four verbs (made, rejected) and lacks
two (modified, affects-future): re-sealing destroys the prior decision
(`test_seal_replacement.py` says so), and no edge relates any pair to any
other. The doc proposes a fourth optional storage capability
(`supports_lineage`), `superseded_by` + a partial unique index that keeps the
concurrent-seal race guard for live rows, `reason` on pairs, `reopen_when` on
rejections (never vs. not-yet), signed `decision_edges`, and a
`DecisionMemory` recipe mirroring `entity.py` with `constraints_on()` as the
traversal. Build-order steps 1–2 stand alone as a fix to the destructive
overwrite. Gate: bench whether the matcher recognizes a re-worded decision
before any CI gate trusts `constraints_on`.

*Steps 1–2 shipped 2026-08-05* after the design was proven standalone in the
SAFE store's playground (`apps/aristarchus`, 33 tests) and its N1 matcher
bench ran (string/token/word-vector matchers falsified; fastembed viable at
0.90–0.95, `wrong_key` 0 throughout — advisory yes, fail-closed no):
`tm_pairs.reason` + `tm_rejections.reopen_when` (N4/N5),
`supports_lineage` + `tm_pairs.superseded_by` + the partial unique index +
`memory.supersede_pair` (N2/N3), ledgered as `supersede`, with pre-lineage
databases migrating in `memory_init` and superseded rows excluded from
bundles. Still open: N6–N9 (edges, DecisionMemory recipe, the gate) and
carrying `reopen_when` in bundles (needs a BUNDLE_VERSION bump — it is not
in REJECTION_FIELDS, so it does not travel yet).

### 6.12 The detection kit as gates, not advice — **measured**, build **open**

*Proposed 2026-08-05, same session as §6.11.*

Sagan's Baloney Detection Kit (*The Demon-Haunted World*, ch. 12) shipped as a
book chapter while the injection side shipped as infrastructure. How much of
the kit's nine tools can become **exit codes** the way `nestor ledger verify`
made "is the chain intact?" one: tool #1 (independent confirmation) is the
witness; #4/#5 (multiple hypotheses, don't trust it because it's yours) are
`nestor decision check` + verifier-differs-from-author; #7 (every link holds)
is the hash chain; #9 (falsifiability) is `reopen_when`. ~~Unmapped: #2, #3,
#6, #8, and the fallacy catalog.~~

> **Worked through 2026-08-06** —
> [`docs/detection-kit-as-gates.md`](docs/detection-kit-as-gates.md). Four of
> the nine are already exit codes, two are blocked on data Nestor discards, and
> three cannot be gated at all. Three claims in the paragraph above are
> corrected in place by that memo:
>
> * **#6 is not unmapped.** `cmd_calibrate` already returns
>   `EXIT_ANSWER_IS_NO` when no cutoff on your corpus meets the target rate —
>   quantification failing a build rather than advising one. Seven commands
>   return that code, not one.
> * **#3 is not unmapped.** Per-verifier keys plus `NESTOR_REQUIRE_SEAL_KEY=1`
>   are the mapping, with a limit that has to be said out loud: Nestor gates
>   whether an authority is *named and bound to a key*, never whether it is
>   *knowledgeable*. Treating the first as evidence of the second is the fallacy
>   the tool names.
> * **`nestor decision check` does not exist.** The subcommand list is `ask,
>   resolve, check, match, export, db, import, ledger, calibrate, keys,
>   rejections, stats, ui, serve`. §6.11 records decision memory as **partly**
>   shipped and the CLI surface is one of the parts that was not, so #4's
>   mapping was written against a planned command.
>
> And #5's mapping — verifier-differs-from-author — is right and not
> implementable: **there is no author field.** Measured, a draft entered with no
> verifier and then sealed by `rita` is accepted, with nothing recording whether
> rita also proposed it.
>
> **#8 is the useful row.** Occam's razor is permanently ungateable: there is no
> mechanical test for *simpler*, and a check claiming to enforce parsimony would
> be a number standing in for a judgement — the exact substitution the kit is
> written to catch. A gate for #8 would be baloney about baloney detection, and
> the right output is that sentence rather than a metric nobody can defend. #2
> is worse than unmapped: `ConflictingSealError` makes recorded disagreement
> impossible by design, so debate happens where the system cannot see it.
>
> **The pattern worth naming:** #1 and #5 are blocked the same way, and it is
> the same way §1.4 and §6.26 are blocked. Nestor records *decisions*
> thoroughly and *the process that produced them* not at all. That is a coherent
> choice — it is why the ledger is small enough to verify — and it puts a whole
> class of detection-kit gates out of reach until some of that process is
> written down.
>
> One new gate is proposed and not built: **a test that cannot fail is a
> description**, mechanized — run a change's new tests against `HEAD~1` and fail
> if none of them fail. It needs no new data and gates the claim this repo makes
> about its own work most often. Not built because the exemption rule (pure
> guards, docs changes, behaviour-neutral refactors) wants designing before the
> gate does.

### 6.13 Ground rule 2b made executable — **shipped**

*Found and closed 2026-08-05, looking for where the product's voice policy
actually lived.*

`nestor/engine.py` stated the output-voice rule twice — as prose in the module
docstring, and as a retyped literal inside `ClaudeEngine._system` — and
executed it in neither. `tests/test_docs.py` had already named that failure
mode for the README (*"a claim nobody executes is a claim nobody maintains"*);
it applied here to a rule governing what a model is told about whose voice to
use. Two copies and no check is not redundancy, it is a pending disagreement.

The larger half was structural. The rule lived on one class while the **tier**
is what it governs, and the engine slot is pluggable by design — `get_engine`
dispatches and `OfflineEngine` is documented as the eventual local-model slot.
The next engine to address a model would have composed its own prompt with
nothing it was obliged to include: §1.6–§1.8's shape exactly, a guarantee held
by convention at one call site, pre-figured rather than already bitten.

Shipped: `engine.VOICE_RULE` as the single definition; `engine.system_prompt`
promoted to module level as the one prompt builder, with the rule unconditional
inside it and no parameter that could disable it; `Draft` documented as
carrying no field an engine could claim verification with, which is why 2b's
second half was never at risk. `tests/test_engine.py` pins all of it, mirroring
rather than importing the constant per `test_ledger_kinds.py`'s rule, and each
gate was proven against its counter-case (reword the rule, drop it from the
builder, add a `voice=` parameter, retype it elsewhere, grow a `verified` field
on `Draft`, and a new engine calling `messages.create(system=...)` with its own
string — the last caught by an **AST** gate over `nestor/*.py`, after a first
attempt that grepped the source flagged the phrase `system=` inside a docstring
about the rule).

Still open, and deliberately not invented here: **the ground rules themselves
live offstage.** "Ground rule 2b" is cited by number in this repo and the
numbered set is nowhere in it — `grep -rn "ground rule"` returns exactly the
one docstring. 2b's *text* is now defined in `VOICE_RULE`, which is the half
Nestor is entitled to own; whether the fleet's rules should be carried here
(the way `docs/decision-memory.md` was carried home from the SAFE store) is the
operator's call, not a code change. Until then a reader meets a rule cited by a
number that resolves to nothing.

### 6.14 Dogfood: this session's decisions fed through Nestor — **measured**

*Run 2026-08-05, feeding the §6.13 session's own decisions into the store. The
two defects it found are fixed in §6.15; the N1 measurement stands.*

Eight decisions from the ground-rule-2b session went in as **drafts** with
`reason` (N4), and four rejected alternatives as `tm_rejections` with `reason`
and `reopen_when` (N5) — three of the four are *not-yets*, carrying the
condition that reopens them. Nothing was sealed: the machine may propose and
may not confirm, so `nestor stats` reads `8 pair(s): 0 sealed, 8 draft` and the
seal queue is the operator's. Two things fell out of it.

**N1 reproduced in-repo, on real decision rows.** `docs/decision-memory.md`
gates N9 on "does the matcher recognize a re-worded decision"; §6.11 records
that bench running in the SAFE store's playground. It now has an in-repo
number. Exact wording scores **1.0000**. Re-worded, against `StringMatcher`:

| probe | right row | rank-1 row | served |
|---|---|---|---|
| exact | 1.0000 | itself | ✓ |
| "who owns ground rule 2b, the class or the tier?" | 0.8380 | itself | ✗ |
| "can callers turn off the voice rule?" | 0.3440 | *a different decision*, 0.4740 | ✗ |
| "why was the model id left alone?" | 0.3110 | *a different decision*, 0.3330 | ✗ |

None of the three re-wordings clears 0.92, and **two of three rank a different
decision first** — the `wrong_key` case §6.11 measured at 0 for fastembed. The
system still fails safe (below threshold, nothing is served), and that is
exactly the danger the design doc names: `constraints_on` returns silence, and
silence reads as "no constraint" rather than "I could not find it." The gate
holds — N9 must not be trusted on the string matcher.

**A review surface that misstates its own reason.** `nestor match` prints
`"{len(matches)} candidate(s) below {threshold}"` whenever `served` is false
(`cli.py:123`). Both halves can be wrong at once. `answer.match` fills
`matches` from `lookup(..., context_threshold=0.0)` — *unfiltered*, so they are
not "candidates below" anything — while `served` comes from `best_sealed`,
which filters by **status**. Feeding an exact query that scored **1.0000**
against a draft row printed `8 candidate(s) below 0.92`: the count is
unrelated to the threshold, and the one row that mattered was above it. The
true answer was "found it, it is not sealed." This is §1.9's shape in a
message rather than a query — the code answering a narrower question than the
one it was asked, and reporting the narrow answer as the whole one.

**A rejection with no `pair_id` does not travel.** Found by exporting the feed
above and reading the counts: `8 pairs, 0 rejections`, from a store holding
four signed, ledgered rejections. `reject_match` documents two ways to name
what is being refused — `pair_id` (the false-seal case) **or** `target_text`
(*"a raw engine draft with no pair yet"*) — and both are first-class, both
signed, both ledgered. But `portable.export_bundle` reaches rejections only by
walking `memory_rejections_for_pair(p["id"])` over the exported pairs, so the
`target_text`-only half is silently dropped. Proven directly: adding one
rejection that names a `pair_id` to the same store took the bundle from 0
rejections to 1 — that one, and still none of the other four.

This is §1.6–§1.8's shape once more, in the transfer path: a guarantee held at
one call site and a second kind of row that never reaches it. It lands hardest
exactly where §6.11 claims the most: *"Nestor's rejection table is already a
rejected-alternatives record… the half the git flow throws away is already
sitting in the schema, durable and signed."* It is — until you move it. A
rejected **alternative** usually never became a pair, which is precisely the
pair-less form, so decision memory's rejected-alternatives record is the part
of it that does not survive `export → import`.

### 6.15 Both §6.14 findings fixed — **shipped**

*Fixed 2026-08-05, same day. Regressions in `tests/test_findings_2026_08_05.py`;
15 of its 19 tests were observed failing against the unfixed revision, and the
four that passed are labelled as no-regression guards rather than offered as
gates.*

**The bundle.** `export_bundle` now collects rejections by **domain**, not by
walking the exported pairs — the walk could only ever reach rows with a
`pair_id`, and the rows it needed to reach are the ones that have none.
`SqliteStore.memory_list_rejections` is the new read, ordered `created_at, id`
so two exports of one store still agree and the digest stays an integrity
check.

Three decisions inside it are worth recording, because each had a wrong answer
that looked reasonable:

* **The new op is not in `_REJECTION_OPS`.** That tuple is all-or-nothing, so a
  fourth entry would report every host store implementing the existing three as
  having *no* rejection capability — turning a bug about short bundles into
  `reject_match` raising on stores that work today. Widening a capability must
  not be able to switch one off. It gets its own predicate,
  `supports_rejection_listing`, following `supports_lineage`'s precedent.
* **`BUNDLE_VERSION` is 2, and 1 is still readable.** `reopen_when` joins
  `REJECTION_FIELDS`, which changes the payload the digest is taken over — so
  `digest()` takes the version and hashes a version-1 bundle with version-1
  fields. Without that, upgrading this build would report a mismatch on bundles
  nobody had touched: the exact failure `_canonical` already exists to prevent,
  and the one that trains people to ignore the check.
* **A store that cannot list by domain still exports, loudly.** It falls back to
  the pair-keyed walk and warns that pair-less rejections are missing. A short
  bundle that looks complete is the defect; the missing method is not.

**The diagnostic.** `answer.match` gains a `reason`, computed in the library
rather than assembled in the CLI format string, naming which gate the query
actually failed: not sealed, suppressed by a rejection, rejected outright,
below threshold, nothing in the domain, or a seal whose signature does not
verify. It checks signatures **first**, where `best_sealed` checks them last —
that function defers the HMAC because it is expensive and a row that cannot win
need not be verified, while a reader should hear about a forged seal before a
note about drafts. The two agree on whether to serve; only the order of
explanation differs, and an earlier draft of this entry claimed they matched. The exact
query that scored 1.0000 against a draft now reads *"matched at 1.0, at or
above 0.92 — but nothing sealed: the best candidate is draft. Nobody has
verified this yet."* A served answer carries `reason == ""`, so the field can
never contradict the verdict.

One thing this does **not** fix: the empty-candidate case can mean "absent" or
"suppressed", and `lookup` drops rejected rows before scoring, so the reason
consults `rejected_ids` to tell them apart. That is a second read on a path
that already did one. It is correct and cheap at review-surface scale, and it
would want revisiting if `match` ever moved onto a hot path.

### 6.16 The audit of §6.15, and what a first fix misses — **shipped**

*Audited 2026-08-05 by an independent agent, adversarially, told not to trust
the commit message. Verdict on the first fix: **not safe to merge**. Five
defects, one of them a regression the fix itself introduced. All fixed;
regressions in `tests/test_findings_2026_08_05.py` under "the audit's finds",
8 of 10 observed failing against the first fix.*

**The regression, and it is the one worth remembering.** Replacing the
pair-keyed rejection walk with a domain walk removed a scope nobody had written
down. The old walk was bounded by the exported pairs, which *exclude superseded
rows* — so a rejection naming a superseded pair had never travelled. Under a
bare domain walk it travels carrying a `pair_id` the bundle deliberately does
not contain, and `rejected_ids` matches on `pair_id`. On a destination that
still holds that id live, importing the bundle **suppresses a sealed,
signature-verified answer while the successor pair that should replace it is
refused as a conflict**. The destination loses an answer and gains nothing.

That is the shape to carry forward: *a filter can be load-bearing without being
stated*. The pair-keyed walk was written to find rejections, and it was also —
silently, as a side effect of what it iterated — enforcing "a bundle never
references a row it does not carry." Replacing the mechanism kept the stated
purpose and dropped the unstated invariant. The fix now states it: a rejection
travels only if it names no pair, or names one in this bundle.

The other four:

* **One `limit` fed two reads.** `export_bundle(limit=)` capped pairs *and*
  rejections — different row types, read in opposite orders (`memory_list` is
  newest-first, the rejection walk oldest-first), so a shared cap truncated the
  two lists from opposite ends. Silently: `counts` reported the short number
  and the digest certified it. Now a separate `rejection_limit`, and hitting
  either cap warns.
* **The importer read the wrong field set.** `digest()` selected fields by
  version; `import_bundle` used version 2's unconditionally. So `reopen_when`
  could be added to a version-1 bundle *after* export, verify cleanly (v1
  hashing does not cover the key), and land in the destination store. The
  digest is explicitly not a signature, so this is hygiene rather than an auth
  break — but a check covering less than the importer consumes is the wrong way
  round.
* **The reason was classified from the display page.** `_why_not_served` read
  the top-8 shown to the reader, so a forged seal ranked ninth was invisible to
  the branch written to name forged seals — which then reported "nobody has
  verified this yet" while a row claiming to be sealed sat above the bar. The
  §6.14 defect, one layer down, in its own fix.
* **Half the rejection surface was reported as "nothing".** The empty-candidate
  guard consulted `rejected_ids` only, which reads `tm_rejections`.
  `reject_pair` writes `tm_pairs.status='rejected'` instead, so a pair somebody
  had explicitly refused came back as *"nothing in this domain matched at all"*.

Also corrected: three prose claims this file and the code made that were not
true — that the rejection ordering made the digest stable (it never did;
`digest` sorts by id itself), that the reason checks gates in `best_sealed`'s
order (it checks signatures first, deliberately), and that all branches had
been driven (one was unreachable, and is now gone).

**What the audit is evidence for.** Every miss sat immediately outside what the
first fix had just understood: it tested the defect it had in hand, on
single-row stores, and the superseded pair, the second row type, the tenth
candidate and the other way of saying no were each one step past that. Round
one's tests were not weak on their own terms — 15 of 19 genuinely failed
against the unfixed code. They were weak in scope, and scope is exactly what
the author of a fix is worst placed to judge. One of round two's own tests
initially passed against the broken code because it did not reproduce the
condition it named; that is the same failure again, one level up, and it is the
argument for the audit rather than against it.

### 6.17 The second audit, a second regression, and the shape that caused both — **shipped**

*Audited 2026-08-05 by a second independent agent. Verdict on §6.16's fix:
**not safe to merge**. Five more defects, one of them critical and, again, a
regression the fix itself introduced. All fixed; 12 regressions added, all
observed failing against the previous commit.*

**The regression.** §6.16 gave rejections their own `rejection_limit` and then
**defaulted it to `limit`** — the shared cap the same docstring calls the bug.
Layered on §6.16's `exported_ids` filter it produced the worst outcome of the
three rounds: pairs are read newest-first, rejections oldest-first, so under any
cap the two windows are disjoint and **no pair-bound rejection travelled at
all**. Measured against both earlier revisions on one store:

| revision | `limit=5` | rejections carried |
|---|---|---|
| `origin/master` | 5 pairs | 5 |
| first fix | 5 pairs | 5 |
| second fix | 5 pairs | **0** |

**The shape, which is the entry's real content.** Three successive fixes, each
one a *filter interacting with the filter before it*:

1. a pair-keyed walk — complete for pair-bound rows, blind to pair-less ones;
2. a domain walk — complete for both, and blind to the scope the first had for
   free, so it carried rejections against superseded pairs;
3. a domain walk **plus** an `exported_ids` filter — correct until a cap made
   the two windows disjoint.

Each fix added a condition to a mechanism that was answering two questions at
once. The answer was to stop adding conditions: **two walks, each bounded by
construction**. The pair-keyed walk cannot return a rejection whose pair is
absent — it iterates the exported pairs. The domain walk is asked only for the
pair-less rows, where nothing can dangle. Union them. The invariant "a bundle
never references a row it does not carry" now holds because of what is read,
not because of what is filtered out afterwards — and `exported_ids` deleted
itself, which is how you know.

The other four:

* **The invariant was export-only.** Import re-ids a pair onto the
  destination's id while the rejection keeps the source's, so a legitimately
  carried "no" landed inert and the destination's own next export dropped it —
  surviving one hop, dying on the second. Now remapped through an `id_map`
  built *before* the branches, because four of them `continue` and the no-op
  branch (same answer both sides, nothing written) is both the easiest to
  forget and the commonest in a real re-import. And the read side now refuses a
  dangling `pair_id` outright, reporting it: a bundle from the previous build
  could still do the documented harm, and taking the file's word is the mistake
  `seal_sig` exists to refuse.
* **`reject_pair` was fixed for the exact key only.** One character off
  (`"a bad mappingg"` scores 0.963) and the sentence the fix removed came
  straight back. The reported case was fixed; the class was not. Now scored
  rather than key-matched — which also fixes the numeric matcher naming an
  unrelated pair, since every unparseable input normalizes to one NaN sentinel.
* **`>=` could not tell "exactly full" from "truncated"**, so complete exports
  warned. Ask for one more than the cap.
* **`partial_rejections` was read by nobody** and was not set in the case its
  own comment argued for. Now set on every short path and surfaced in
  `verify_bundle`'s detail and the import report.

**What three rounds of this are evidence for.** Every regression was introduced
by the fix for the previous one, in the same function, by the same move: adding
a condition instead of removing an interaction. The tests did not catch them
because each round tested the defect it had just understood — and, twice, a
round-N test *passed against the broken code* because it did not reproduce the
condition it named (a forged row that scored 1.0 and so never left the display
page; a numeric pair stored with the default matcher, so the sentinel never
collided). Both are now measured and asserted. An author cannot audit their own
scope; that is not a discipline failure, it is what scope means.

### 6.18 What Nestor says about the §6.15–§6.17 rounds — **measured**

*Run 2026-08-05, feeding the three fix rounds back through the store. The
output is mostly a refusal, and the refusal is the finding.*

The rounds have the one thing §6.14's feed did not: **lineage**. One question —
*how does `export_bundle` collect rejections?* — answered four times, each
answer superseding the last. That is exactly what N2/N3 shipped `supersede_pair`
for, and it has never run on real data. It could not run on this either.

**An agent cannot record a changed mind by any path.**

| path | result |
|---|---|
| `supersede_pair` | `ValueError` — requires a verifier, and *"replacing a sealed decision is itself a decision"* |
| `supersede_pair` with a verifier | `ValueError` — the predecessor is a draft; supersede replaces a **sealed** decision |
| `add_pair` over the draft | **silent no-op** |
| the ledger | **zero entries** for any of it |

The third row is the one worth staring at. `add_pair` writes only when
`status == "sealed"`, so a draft proposed over an existing draft with a
*different* target falls through every branch and returns the stored row:

```
returned id is the same row : True
stored target              : 'FIRST answer'
what the 2nd call returned : 'FIRST answer'      # the caller passed 'SECOND answer'
ledger entries             : 0
```

No write, no ledger line, no warning, no exception — and the **return value is
the previous proposal**. A caller that does `p = add_pair(...)` and reads
`p["target_text"]` is handed an answer it did not propose, with nothing to
distinguish that from success. Four successive answers leave one row, and it is
the **first**, not the latest.

So for a machine, which may propose and may not confirm, the commitment column
can only ever hold its first guess. §6.11 named the asymmetry *"Nestor records
why you said no and not why you said yes"* and N4 added `reason` to close it —
but a draft's `reason` is written once and frozen by the same no-op, so N4's
why-yes is mutable only by sealing.

**The one channel that does work is the rejection table**, which is the result
worth keeping. Recording the three superseded approaches as refused
alternatives gives 3 rejections, each with its reason, each ledgered
(`reject_match` ×3), and — since §6.15 — each travelling in the bundle. §6.11
observed that *"Nestor keeps the rejections… and models no lineage."* For an
unratified agent that is not half the picture, it is the **whole** one: the
rejection table is the only revision log available to it, and the reasons for
three abandoned designs live there or nowhere.

Two smaller things from the same run: the current commitment plus three refused
predecessors export cleanly (`1 pair, 3 rejections, partial=False`), which is
the §6.15–§6.17 work doing its job on real data; and asking the same question in
different words — *"how should export gather the no's?"* — scores **0.438**,
nowhere near 0.92. §6.14's N1 result again, unchanged.

**Not fixed here.** What `add_pair` should do with a draft over a draft —
overwrite, raise a conflict, or route to a draft-aware supersede — is a design
decision about who may revise what, and it belongs to the operator. Worth
noting that the silent-no-op *return value* is separable from that question and
is wrong under every answer to it: whatever revision should mean, handing a
caller back a proposal it did not make, with no signal, is not it.

### 6.19 The loop, run twice — **partly** (one verb still missing)

*Two passes of §6.18's feed, fixing between them.*

**Pass one → the refusal.** §6.18 found that `add_pair` over an existing draft
with a different target wrote nothing, ledgered nothing, warned about nothing,
and returned **the stored proposal to a caller that had proposed something
else**. That is now `ConflictingDraftError`, on the same terms
`ConflictingSealError` refuses one rung up: a second answer for the same source
is a disagreement to surface, not to resolve silently. Re-proposing an
*identical* target stays idempotent, and sealing over a draft — a human
checking a machine's guess, which is the product — is untouched.

Two hazards make the old silence indefensible rather than untidy. Overwriting
would let a machine swap the row under a reviewer mid-review, so they seal
something they never read. No-op'ing lets a caller believe a proposal landed.
Refusing does neither and costs one explicit decision at the call site.

**The first attempt at that fix was the bug again.** It offered
`override_draft=True` — and because every branch below the guard is a seal, the
flag fell through and returned the stored row. An escape hatch that cannot be
honoured, inside the fix for a silent lie, being a silent lie. It was removed
rather than repaired, which turned out to be the right instinct for a reason
worth writing down:

**No `memory` function revised a draft.** `supersede_pair` covers
sealed→sealed, `add_pair` covers draft→sealed, and draft→draft had nothing —
which is why the no-op was never an oversight in `add_pair`: the operation
simply did not exist to be called.

> **Corrected in §6.20.** This entry originally said the *Protocol* had never
> been given the verb, and cited `memory_seal` hardcoding `status='sealed'` as
> proof. That was wrong. `supersede_pair` revises a row using
> `memory_mark_superseded` (the lineage capability) + `memory_insert` (a
> required core op) — so the store could always do it and `memory` was
> withholding it. An earlier wording of this correction said both were in the
> lineage capability, which is also wrong; `_LINEAGE_OPS` is
> `("memory_mark_superseded", "memory_lineage")`. A correction whose subject is
> a careless read of one op should not repeat the genre.
> The claim was made from reading one write op and not the function that
> already did the work; it survived into a commit message and an IDEAS entry
> before anyone tried to implement around it.

**So the refusal makes the failure visible without making the operation
possible.** An agent's revised proposal still cannot enter the store: it now
gets an exception instead of a false success, which is strictly better and
still not enough. Adding the verb is a Protocol change — a new optional
capability with its own predicate, on `supports_lineage`'s precedent — and it
belongs to the operator. Three regressions in the export path this session
argue against another unprompted redesign in the same file.

**Pass two → the miscount.** With the refusal in place, running the loop again
surfaced a smaller one of the same family: `rejected_ids` returns rejected pair
ids *and* rejected target texts, and the reason reported their sum as
*"3 candidate(s) are suppressed"* against a store holding **one** pair. It was
counting records and calling them candidates — a number attached to a noun it
does not count, which is the defect §6.14 opened with. Now: *"3 recorded
rejection(s) for this query suppress every candidate…"*

**What the loop is worth.** Both passes found defects the audits did not, and
neither is subtle in hindsight — they are the kind that only surface when the
system is asked to hold a real history rather than a constructed one. Feeding a
session's own record back through the thing it was built with is cheap, and it
has now found four defects across §6.14, §6.18 and here.

### 6.20 `revise_draft` — the third verb — **shipped**

*Added 2026-08-05 at the operator's instruction, after §6.19 stopped at the
refusal.*

```
supersede_pair   sealed → sealed    verifier required, successor sealed
add_pair         draft  → sealed    verifier required, successor sealed
revise_draft     draft  → draft     NO verifier,       successor draft
```

The three rounds of §6.15–§6.17 are now recordable, which is the test that
matters: one live row holding the answer that survived, three superseded rows
behind it, each carrying the reason it was abandoned, and `memory_lineage`
walking the chain. The ledger shows `supersede` ×3 and **no `seal`** — nothing
was verified, and an entry saying otherwise would claim a human had acted.

**No verifier, and that is the whole difference.** `supersede_pair` demands one
because *"replacing a sealed decision is itself a decision"* — a human's
recorded judgment is being retired and somebody must own that. A draft is
nobody's judgment. Requiring a verifier here would be the machine signing for a
decision it may not make; the successor is therefore a draft too, unsealed and
unsigned, and sealing stays a separate human act. So the covenant holds at
strictly more points than before: an agent can now record *that it changed its
mind and why*, and still cannot record *that anything is true*.

**It needed nothing new in `Storage`**, which is the part worth remembering.
§6.19 asserted the Protocol lacked the verb and named `memory_seal` hardcoding
`status='sealed'` as the evidence. The evidence was real and the conclusion was
wrong: `supersede_pair` had been revising rows all along via
`memory_mark_superseded` + `memory_insert`. The claim came from reading one
write operation instead of the function that already did the work, and it
reached a commit message and an IDEAS entry before an attempt to build around
it exposed it. §6.19 now carries the correction inline rather than being
quietly edited — a wrong claim that was acted on is part of the record.

Two things deliberately kept from `supersede_pair` rather than re-derived: the
mark → insert → re-point order with rollback, because the partial unique index
correctly refuses two live rows for one key and a failed insert must leave the
store as it was found; and dropping the superseded row's cached embedding,
since a row that will never be scored again is dead weight. Superseded drafts
are excluded from bundles on the same rule as superseded seals — history, not
stock.

**What it does not do.** It does not decide when an agent *should* revise
rather than reject. `revise_draft` says "this replaces that, here is why";
`reject_match` says "a human refused this". They are different claims and the
second is not the machine's to make — §6.18 found the rejection table doing
duty as an agent's revision log precisely because no third verb existed. That
workaround should now retire, and any code that adopted it wants revisiting.

### 6.21 The third audit: two criticals in the verb, and the first fix for one of them was wrong too — **shipped**

*Audited 2026-08-05, third independent pass. Verdict on §6.20: **not safe to
merge**. Twelve findings; the two criticals were reproducible in seconds with
ordinary threads and no fault injection.*

**A machine could retire a human's seal.** `revise_draft` checked
`status == 'draft'` against a `memory_find` read, then issued an unconditional
`UPDATE … WHERE id=?`. A human sealing the row in between had their seal pushed
into history and replaced by an unsigned draft — **282 of 300 threaded
trials**. The partial unique index catches racing INSERTs; nothing caught this,
because an UPDATE touches no index constraint. It was also a route around
`ConflictingSealError`, with no verifier and no `seal_replaced` entry.

That is the worst defect this branch has produced. The system's entire claim is
that a served answer carries a human's verification; this destroyed one, at
machine frequency, and reported success.

**The first fix for it was also wrong**, which is worth recording as plainly as
the defect. Adding compare-and-set to the retirement (`memory_mark_superseded_if`,
`UPDATE … WHERE id=? AND status=? AND superseded_by=?`) stopped `revise_draft`
retiring an *already-sealed* row — and the measurement came back **256 of 300**,
barely moved. The other interleaving was untouched: a seal landing on a row
just retired, because `memory_seal` was itself an unconditional
`UPDATE … WHERE id=?`. The verification applied to a row no serve path would
ever read. Both halves needed the precondition in the WHERE clause; fixing one
and measuring is what caught it, and the lesson is that a race fix is not done
when it is written, it is done when the number moves.

| | before | after |
|---|---|---|
| seals lost to history (300 trials) | 282 | **0** |
| revisions whose lineage was destroyed (200 trials) | 184 | **0** |

The second critical: two concurrent revisions, where the loser's rollback fired
unconditionally and could overwrite the *winner's* successor pointer with its
own abandoned marker — leaving the surviving revision with no history, which is
the one thing the verb exists to provide. The rollback now runs only if it
still owns the marker, and its own failure is suppressed so it cannot mask the
real cause.

A store that cannot retire a row conditionally is **refused**, not degraded
(`supports_atomic_supersede`, its own predicate on
`supports_rejection_listing`'s precedent). "Probably not concurrent" is not a
basis on which to risk a human's verification.

The other four that shipped: `revise_draft` consulted `reject_pair` but never
`reject_match`, so an agent could install a target a human had signed a "no"
against — after which `lookup` suppresses it and the store stops answering at
all. The `nestor ui` match panel never rendered `reason`, so the fix for *"a
review surface that misstates its own reason"* landed in the CLI and the API
and missed the surface humans actually review on — and its empty-list message
still asserted *"No candidate scored high enough"* when the true cause was
often that every candidate was rejected. The rejection count reproduced its own
bug one line lower (`rejected_ids` returns two **sets**, so one record naming
both a pair and a target counted twice and two records naming one target
counted once). And a rejection naming a superseded pair stopped travelling —
rare before, routine the moment `revise_draft` made superseding an agent's
normal move; it now travels with `pair_id` blanked, so the target-text
suppression survives and nothing dangles.

**Deliberately not fixed, both pre-existing on `master` and both in
`supersede_pair`'s shared machinery:**

* **The crash window.** Between marking the old row and inserting the successor
  the answer is invisible with no successor, and a process death there is
  unrecoverable by any in-tree tool. Identical in `supersede_pair` since
  `7b56adb`. It wants a transaction primitive the Protocol does not have, or a
  `nestor repair` for `superseded_by LIKE 'pending:%'`.
* **`memory_lineage` has no cycle guard** (`while True:` with no `visited` set),
  so a forged `superseded_by` cycle hangs it. Not reachable through the public
  API today.

**The pattern, three audits in.** Every critical has been the same shape: a
condition checked in Python guarding a write that cannot re-assert it. It has
now appeared in the export walk, the rejection filter, and the row retirement —
three different mechanisms, one habit. The counter-move that has worked each
time is not a better condition but moving the precondition into the operation:
two walks each bounded by construction; a WHERE clause instead of a read.

### 6.22 A name is not a word: the proper-noun case has no field — **measured**, design **open**

*Raised 2026-08-05 out of a conversation about the repo's own name, after the
operator observed that the translations produced by hand in that conversation
were exactly the thing the store exists to hold. They were. The attempt to say
where they would go is what turned up this.*

Two source strings, translated into Russian:

```
Nestor  -> Нестор            a name. transliterated, not translated.
nestor  -> мудрый советник   the common noun. a real translation.
```

Both are correct. `StringMatcher.normalize` case-folds, so both key to
`nestor`, and the partial unique index permits **one live row per
`(source_norm, source_lang, target_lang)`**. The store cannot hold both.

**Measured, on a file-backed store:**

* Two *different* verifiers → `ConflictingSealError`. The guard fires, and it
  is right about its own premise and wrong about the situation: it reports two
  humans disagreeing about one source, when what happened is two humans
  agreeing about two different sources. There is no outcome available that
  keeps both.
* One verifier (the self-correction path, and the ordinary case for a single
  operator) → **no error, one row, mixed**: `source_text='Nestor'`,
  `target_text='мудрый советник'`, `status='sealed'`, and `verified_sealed`
  passes it. First writer wins `source_text`, last writer wins `target_text`.
  The surviving row asserts a pair nobody entered. This is the documented
  same-actor upgrade behaving as documented — it is not a hole, and the
  reason it reads like one is that the key says these are the same source.

Case folding is a deliberate and correct choice; "Hello"/"hello" sharing a row
is the whole point of normalization. The cost lands entirely on the class of
strings where case *is* the meaning, and there is no field that says so.

**The one mechanism that could express it is outside everything.**
`glossary.locks_in_text` → `system_prompt(locks=...)` already emits *"Locked
terminology — always render these terms exactly as given"*, and ~~an identity
lock (`{"Nestor": "Nestor"}`) is precisely carry-through~~. But the glossary is
`data/glossary.json`, and `grep` for it in `portable.py`, `cascade.py` and
`sqlite_store.py` returns **0, 0, 0**: not bundled, not ledgered, not sealable,
not superseded, no verifier, no signature. The one place Nestor can say *do not
translate this* is the one place with none of Nestor's guarantees. A bundle
that carries every pair and rejection carries no locks, so the receiving host
composes prompts the sending host would not have.

> **Corrected in place, 2026-08-06**, while answering the three questions below
> in [`docs/carried-strings.md`](docs/carried-strings.md). The identity-lock
> escape hatch does not work. `locks_in_text` matches case-insensitively
> (`glossary.py:36` lowercases both sides), so `{"Nestor": "Nestor"}` fires on
> *"he was the nestor of the committee"* as readily as on the name — measured,
> all three of `Nestor` / `nestor` / `NESTOR` return the lock. It would put
> *always render exactly as given* into the prompt for the one row in the pair
> that is a real translation.
>
> So the glossary is not the mechanism that could express the distinction and
> merely lacks guarantees. It is a **second** mechanism with the same blindness:
> the store case-folds in `normalize` deliberately, the glossary case-folds in
> `locks_in_text` incidentally. The diagnosis "there is no field that says so"
> stands; the named way out does not. There is no way to say this today, in any
> component, with any combination of existing parts.

**What is not being proposed.** Not a `kind` column, and not on the strength of
one example — that is the shape §6.17 keeps punishing, a field added to carry a
distinction the mechanism does not otherwise make. Three questions come first,
and the third may dissolve the other two:

1. Is the distinction *proper noun* or is it *this string is carried, not
   rendered*? The second is broader (product names, identifiers, code) and does
   not need a linguistics answer.
2. Should the glossary move into the store — where it would inherit sealing,
   supersession and the bundle — or is it correctly a policy file that happens
   to be under-guarded?
3. Does a carried string want a *pair* at all? `Nestor -> Нестор` is a fact
   about a script, not about a language pair, and the table is a language-pair
   table.

**Answered 2026-08-06** — [`docs/carried-strings.md`](docs/carried-strings.md),
and question 3 does dissolve the other two:

1. **Carried, not proper.** "Proper noun" is a property of a word; carriage is a
   property of an intention, and *Nestor* is a name in one segment and a common
   noun in the next — which is this entry. The broader framing also needs no
   linguistics and covers SKUs, identifiers, paths and citations, none of which
   a grammarian would call proper nouns and all of which have the requirement.
2. **Neither, as posed** — the glossary is not currently a policy file, because
   a policy file has a location and `data/glossary.json` is relative to the
   process working directory (§6.27). The real complaint in this entry is the
   *bundle*, not the seal, and bundling locks fixes it without sealing them:
   nobody verifies that a string is carried, so there is nothing for a
   `verifier` column to have been right about.
3. **No pair.** `Nestor -> Нестор` is transliteration — a real transform with a
   real target, which belongs in a pair table like any other. The carried case
   is `Nestor -> Nestor`, and that is not a pair but **membership in a set**:
   one column, no target (it can only equal the source), no language direction
   (a string carried `en->ru` is carried on the way back). The two rows stop
   competing because only one of them is a translation, and no field has to say
   which — the set says which, consulted before normalization rather than
   inside it.

The one hard constraint that falls out: whatever holds carried strings must not
be keyed on a case-folded normal form, which is what rules out putting them in
`tm_pairs` and reproducing this collision one layer down.

**Also true, and the reason this is in §6 rather than fixed:** nobody has hit
it. It has no reporter, no failing host, and one contrived reproduction. It is
recorded because it was found while looking for somewhere to put a dozen
unsigned translations, and per §6's own rule a follow-up raised in conversation
and not written down did not happen.

**And the translations themselves.** A dozen renderings of *nest* into
languages nobody in the session reads, asserted in one breath at one
confidence, none signed. Five (`nid`, `nido`, `ninho`, `Nest`, `nīḍa`) are
cognate descent from PIE \*ni-sd-ós; one (`cuib`) is not — it reaches the same
metaphor by a different road — and stating them together flattened exactly the
difference a `reason` field exists to keep. If they are ever entered they are
`draft`, with the shaky ones marked and `revise_draft` waiting for the moment
somebody who actually speaks Romanian looks at *cuib*.

> **Corrected in place, same day**, while printing the table into the README —
> which is what checking is for. This paragraph first said *cuib* came "from
> Latin *cubium*". Wiktionary gives Vulgar Latin \*clubium ← Ancient Greek
> κλυβίον, with \*cubium as a variant; the *cubāre* "lie down" association I had
> in mind is not the given derivation. Two more of the same kind turned up in
> the same pass: Armenian *nist* means **"seat, session"**, not "nest", and its
> derivation is contested (from \*nisdós *or* deverbal from նստիմ); and Greek
> kept **no** reflex of \*nisdós at all — φωλιά is unrelated. Three errors in
> sixteen rows, all in the rows I had already flagged as the uncertain ones,
> and none of them visible without looking them up. The README table is
> published with every row marked `draft` for exactly this reason.
The etymology is not translation and no engine here would produce it;
`system_prompt` says *translate*, so asking it for a reconstruction returns a
bad translation of a question. That half is research and belongs here, in the
list, which is where it now is.

### 6.23 The refusal voice: three sentences rewritten, one bug, two rules — **shipped**

*Prompted by an operator's observation, from months of doing this: the persona
is load-bearing, and it is usually better slightly humorous and
self-deprecating. Recorded because the reasoning changed a design and the
design was wrong before it.*

**The argument is already in the tree.** `portable._canonical` carries it:
*"an integrity check that fails on a lossless round-trip trains people to
ignore it, which is worse than not having one."* Same mechanism, different
surface — a refusal that reads as officious trains people to route around it.
And it matters more here than most places, because **by volume Nestor's output
is refusal**: the sealed hit is instant and silent, and everything a curator
actually reads is a machine saying *below the bar*, *nobody has verified this*,
*nothing matched*.

**Where the voice actually was.** `_why_not_served` was written in an
unmistakable register — dry, precise, unapologetic, wry about its own
failures — **in the comments**. `# a number attached to a noun it does not
count`. `# The previous fix for this sentence reproduced its own bug one line
lower.` That last is the best sentence in the file and no user will ever read
it. The six strings a human *does* read were flat. The voice was aimed
entirely at reviewers and absent from users. Same in the README, where
*"Nothing to offer. Said plainly rather than improvised"* is in the docs and
not in the product.

**A partition, not a tone.** Which acts may be wry follows from the covenant
rather than from taste:

```
machine is the subject   below_threshold, nothing_sealed, nothing_in_domain   may be wry
human is the subject     forged_seal, rejected_outright, suppressed           plain, always
```

The machine may be laughed at because the machine is the junior party — it may
propose and may not confirm. When two people assert different things, when a
curator's "no" is being honoured, when a signature does not verify: nothing is
funny. The rule predicted that exactly three of six would change, and it also
predicted **which tests would break** — only the machine-subject assertions.
Both held.

There is a duller reason it held, worth more than the rule: the three
human-subject strings are the three that already got the most engineering
attention (the rejection branches carry paragraphs about counting records
versus rows). Nobody agonizes over how to say *I didn't find anything*, so the
flatness pooled exactly where the rule points.

**The bug, found by rendering the sentence rather than reading it.**

```
- closest of 20000 candidate(s) is 0.71, below 0.92 (20000 scored, showing 8)
+ closest of 20000 candidate(s) is 0.71, below 0.92 (showing 8) — the bar
+ exists because a near miss served as verified is worse than no answer
```

`20000` twice: the display-slice clause re-reported a number already the second
word of the sentence. Cosmetic, pre-existing, invisible until someone tried to
say it out loud.

**Two rules the writing produced, neither of which was in the design:**

* **Range safety.** The first draft read *"close enough to be tempting, which
  is why it is not served"* — a good sentence, and **false at 0.11**. A flat
  string is true across its whole format domain; a pointed one need not be, and
  the register makes that easy to introduce. The fix is to make the clause
  about the *bar* rather than about *this row*, and it is genuinely
  property-testable: render at both ends, assert nothing reads as a lie.
  `TestRangeSafety` does that, and forbids the four words that were the
  temptation.
* **The direction of the self-deprecation.** The empty-domain rewrite works
  because it *takes the blame*: `"...which usually means en→es is empty rather
  than that the question was strange"`. Flat "nothing matched at all" quietly
  leaves the reader wondering whether their input was odd. The real principle
  under "at the machine's expense" is not *make jokes about yourself* — it is
  **absorb the awkwardness of an empty result instead of leaving it where the
  user will pick it up.** That generalizes well past humour.

**A silent degradation, avoided narrowly.** Four assertions in
`test_findings_2026_08_05.py` read `"nothing in this domain" not in reason`, to
prove a rejection is not reported as an absence. Reword that branch and all
four keep passing **while checking nothing** — no branch emits the phrase, so
its absence is free. The phrase was therefore kept and the branch extended
around it, and `TestTheAssertedPhrasesAreRealSince` now pins it: a negative
assertion is only worth anything while something can still produce what it
denies. This is the one finding here that is not about prose.

**And one wrong sentence pinned by a passing test.** The nothing-sealed branch
said *"the best candidate is {kinds}"*; `kinds` is the set of statuses across
**every** row above the bar, not the best one's. A test asserted the phrase
verbatim and passed — because it agreed with the sentence, not because the
sentence was right. §6.14's finding again, in a test rather than a claim.

**What this says about `persona.py`, which was not built.** The tests pin prose
because the classifier has no stable identifier — the branch returns a
sentence, so a sentence is the only thing to assert on. That is the concrete,
measured cost of the missing module, and it is *one assertion*, not a crisis.
The order that follows: get the sentences right in place, extract the module
from strings that already work, and do not invent a schema and fill it. The
sketch is otherwise unchanged except in one place — the argument against a
`warmth=` knob. It was *"tone trades against clarity"*, which is wrong. The
right argument is `system_prompt`'s own, about `VOICE_RULE`: **the only reason
to make it optional would be to turn it off.** The register is not a parameter
because it is load-bearing, not because it is dangerous.

### 6.24 `persona.py` — installed, and the two gates that bit me — **shipped**

*Built 2026-08-05 after §6.23, on the order §6.23 argued for: get the sentences
right in place first, then extract the module from strings that already work.
The alternative — invent a schema and fill it — is how the glossary happened.*

**What it is.** A closed vocabulary of six speech acts, one rendering each, a
`get_persona`/`set_persona` seam matching `set_store` and `set_matcher`, and
`answer._why_not_served` split into `_classify` (returns an act plus its facts)
and a renderer. The strings moved out of `answer.py` unchanged.

**The split is the part that pays.** §6.23 recorded the cost of a classifier
that returns prose: every assertion about *which* refusal happened was a
substring match on the sentence. Four negative assertions in
`test_findings_2026_08_05.py` were one rewording away from passing vacuously,
and one positive assertion pinned a sentence that was *wrong*. `_classify` now
returns `("nothing_in_domain", {...})`, and `test_every_act_classify_returns_
is_a_pinned_one` reads those literals **statically** — a branch reachable only
under a store state no test builds would otherwise ship an unpinned act.

**Two gates in the repo caught the author of the module within minutes,
which is the only reason to write this entry.**

* **`test_engine.py::test_the_rule_is_written_once`** (the §6.13 gate) failed
  on `persona.py`'s own docstring. Explaining that this module is *not* ground
  rule 2b, I retyped ground rule 2b — making its distinctive phrase appear
  twice in the package, which is the exact defect §6.13 existed to remove. The
  docstring now points at `engine.VOICE_RULE` and says why it does not quote
  it.
* **`test_docs.py`** failed because the project layout is a promise about
  what is in the package, and a new module had not been added to it.

Neither was clever. Both fired on a change made by someone who had read them
that morning, which is the argument for gates over guidance in one line.

**A third gate turned out stronger than designed.** Adding an act to
`SPEECH_ACTS` without a rendering does not fail a test — it fails **import**,
because `NESTOR` is constructed at module scope and `Persona.__post_init__`
refuses an incomplete persona. The all-or-nothing rule enforces itself before
any test runs. That was not foreseen and it is the right behaviour.

**Where the negation check lives, and why it is not at construction.**
`NEGATIONS` is checked on the *output* of a rendering, in `say`, not on the
persona when it is installed. A rendering is a callable, so a sentence that
negates at one count and not at another is exactly the failure worth catching,
and a construction-time check cannot see it. Cost: one substring scan per
refusal, on a path that has just scanned the whole domain.

**Mutation-proved, because a gate that cannot fail is a description:**

```
engine.py imports persona            -> test_engine_does_not_import_persona FAILS
_classify interpolates an f-string   -> test_classify_composes_no_prose     FAILS
an act added to SPEECH_ACTS          -> the package does not import
```

**Deliberately not done.** The exception messages (`ConflictingSealError`,
`RejectedPairError`) and `cascade.py`'s state glyphs are also Nestor speaking
as itself, and they stayed where they are. Sweeping them in would mean routing
exception text through a global seam — a persona that can reword an error is a
persona that can reword a stack trace's meaning — and it is a much larger
change than the one that was asked for. `SPEECH_ACTS` is the refusal surface,
and the frozenset is pinned so growing it is a decision rather than a drift.

**Still open.** i18n of Nestor's own speech is a genuinely good idea and a
different module: it puts a translation system in the position of translating
its own refusals, unverified, which wants its own entry rather than smuggling
into this one.

### 6.25 `init_db` on a pre-lineage database raises — **shipped**

*Found 2026-08-06 while building §6.8, in a test that had to be rewritten to
stop riding on it.*

`init_db()` calls `_ensure_unique_key`, which creates
`idx_tm_pairs_superseded ... WHERE superseded_by != ''`. It does **not** call
`_ensure_lineage_schema`, which is what adds `superseded_by`. On a database
written before lineage existed, `init_db()` therefore raises
`OperationalError: no such column: superseded_by`.

Reproduced on `c68b8be` and on the §6.8 branch, identically — this predates
§6.8 and is not caused by it. `memory_init()` is unaffected: it runs the
lineage migration first, which is why `test_supersede.py`'s migration test has
never seen this.

It is only reachable on the `init_db`-before-`memory_init` ordering against a
legacy file, which the two callers in `test_findings_2026_08_05.py` do — but on
a fresh database, where `_SCHEMA` creates the modern `tm_pairs` and the column
is present. So it has no reporter and no failing host, same as §6.22.

~~The fix is one line — `_ensure_lineage_schema` before `_ensure_unique_key` in
`init_db`~~ — and it is deliberately **not** in the §6.8 commit. A latent
correctness bug folded quietly into a performance change is how a reviewer ends
up unable to tell which half a regression came from.

**Shipped 2026-08-06, and not as the one-liner above.** Reordering the calls
inside `init_db` fixes this instance and leaves the shape: a precondition
honoured by convention at call sites, with a second path free to forget it —
which is the defect `TODO.md`'s closing note and review-lessons §8 give three
worked examples of, and `init_db` *was* the second path. `_ensure_unique_key`
owns the migration its own indexes depend on now, so no caller can arrive
without it and there is no ordering left to get wrong. Idempotent; the cost is
two `PRAGMA table_info` calls on a path that runs once per connection (§6.8).

This falsified a claim in `_Conn`'s docstring — that `init_db` applies a strict
subset of `memory_init` — which is corrected there rather than left standing.

### 6.26 A countersignature is discarded without a word — **shipped**

*Found 2026-08-06 while arguing §1.4 through; see
[`docs/seal-staleness-and-quorum.md`](docs/seal-staleness-and-quorum.md) §1.*

A second verifier sealing an already-sealed pair with the **same** target
writes nothing, appends nothing, and raises nothing. `memory.add_pair` returns
the stored row, so the caller has every reason to believe they sealed it.

Measured, file-backed store, `NESTOR_SEAL_KEY` set:

```
after rita : verifier='rita' weight=1.0 sig=07e4bf0dd287...
after sam  : verifier='rita' weight=1.0 sig=07e4bf0dd287...
rows for this source: 1
```

and one ledger entry, `{'kind': 'seal', 'verifier': 'rita'}`.

The branch is `memory.py:374` — a seal writes when the row is not already
sealed **or** the target differs. Agreement satisfies neither arm.

**This is the failure mode the file next to it already names.** Fifteen lines
below, `ConflictingDraftError` exists precisely because a draft over a different
draft *"silently returned the stored row"*, and its comment says that is worse
than either alternative. The concurring-seal path does exactly that, and has no
error, because before quorum was contemplated there was no reason to tell "you
sealed it" apart from "somebody else did".

Note what is **not** wrong here: nothing is overwritten, no rejection is
bypassed, and the served answer is correct. Disagreement is still loud
(`ConflictingSealError`). The defect is that Nestor is better instrumented for
reviewers who fight than for reviewers who concur — a person did a thing, under
their own key, and the tamper-evident record of who decided what does not
contain it.

**The fix is one ledger append**, not a schema change: a `countersign` entry
naming the second verifier, leaving the row and the serving path untouched. It
is listed separately from §1.4 because it stands on its own — it is worth doing
whether or not N-of-M is ever wanted, and it is the prerequisite that makes
"does anyone countersign?" a measurement rather than a guess.

**Shipped 2026-08-06, and it was one ledger append.** Landed alone, on its own
branch, because two reviewers and the PR that found it all said the same thing:
do not bundle this with the performance work it was discovered next to.

*What it records.* `countersign` names the second verifier and the first
(`countersigned`), the source and target digests, and — the part that makes it
evidence rather than a log line — **a signature over the same bound fields a
seal signs, made with the countersigner's own key.** `tm_pairs` has one
`verifier` and one `seal_sig` and they belong to whoever got there first, so
the second signature has nowhere to live but the chain. Verified: the entry
validates under `sam` and does not validate under a claim that `rita` made it.
With a keyring installed, an unknown or revoked countersigner is refused before
the store is touched, exactly as a seal is.

*What it does not record, and this is where the fix could have gone wrong.* The
obvious way to write the condition is `not _same_verifier(first, second)`. That
helper answers *may we assume the same actor* and resolves unknown to **not the
same**, so a conflict guard fails closed — and negating it inherits the wrong
polarity. Two anonymous re-seals would have become a recorded agreement between
two people who never identified themselves: a fabricated countersignature, in
the one file that exists to say who decided what. Both sides must name somebody.
`test_two_anonymous_seals_do_not_fabricate_a_countersignature` is the gate.

*Nothing else moves.* The row is byte-identical before and after, `best_sealed`
returns the same row with the same verifier, and the chain still verifies. Three
of the ten tests fail against the reporting revision — the entry itself, the
signature-is-evidence check, and the accumulation of a third reviewer. The other
seven pass on both sides and are guards: they are the *must-not-record* and
*must-not-move* cases, which is precisely where a wrong version of this breaks.

*What is now unblocked.* §1.4's step 2 —
[`docs/seal-staleness-and-quorum.md`](docs/seal-staleness-and-quorum.md) §5 —
was "measure whether anyone countersigns", and it was unanswerable because the
data did not exist. It exists now. **Nobody has run that measurement yet**, and
the memo's position is unchanged until somebody does: N-of-M is a schema change
that should not be designed for users who have not been shown to exist.

> **Two things review found, and the second is this entry's own defect one edge
> over.**
>
> **Counting.** `seal` is idempotent and `countersign` is not: `rita`×3 records
> one entry, `sam`×3 after rita records **three**. Kept deliberately — a seal is
> a state and a countersignature is an event, and three attestations carry three
> timestamps and three signatures that an append-only chain exists to keep. But
> it means `grep -c countersign` answers a different question from the one step 2
> asks, and a UI retry inflates it. The memo now says **count distinct
> `(pair_id, verifier)`**, and a test pins the two fields that count needs. Not
> deduplicated in code: that would put a ledger read on the write path — a new
> interaction, to enforce something the reader can do for itself.
>
> **Append failure.** `_log_seal_event` swallows a failed append, warns, and
> returns; its docstring says why, and the reason is *"the pair is already
> committed… raising would hand the caller a completed write plus an
> exception."* **A countersignature commits nothing.** The ledger entry is the
> whole product, so swallowing meant the operation silently did not happen —
> which is precisely the defect this entry exists to close, reappearing on the
> error edge. Worse, the warning it did emit read *"a seal was written but its
> ledger entry was not"* on a call where no seal was written, so the one signal
> a curator got was false.
>
> Countersignatures now append through `_log_countersign`, which **raises**.
> That is safe here for exactly the reason the swallow is safe there: there is
> nothing to roll back, so the caller is left where they started. Two gates fail
> against the reviewed revision; a third is a guard on the fields the count
> needs.

### 6.27 The glossary is addressed relative to the working directory — **shipped**

*Found 2026-08-06 while answering §6.22's second question; see
[`docs/carried-strings.md`](docs/carried-strings.md) §Q2.*

```python
_PATH = pathlib.Path("data/glossary.json")     # nestor/glossary.py:7
```

Relative, and resolved against the process working directory on every call —
`load()`, `save()`, `add_term()` and `locks_in_text()` all go through it. So the
glossary a deployment has is a function of where it was launched from. A
`systemd` unit with a different `WorkingDirectory` than the developer shell that
wrote the locks reads an empty glossary and says nothing.

Measured, one process:

```
glossary path is relative to CWD: data/glossary.json -> True
same process, different cwd, load() returns: {}
```

It wrote a glossary, read it back, changed directory, and the same call returned
`{}`. No error, no warning — term locks simply stop being applied, and the only
visible symptom is that tier-2 drafts quietly stop respecting terminology
somebody entered on purpose.

§6.22 calls the glossary *"correctly a policy file that happens to be
under-guarded"*. That is one step short: it is unsigned, unledgered, unbundled
**and** unlocatable, and the last of those is the only one with a live blast
radius today. The others are gaps in guarantees Nestor could offer; this one
silently drops a promise it already makes.

Unlike the rest of §6.22 this does not wait on a design question and does not
need a reporter — it needs an absolute path, resolved once, from an explicit
setting rather than from `os.getcwd()` at call time. It is listed separately for
that reason: everything else in §6.22 is deliberately parked, and this should
not be parked with it.

### 6.28 Concurrent writers: the known limit, quantified — **measured**, fix **open**

*Measured 2026-08-06 while walking `docs/code-review-lessons.md` §11 over the
§6.8 change — the checklist row "concurrent / pooled threads?".*

`TODO.md` §2 says a store that takes concurrent writers is missing and that the
reference `SqliteStore` is not it. That is qualitative. The number:

12 threads on one file-backed store, each calling `memory_init()` then
`add_pair()` then `memory_find()`, released from a barrier together, 300 trials
= 3600 concurrent init-and-write sequences per run. Failures are
`OperationalError: database is locked`.

| revision | run 1 | run 2 | run 3 |
|----------|------:|------:|------:|
| `c68b8be` (before §6.8) | 12 | 9 | 3 |
| after §6.8 | 4 | 5 | 9 |

**Roughly 0.1–0.3%, and §6.8 neither causes nor fixes it.** The ranges overlap
completely. The first pair of runs read 12 against 4 and looked like the fix had
reduced contention — a plausible story, since shorter write transactions ought
to conflict less — and repeating it dissolved that. It is recorded here because
the wrong version of this entry is the one I nearly wrote from a single pair.

Nothing to fix in §6.8. What this quantifies is the limit `TODO.md` already
names: a caller doing concurrent writes to `SqliteStore` gets a hard failure a
fraction of a percent of the time, with no retry and no queue. `nestor.ui` is a
threaded server, so the reachable form of this is two reviewers acting at the
same moment.

**Not added as a test.** It takes minutes, and a gate that fires on 0.1% of runs
is a flaky build rather than a guarantee. The number belongs in the record; the
fix belongs in whatever replaces the reference store.

A method note, since the count is the point: the first attempt at this
comparison used `git stash push` on an already-committed file, which stashes
nothing and silently ran the *same* revision twice. The paired runs above use
`git checkout c68b8be -- nestor/sqlite_store.py`, verified each time by grepping
for `_Conn` in the file before running.

### 6.29 Two of the three refusals are exported; the third is not — **shipped**

*Found 2026-08-06 by building a recipe against the package rather than reading
it — §6.30.*

`nestor/__init__.py` exports `ConflictingSealError` and `RejectedPairError`.
It does not export `ConflictingDraftError`.

```
ConflictingSealError     in nestor.__all__: True    attr: True
RejectedPairError        in nestor.__all__: True    attr: True
ConflictingDraftError    in nestor.__all__: False   attr: False
```

So the one refusal that exists to direct a caller to the third verb is the one
refusal a caller cannot catch from the public surface. A recipe hits it, reaches
for `nestor.ConflictingDraftError`, gets `AttributeError`, and has to import
from `nestor.memory` — while the other two sit where they were looked for.

Not a functional defect: the exception is raised, it is catchable from the
module, and nothing silently succeeds. It is an inconsistency in what the
package presents as its vocabulary, and §6.20 is where it entered — the verb
shipped, the error's export did not follow it.

One line. Left unfixed here for the same reason §6.25 was: it belongs in a
commit that is about the public surface, not folded into a recipe.

### 6.30 A recipe for patches — built, measured, and it does not serve — **measured**, and **qualified by §6.32**

*Built 2026-08-06 against the shipped package, `recipes/patch_review.py`.
Nothing in `nestor/` was modified, which was the point.*

The README's Matcher-seam table has a row reading *yours / yours / whatever you
can normalize and score*, with a date matcher and a CSV-header mapper cited as
evidence. This is a third: **source = a defect described in prose, target = the
fix, sealed = a human checked that this fix is the fix.**

**`DefectMatcher` weights identifiers above prose.** Defect descriptions carry
two token populations — prose (*"returns"*, *"silently"*) that is near-identical
across every bug report ever written, and identifiers (`memory_init`,
`ConflictingSealError`, `sqlite_store.py:374`) that are almost the whole signal.
`StringMatcher` is character difflib and cannot tell them apart. Identifiers are
detected syntactically — snake_case, an internal case change, a dotted or
colonned path — with no vocabulary list to maintain or mis-weight.

**Measured**, 13 real defect→fix pairs from this repository's own history, each
probed with a sentence somebody might type a month later:

| matcher | correct defect at rank 1 |
|---|---:|
| `StringMatcher` (shipped default) | 4/13 |
| `TokenJaccard` (bench, unweighted) | 6/13 |
| `DefectMatcher` (`IDENT_WEIGHT=3.0`) | **7/13** |

`IDENT_WEIGHT` was fixed at 3.0 **before** anything ran, and the curve is
reported rather than tuned to: 1.0 → 6/13, 2.0 → 6/13, 3.0 → 7/13, 5.0 → 7/13,
8.0 → 7/13. It saturates at the a-priori choice, so the constant stands and
raising it buys nothing.

**The headline is the disappointing half.** 7 of 13 is better than both
baselines and is not good. And the threshold sweep says the recipe cannot serve
at all:

| cutoff | serves the right one | serves a **wrong** one |
|---|---:|---:|
| 0.04 | 7/13 | 6/13 |
| 0.10 | 4/13 | 2/13 |
| 0.15 | 3/13 | 1/13 |
| 0.92 (shipped) | 0/13 | 0/13 |

No cutoff is good at both jobs — the same shape the README's Accuracy section
already reports for translation, and the same *class* of finding as §3.4 stage
3, where `StringMatcher` returned 0.000 recall at every shipped threshold on a
real human corpus. Token weighting improves **ranking** and does not make
**serving** safe. So this recipe is a review queue, not a tier-1 server, and
saying otherwise would be the thing §4.4 exists to refuse.

**The package caught me mid-measurement**, which is worth recording as evidence
the warning works: `best_sealed` with a custom matcher emits a `RuntimeWarning`
saying `SEAL_THRESHOLD=0.92` was measured for `StringMatcher` and telling the
caller to run `nestor calibrate --matcher`. It fired unprompted, in the right
direction, on exactly the mistake a recipe author is most likely to make.

**Rival patches: the refusal is right.** A defect can have two plausible fixes,
and the store permits one live row per normalized source. Building this is what
made the refusal make sense. §6.19's two hazards apply word for word — a machine
swapping the row under a reviewer mid-review so they seal something they never
read, or a caller believing a proposal landed when it did not. So rivals get two
named exits and no third: `revise()`, where the abandoned proposal is kept with
the reason it was abandoned *for*, and splitting the defect, because a
description broad enough to admit two correct patches is usually describing two
problems. That last is §6.22 in another domain — the key says these are the same
source when they are not.

What is genuinely lost is two *live* proposals awaiting one decision, which is
the gap `docs/detection-kit-as-gates.md` names at the kit's tool #4: Nestor
holds alternatives as lineage, never as concurrent competitors. If you want a
bake-off between two patches, Nestor is where the outcome is recorded, not where
the bake-off happens.

**What it cannot do, and does not pretend to.** Decide whether a patch is
correct. There is no execution in Nestor and the recipe adds none. A seal here
means *a person checked this* and never *the tests passed* — the same limit
§6.12 forced into precise words for the detection kit's tool #3.

Corpus caveat, stated because 13 is a small number: this is far too few rows to
set a deployment's dial from, and the probes were written by the same person who
wrote the defect descriptions — §3.4 stage 2 is the entry about why that flatters
a matcher.

> **The caveat was right, 2026-08-06 — §6.32.** Run against a second corpus
> (`IDEAS.md`'s own open entries, probed with questions that are not paraphrases
> of them), `DefectMatcher` scores **3/6** and `StringMatcher` **4/6**. The 7/13
> advantage above does not reproduce. At n=6 one question is the whole
> difference, so this establishes the advantage is *not general* rather than
> reversed — but the table above should not be read as evidence that identifier
> weighting beats character similarity, only that it did on the corpus I wrote.
>
> The mechanism is that token sets have no morphology: `seals` and `seal` share
> nothing, so a query scoring 0.1975 under character difflib scores **0.0000**
> here. The win was measured and the loss was never looked for.

### 6.31 Nothing that persists carries a version — **measured**, fix **open**

*Raised 2026-08-06 while wiring the package for PyPI. The packaging half
shipped; this is the half that did not, because it should not be stamped
without being argued.*

> **The numbering took three tries, which is worth one sentence.** This entry
> was written on a branch off `master` where §6.25–§6.30 did not exist, and
> carried a warning that its number assumed another PR landed first. It was
> folded into #42; #42 was then split, merged, and reverted, and the docs half
> landed separately as #43 — so §6.26 and §6.27 reached `master` while §6.25 and
> §6.28 went back out with the revert. This is the reland, and §6.24 through
> §6.31 are contiguous again. Recorded because a caveat that silently disappears
> is indistinguishable from one that was never checked, and because "the numbers
> are fine now" is exactly the kind of claim this file exists to make somebody
> verify.

Four things could carry a version. Measured, as of `c68b8be`:

| | version? |
|---|---|
| the **package** | `0.1.0` in `pyproject.toml` since `7fb841e`, never moved; no `__version__`, no tags, no changelog |
| the **bundle** (`portable.py`) | **yes** — `BUNDLE_VERSION = 2`, `SUPPORTED_BUNDLE_VERSIONS = (1, 2)`, a per-version field map, and an explicit refusal naming what it reads and writes |
| the **store schema** | **no** — no `PRAGMA user_version`, no meta table |
| the **ledger format** | **no** — entries carry `kind`, `at`, `prev`, `hash` and a payload, and nothing saying which format wrote them |

The package half is now done: `__version__` from installed metadata, a
changelog, a release runbook, and a publish workflow that cannot fire. The
interesting part is the asymmetry the table shows.

**The thing that crosses a trust boundary is versioned carefully. The things
that persist locally are not versioned at all.** A bundle leaves one deployment
and lands in another, so it got a version, a supported-range check, per-version
field sets, and a guard subtle enough to know that `True` is not version 1 and
that `2.0` is version 2 because a browser round-trip turns `1` into `1.0`. The
store and the chain never leave, so nobody had to think about it — and they are
the two things that outlive every process that touches them.

**The store.** Migrations detect state by probing with `PRAGMA table_info` and
reacting to which columns are absent. That works, and it is why `init_db` on a
pre-lineage database raises `OperationalError: no such column: superseded_by` —
it builds an index over a column that another method adds, and with no version
to consult there is nothing but call order enforcing the dependency. (Filed
separately as §6.25 on the PR #42 branch.) A `user_version` would make the
migration a decision about a number rather than an inference from a shape.

**The ledger is the one that gets harder the longer it waits**, and it is why
this entry proposes nothing. The chain is append-only and hash-linked, so
historical entries cannot be re-hashed under new rules without breaking the
chain they exist to protect. Which means the format is *already frozen* — not by
a decision, but by the first entry anybody wrote. Adding a version field now
versions everything after it and leaves everything before it as the implicit
version 0, and whether that is acceptable is exactly the kind of question
`docs/seal-staleness-and-quorum.md` had to ask about `weight`: what does a
reader do with a record whose format predates the field that would have told
them its format?

**Not proposed here:** a `user_version` stamp, a ledger `v` field, or any
migration. Both touch persistence and the audit path, which per `CLAUDE.md`
wants an adversarial read, and the ledger question wants deciding before
anything is stamped rather than after. What is proposed is that the decision
stop being deferred by not being written down.

> **The two halves have come apart, 2026-08-06.** An adversarial review of the
> PR #45 reland found the store half has a defect motivating it *now*, which the
> ledger half does not. They should stop being one entry.
>
> **The store half is no longer speculative.** §6.8 made `memory_init` skip its
> work on a connection that has already done it, so a process holding warm
> pooled connections does not run a migration it did not have when those
> connections were opened. Reproduced: after a warm `memory_init`, a newly
> introduced `_ensure_*` does not run; after `checkpoint_wal` clears the pool,
> it does. Whether a migration lands therefore depends on whether something
> unrelated flushed the WAL first, which is not a rule anyone should have to
> reason about at upgrade time. Before §6.8 this self-healed, because every call
> replayed the idempotent DDL — the performance win and this hazard are the same
> change. A `user_version` that invalidates the flag when it moves is the fix,
> and it touches no hash chain, so the argument it needs is small.
>
> `docs/releasing.md` carries the interim rule: **a release that changes
> `_SCHEMA` or an `_ensure_*` must say that long-lived processes need
> restarting.** It is what is owed until the `user_version` argument happens,
> and if the next migration is security-relevant the argument happens first.
>
> **And it is latched, on a second reviewer's objection: *gates fail builds,
> `docs/releasing.md` does not.*** That objection is §6.12's own thesis pointed
> back at me — I wrote *the detection kit as gates, not advice* and then answered
> a finding with advice. `test_a_schema_change_has_to_be_a_deliberate_release_decision`
> pins a digest of the DDL `memory_init` leaves in `sqlite_master`: the effective
> schema rather than the source, so comments and refactors move nothing and a
> real change moves it every time, with the restart requirement in the failure
> message. Verified by adding a plausible `quorum_count` column and watching it
> go red. Stable across interpreters — identical digest under 3.10/sqlite 3.45.1
> and 3.11 — because `sqlite_master` stores the DDL as written.
>
> The latch does not upgrade documentation into a fix. It makes the
> documentation unskippable, which is a different and smaller claim.
>
> **The ledger half is unchanged and still wants arguing.** A hash chain cannot
> be re-hashed under new rules, so the format is already frozen by its first
> entry, and adding a version now leaves everything before it as an implicit
> version 0. Nothing found in review moves that question either way.

### 6.32 The loop, fourth turn — and it found the recipe's caveat was right — **measured**

*Run 2026-08-06 with `scripts/dogfood_next_piece.py`. The operator asked for
Nestor to be used to write the next piece of Nestor; I had built §6.26 without
running the loop once, which is the thing §6.19 exists to say is worth doing.*

The first three turns (§6.14, §6.18, §6.19) fed session decisions through the
translation recipe. This one feeds **`IDEAS.md`'s own open entries** through
`recipes/patch_review.py` — defect → proposed fix — and asks the six questions
somebody would type before picking up the next piece of work. The questions were
written before any score was looked at, and deliberately are **not** paraphrases
of the defect text.

**§6.30's advantage does not reproduce.**

| matcher | rank-1 on the bench corpus (§6.30) | rank-1 on Nestor's own findings |
|---|---:|---:|
| `DefectMatcher` | 7/13 | **3/6** |
| `StringMatcher` | 4/13 | **4/6** |

§6.30 shipped with a caveat in its own last paragraph: *"the probes were written
by the same person who wrote the defect descriptions — §3.4 stage 2 is the entry
about why that flatters a matcher."* This is the second corpus that caveat asked
for, and the caveat was right.

**Stated precisely, because n is 6.** One question is the entire difference.
This establishes that the 7/13 advantage **is not general** — not that
`StringMatcher` is better. What it removes is the licence to describe
`DefectMatcher` as an improvement without saying on which corpus.

**The mechanism, and it is not subtle: no morphology.**

```
"should seals expire?"  vs  "every seal is authoritative forever…"
    DefectMatcher 0.0000      StringMatcher 0.1975
    shared tokens: []
```

`seals` and `seal` are different tokens, so a token-set matcher scores **zero**
on a query that character difflib handles for free. Change one letter and
`DefectMatcher` gives 0.1111 and ranks §1.4 first. Weighting identifiers buys
precision on the rows that share an identifier and pays for it by throwing away
everything character similarity knew about the shape of a word. §6.30 measured
the win and never looked for the loss.

**And the acronym/synonym class, live on Nestor's own corpus.** *"can I catch
the error that tells me to call `revise_draft`?"* shares **zero** tokens with the
entry that answers it, which talks about `ConflictingDraftError` and "the third
verb". No lexical matcher of any kind reaches that; it is exactly the fraction
§3.3's semantic matcher exists to justify itself on, and `bench/token_matchers.py`
was written to size. Here it is, in the wild, in this repository's own notes.

**Not fixed, and that is the point.** Adding singular-folding because six
questions asked for it is fitting the corpus and calling it a method —
`bench/token_matchers.py` says so about stopword lists and §6.30 says so about
`IDENT_WEIGHT`. The fix is cheap and it should be *measured on a corpus nobody
wrote for it*, which is the same standard this entry just held §6.30 to.

**What the loop says about using Nestor to write Nestor.** `fix_for` returned
`None` six times out of six and structurally always will: everything a machine
proposes is a draft, a machine may not seal, and tier 1 serves seals. So the
answer to *"can Nestor help write the next piece of Nestor"* is **it can surface
what was already decided and it cannot decide** — the queue view is available to
a machine, the serving view is not, and the gap between them is a human at
`nestor.ui`. That is the covenant working exactly as designed, and it is worth
having measured rather than assumed.

One question earned its place: *"can I use the patch recipe to pick a fix
automatically?"* returned §6.30 at rank 1, whose fix text reads *"it is a review
queue, not a tier-1 server; do not wire `fix_for` in anger."* The recipe
correctly warned me off itself.

### 6.33 The memory has never been given the project's decisions — **measured**, fix **open**

*Found 2026-08-06 doing what the operator asked: feeding a code review through
Nestor before answering it.*

Three findings from the review of PR #46, queried against a store holding the
open `IDEAS` entries plus a session's build decisions — 21 rows. Predictions
were written down first, which is the only reason this is a finding rather than
a shrug:

| finding | predicted | returned |
|---|---|---|
| countersign idempotence | nothing relevant; new | nothing relevant (top 0.067) |
| append-failure silence | the `_log_seal_event` swallow decision | §6.29 exports, §6.31 versioning (0.083) |
| unsigned `sig` | the signing / keyring decisions | §6.31a, a README decision (0.057) |

**Two of three wrong, and the one that was right is unfalsifiable** — the
matcher returns noise for everything, so "nothing relevant" is its answer
regardless. The loop contributed nothing to that review.

§6.32 is one cause and not the main one. The bigger one: **the decisions that
would have answered two of those three are not in the corpus, and never have
been.** Why `_log_seal_event` swallows is a docstring. Why signing is opt-in is
`QUESTIONS.md` §5 and Nestor#2. Every dogfood store this project has built holds
`IDEAS` entries and one session's decisions — 21 rows against ~11k lines of
code whose distinguishing feature is that almost every line is argued.

So "use Nestor to help write Nestor" is currently limited less by the matcher
than by an empty memory. The corpus exists; it is in docstrings, `QUESTIONS.md`,
`docs/*.md` and commit messages, and nobody has fed it through.

**Not proposed: a scraper.** Harvesting docstrings into pairs would produce
thousands of rows nobody decided to put there, which is the opposite of a
memory of *checked* decisions — and every one would be a draft, so it would
grow the queue by thousands without a single seal. What the shape should be is
the open question, and it is a real one: the thing that makes Nestor's memory
worth having is that a human put each row in it.

> **Corrected in place the same day, by running it again on PR #47.** "The loop
> contributed nothing" was measured on one query set and stated too broadly. On
> #47's own decisions, **2 of 5 hit, and hit hard**:
>
> | asked about | top | retrieved |
> |---|---:|---|
> | §6.25 fixed structurally, not as proposed | **0.226** | *"Should the §6.25 init_db bug be fixed inside the §6.8 commit?"* — the decision that deferred this very fix |
> | §6.29 export the third refusal | **0.429** | §6.29 itself |
> | §6.27 path seam | 0.040 | noise |
> | three fixes in one commit | 0.042 | noise |
> | no scraper for the corpus gap | 0.042 | noise |
>
> An order of magnitude above the ~0.04 floor, not a lucky ranking. And the
> §6.25 hit was **useful**: it surfaced the decision this PR discharges, which
> is what a decision memory is for.
>
> **The split is not random and it is not about the corpus.** The two that hit
> share identifiers with their targets — `init_db`, `_ensure_unique_key`,
> `ConflictingDraftError`. The three that missed are about *practice*: how to
> shape a seam, how to size a commit, whether to scrape. Prose with no shared
> identifier, which is §6.32's mechanism confirmed on a third corpus.
>
> So the accurate statement is not "the memory cannot help". It is: **it helps
> when the question names code, and fails when the question names a practice —
> and this project's decisions are mostly practices.** That is a worse problem
> than an empty corpus, because filling the corpus does not fix it. A second
> prediction failed too: I expected *"three fixes in one commit"* to collide
> with this session's repeated decision to keep findings out of the commits that
> found them. It scored 0.042, and the right row sat at rank 2 beneath a
> nonsense score.

### 6.34 A ledger line that cannot exist was ignored by every reader — **shipped**

*Found 2026-08-06 while asking what this codebase does when it meets a state it
believes impossible. Only writers of JSON append to the ledger, so a line that
will not parse cannot happen: a torn write, a truncated copy, an editor, a
merge. It happens anyway.*

**Measured, on a four-entry chain with the third line truncated:**

| | |
|---|---:|
| non-blank lines on disk | 4 |
| `ledger.entries()` returned | 3 |
| said so | nothing |

`entries()` walked past the line and returned one fewer record. Everything built
on it inherited that silently:

* `nestor ledger entries` printed three rows of a four-line file;
* the UI's ledger tab showed three, and its **kind** filter was built from the
  three — a torn line has no kind, so it cannot even be filtered *for*;
* `portable.export_bundle(include_ledger=True)` shipped three under the note
  *"the source instance's chain, for audit"*, to the one party who cannot go and
  look at the file.

`verify()` did catch it, and `entries()`' own `# noqa` said so — *"skip, verify()
reports it."* That is true and it is not a mechanism: nothing makes a caller run
`verify()` before believing the list, and `verify()` stops at the **first**
break, so it is a verdict and never an inventory. It is TODO.md's closing
variant exactly — *a guarantee that only holds where somebody thought to look* —
and the same shape as `best_sealed` filtering `lookup()`'s top five: nothing was
bypassed, no rule was missed, the code just answered a narrower question than
the one it was asked.

**The fix is the two-walk move, not a condition.** `entries()` collects what
parses; a new `ledger.unreadable()` collects what does not. Each is bounded by
construction and neither filters the other's output, so together with an
unfiltered, untruncated `entries()` they account for every non-blank line —
which is a property the single filtering walk could not have had, because a
discard leaves no residue to count. `unreadable()` deliberately takes **no**
`limit`: the file is already fully in memory when it returns, so truncating a
damage report would buy nothing and cost the only reason to read it. The three
surfaces above now carry it — the CLI on **stderr**, so a script parsing stdout
is unaffected.

**And an off-by-one in the message an operator acts on.** `verify()` numbered
from 0 and reported the third line of the file as `line 2`. The only thing
anybody does with "line 7" is open the file at line 7. Both walks now number
from 1. Nothing pinned the old numbering — no test, no doc, no caller parsing
the string — which is why it survived.

**The write path was already right, and I published the opposite to myself
first.** A probe said a fresh process would happily append onto a torn chain. It
would not: `_verify_chain_once` refuses, and my probe had cleared
`cascade._checkpoints` while leaving `_verified_ledgers` populated, so the
process under test had already cached a verdict from the appends the probe
itself had just made. Re-run in a real subprocess it refuses on a torn tail
*and* a torn middle. The defect was only ever on the read side; one more minute
of assuming would have put a false claim about the appender in this file.

**Tests — `tests/test_ledger_unreadable.py`, 15 of them.** Against the revision
before the fix: **13 fail, 2 pass.** The two that pass before and after are the
guards — the CLI stays silent about an intact ledger, and the module leaks
nothing into `os.environ`. Three tests that read like guards (intact ledger,
missing ledger, blank lines) are **not** guards; they call the new function and
fail on `AttributeError`, and filing them as guards would have been the
flattering half of the truth. Two mutations, run:

| mutation | result |
|---|---|
| `unreadable()` numbers from 0 again | 7 red |
| `unreadable()` returns only the first damaged line | exactly 1 red — the test that names that |

**What this does not close, and it is the same shape one layer up.** A third
party using the library can still call `entries()` and never call
`unreadable()`. Every surface *in this package* now carries it, and nothing
makes the next one. The construction that would close it is a gate over the
package's own call sites rather than a better docstring — §6.12's argument, and
it is **open**.

### 6.35 The solo verifier: two records kept carefully and shown to nobody — **measured**, fix **open**

*Found 2026-08-06 by building a fixture for one person instead of a team. The
operator's framing: the code side has had all the attention and the human side
almost none, and one would complement the other. It did, in about fifteen
minutes.*

**The fixture.** `demo/shoebox.py` — Nieves Aguirre-Toll, translating her dead
grandmother's letters from Spanish for a seven-year-old who has no Spanish. One
verifier, her own archive, fourteen months. She is not keeping a memory for
consistency across a team; she is keeping one for **consistency across time with
herself**. Fiction, tagged `origin="fixture:consuelo-shoebox"` in every row and
in the trail, on a temporary store.

Nothing about the finding depends on the phrases chosen. It falls out of her
*structure* — one verifier, revising over months — and reproduces under any
archive, any language pair, any grandmother.

**Two records this package keeps carefully and shows to nobody.**

| record | kept where | read by |
|---|---|---|
| what a seal was revised *from* | `tm_pairs.superseded_by`, `memory_lineage()` | nothing in `nestor/` |
| `reopen_when` — never vs not-yet | `tm_rejections`, bundle digest v2 | `portable.export_bundle` only |

*The revision.* `Curator.replaced_seals` reads `kind="seal_replaced"`, which the
**destructive** `add_pair` overwrite writes. `supersede_pair` — the safe verb
that shipped as §6.11/§6.20's third verb — writes `kind="supersede"`. Measured
on her store, where a seal was demonstrably replaced: `/api/replaced-seals`
returns **0 rows at both settings**. `memory_lineage` has no caller anywhere in
the package; the only production reference is `storage.py`'s capability-name
list. `portable.py:190` then drops superseded rows from the bundle, so the
history does not travel either.

*The deferral.* `reject_match(reopen_when=...)` is stored, versioned into the
digest (that is what `BUNDLE_VERSION = 2` is for) and exported. No human-facing
surface reads it. Its own docstring says *"a reader that surfaces rejections
should surface a non-empty `reopen_when` as a condition to re-check, not a
closed door"* — a sentence describing a reader that does not exist.

**Stated precisely, because neither is total invisibility.** Both events are in
the raw ledger and she can scroll it. The chain carries her reason **in full**
and the text she replaced as a **digest**. So she can learn *that* she changed
her mind and *why*, and not *what she changed it from*, on any shipped surface.

**Why a team never finds this.** `replaced_seals`' own docstring calls a
different verifier's overwrite *"the highest-signal event this surface
reports"* and files self-correction as *"routine and never refused"*. For a team
that is defensible. For Nieves, self-correction is the **only** revision that
can ever occur, so `conflicts_only=True` — the UI default — is empty by
construction and stays empty for as long as she is the only person holding a
key. The surfaces are not wrong about teams. They were never asked about her.

It is the shape TODO.md's closing note already names, one layer out: not a guard
that can be reached around, but **a record whose only reader was the use case
somebody had in mind**. §6.34 was the same shape on the ledger's read side a few
hours earlier — that one had `verify()` as a partial reader; these have none.

**The gates.** `tests/test_shoebox.py` runs the fixture, and its two gap
assertions fail when a gap is **closed** — the good outcome, and it still has to
stop the build, because a demo narrating a gap that no longer exists is the same
defect as one narrating a fix that never landed. Both proven to fire, by
mutation:

| mutation | result |
|---|---|
| `replaced_seals` also reads `kind="supersede"` | red — *"GAP CLOSED … blind to supersede"* |
| the rejections view carries `reopen_when` | red — *"GAP CLOSED … no human-facing surface reads reopen_when"* |

**Not fixed here, deliberately.** The obvious fix for the first is to make
`replaced_seals` read both kinds, and that is the move CLAUDE.md warns about —
another condition on a surface that already has one. The question underneath is
whether "somebody overruled you" and "you changed your mind" are one view with a
filter or two views, and that is a design decision about what a reviewer is
looking for, not a spelling of a `kind`. Deciding it from inside the fix is how
this repo has produced three criticals in a row before. **Open**, and the fixture
now fails the build if either gap closes without this entry being updated.

### 6.36 `nestor keys add` prints the wrong key and calls it the only copy — **measured**, fix **open**

*Found 2026-08-06 by standing up a second instance (§6.35's fixture, box B) and
enrolling a verifier on it. Not found by the test suite, which never reads the
sentence.*

`cmd_keys` emits one message for all three ways to add a verifier:

```
added nieves to keys.json
  key  7b73c0cd0ddf020f…
  This is the only time it is printed. nieves needs it to sign in
  to the UI; the file itself is 0600 and holds the copy Nestor
  verifies against.
```

Three claims. **All three hold for `hmac`**, the default: `entry.key` *is* the
shared secret, it *is* only printed here, and it *is* what signs in. On both
ed25519 paths they fail, and they fail differently.

**`--type ed25519` (generate).** `Keyring.add` stores the public half as
`entry.key` and the secret as `entry.private`; `signing_key()` returns
`entry.private` for ed25519, and `Sessions.open` compares what is offered
against that. So the CLI prints the half that does not sign in. Measured against
box A's keyring:

| key offered at `/api/session` | result |
|---|---|
| the one `nestor keys add` printed (public) | **403** — *"that is not nieves's key."* |
| the one it never printed (private) | 200, session opened |

The verifier is handed a key that is refused, told it is the only time they will
see it, and never shown the one that works. It is in the 0600 file, which the
message points at while describing something else.

**`--type ed25519 --public HEX` (register a peer).** The key was typed on the
command line by the operator, so *"the only time it is printed"* is false before
the command runs — it is in their shell history. And the peer does not need it
to sign in: they sign on their own instance with their own private half, which
is the entire point of the peer case. Measured: a peer entry reports
`can_sign=False`, exactly as designed. The sentence describes the opposite.

**Also the machine-readable half.** `--json` emits `"key": entry.key.hex()`,
which is the public half for ed25519. Consistent with the data model and still a
trap: a script that pipes `.key` to a new verifier hands them something that
cannot sign in.

**Severity, stated precisely so nobody over- or under-reads it.** This is *not*
a disclosure bug. A public key is not a secret and printing it costs nothing.
The damage is an operator who cannot sign in and believes they have lost their
only copy, and a sentence that teaches people to treat a public key as a
credential — which is the habit the asymmetric work in TODO §1 exists to break.

**Why it survived.** It is `docs/code-review-lessons.md`'s pointed-prose rule
again: *a claim in a sentence must hold across every value that sentence can
take.* The message was written when `hmac` was the only kind, and ed25519 was
added underneath it (Nestor#17) without the sentence being re-read. Same error
as the refusal that read *"close enough to be tempting"* — true at 0.71, false
at 0.11.

**And the fix is not the usual move.** CLAUDE.md says a failing guard wants the
interaction removed rather than a condition added. That rule does not apply
here: this is not one mechanism doing two things, it is **one sentence written
for one case and applied to three**. Three cases that differ in what the key
*is* want three messages, and collapsing them into flat prose that is true
everywhere would drop the one thing an operator actually needs — where their
signing key is.

Which leaves the question this entry does not decide: **should the generate case
print the private key at all?** Printing a signing key to a terminal puts it in
scrollback and history; not printing it means the message must say where to find
it instead. That is a deployment decision of the same family as TODO §1's key
distribution, and it should be made with that rather than in passing. **Open.**

### 6.37 The entity graph destroys what the numeric recipe keeps, and has no word for an ambiguous name — **measured**, fix **open**

*Found 2026-08-06 by extending §6.35's fixture past translation. Nestor has three
recipes and the shoebox exercises all three: the letters are Spanish, the people
in them are an entity graph, the recipe notebook is figures. The people are where
it broke.*

**The case.** In Spanish families given names repeat. Consuelo's father was José
— *Pepe*. Her brother was also José — also *Pepe*. Two men, one nickname, thirty
years apart, both in the same shoebox. Nieves seals the second:

```
people.seal("Pepe", "Jose Aguirre Toll (1938-2011)", verifier="nieves")
    -> succeeded. No exception, no warning.

live rows for 'Pepe'                :  1  -> Jose Aguirre Toll (1938-2011)
memory_lineage(that row)            :  []
replaced_seals(conflicts_only=True) :  0     (the UI default)
```

Her great-grandfather is gone from the store. Not superseded — **overwritten**,
by `add_pair`'s destructive path.

**The guard that should have fired cannot.** `EntityResolver.seal`'s own
docstring says *"two aliases resolving to different canonicals is the entity
graph's version of a conflicting seal — `AWS` meaning one company to one analyst
and another to the next is precisely the disagreement worth stopping."*
`ConflictingSealError` is raised by `add_pair` **unless the verifier matches**,
because a same-actor re-seal is a correction. For one person holding one archive
that exemption is always in force, so the protection the recipe advertises can
never stop anything. Same shape as §6.35: a mechanism built around two people,
meeting one.

**And the semantics are wrong for the domain, which is the deeper half.** In
translation a same-actor re-seal usually *is* a correction — §6.35's `me hago
cargo` is exactly that. In an entity graph it usually is **not**: a second
canonical for one alias normally means two entities, not a fix. Translation's
rule was inherited without asking whether it fits.

**What makes it a defect rather than a design: the sibling recipe already
solved it.** Same situation, one verifier, second value for the same key —
measured in both:

| recipe | the old value | the chain |
|---|---|---|
| `reconcile.seal_baseline` | **survives** — `memory_unseal`'d to draft, still in the store | `baseline_replaced` names `200` in plain text |
| `entity.seal` | **gone** — no live row, empty lineage | `seal_replaced` carries only `4f25dd8e…` |

`reconcile._guard_existing_baselines` was written on purpose, and says why: *"a
second baseline does not replace the first, it joins it, and `check()` would
then have two figures to pass against."* Read `alias` for `label` and that
sentence is about the entity graph too.

One qualifier, because it is not unrecoverable: `entity_seal` writes the
canonical **verbatim** to the chain, so `Jose Aguirre (1901-1974)` is still in
`ledger.jsonl`. Recoverable from the chain, absent from the store, invisible on
the default curator view. Better than `seal_replaced`'s digest, worse than
`reconcile`.

**There is no vocabulary for ambiguity, and structurally there cannot be.**
`check()` returns `ambiguous: bool` and `baseline_count: int`, and its docstring
argues which baseline to prefer when they collide and why "newest" beats
"closest". `resolve()` returns `canonical / confidence / sealed / provenance`
and nothing else. It cannot grow the field without a store change: one live row
per normalized source means a second canonical replaces rather than joins.

The obvious workaround was measured and does not work. Disambiguated surfaces
coexist happily —

```
Pepe (el padre de Consuelo)    -> Jose Aguirre (1901-1974)
Pepe (el hermano de Consuelo)  -> Jose Aguirre Toll (1938-2011)
```

— and `resolve("Pepe")` still returns one man, `sealed=True`, `confidence=1.000`,
with nothing indicating the other exists. This is §6.22 — *a name is not a word:
the proper-noun case has no field* — reached from the other end, and it is the
same entry's open design question.

**A scope boundary the archive case walks into, stated because it is not a
bug.** `resolve("Pepe vino a comer")` returns nothing, not even a suggestion:
the resolver matches a whole surface against sealed aliases and does not find
names inside prose. `surface -> canonical` is what it says it does. But it means
she has to already know "Pepe" is a name before she can ask about him, which is
precisely what she does not know while reading a letter in a language she reads
badly. Whether that gap belongs to `nestor.segment`, to a recipe, or to nobody
is undecided.

**A probe that came back negative, recorded because otherwise this list reads as
if every look finds something.** Her name is a cookery term — `a punto de nieve`
is sealed in `es/en` and `Nieves` in `person`, the same word in two domains at
once, which is the normal condition of a personal archive and never of a company
deployment. I expected no way to ask *"what have I decided about this word,
anywhere"*. There is one: `Curator.list(contains=...)` crosses domains, and
`GET /api/pairs?contains=` exposes it. Both return both rows. **Nothing to fix.**

**Not fixed, and the reason is specific this time.** Porting
`_guard_existing_baselines` across would take an afternoon and would decide, in
passing, that an alias may hold exactly one canonical and old ones get retired.
That is a product decision — *a second canonical replaces the first* and *a
second canonical joins it* are different tools — and §6.22 has it open already.
The fixture is the thing to keep: it is the case that makes the question
concrete, and it took a fictional woman with two dead relatives called José to
produce it. **Open.**

**Retrieval, third data point.** `dogfood_codebox.py --look` on this finding
returned the wrong row at 0.042, and ranked §6.35 — this finding's structural
sibling, the entry that would have told me exactly where to look — **third, at
0.031**. The box has now failed to connect a new finding to its own sibling
three times running. §3.3's argument, again, from inside the tool.

### 6.38 `locks_in_text` is a raw substring, so a short lock fires inside longer words — **measured**, fix **open**

*Found 2026-08-06 giving §6.35's fixture a glossary. The second blindness on the
line §6.22 already corrected itself about, and a different one.*

```python
lower = text.lower()
return {t: tr for t, tr in terms_for(source_lang, target_lang).items()
        if t.lower() in lower}                    # glossary.py, locks_in_text
```

`in` on a string is a substring test with no word boundary. Measured, with
`{"Tito": "Tito"}` installed — her uncle's name, in a recipe notebook:

```
'Tito trajo el vino'                        -> {'Tito': 'Tito'}
'se come con buen apetito'                  -> {'Tito': 'Tito'}
'hay que comer con apetito, dice la abuela' -> {'Tito': 'Tito', 'abuela': 'abuela'}
```

The glossary is **tier 2's constraint**: `locks_in_text` feeds
`engine.system_prompt(locks=...)`, which emits *"Locked terminology — always
render these terms exactly as given."* So a sentence about appetite goes to the
draft engine carrying an instruction about a man.

**Distinct from the blindness already recorded, and worth keeping separate.**
§6.22 corrected itself in place about *case*: both sides are lowercased, so
`{"Nestor": "Nestor"}` fires on *"the nestor of the committee"*. Every example
in that correction is a whole word, so the boundary problem is invisible in it.
Case-blindness makes a lock fire on the wrong **sense** of the right word;
boundary-blindness makes it fire on a word that was never there. Same line, two
failures, and only one of them was known.

**Why a family archive found it and a company deployment would not.** Business
term bases lock long, distinctive strings — product names, legal phrases. A
personal archive locks nicknames, and nicknames are short: `Tito`, `Chelo`,
`Pepe`, `Nieves`. The shorter the lock the likelier it is a substring of
something ordinary, and Spanish is rich in the endings that make it happen.

**Not fixed, and the trade is real.** A word boundary kills `Tito` inside
`apetito` and also kills `abuela` matching `abuelas`, which the substring gets
for free — the glossary has no morphology and substring is standing in for it.
So the choice is between a lock that over-fires and one that misses every
inflection, and picking either from inside a bug fix decides what a term lock
*is*. Deliberately left: no test pins the current behaviour, because a test
asserting `Tito` matches `apetito` would fail on the fix, and
`scripts/dogfood_session_decisions.py` already argues that findings which should
move are printed rather than pinned. Nor does `locks_in_text`'s docstring name
either blindness — it says only *"the subset of glossary terms that actually
appear in this segment"*, which is what the function is for and not what it
does. Annotating the defect where it lives would be worth a line and is not
done here.

**Related and not the same:** §6.22's real question is whether a glossary can
express *do not translate this*, and the answer stayed no. This entry does not
change that. It removes one more reason to reach for the glossary as the way out.

### 6.39 The entity graph has only the verb a machine may not use — **measured**, fix **open**

*Found 2026-08-06 by putting a living person into §6.35's fixture. The operator
gave Nieves an aunt, the aunt met somebody, and the honest record of that is a
row nobody has verified.*

`EntityResolver` has three public methods:

```
seal          surface -> canonical, status="sealed", appends entity_seal
add_alias     calls seal
resolve       reads
```

There is no way to **propose**. To put an unverified alias into the entity graph
you go around the recipe and call `memory.add_pair(..., status="draft")`
yourself, which is what this fixture had to do — Nieves has not met Tony, her
aunt described him on the telephone, and *"goes by Tony"* does not license
writing down *Antonio*.

**The reader is already there.** `resolve()` has a full branch for the state the
writer cannot produce — measured on the row added by hand:

```
resolve("Tony") -> {"canonical": None, "sealed": False,
                    "provenance": {"draft": True,
                                   "suggestion": "Tony (b. 1972)", ...}}
```

`canonical=None` with a `suggestion` the caller *"may queue for a human seal"*,
in the docstring's words. So the recipe describes a queue it has no verb to put
anything into.

**And it is the covenant's own shape.** The one verb the entity graph offers is
the one a machine may not use. Ground rule: propose, do not confirm — and in this
domain there is nothing to propose *with*. §6.19 and §6.20 gave the translation
domain its second and third verbs (`revise_draft`, `supersede_pair`) after
argument; the entity graph never got its first.

**Checked before claiming there is no design question under it**, because that
claim was made in conversation first and this repo has a rule about the
difference. Both edge cases are already decided by `add_pair`, so `propose`
inherits rather than invents:

| | |
|---|---|
| a draft landing on an already-**sealed** name | returns the existing sealed row, untouched — no overwrite |
| a second, **different** draft for one surface | raises `ConflictingDraftError` (§6.19's message) |
| either, on the chain | nothing appended — a proposal is not a decision |

That last row is also the one thing `propose` must **not** copy from `seal`: no
`entity_seal` entry. `seal` appends because a seal is a decision. The published
dogfood stores already establish the rule — a store of pure drafts has an empty
chain by construction.

**So the shape is:** `propose(surface, canonical, reason="", origin="")` =
`seal()` minus the seal, minus the verifier, minus the append. Unlike §6.35,
§6.37 and §6.38 this one is not parked on a design question — it is parked
because it was found at the end of an afternoon and nothing here ships
unreviewed. It is the smallest open entry on this list and the only one I would
take a patch for.

**A note on how it was found, because it is the fixture's third hit and the
pattern is now legible.** §6.35 came from one verifier revising her own work.
§6.37 came from two dead men sharing a nickname. This came from one living man
nobody has met yet. All three are states a business deployment either does not
reach or reaches with a colleague standing next to it, and all three were
invisible until somebody's actual life was in the store. The fixture is worth
more than the entries it produced.

### 6.40 `nestor ui` can be aimed at a custom domain and cannot be told its matcher — **measured**, fix **shipped**

*Found 2026-08-06 by standing a fictional client's intake desk next to a desk
reviewing this repo, in `demo/two_desks.py`. Both desks brought their own
matcher, because the README's recipe table invites exactly that. Only one of
them survived the human surface, and §6.41 is why.*

The surface takes the domain and not the matcher:

```
nestor ui --source-lang incident --target-lang incident     # accepted
nestor ui --matcher …                                       # no such flag
ui.App(store, source_lang=…, target_lang=…, engine_name=…)  # no such field
```

So every write the UI makes goes through `memory.get_matcher(None)` — the
process-wide default, `StringMatcher`. Measured, on a domain whose matcher keys
an incident report to the device serial it names:

| | |
|---|---|
| draft written by the domain | key `'CH4471'` |
| the human seals it at `/api/seal-draft` | HTTP **200** |
| the row that is now sealed | key `'pump sn ch4471 overdelivered during the night run'` |
| the draft she was sealing | **still a draft**, still queued |
| `best_sealed` for the *exact wording she sealed* | **None** |

`_seal_draft` loads the row by id — it is holding `source_norm` — and then calls
`add_pair(row["source_text"], …)`, which recomputes the key from the text with
the default matcher. `memory_find` on the recomputed key misses the draft, so
this is an insert rather than an upgrade. Two rows for one incident: a signed,
chain-recorded seal under a key the domain will never compute, and the draft it
was supposed to retire.

**The rejection path is the same defect and the worse consequence.**
`_reject_match` passes no matcher either, so a human's *no* is filed under
`query_norm` computed by `StringMatcher`, while `best_sealed` looks rejections
up under the domain's own key. Measured: `rejected_ids` under her key is
`(set(), set())`; under the UI's key it holds the target. The record is real,
correct and signed. It is filed where nothing will ask for it, and the wrong
match is served again.

That is the README's first two promises — *verified once, served forever* and
*a wrong match is never served again* — both void for any domain that took the
Matcher seam at its word.

**The audit trail cannot catch this, which is the part worth sitting with.** The
chain is intact and every entry in it verifies. Nothing was tampered with,
nothing was forged, and a `nestor ledger verify` is clean. The record is *true*
and the answer is *missing* — a failure mode no hash chain is aimed at, in the
one product whose pitch is that the trail is the guarantee.

**The rescue exists and is one per process.** `memory.set_matcher(SERIALS)`
fixes it completely — measured: the UI upgrades the row in place, the key
survives, `best_sealed` returns 1.0. It is a module global. So one interpreter
holds one matcher, and with the intake desk's installed, the review desk's next
defect — prose about code, quoting a device serial as any real write-up would —
is stored under `'CH4471'`. Two custom-matcher domains are two deployments.
Nothing in the package, the README or `docs/` says so.

**Not proposed here, deliberately:** the fix. `ui.App` gaining a `matcher` field
threaded through `_seal`, `_seal_draft` and `_reject_match` is what the mutation
below implements and it turns all eight of the fixture's gap assertions red, so
it is *a* fix. Whether it is the right one is a design question this entry does
not settle: the alternative is that the UI stop recomputing a key it was already
holding, which is the smaller change and fixes `_seal_draft` without answering
what `_seal` or a fresh `/api/reject-match` should do. Per `CLAUDE.md` this
touches persistence and the audit path and wants an adversarial read before a
patch, not after.

---

**Shipped 2026-08-07, as the `ui.App.matcher` version — and the entry above was
right to hesitate, because the smaller alternative is wrong.** "Stop recomputing
a key it was already holding" fixes `_seal_draft`, which is the one path holding
a row whose `source_norm` it could reuse. It has no answer for `_seal` (raw text,
no row), for `/api/reject-match` (a *query* that was never stored), for
`/api/ask`, or for `/api/match` — all of which must key by something, and in a
custom domain the only correct something is the domain's matcher. Reusing a
stored key would also make the surface unable to *re-key* a row whose matcher
changed, which is a repair operation the curator will eventually want. So the
field it is.

What shipped is wider than the three functions named above, because tracing the
paths found more of them:

| | |
|---|---|
| `ui.App.matcher` | the domain's matcher, injected like `store`. `None` = defer to the process-wide one, so nothing changes for a host that never had this problem |
| `nestor ui --matcher` | the **shipped** matchers by name. A custom one cannot come off a wire and the flag's help says so |
| threaded through | `_seal`, `_seal_draft`, `_reject_match`, `_queue_seal` (both branches), `_queue_reject`, `_ask`, `_match` |
| `cascade` | `translate_segment`, `translate_text`, `graduate_segment`, `reject_segment` all take `matcher=` — the serve path was global-only too, so `/api/ask` disagreed with the writes |
| `answer` | `ask(matcher=)`; `match()` now takes a `Matcher` **or** a name, because a name cannot conjure a custom one |
| `/api/state` | reports `domain.matcher` and `domain.matcher_source`. Two surfaces keyed differently used to describe themselves identically, which is what made this invisible |

`/api/match` **refuses** a named matcher when the App has its own (400) rather
than silently substituting: answering "would this be served?" under a different
notion of similarity than the one that sealed the row is a confident wrong answer
to the only question Nestor is asked.

Proven by mutation *after* the fix as well as before: reverting the seven
`matcher=app.matcher` call sites to `None` turns 8 of the 12 tests in
`tests/test_ui_custom_matcher.py` red. The 4 that stay green are the ones about
the field and the refusal rather than the threading, which is correct and worth
recording — a test that passes under the mutation it was written to catch is a
test that proves nothing.

`demo/two_desks.py` keeps every beat and inverts every outcome; its eight `gap()`
assertions are now `claim()`s. The fixture is kept rather than retired because it
asks the same questions it asked when the answer was no.

**Proven by mutation before commit.** Implementing the `ui.App.matcher` fix and
wiring the fixture to pass each desk's matcher turns all eight gap assertions in
`demo/two_desks.py` red and the run exits non-zero. The first version of the
beat-7 assertion was **vacuous** and is worth recording: it compared the stored
key to `SerialMatcher.normalize(text)` for a defect description containing no
serial, where that matcher falls through to `str(v).strip().lower()` — which is
byte-identical to `StringMatcher`'s output for that string, so the assertion held
whether or not her matcher was installed. It was rewritten around a defect
description that quotes a serial, where the three matchers produce three
distinct keys. That is `CLAUDE.md`'s "a test that cannot fail", found in a test
written to prove a gap, by the same session that had just read the rule.

### 6.41 An optional method on the Matcher seam is what decides whether seals survive — **measured**, design **answered, everywhere**

*The other half of §6.40, and the reason it went unfound for so long: the two
desks in `demo/two_desks.py` hit the identical bug and only one of them notices.*

`README` calls `Matcher` **a two-method seam** — `normalize` and `similarity` —
and `recipes/patch_review.py` describes `score(raw_a, raw_b)` as *"the optional
`score`"*. `best_sealed` prefers it when it is present, and then compares the
raw query text against each row's `source_text`, **never consulting the
normalized key at all**.

So a wrong key is free for a matcher that implements the optional method, and
fatal for one that does not:

| matcher | `score()` | key rewritten by the UI | seal still served |
|---|---|---|---|
| `DefectMatcher` (the review desk) | yes | yes | **yes**, 1.000 |
| `SerialMatcher` (the intake desk) | no | yes | **no** — `None` |

Both desks are running the same package through the same endpoint with the same
defect underneath. The intake desk implemented the seam exactly as documented
and lost a human's verification; the review desk implemented one method more
than it had to and kept it.

**Measured by mutation, and it is a one-method diff.** Adding `score()` to
`SerialMatcher` — touching *nothing* in `nestor/` — makes her lost seals
reachable again and turns this entry's gap assertion red along with the two in
beat 3 that say her verification is gone. The guarantee is riding on a method
the seam says is optional.

**The design question, not picked here.** Three coherent answers and they are
not the same product:

* `score()` is **not** optional — promote it to the seam and say so, which
  breaks every matcher written against the documented two.
* The UI stops re-keying, and `score()` stays a performance and fidelity
  choice rather than a correctness one. This is §6.40's smaller fix.
* The seam keeps both paths and the package **says** which guarantees hold on
  each, which is the honest documentation answer and fixes nothing.

The reason to write it down rather than pick: this is the same shape as §3.1's
`normalize`-versus-`score` split, which was argued on retrieval quality when the
question was retrieval. It turns out to also decide whether a seal is reachable,
and that argument has not been had.

**Answered 2026-08-07 by §6.40 shipping, and it is the second option — at
`nestor ui`.** That surface stops re-keying: it keys with the domain's own
matcher, so `score()` goes back to being the performance and fidelity choice §3.1
argued it was, and the two methods the README documents are sufficient *there*.
The first option is not taken: promoting `score()` to the seam would break every
matcher written against the documented two, to fix a problem that turned out to
be the caller's, not the seam's.

**Was still open at `nestor serve` and `nestor ask`** — a correction owed to an
audit that caught the first version of this paragraph claiming the whole question
closed. Neither surface had a matcher field: `serve.Server.call` reached
`answer.ask` with none, `nestor_match` took a name only, and `cli.cmd_ask` did
the same. Both are launched as *processes*, so `memory.set_matcher()` was not
reachable either, and unlike `ui.App` neither is usefully constructible as a
library object with one injected. So a model asking over MCP, or an operator at
the terminal, got `pending` for a phrase a human had sealed through the fixed UI.

**Closed 2026-08-07 by `answer.load_matcher`.** The missing piece was never a
flag — `nestor ui --matcher` already existed and took shipped names, which is
exactly the thing that cannot name a custom matcher. What a process needs is a
*spec*:

```bash
nestor serve --matcher acme.incidents:SERIALS     # a module attribute
nestor ask   --matcher acme.incidents:SerialMatcher   # a class, or a factory
nestor ui    --matcher acme.incidents:SERIALS     # the same spec, same loader
```

Measured end to end over real stdio MCP, one sealed row keyed `CH4471`, the same
question asked twice:

| | |
|---|---|
| `nestor serve` (no `--matcher`) | `verified: False`, state **pending** |
| `nestor serve --matcher acme_incidents:SERIALS` | `verified: True`, state **sealed** |

`Server` gains `matcher` and the same `domain_matcher()` rule `ui.App` learned
the hard way — the server's matcher for the server's domain, and nothing else,
because every tool takes per-call domain tags. `nestor_match` refuses a name that
disagrees with what is in force and honours one that agrees, matching the browser
surface; a model is less able than a human to notice a confidently wrong answer.
`nestor_propose` needs nothing: it writes a segment, not a pair, so it keys
nothing (pinned by a test, so a future change that starts keying is noticed).

**The loader imports and runs the module named**, which is why the spec is a flag
and never a value read from a request, a bundle or a stored row. It is the same
authority the command line already has — an operator who can pass this flag can
pass `python -c` — so it is not a new privilege, but the boundary is worth
stating rather than assuming. It also validates: something that is not a matcher
is refused at load time, because a seam failure at the first *query* arrives
after the operator has been told the server started.

So `score()` is now optional on every surface, which is what this entry asked
for. "Every" was checked rather than assumed, and an audit found two it had
missed: `nestor_resolve` (which honoured nothing while `nestor_ask` beside it
honoured the matcher, so one server gave two answers about one row) and `nestor
calibrate --matcher`, still restricted to shipped names — the one tool
`memory.py` tells you to measure a threshold with, unusable by anyone who had
just followed this entry's advice to ship a custom matcher. Both take the spec
now. The epistemic point stands and is the reason to keep reading it: **a defect
that spares whoever implemented more than the documentation asked, and bites
whoever implemented exactly what it asked, is invisible to the person who wrote
the documentation** — they are the most likely to have done more.

What stays true, and is the part worth keeping this entry for: **the guarantee
was riding on an optional method, and that is why nobody found it.** A defect
that spares whoever implemented *more* than the documentation asked, and bites
whoever implemented exactly what it asked, is invisible to the person who wrote
the documentation — they are the one most likely to have implemented more.
`demo/two_desks.py` beat 6 still measures the one-method difference between the
two desks for exactly this reason; it is no longer a gap, it is the explanation.

---

### 6.42 The quorum memo's step 2 has been unrunnable, and its zero would have been unreadable — **measured**, question **open**

*Written 2026-08-06. Not a defect in the package — a defect in the way its one
open persistence question was going to get answered.*

[`docs/seal-staleness-and-quorum.md`](docs/seal-staleness-and-quorum.md) §5 lists
four steps toward N-of-M sealing. Step 1 shipped (§6.26 — concurrence stopped
being discarded). Step 2 is *measure whether anyone countersigns*, and everything
below it is blocked on the answer, because N-of-M is a schema change to the
audited path.

The memo ends step 2 with three words: **"Nobody has run it."** It stayed that
way partly because the measurement had two ways to come out wrong, and both look
like an answer.

**The count is not the number of entries.** The memo says so — *distinct actors
is the measurement; entries are the evidence* — and now it is measured rather
than argued. A chain where one reviewer countersigned one pair three times:

```
   4 entrie(s)                    what `grep -c countersign` would say
   2 distinct (pair, verifier)    what step 2 asks for
```

Three of those four entries are one person, one pair, three clicks. The
asymmetry is deliberate — a seal is a *state* and re-asserting it changes
nothing, while a countersignature is an *event* — and it means a UI retry or a
flaky client inflates the raw count without anybody countersigning anything.
Measured on a chain `memory.add_pair` wrote: four re-seals produced **1** seal
entry and **3** countersign entries.

**The zero has two meanings and only one of them is data.** `add_pair` logs a
countersignature only when `first and verifier and first != verifier` — both
sides must name themselves. So a chain with one reviewer *cannot* produce one,
however its reviewers feel about quorum:

```
   no second reviewer   1 named actor(s) in the whole chain
   measured             2 people decided things here, so a countersignature
                        was available — and none of them took it
```

Those are the same zero and different findings. Reporting the first as "no
demand for quorum" is [`scripts/feed_all.py`](scripts/feed_all.py)'s conflation
with different nouns: *nothing matched* and *I could not look* are different
sentences, and so are *they did not* and *they could not*. The discriminator is
in the chain — count the distinct people who ever decided anything in it — so
the tool can tell without being told.

[`scripts/count_countersignatures.py`](scripts/count_countersignatures.py) reads
a chain and nothing else: no store, no matcher, no process globals, no writes,
and a chain that does not verify gets no count at all. A tally over an entry
somebody may have edited is worse than none, because it reads as a measurement.

**What is still open, precisely.** The tool exists and is gated. It has been run
against fixture chains covering all four of its verdicts. It has **not** been run
against a deployment, because there is no deployment chain in this checkout —
`data/ledger.jsonl` does not exist and the dogfood store is drafts. So step 2's
*answer* is exactly as unknown as it was this morning. What changed is that the
question is now askable by somebody with a real chain, and cannot be answered
wrong in the two ways it was going to be.

**And the count is of names, not people.** jeles reaches the same bar of 2 from
the other direction (`jeles/_independence.py`) and is careful about what it
buys: two distinct domains can still be one actor who bought both, so its rule
is "a cheap heuristic, deliberately weaker" than its constitution's Independent
Witness. That caveat lands harder here. jeles at least has
`registrable_domain()` to collapse two pages on one site into one source. There
is no such function for humans, and two names in the `verifier` column can be
one person with two keys.

---

### 6.43 `dogfood_store.py --verify` says the store matches the decision files, and does not check where a row came from — **measured**, fix **open**

*Found 2026-08-06 while consolidating seven branches into one and correcting the
`pr` field in seven decision files. Found by querying the store instead of
trusting the gate that had just said the store was correct.*

The builder turns each file's `pr` field into every row's **origin**:

```python
origin = f"pr:{data.get('pr', '?')}"
```

`--verify` compares a digest, and the digest is over three columns:

```python
rows = sorted((p["source_text"], p["target_text"], p["status"]) ...)
```

`origin` is not among them. Neither is `reason`. So a decision file can change
where its rows claim to have come from, the committed `.db` can keep saying
something else, and the gate prints:

```
the committed store matches the decision files, and seals nothing
```

Measured: set `"pr": 9999` in one decision file, do **not** rebuild, run
`--verify`. Exit 0, digest unchanged, and the store still says `pr:?` for those
rows. The sentence the gate prints is wider than the check it ran — it says
*matches the decision files*, and it means *the questions, commitments and
statuses match*.

Why it matters more here than the size of the bug suggests: the dogfood store's
entire claim is provenance. `tests/test_dogfood_store.py` opens by saying the
value of that store "is entirely in where its rows came from — a memory whose
contents arrived from somewhere nobody can see is not an audit trail, it is a
pile." The one field carrying *where it came from* is the field the gate does
not cover.

**It is also the repo's recurring shape, in a mild form.** The digest is a
narrower assertion than the sentence printed beside it, so the guard is real and
the promise is not — `docs/code-review-lessons.md` §8–§9, one layer up from the
usual instance.

**Fix, deliberately not taken in the consolidation PR that found it.** Add
`origin` (and probably `reason`) to `_bundle_digest`. That churns the digest once
and closes it. It was left out because the branch it was found on exists to
*reduce* scope, and a gate's semantics changing inside a seven-branch merge is
the wrong place to hide it. The finding is here so the fix can be its own change
with its own mutation test — a digest that does not go red when `origin` moves is
the whole defect, so the test writes itself.

**Not affected:** this consolidation's own correctness. The seven files' origins
were checked by querying `tm_pairs` directly rather than by believing `--verify`,
which is how the gap was noticed at all.

---

### 6.44 `nestor_propose` discards a forbidden argument without saying so — **measured**, fix **open**

*Found 2026-08-06 by running jeles' own escalation against this package
(`scripts/audit_against_jeles.py`). jeles closed this hole after demonstrating it
had one; the demonstration is what made it worth aiming here.*

`conflict_scan.py` carries a comment recording a hand-built proposal that claimed
`verification_kind="human"` and **was given it**. The fix was an allow-list
(`_ALLOWED_ARGS`) plus a pin, and jeles was explicit about the shape of the
refusal: an argument outside the list "produces an error receipt naming what was
refused. It is **not silently dropped**, and it does not stop the rest of the
list."

Aimed here, the escalation fails — which is the part that matters:

```
nestor_propose {source_text, candidate, status: "sealed",
                verifier: "a-machine", verification_kind: "human"}
  -> {"state": "draft", "verified": false,
      "note": "queued for human review — a proposal is never served as verified"}
```

`answer.propose` has no `status` parameter to pass, and `serve.call` forwards
named arguments rather than splatting the dict, so there is nothing to smuggle
through. That is one step *earlier* than jeles' vet, and stronger: no verb, no
argument, nothing to allow-list.

**The gap is the reply.** Three forbidden arguments were discarded and the
response says so nowhere. A model that sent `status: "sealed"` gets an
unqualified success and a general sentence about human review. It has no way to
learn that what it asked for is refused, so it will ask again.

This is the same asymmetry §6.26 closed for countersignatures — *"a reviewer who
countersigns believes they did something, and nothing anywhere records that they
did"* — and the same one `ConflictingDraftError` exists for. It is also the
persona rule applied to a machine reader: **a refusal has to read as one, and if
you did not do something the sentence saying so must contain the not.** The note
is true and general; it is not a refusal of what was asked.

**Fix, not taken here:** name the discarded keys in the reply, the way the
keyring already names an unknown verifier (`'(empty)' is not in the keyring`).
Left open because the reply shape is a wire contract with any MCP host, which is
a wider blast radius than the audit branch that found it.

**What the rest of the audit found** — 2 satisfied, 3 differently, 0 failing:

| | |
|---|---|
| JELES-RUNG | **satisfied** — closed one step earlier than jeles' vet |
| JELES-RECEIPT | **differently** — above |
| JELES-WITNESS | **differently** — key custody, and it is off by default |
| JELES-INDEPENDENCE | **differently** — one *signed* attestation against jeles' two unsigned |
| JELES-DEFAULT | **satisfied** — `add_pair` defaults to `draft`; `put_nugget` defaults to `human` |

The defaults falling opposite ways is the one worth keeping. A caller here who
says nothing **proposes**; a caller there who says nothing **asserts a human
checked it**. jeles guards that at its gateway and this package does not need to.
Recorded because an audit that reports only where the audited party is weaker is
not an audit, it is a posture.

**And the witness verdict was FAILS on the first run, wrongly.** The probe sealed
with an empty verifier under a single `NESTOR_SEAL_KEY`, saw it verify, and
reported that an anonymous seal is served. Under a keyring the same call is
refused *before the store is touched*, with the empty string rendered `'(empty)'`
— somebody had already thought about that exact case. What the probe had measured
was the weakest of two configurations, picked by accident because it was the one
the script set at import. Second false FAIL in one day from a probe that did not
reproduce the condition it named; both are now pinned by tests that run both
configurations.

---

### 6.45 Two repositories hit "a condition checked outside the write", separately, and both wrote down what it cost — **verified**, lesson **shipped**

*Round 2 of the jeles/Nestor exchange, 2026-08-06. A reading, not a run —
[`docs/two-stores.md`](docs/two-stores.md) cites a file and line for every claim.
Nothing was imported, executed or written on jeles' side.*

`jeles/corpus.py:168-174`, explaining why the overwrite guard is a callable run
*inside* the write transaction rather than a check in the caller:

> a check that reads the prior record, returns, and only then writes is a
> read-modify-write with nothing holding the gap — **the same shape that lost 36
> of 50 gap counts.**

That is [`CLAUDE.md`](CLAUDE.md)'s recurring defect — *a condition checked in
Python, guarding a write that cannot re-assert it* — arrived at independently,
with a measured cost. Three criticals of that shape landed here in one session
and the fix that worked every time was the same move in a different mechanism:
the precondition in the `WHERE` clause; two walks each bounded by construction
instead of one walk with a filter.

Two codebases, no shared code, same failure, same correction, both recorded. The
lesson was already written down in both places; what is new is that it was
reached twice. That is the difference between a house style and a real property
of this kind of system, and it is the sense of corroboration
`scripts/count_countersignatures.py` was built to care about — two independent
observations rather than one repeated.

**The round expected something else and was wrong three times.** It set out to
show that jeles' corpus vouches for itself: that `put_nugget` writes a
human-verified nugget with no human, that the `verification_kind="human"` default
is a hole, and that a lower rung can overwrite a higher one. `verified_by` is
required and the write is refused without it (`corpus.py:416`); the default is
documented as being for in-process callers and is pinned to `"asserted"` at the
MCP boundary (`corpus.py:395-401`); and a lower rung is refused with the remedy
in the message (`corpus.py:408`). The one claim that survived — no hash chain —
is a tradeoff jeles never claimed otherwise about, so reporting it as a gap would
be grading another package against this one's product pitch.

**And jeles is ahead of this package in the one place §6.44 says it is behind.**
`corpus.py:466`: *"The kind comes back in the receipt: a caller that asked for one
rung and got another should not have to re-read the record to find out."* Plus
`conflict_scan.py:386`, where a refused argument produces a receipt naming it,
"not silently dropped". §6.44 found the same gap here from the opposite
direction one round earlier. Two independent routes to one finding, and jeles
got there first — which is the strongest argument yet for fixing it.

---

### 6.46 The empty-run discipline was in four scripts and not in the fifth's absent branch — **measured**, fix **shipped**

*Found 2026-08-06 by pointing the box at itself: running every script that reads
another repository against a corpus that is missing, and one that is present and
bare.*

Six scripts under `scripts/` read a checkout that is not this one, written at
different times, sharing a discipline articulated *after* two of them existed:

```
could not look   the corpus is absent          -> exit 1, and say so
a true empty     the corpus is there, and bare -> exit 0, and say so
```

The sweep found the discipline holds on exit codes everywhere. It does not hold
on **words**, and the words are the whole point — an exit code of 1 does not tell
a reader which of the two refusals they got.

`feed_jeles_sources.py` refuses an absent `jeles/sources.py` with:

```
no jeles/sources.py under <path>
```

and nothing else. Twelve lines below, its *unparseable* branch says *"'I could
not look' — refusing rather than reporting zero"* and explains that this is not
the same as an empty registry. So the file whose docstring exists to distinguish
`None` from `{}` had two refusals distinguishable only by exit code. Fixed.

**And one message overstated in a partial case.** `feed_willow19_plans.py` looks
for `docs/superpowers/plans` and `.../specs` and reported *"the plan directories
exist and hold 0 .md files"* whenever **either** existed. A deployment whose
`specs/` was missing or misspelled was told both were checked and both were
empty. The empty case is the one nobody re-reads the path for, which is exactly
where a plural that is sometimes singular does its damage — the same shape as
CLAUDE.md's refusal-message lesson, where a sentence true at 0.71 was false at
0.11. It now names the directories it found and names the ones it did not.

**The gate is one file over all six**, not a paragraph in each:
`tests/test_corpus_readers_fail_closed.py`. The failure being prevented is
*drift* — one reader answering in another's vocabulary — and a seventh script
would have no way to inherit the lesson otherwise. It caught the
`feed_jeles_sources.py` defect on its first run.

**A false finding on the way, the fourth of the day.** The sweep first reported
that `feed_willow19_plans.py` called a readable-empty corpus unreadable. It does
not. The fixture was a bare `docs/superpowers/` with no `plans/` or `specs/`
inside it, which is an *absent* corpus, and "I could not look" was the correct
answer being read as a defect. A bare directory is not an empty corpus, and that
distinction is now a test of its own so the next reader of this file does not
have to rediscover it.

---

### 6.47 A claim's own source counts as an independent witness — **measured**, fix **open** (and it may not have one)

*Found 2026-08-06 by running `demo/the_verification.py`, not by designing it. An
article about animal-sound onomatopoeia crossed the operator's desk mid-session;
three of its word-origin claims looked wrong, and checking them turned out to be
a better test of the box than anything invented, because the answers were not
known when it started.*

jeles corroborates a finding only when at least `MIN_INDEPENDENT_SOURCES = 2`
**distinct registrable domains** back it. Running four real claims past that bar:

```
squeak           4 source(s)   draft   the article is wrong
woof             5 source(s)   draft   the article is wrong
ribbit           6 source(s)   draft   the article is wrong
hollywood-frog   3 source(s)   draft   the article holds
```

Two of the ribbit row's six domains are **`wordsmarts.com` — the article being
checked — and `x.com`, a post quoting it nearly verbatim.** Distinct registrable
domains, so the independence rule counts them as two independent sources. They
are one claim, twice.

**This is not news to jeles and the entry should not pretend it is.**
`_independence.py` already says the bar is *"a cheap heuristic, deliberately
weaker and deliberately named apart"* than its constitution's Independent
Witness, *"so nothing built on it borrows authority it has not earned"* — because
two domains can be one actor who bought both. What is new is a concrete instance,
measured, of a shape the disclaimer describes abstractly: not one actor holding
two domains, but **one text republished**, which is far more common and needs no
bad faith at all.

**And it is a step past the defect jeles already fixed.** `_NON_WITNESS` lists 21
domains that can never witness, because an unfiltered count read DuckDuckGo as a
source about every claim — verified there by a claim invented on the spot being
"corroborated by 2 independent sources (duckduckgo.com, wikipedia.org)". A
blocklist closes that, because the search engine is the same for every query. It
cannot close this one: **the domain to exclude is different for every claim, and
is only knowable once you know where the claim came from.** Provenance, not a
list — and provenance of the claim under test is not something a corroboration
count has access to.

**Which is an argument for the seal rather than against the count.** No number of
agreeing pages distinguishes four sources from one source quoted four times. A
human reading the four pages notices in seconds. That is the division of labour
this repo asserts, arrived at from the other end: corroboration is evidence, and
verification is a decision.

**Every row landed as a draft, including the three that are right.** Three of
these four are refutations of a published claim and the evidence backs them,
which is precisely the situation where a demo is tempted to reward itself. Being
right is not being checked, and a test pins that the demo contains no
`status="sealed"` and no `verifier=` at all.

**Fix: open, and possibly none.** The honest options are (a) pass the claim's
source domain into the independence test so it can exclude itself — cheap, and
catches only the literal self-citation, not the four repeaters; (b) compare text
similarity across citations and count near-duplicates once — which is a matcher
problem, and this repo has one; or (c) accept it, keep the disclaimer, and let
the seal carry the weight. This entry does not pick. Filing anything on jeles'
side needs the operator's word.

---

### 6.48 Both hypotheses §6.47's feed raised were measurable, and neither was right as written — **measured**, filed as jeles#53

*Measured 2026-08-07 against jeles at `ed48de7`, offline, with a stubbed
`llm_respond`. `scripts/feed_jeles_sources.py` printed both as open questions;
both are corrected in place there, and this entry is why.*

The feeder ended on two things it said it had not measured. Asked properly, one
is **confirmed with the wrong reason attached** and the other is **false, in the
opposite direction from the one feared**.

**Hypothesis 1 — "a single-sourced subject struggles to clear the bar."**
True. 43 of 71 subject tags in jeles' registry have exactly one source, and a
claim routed to any of them cannot be corroborated. The stated reason — narrow
routing breadth — was not the mechanism.

`verify._identity` reads `citation["source"]` first and falls back to
`institution` only when that is empty. `sources._result` puts the **registry
key** in `source`: checked by parsing rather than by sampling, all **69**
`_result` call sites pass a non-empty constant, 65 distinct values. So the
`institution` arm is unreachable for registry output, and the per-record
institution each adapter assembles — author affiliations, publisher, journal —
is never counted. Measured:

```
1 adapter, 5 genuinely different institutions -> ['openalex']         single_source
2 adapters, the SAME 5 institutions           -> ['core','openalex']  corroborated
```

The count is over **adapters**. Which means the same defect runs both ways, and
the second is worse: two adapters carrying one institution read as corroborated,
which is the false corroboration `tests/test_verify.py` opens by saying the
module exists to prevent.

**Hypothesis 2 — "9 sources list doi.org, `registrable_domain()` collapses them,
so nine institutions could corroborate as one."** False for registry output, and
backwards. The site is only a *fallback* for a citation with no label, and
`_result` always sets one, so the fallback is unreachable on that path.
Measured: two doi.org citations from different adapters keep distinct keys
(`openalex`, `core`) — they do not collapse. The error is the reverse of the one
guessed: not over-collapsing distinct institutions into one, but failing to
collapse one institution reached twice.

**What this is not.** Nothing inside jeles wires `sources.search()` into
`verify_claims` — the only callers are its tests — so this is a latent contract
mismatch across a seam rather than a live defect there. Whether it bites depends
on what the host passes, and that host's design docs live in safe-app-store,
which is not readable from here. Filed as **jeles#53** saying exactly that, with
no fix proposed: the obvious inversion (prefer `institution` over `source`) would
change what `institutional.py` citations count as, since there `source` genuinely
*is* the institution.

**The lesson is the one this repo keeps paying for.** Both hypotheses were
written with the uncertainty honestly flagged, and flagging was worth something —
it is why they were still there to check. It was not worth as much as checking:
one had the wrong mechanism, and the other pointed the wrong way entirely. A
hypothesis nobody runs decays into a fact nobody questioned.

---

### 6.49 The staleness memo's §2 names the wrong timestamp as unmovable, by one entry — **measured**, listing **shipped**, caveat **open**

*Round 3 of the jeles exchange, 2026-08-07. Built as §3 of
[`docs/seal-staleness-and-quorum.md`](docs/seal-staleness-and-quorum.md) says to
build it, and the building measured §2's own argument.*

`scripts/due_for_reverification.py` is the listing §3 argues for: an aged seal
keeps serving, keeps saying who sealed it and when, and additionally appears as
work for a person. It carries no score, no weight and no multiplier, and a test
pins that those words stay out of it — the day this feeds `best_sealed` is the
day the memo was written to prevent.

**§2's first claim holds.** `signing._message` covers exactly
`[source_norm, target_text, verifier]`, so `tm_pairs.created_at` is outside the
signature. Measured: move a sealed row's `created_at` back twenty-seven years
and `is_verified_seal` still returns True. Age must not come from the row.

**§2's second claim is too strong by one entry.** It calls the ledger's `ts`
*"the only timestamp in the system that cannot be moved without the chain saying
so"*. On a three-entry chain:

```
entry 0 ts (2 entries follow)   -> verify=False  broken chain at line 2
entry 1 ts (1 entry follows)    -> verify=False  broken chain at line 3
entry 2 ts (LAST — none follow) -> verify=True   intact — 3 entries
```

**This is not a finding about the code, and reporting it as one would have been
the fifth false finding of the day.** `ledger.verify`'s docstring already states
it in full — *"each line is vouched for by the line after it, so the newest entry
has nothing after it to vouch for it… That is a property of the chain, not a bug
in the walk"* — and already ships `expected_head` to close it. The defect is in
the memo, which asserted the property without the caveat. Corrected there in
place.

It bites hardest exactly here. The unvouched-for entry is the newest decision,
which is the one a freshness question asks about most often. So the listing
reports an age drawn from the tail as **reported, not verified**, and says to
pass `--expected-head`.

**And it caught a lie in its own output while being tested.** The per-row
`[tail: age unvouched-for]` marker ignored `--expected-head`, so following the
command's own advice changed nothing on screen — the summary said *"pass
--expected-head to close it"* and passing it did not close it. Found by running
both ways rather than by reading, fixed, and pinned by a test that asserts the
marker disappears when the head is supplied.

**Still open:** nothing consumes this. It is a command somebody runs, not a queue
the curator shows, and §3's design wants the listing surfaced where the review
work already happens. That is the next bite and it touches the UI, which is a
wider blast radius than a read-only script.

### 6.50 `minimal_output` is a parameter on one tool of fifty-five, and the group it belongs to decides what a repo corpus costs — **measured**, corpus build **open**

*Raised 2026-08-06 by the operator, who read `minimal_output` in a tool call and
took it for a tool name. It is not one, and the correction is the useful part:
the thing worth knowing is the family of response-shaping parameters it belongs
to, because that family sets the price of every corpus built through these
tools.*

**What it actually is.** A boolean parameter on the GitHub MCP server's
`search_repositories`. `true` (the default) returns a trimmed object; `false`
returns the full GitHub API repository object. Measured on the same row
(`rudi193-cmd/willow-2.0`), reading the two responses:

| | per repo |
|---|---|
| `minimal_output: true` | ~0.4 KB |
| `minimal_output: false` | ~2.5 KB |

Both carry `created_at`, which was the field wanted. Across 105 repos that is
the difference between ~40 KB and ~260 KB of context for the same answer.

**The correction that matters more than the parameter.** The server's own
instructions recommend `minimal_output` generically — *"Use minimal_output
parameter set to true if the full information is not needed."* All 55
`mcp__github__*` schemas were loaded and read to check that. **One accepts it.**

The general lever is a different parameter, `fields`, an enum array naming the
keys to return, and it is on eight tools: `list_issues`, `search_issues`,
`list_pull_requests`, `search_pull_requests`, `list_commits`, `list_releases`,
`search_code`, and `get_file_contents` (directory listings only). Measured on
this repository's issues:

| | two issues |
|---|---|
| `fields: [number, title, state]` | ~0.5 KB |
| no `fields` | ~9.6 KB |

~20×, and repository-dependent — it is this large here because Nestor's issue
bodies are long. Three more tools shape their own responses by other names:
`get_commit`'s `detail` (`none` / `stats` / `full_patch`), `get_job_logs`'s
`tail_lines` + `return_content`, and `get_check_run`'s `textLimit` /
`textOffset` byte window. So the honest summary is that there is **no single
knob** — there are twelve tools with four different spellings of one idea, and
the server's instructions name the rarest of them.

**The group, counted.** 55 tools: issues 9, pull requests 17, files and git 10,
repositories and releases 6, Actions and CI 5, cross-repo search 6
(repositories · code · commits · issues · PRs · users), identity and org 4,
secret scanning 1. Reads and writes are not separated by name — `issue_write`,
`push_files`, `merge_pull_request`, `actions_run_trigger` and
`create_repository` sit in the same namespace as the readers, and
`create_repository` defaults to `private: true`. Two of them,
`subscribe_pr_activity` / `unsubscribe_pr_activity`, exist under a second
namespace as well.

**The reach asymmetry, measured, and it is the finding with consequences.** This
session is bound to one repository. Direct API calls honour that; the MCP search
tools do not go through the same gate:

| path | result |
|---|---|
| `curl /user/repos` | 403 — *"sessions are bound to their configured repositories"* |
| `curl /repos/{owner}/{repo}` for an unconfigured repo | 403 — *"use add_repo to request access"* |
| `curl /search/repositories` | 403 — same bound-session message |
| `mcp__github__search_repositories` | returned repositories across four owners |

Same account, same credentials, two enforcement points that disagree. The
listing above was assembled only because of that gap, and every row in it was
cross-checked against the sanctioned listing tool before use — 105 of 106
matched, the one difference being a repository belonging to somebody else.
Nothing here is an argument that the gap should be used casually; it is written
down because a corpus is only as auditable as the account of where its rows came
from, which is this repository's whole subject.

**Why this is a Nestor entry and not a note about somebody else's server.** The
next task is a corpus built from these 105 repositories. Its cost, its
completeness and its provenance are all set by the table above: what `fields`
can drop, what the search tools can reach that the API cannot, and the fact that
`created_at` — the field the whole chronology depends on — is absent from the
sanctioned listing tool and present only in a search response. A memory whose
rows came from somewhere nobody can see is the thing this project exists to
refuse. **Open:** which of these tools the corpus build is allowed to use, and
whether each row records the call that produced it.

### 6.51 The oldest repository, extracted: 229 drafts, eight self-contradictions, and three things Nestor has no field for — **measured**, corpus design **open**

*Run 2026-08-06 against `rudi193-cmd/SAFE` (created 2026-01-05, the first
repository on the operator's list), the opening move of a corpus built from a
corpus. Extractor lives outside this repository; the store it wrote is in
gitignored `data/`. What follows is what the run measured, and what it could not
hold.*

**Method, so the numbers mean something.** The repeating structures were
*counted* before anything was parsed — 21 four-field entries, 10 `Constraint`
labels, 5 identified stops, 265 table rows — and three extractors were written
to those shapes rather than to prose. Nothing was inferred: a row exists only
where a heading or a table cell put it. Every row landed as a **draft** via
`add_pair(..., status="draft")`. The ledger has one entry after the run, which
is the covenant working — a proposal is not a decision and appends nothing.

| extractor | drafts |
|---|---|
| identified constraints (`Constraint` → `Response`/`Rules`) | 5 |
| schema'd entries (`Domain`/`Voice`/`Function`/`Direction`) | 21 |
| two-column definition tables | 203 |
| **total** | **229 draft, 0 sealed** |

**The finding worth the exercise: the store refused eight rows, and it was
right.** `ConflictingDraftError` (§6.19's message) fired eight times — one key,
two different answers. Five of them are the same rule restated in two places in
one security document, each time with a qualifier present in one version and
absent in the other. Read as prose the pairs look like tidying; read as rules
they are different rules, and the terse form is the permissive one. Nobody asked
Nestor to look for that. It fell out of refusing to let a second proposal
overwrite a first, which is the behaviour §6.19 and §6.20 argued about for two
sessions.

**And one of the eight is mine, not the corpus's.** Two different tables in one
file share a row label, and the extractor treated them as one key. Recorded here
because the run's headline number is only worth what its error rate is, and a
collision report that quietly included a parser fault would be the same
"absence reported as success" this codebase refuses elsewhere.

> **Correction, same day (§6.53).** That paragraph was wrong, and wrong in the
> way this file exists to prevent: it was inferred rather than checked. The run
> did not print the *held* row's origin, so "two tables in one file" was a guess
> from the new row's origin alone. Re-run with both origins printed, **all eight
> collisions are across documents; none are within one file.** The `Journal
> entries` pair is `docs/RELATIONSHIP_SCHEMA.md` against
> `reference-implementations/aionic-journal/README.md` — two documents answering
> two *different questions* about one term, which is still a key-scoping
> weakness (the key does not record which question is being asked) but is not
> the parser fault claimed above. The error rate this paragraph reported for
> itself was made up. Left in place per §6's rule.

**One exact duplicate deduped in silence.** 204 successful `add_pair` calls
produced 203 rows: an identical restatement returns the stored row rather than
raising. That is correct — it is not a conflict — but the asymmetry is worth
naming. **Near**-restatement is loud and **exact** restatement is invisible, so
the corpus's cheapest form of drift is the one the store says nothing about.

**Three things it could not hold, written down rather than forced:**

1. **No field says a row may not leave.** The source is a private repository,
   and five of its files name the owner's children and carry birth details. A
   pair has `status`, `origin` and `reason`; it has nothing that says *this row
   is not publishable*. Eighteen of the hundred and five repositories on the
   list are private. A corpus spanning them needs a visibility classification
   that survives `export_bundle`, and today the only thing keeping the sensitive
   rows local is that a human chose the output path. That is a convention, not a
   mechanism — the exact shape CLAUDE.md warns about.
2. **The entity graph is the right recipe and has no verb.** The source is dense
   with aliases: one system carries at least four names across its documents,
   and resolving them is precisely what `EntityResolver` is for. It offers
   `seal`, `add_alias` (which calls `seal`) and `resolve`. §6.39 recorded that
   there is no way to *propose*; this is the first corpus to walk into it, on
   the first repository, and the workaround is the same one §6.39 had to use —
   go around the recipe and call `add_pair` directly, which means the alias
   never enters the graph the resolver reads.
3. **Nothing records which call produced a row.** `origin` carries the source
   file and anchor, which is good provenance for the *text*. It says nothing
   about the extraction: which extractor, which revision of it, which run. Two
   rows disagreeing is only diagnosable if you can tell a corpus contradiction
   from a parser change, and the eight collisions above are exactly that
   question. §6.50 left this open as *whether each row records the call that
   produced it*; one repository in, it is no longer hypothetical.

**A fourth thing, which is not a gap but a reason to keep going.** The oldest
repository states this project's central rule seven months before this project
existed — the propose/ratify split, as a constitutional document, including the
clause that silence is not approval. The chronology assembled in §6.50 is
therefore not a list, it is a lineage, and "a corpus from a corpus" has a
subject: watching one idea get restated across a hundred and five repositories
and seven months, with a store that objects when two statements of it disagree.
That is the same mechanic as the eight collisions, run at the scale of the
whole list.

**Held back deliberately.** No extracted row, and no quotation from the source,
is committed here. The repository is private and the content includes personal
data about minors; putting any of it into this public repository is a
publication decision that belongs to its owner, not to the process that read it.
The rows exist locally and can be shown on request. **Open:** where the corpus
lives, what its visibility field looks like, and whether the extractor becomes
committed tooling or stays scaffolding.

### 6.52 Willow extracted: the first bilingual rows, a constitution that is 56% human, and a generic extractor that buried its own best content — **measured**, extractor design **open**

*Run 2026-08-06 against `rudi193-cmd/Willow` (created 2026-01-10, second on the
chronology), rung 2 of the per-repo stack, branched from the SAFE rung. Public
repository, so unlike §6.51 this entry may quote it.*

**Yield, after the rewrite described below.** Named shapes only:

| shape | drafts |
|---|---|
| bilingual, tables (`In computer terms` → `In human terms`) | 16 |
| bilingual, prose (same two labels, under a heading) | 12 |
| governance patterns (name → `Canonical phrasing`) | 6 |
| constitutional decisions (`Decision` → `Class`) | 73 → 72 rows |
| definitional tables (first column named as a term) | 28 |
| **total** | **134 draft, 0 sealed** |

467 further table rows under 82 headers are **not** extracted, and the run
prints them by header. A corpus that drops 78% of the candidate rows and says
so is worth more than one that quietly takes them.

**The first genuinely bilingual content in the corpus.** `In computer terms` /
`In human terms` is one referent stated in two registers — *"an office's
envelope enumerates lanes, actions, and duration"* against *"the teacher does
not read the diary. The boss does not own the evenings."* Structurally that is
exactly a translation pair, and it is the first material in this exercise that
uses Nestor as built rather than as a decision store.

**Nestor's own question, asked of a constitution.** The 72 decision rows carry
an authority class each. Counted:

```
15  Operator Key            15  Auto-Applied            11  Auto-Applied + Ledger
 8  Quorum + Ledger          5  Quorum                   4  Operator Key + Quorum
 4  Quorum + Operator Key    2  Forbidden absolutely     …
require a human key or quorum: 40/72 (56%)
```

A machine may act alone on 44% of the acts its own constitution enumerates.
That number is the whole product stated as a measurement, and it came out of a
markdown table nobody wrote for this purpose.

**The mistake worth more than the yield.** The first extractor took *every*
two-column table: 568 rows. Measured afterwards, 7% came from a header naming a
term — and the other 93% were status, finding and priority tables. It filed
`CONSTITUTION.md`'s decision rows under the same domain tag as a `P1` row from a
sandbox findings list. **A generic extractor is not merely noisy; it buries its
best rows among its worst**, because nothing downstream can tell them apart
afterwards. The rewrite names each shape and declines the rest.

**And the collision count moved with the extractor, not the corpus.** The
generic run raised 63 `ConflictingDraftError`s. Sampled with the held row's
origin beside the new one, they were `P0`, `P1`, `Doctor`, `Store` — generic
first cells colliding across unrelated tables. The named run raises **zero**.
So: *a collision is evidence about the corpus only after the key is scoped
correctly; before that it is evidence about the parser.* §6.51 reported eight
collisions on SAFE and caught one parser fault among them. That ratio was luck
of a small definitional repository, not a property of the method.

**Two things the store cannot see, written down rather than fixed:**

1. **Drift on the target side is invisible.** `Operator Key + Quorum` (4 rows)
   and `Quorum + Operator Key` (4 rows) are the same authority class written two
   ways. No collision fires, because collisions key on the *source*. A pair
   store notices two answers to one question and cannot notice one answer spelled
   two ways — which in a controlled vocabulary is the more common drift, and here
   it is 8 of 72 rows.
2. **Exact duplicates dedupe in silence, again.** 73 successful adds, 72 rows.
   Same asymmetry as §6.51, now confirmed on a second corpus rather than
   inferred from one.

**The lineage holds and sharpens.** SAFE stated the propose/ratify split as a
constitutional principle on 2026-01-04. Willow enumerates it into 72 specific
acts six days later. Nestor implements it as a store seven months after that,
and this entry measures the enumeration with the implementation. Three rungs,
one idea, and the corpus is the thing that lets you see it is one idea. That is
the argument for continuing up the stack.

### 6.53 `origin` now says what produced the row, which forced the extractors into the repository — **shipped**, visibility field still **open**

*Built 2026-08-06 on the operator's instruction, closing the third gap of
§6.51. Rung 2 of the corpus stack; applies to every rung, including the one
below it when re-run.*

**What a row's origin says now.** Four facts where there was one:

```
willow@cf1040a:CONSTITUTION.md#Identity Authority [decision/0853d53]
└─repo  └─commit └─path        └─anchor            └─shape └─toolchain
```

The toolchain digest is a content hash over the extractor **and**
`scripts/corpus/provenance.py` together, because a change to either changes what
the rows mean. It cannot be bumped by hand and cannot go stale.

**The consequence that made this more than a formatting change.** A digest of a
script in a scratch directory names a thing nobody can fetch — the exact failure
`scripts/dogfood_store.py` was built to refuse. Recording the extractor's
identity is therefore only honest if the extractor is retrievable, so the
extractors moved out of the container's scratchpad and into
`scripts/corpus/`: `provenance.py`, `common.py`, and one file per repository.
The instruction was three words long and its real content was *commit your
tooling*.

**Both claims in that module's docstring were checked, not asserted:**

| claim | check | result |
|---|---|---|
| origins are reproducible | ran the Willow extractor twice, digested `(source, origin)` over all 134 rows | `753e01e259360b3a` both times |
| the digest tracks content | appended one comment line to a copy of the extractor | `0853d53` → `70bf56c` |

The second is the mutation this repository asks for: a digest that could not
change would be decoration.

**And it immediately caught a false claim in §6.51, which is corrected in place
above.** Printing the *held* row's origin beside the new one — the thing the
new format exists to make possible — showed that all eight SAFE collisions are
across documents and none within one file. §6.51 had asserted that one of the
eight was a parser fault, from the new row's origin alone, without ever reading
the other. So the first thing better provenance did was falsify the paragraph
that asked for it, roughly two hours after it was written and about ninety
minutes after the same file recorded that inference-instead-of-checking is this
project's characteristic error.

**Yields are unchanged** — SAFE 229, Willow 134 — which is the point: the move
from scratchpad to repository altered provenance and nothing else. SAFE's run
additionally now reports 57 declined `field | value` rows it used to skip in
silence.

**Still open, and now the only unaddressed gap from §6.51:** no field marks a row
unpublishable. Rung 3 (`Aionic-Claude-Skills`, 2026-02-11) is private, as is
rung 1. Every private rung so far has been kept local by choosing an output path
under gitignored `data/`, which remains a convention where this repository
demands a mechanism.

### 6.54 Aionic extracted: a linter that passes none of its own subjects, and the discovery that silence from the store means nothing — **measured**, extractor coverage **open**

*Run 2026-08-06 against `rudi193-cmd/Aionic-Claude-Skills` (created 2026-02-11,
third on the chronology), rung 3 of the stack. Private repository, so as with
§6.51 this entry records structure and counts and quotes no content.*

| shape | drafts |
|---|---|
| skill contract (name → what it is for) | 20 |
| trigger (skill → when it fires) | 15 |
| framework (`MANIFEST.json` id → version @ path) | 4 |
| definitional tables | 27 |
| **total** | **66 draft, 0 sealed** |

> **Corrected at rung 5 (§6.56): 81, not 66.** The 15 rows this run declined
> under `# | check | status | notes` are the author's standing security rubric,
> not noise. They are claimed now. The number above is what was measured on the
> day, and it was an undercount.

81 further table rows under 14 headers declined and printed. Two headers were
moved *into* the definition shape mid-run after the first pass declined them —
both name a term column outright — which moved the toolchain digest `d758565` →
`fbee500`, exactly as §6.53 intends: the rows now say which extractor produced
them, and it is not the earlier one.

**The repository carries two incompatible skill formats.** Of 26 `SKILL.md`
files: 19 use front-matter `name:`/`description:`, 1 uses `Skill-Name:` with the
summary in its first paragraph, and **6 carry neither** and yield no contract
row at all. Which format a row came from is recorded in its `reason`, because
that difference turned out to be the most interesting fact in the corpus.

**The repository's own linter passes none of them.** `scripts/aionic-verify.py`
requires six literal strings — `Skill-Name:`, `Version:`, `Architect:`, and
three numbered headings. Run over all 26 subjects:

```
0 pass, 26 fail
```

Including all four frameworks the manifest names. It is not a broken linter; it
is a correct linter for a format the repository stopped using, and nothing runs
it in CI, so it has never reported anything to anyone. `test_docs.py`'s
docstring names this exact failure — *a claim nobody executes is a claim nobody
maintains* — and this is the same shape one layer out: a **check** nobody
executes.

**Three more, each verified by running rather than reading:**

| | |
|---|---|
| `MANIFEST.json` → `momentum-engine` v1.1.0 | path is `…/SKILL.md`; the file is `SKILLS.md`. Off by one character, and nothing validates manifest paths |
| `core/base17-compact/SKILL.md` | empty — zero lines |
| `core/dual-commit/SKILL.md` | 7 lines, opening inside a stray ```` ```markdown ```` fence |

**The finding that generalises, and it is the complement of §6.52.** Two skills
exist in both `core/` and `skills/`: `ternary-context` is byte-identical in both,
`base17-compact` is empty in one and 105 lines in the other. **The store raised
no collision for either**, and could not have — both live among the 6 files with
no contract row, so nothing about them ever reached it.

§6.52 established that a collision is evidence about the parser before it is
evidence about the corpus. This rung adds the other half: **a non-collision is
evidence about nothing at all.** Silence from the store can mean the corpus
agrees with itself, or it can mean the rows never arrived — and the store cannot
tell you which, because the extractor decides what it is allowed to notice. Any
future claim of the form "the corpus is consistent about X" has to be paired
with the coverage number for X, or it is unfalsifiable. That is now the largest
open question in this exercise and it did not exist two rungs ago.

**The lineage, third beat, and it is not a flattering one.** SAFE states the
propose/ratify split as a constitutional document (2026-01-04). Willow
enumerates it into 72 specific acts (2026-01-10). Aionic tries to make it an
executable skill a month later — and `dual-commit` is seven lines long, wrapped
in a broken fence, failing the repository's own verifier, one of four things
that verifier fails. The idea did not decay; the **carrier** did, each time it
moved from a document to a mechanism. That is worth having found, and it is the
first thing in this corpus that the chronology alone would never have shown.

### 6.55 willow-seed extracted: ten drafts, coverage 2/8, and a promise the document keeps once — **measured**, coverage now **shipped**

*Run 2026-08-06 against `rudi193-cmd/willow-seed` (created 2026-02-25), rung 4.
Private, so structure and counts only. The smallest yield of the exercise so
far, and the entry is longer than the extraction because the small yield is the
result.*

| shape | drafts |
|---|---|
| grading question → `*Measure:*` | 1 |
| grading question → `*Reference:*` | 8 |
| audit finding → recommended fix | 1 |
| definitional tables | 0 |
| **total** | **10 draft, 0 sealed** |

> **Corrected at rung 5 (§6.56): 25, not 10.** Same cause as §6.54's correction
> — the 15 declined `# | check | status` rows are a rubric, and are claimed now.
> The finding below about `GRADING.md` is unaffected: it concerns fields that do
> not exist, which no amount of extractor coverage can conjure.

Verified against the source rather than trusted: the document contains 10
questions, 1 `*Measure:*` line, 8 `*Reference:*` lines, and 1 `Recommended fix`.
The extractor found exactly what is there.

**Coverage is now printed by every run**, which is §6.54's open question turned
into a mechanism in `scripts/corpus/common.py`:

```
coverage: 2/8 document(s) produced at least one row
  silent  CANON_MOVED.md · MAINTAINER.md · README.md · REPLANT.md
  silent  docs/QUICKSTART.md · log/2026-07-10-first-session.md
```

Six of eight documents are prose that declares no schema, and the run says so
rather than reporting ten rows and letting the reader assume that was all there
was to find.

**It earned itself inside one run.** The first execution reported `1 draft` and
`coverage 1/8`. Without the coverage line that is a plausible result for a small
repository and would have been written up as one. With it, the number was
obviously wrong, and the cause was mine: `_italic` builds its pattern as
`\*{}:\*` and I called it with `"Measure:"`, producing a doubled colon that
matched nothing. **The mechanism built to stop me trusting a silent store caught
me trusting a silent store, on its first use, about ninety minutes after §6.54
argued for it.**

**The finding, which the store did not produce and counting did.** `GRADING.md`
opens by describing itself as *"ten questions … with how to measure each and
reference points to sit your numbers against."* Measured: the reference points
are there for 8 of 10. **The measure is there for 1 of 10.** The document's
first promise holds for one question and the second for eight, and nothing in
the repository says so, because nothing in the repository counts.

That is worth separating from every earlier rung. §6.51 through §6.54 found
things by *collision* — two answers to one key, the store objecting. This found
something by *absence*, and no collision could ever have surfaced it: nine
missing `*Measure:*` fields are nine rows that do not exist, and a store cannot
object to a row it was never offered. A corpus of drafts detects contradiction;
only coverage detects omission. Both numbers have to be reported or the memory
flatters its source.

**Rung 4 also breaks the lineage's shape, which is itself information.** SAFE,
Willow and Aionic each carried the propose/ratify idea in some form. `willow-seed`
does not restate it at all — its subject is a person grading their own system,
and its one boundary statement is about *not* pointing the instrument at somebody
else. Four rungs in, the chronology is not a single idea repeated; it is one idea
that stops here and a different one starting.

### 6.56 openclaw-sap-gate extracted: the first code rung, two coverage denominators, and thirty rows recovered from the declined pile — **measured**

*Run 2026-08-06 against `rudi193-cmd/openclaw-sap-gate` (created 2026-04-18),
rung 5. Public. The first repository in the sequence that is mostly code — two
markdown documents against four Python modules — and the shape of the extraction
changes accordingly.*

| shape | drafts |
|---|---|
| docstring (`symbol` → what it is for) | 15 |
| rubric (`check` → verdict) | 15 |
| finding (`ident` → recommended fix) | 2 |
| definitional tables | 3 |
| **total** | **35 draft, 0 sealed** |

**Two coverage numbers, because one would have lied.**

```
coverage: 2/2 document(s) produced at least one row
docstring coverage: 15/41 definition(s) carry one
```

The same repository is fully covered in documents and **37% covered in code**.
A single figure would have reported either total success or a bad miss, and
neither is true. §6.55 established that omission is invisible without coverage;
this rung adds that coverage is per-*kind*, and a corpus spanning documents and
code needs one denominator per kind or it is back to flattering its source.

Note what the 26 undocumented definitions are not: they are not a defect. A
docstring is a declaration the author chose to make, and the interesting fact is
the ratio, not a demand.

**Thirty rows came back from the declined pile, and that is the mechanism
working as designed.** `# | Check | Status | Notes` was declined as noise in
rung 3 (15 rows) and rung 4 (15 rows). Seeing it a third time here made it
legible: it is the author's standing security rubric, one row per check, with
the verdict in the second column. It is now claimed, and **§6.54 and §6.55 are
corrected in place above — 66 becomes 81, 10 becomes 25.**

`common.declined()` was introduced at rung 2 as *honesty* — an extractor that
silently ignores 78% of candidate rows reads like one that found nothing. By
rung 5 it is the **discovery channel**: the only reason those thirty rows were
ever recoverable is that declining them printed their header instead of
dropping them. Reporting what you refuse turns out to be how you find what you
should have taken.

**A shape that recurs across repositories is a fact about the author, not the
repository.** `### P1: XX-YY-01 — title` with a `**Recommended fix:**` has now
appeared unchanged in three checkouts spanning four months, so it moved into
`common.findings` and rung 4's local copy was deleted. Re-run afterwards, rung 4
yields the same 10 rows it did before the refactor (25 with the rubric), and its
toolchain digest moved `bdc7abf` → `f12ce2f`, which is §6.53 behaving exactly as
specified: same rows, different tooling, and the rows say so.

This is the first thing the corpus has found that no single repository contains.
The convention is only visible across three of them, and the chronology is what
made it visible in order.

### 6.57 willow-1.9 extracted: 1,340 drafts, two coverage ratios that match across an 80× size gap, and a key that was wrong in a second domain — **measured**

*Run 2026-08-06 against `rudi193-cmd/willow-1.9` (created 2026-04-22), rung 6.
Public and **archived**, which is the reason it is safe to read: an archived
repository has a head that will not move under the `repo@commit` pin every row
carries. `willow-mcp`, four days older, is held out of the sequence for exactly
the inverse reason.*

| shape | drafts |
|---|---|
| docstring (`path::symbol` → docstring) | 1,155 |
| definitional tables | 145 |
| goal (plan → what is to be built) | 16 |
| rubric (check → verdict) | 15 |
| when (power → trigger) | 12 |
| success (plan → how you would know) | 3 |
| finding | 0 |
| **total** | **1,340 draft, 0 sealed** |

Forty times the previous largest rung. 626 rows under 84 headers declined and
printed.

**The key was wrong again, in a domain where it looked obviously right.** Keyed
on the bare symbol name, the run raised **54 docstring collisions**. Nearly all
were two unrelated functions that happen to share a name across modules. Keyed
on `path::symbol` the count is **0**, and the 54 rows that had been refused come
back — yield rose 1,101 → 1,155 purely from fixing the key.

This is §6.52 arriving in a second domain, and the recurrence is the point. In
markdown the coarse key was a table's first cell; in Python it was a function
name. Both looked like identifiers. Neither was one. **A collision is evidence
about the key until the key is proven, and "it is obviously unique" is not a
proof** — it was obvious in both cases and wrong in both.

**Two coverage ratios, and they agree across an enormous size difference:**

| rung | repository | docstring coverage |
|---|---|---|
| 5 | openclaw-sap-gate (41 definitions) | 15/41 — **37%** |
| 6 | willow-1.9 (3,303 definitions) | 1,155/3,303 — **35%** |

An eightyfold change in size and a two-point change in the ratio. One
repository is a small library and the other is a fleet; the habit is the same.
That is the second thing this corpus has found that no single repository
contains, and unlike the shared `### P1:` convention it is a *quantity* rather
than a form — the sort of claim that needs two measurements before it can be
made at all, and a third before it should be trusted.

Document coverage is a different story: **38 of 134** markdown files produced a
row. The silent ones are largely `.claude/` agents, commands and skills, which
declare their contract in prose rather than in any repeated schema. Per §6.56
that is reported per-kind and not averaged, because 35% of code and 28% of
documents are two facts, and their mean is none.

**What the wrong key surfaced, kept deliberately rather than by accident.** With
the key fixed the store no longer objects, so the question it stumbled onto is
now asked directly. Of the symbols defined in more than one module:

```
38 symbols defined in >1 module
  31  the docstrings differ   — parallel implementations, or unrelated namesakes
   7  the docstrings match    — the same sentence maintained in two places
```

Those 7 are the interesting ones: identical text in two files, which is the
cheapest kind of drift to create and the hardest to notice, because nothing
disagrees yet. §6.52 recorded that exact duplicates dedupe in silence; here they
do not even reach the store as duplicates, since the qualified key makes them
two legitimately distinct rows. **Fixing the key traded a false signal for a
blind spot**, and the honest response was not to revert it but to measure the
blind spot on purpose and write the number down.

### 6.58 willow-nest extracted: the first repository that declares nothing new, and a ratio that survived its third test — **measured**

*Run 2026-08-06 against `rudi193-cmd/willow-nest` (created 2026-04-23), rung 7.
Public, archived, and its own README says it was consolidated into Willow 2.0 —
a repository that ended by being absorbed.*

| shape | drafts |
|---|---|
| docstring | 19 |
| rubric | 15 |
| finding | 1 |
| definitional tables | 0 |
| **total** | **35 draft, 0 sealed** |

Document coverage 1/1 — the repository has exactly one markdown file.

**It declares no shape this corpus had not already met**, and that is the
result rather than a disappointment. Every rung so far has contributed at least
one new structure: constraints, facets, bilingual registers, skill contracts,
graded questions, docstrings, plans. Rung 7 contributes none. The four shapes it
does carry are the four that have now appeared in every code repository read.

**So the extractor caught itself about to duplicate.** Rung 7 needed
byte-for-byte what rung 5 needed. Writing `extract_willow_nest.py` as a copy
would have been the third instance of the same four shapes in three files — the
exact defect this whole exercise exists to detect, committed by the exercise. The
shapes moved into `common.standard`, rung 5 was pointed at it, and rung 5
re-runs to the **same 35 rows** with its toolchain digest moved `9577ac1` →
`788c98f`: same rows, different tooling, and §6.53's format says so on every
one. `extract_willow_nest.py` is now a docstring and a call.

**The ratio held on its third measurement, which is the one that counts.**
§6.57 committed to needing a third before the claim could be trusted:

| rung | repository | definitions | docstring coverage |
|---|---|---|---|
| 5 | openclaw-sap-gate | 41 | **37%** |
| 6 | willow-1.9 | 3,303 | **35%** |
| 7 | willow-nest | 55 | **34.5%** |

Three repositories, sizes spanning 80×, spread of 2.5 points. A library, a
fleet, and an intake pipeline. This is now the most robust claim the corpus has
produced and it is about the author rather than any repository: **roughly a
third of what gets defined gets described, and the ratio does not move with
scale.** It was stated as a hypothesis at rung 6 with two points and a warning;
it is measured now.

> **Corrected at rung 11 (§6.62).** The fourth measurement is **42%**
> (`willow-bot`, 74/177), which sits outside the 34.5–37 band above. Four points
> are 34.5 · 35 · 37 · 42 — a spread of 7.5, three times what this paragraph
> reports. The claim survives in weakened form — *between a third and two fifths
> of what gets defined gets described* — but **"does not move with scale" is not
> supported** and was written on three points that happened to agree. The
> sentence was true of its evidence and overstated as a rule.

Worth being precise about what it is not. It is not a quality judgement — a
docstring is a declaration the author chose to make, and 35% may be exactly the
right number for code where two thirds of the definitions are obvious. What it
is: a constant, discovered by reading three repositories in the order they were
written, which no one of them contains.

**One question left for a later rung.** `willow-nest` was folded into
`willow-2.0`. Its 19 docstrings therefore exist twice — once here, archived at
`2841ce2`, and once in whatever they became after the move. When the sequence
reaches `willow-2.0`, those 19 rows are a ready-made test of whether
consolidation preserved what it absorbed, and it is the first time this corpus
will be able to ask that question with both sides in hand.

### 6.59 hermes-agent extracted as a delta: 2 commits of 4,766, and a headline number that was somebody else's — **measured**, per-file attribution **open**

*Run 2026-08-06 against `rudi193-cmd/hermes-agent` (created 2026-04-18), rung 8,
and the first **fork**. The operator's correction — that what was built on the
forks matters — reversed the skip rule recorded a rung earlier. It does not
change the objection to extracting a fork's tree; it identifies the unit.*

**The unit is the delta.** A fork's tree is its upstream author's work: 2,034
files here, ~4,700 commits, none of it this operator's. Extracting it would file
somebody else's structure under this chronology. `scripts/corpus/extract_fork.py`
instead selects commits by author, takes each subject and body as a pair, and
runs the standard shapes over **only the files those commits touched** —
`common` grew an `only=` filter threaded through every shape to make that
possible.

| shape | drafts |
|---|---|
| commit (subject → stated reason) | 2 |
| docstring (touched files only) | 20 |
| rubric | 15 |
| finding | 1 |
| **total** | **38 draft, 0 sealed** |

```
delta: 2 of 4766 commit(s), touching 3 file(s)
commits with a stated reason: 2/2
```

> **Corrected at rung 19 (§6.71): 12 commits, not 2; 7 files, not 3; 295 rows,
> not 38.** The scan walked `HEAD`, and this fork's contribution lives on
> pull-request branches. Every number in this entry is an undercount and the
> paragraph below reasons from the wrong one.

**The delta count is itself the measurement.** 2 of 4,766 is 0.04% — this fork
is very nearly a bookmark. Very nearly, and the remainder is a Kart task-queue
tool and a security audit, which the tree extractor would have buried under two
thousand upstream files. Both commits carry a real body; the ratio 2/2 is too
small to mean anything yet but the *question* — how often does a change here
state its reason — is now asked of every fork automatically.

**The headline number was wrong and it was wrong flatteringly, which is the
dangerous direction.** The run reports docstring coverage in touched files as
**20/26 — 77%**, against the 35% established over rungs 5–7. A 77% would have
been a striking result. Disaggregated by who created the file:

| file | documented | created by |
|---|---|---|
| `tools/kart_task_tool.py` | 3/5 — 60% | the operator |
| `tools/file_tools.py` | 17/21 — 81% | upstream |

The 77% is upstream's habit, measured through this operator's diff and about to
be attributed to them. The operator's own file is 3/5, and **n=5 neither
confirms nor challenges the 35% ratio** — it is one file. The number is recorded
here so that nobody, including a later session reading this file, mistakes the
run's output for a finding.

**The mechanism gap, stated plainly: `touched` is not `authored`.** The `only=`
filter is correct for scoping *shapes* — those rows are about files the operator
chose to work in either way. It is wrong for attributing *ratios*, because a
modified file's docstrings were written by whoever created it. Every per-author
statistic this extractor computes over a fork is contaminated in exactly this
way, and the extractor does not currently know it. **Open:** attribute per file
by `git log --diff-filter=A`, and report operator-created and operator-modified
separately, so a fork can contribute to the ratio instead of poisoning it.

This is the same defect as §6.52 and §6.57 in a third dress. Those were keys
that looked unique and were not. This is a *population* that looked like the
author's and was not. In all three the extractor produced a confident number
about the wrong set of things, and in all three the only thing that caught it
was asking what the denominator was made of.

### 6.60 python-sdk: zero, and the attribution fix that made zero trustworthy — **measured**

*Run 2026-08-06 against `rudi193-cmd/python-sdk` (created 2026-04-23), rung 9, a
fork. Read under the delta rule.*

**§6.59's open gap is closed first**, because running two more forks with a
denominator known to be contaminated would only have produced two more wrong
numbers. `extract_fork.py` now splits touched files by *creator* —
`--diff-filter=A`, oldest adding commit — and reports coverage for each group
rather than blending them. Verified against the hand-measurement from §6.59
rather than trusted:

```
docstrings over all touched files: 20/26   <- blended, not the operator's
  created here      3/5   (60%)  over 2 file(s)
  modified only    17/21  (81%)  over 1 file(s)
```

Those are the two numbers §6.59 computed by hand after the fact. The extractor
now derives them, so no later fork can quietly report upstream's habit as this
operator's.

**And then the rung itself returned nothing.**

```
delta: 0 of 851 commit(s) by rudi193@gmail.com, touching 0 file(s)
0 pair(s): 0 draft, 0 sealed
```

> **Corrected at rung 19 (§6.71): 9 commits, not 0.** This entry's central claim
> — that the repository was "forked and never advanced by a single commit" — is
> false. It was produced by a `HEAD`-only scan. The nine commits touch no files
> (their content merged upstream), which is a different and less flattering
> finding than the one below.

Zero operator-matching author identities appear anywhere in its history, and its
head commit is dated 2026-04-15 — eight days *before* the fork was created. The
repository was forked and never advanced by a single commit. It is a bookmark.

**A zero is a finding when the alternative was a large wrong number.** The tree
holds 356 Python files and 36 markdown documents. The standard extractor would
have read them happily and produced several hundred rows about the Model Context
Protocol SDK's authors, filed under this operator's chronology at position nine.
Every one would have carried a correct `origin` and been about the wrong person.
That is the failure mode §6.59 named — a population that looks like the author's
and is not — and here the delta rule refuses it by construction rather than by
noticing afterwards.

The corpus now records something it could not have before: **the difference
between a repository this operator built and one they bookmarked, as a number
rather than an impression.** Of the two, only the number survives a session
ending.

### 6.61 litellm: zero again, and what two zeroes in a row are worth — **measured**

*Run 2026-08-06 against `rudi193-cmd/litellm` (created 2026-04-23), rung 10, a
fork, read under the delta rule. The largest repository the sequence has
touched by an order of magnitude.*

```
delta: 0 of 37628 commit(s) by rudi193@gmail.com, touching 0 file(s)
0 pair(s): 0 draft, 0 sealed
```

> **Corrected at rung 19 (§6.71): 7 commits, not 0; 5 files; 81 rows.** The
> table below, and the argument built on it, rest on a `HEAD`-only scan.

Zero operator-matching author identities in 37,628 commits. Head dated
2026-04-23, the day the fork was created, and not advanced since.

**The two rungs together are the argument the delta rule needed.** Rung 8 found
a fork with a real contribution buried under two thousand upstream files. Rungs
9 and 10 found two with none at all. Had all three been read as trees:

| rung | repository | files a tree read would take | rows about the operator |
|---|---|---|---|
| 8 | hermes-agent | 2,034 | 38 |
| 9 | python-sdk | 445 | 0 |
| 10 | litellm | **8,137** | 0 |

Ten and a half thousand files, and the operator's entire contribution across all
three is two commits. A tree extraction would have buried a 38-row signal under
a five-figure pile of other people's work and called the result a corpus of this
author. **The delta rule is not a filter applied to the corpus; it is the
difference between the corpus being about somebody and not.**

**On reporting nothing, which this exercise now has to do 42 more times.** Two
consecutive empty stores is the point at which the temptation appears to stop
running the extractor on forks and simply record "no contribution" — and that
would be an assumption dressed as a result, of exactly the kind §6.54 warned
about when it established that silence cannot be distinguished from absence
without a coverage number. So both runs are real runs, both wrote a store, and
both printed their denominator. `0 of 37628` is a measurement. *"I did not
bother"* is not, and the two are indistinguishable a month later.

**One thing left open by the identity test.** The delta is selected by author
email, and one email. If the operator ever committed under another address, or
if a fork's contribution arrived by a merged pull request attributed upstream,
this method scores it zero and would say so with the same confidence it says it
here. Both these repositories also show **zero author identities matching the
name**, which is a second and independent check — but it is still two checks of
the same kind, and the honest statement is *no commit in this history is
attributed to the operator*, not *the operator did nothing here*.

### 6.62 willow-bot: a generic runner that demoted itself within one run, a rule shape, and the ratio's fourth point breaking the band — **measured**

*Run 2026-08-06 against `rudi193-cmd/willow-bot` (created 2026-04-28), rung 11.
Private, so structure and counts only. Read together with rung 12 at the
operator's request — same creation date, one private source and one fork.*

| shape | drafts |
|---|---|
| docstring | 74 |
| rubric | 15 |
| rule (condition → action) | 11 |
| finding · definition | 0 |
| **total** | **100 draft, 0 sealed** |

Document coverage 3/4.

**The generic runner was written for this rung and this rung refused it.**
`extract_standard.py` exists because rung 7's bespoke file was a docstring and a
call, and rung 11 looked like a second copy of it with one string changed —
which is where a third copy becomes inevitable. It was written,
`extract_willow_nest.py` was deleted after verifying `--name willow-nest`
reproduces its 35 rows exactly, and rung 11 was run through it.

Its declined-row report then said, within that one run, that the assumption was
wrong: eleven rows under two headers, both of the form *when this, do that*.
Eight named triggers — Lokasenna, Mistletoe, Web of Anansi, Cattle of Hermes —
each with the condition that fires it and the action it takes, plus three
webhook events mapped to disk operations. So rung 11 got a bespoke extractor
after all, and the sequence is the design working rather than a mistake: the
generic path is correct for a repository that declares nothing new, and the
mechanism that tells you which kind you have is the one that prints what it
refused.

**A rule is not a definition and not a finding.** It is a third kind of claim
with its own failure mode — a rule can be wrong by *firing when it should not*,
which nothing definitional can do. Given a store whose whole subject is whether
a human checked something, rules are the rows most worth a human checking, and
they are the first shape in this corpus that could be tested by running it
rather than by reading it.

**The docstring ratio's fourth point breaks the band, and §6.58 is corrected in
place above.** 74/177 is **42%**, against 34.5 · 35 · 37 from rungs 5–7. The
spread goes from 2.5 points to 7.5. The claim survives as *between a third and
two fifths*; the phrase **"does not move with scale" does not survive** — it was
written on three points that happened to agree, two rungs after this same file
recorded that a claim must hold across every value its sentence can take.

That is twice now that a number stated at three observations has moved on the
fourth: the `### P1:` convention held, this did not. The difference is that a
form either recurs or does not, while a quantity has a distribution, and three
points do not describe one. **Any future claim of this shape needs its spread
reported beside it, not just its centre.**

### 6.63 claude_code_RLM: the third bookmark, and the pairing that gives it meaning — **measured**

*Run 2026-08-06 against `rudi193-cmd/claude_code_RLM` (created 2026-04-28), rung
12, a fork. The operator asked for this and rung 11 to be read together: both
were created on the same day, one a private repository of their own and one a
fork of somebody else's.*

```
delta: 0 of 4 commit(s) by rudi193@gmail.com, touching 0 file(s)
0 pair(s): 0 draft, 0 sealed
```

> **Corrected at rung 19 (§6.71): 1 operator commit, not 0.** The pairing
> argument below still holds directionally — willow-bot is work and this is
> close to a link — but it was stated on a number that was wrong.

Four commits in the entire history, all four by `john-adeojo@brainqub3.com`, all
dated 2026-01-18 — three months before the fork was taken. Ten files. Forked,
never touched. The third bookmark in five forks read.

**The pairing is what makes the zero informative, and it is the operator's
framing rather than mine.** These two repositories were created the same day:

| | willow-bot (own) | claude_code_RLM (fork) |
|---|---|---|
| drafts | 100 | 0 |
| commits by the operator | the whole history | 0 of 4 |
| shapes declared | docstrings, rubric, **rules** | none |

On 2026-04-28 the operator built a bot with a named trigger table and bookmarked
somebody's scaffold. A chronology alone records two repositories created that
day and implies a day's work in two places. The corpus says one of them is work
and the other is a link, and it says it with a number that does not depend on
anyone remembering.

**Three of five forks are empty, and that ratio is now worth watching rather
than concluding.** `hermes-agent` 2 commits, `python-sdk` 0, `litellm` 0,
`claude_code_RLM` 0 — and §6.62 has just finished being corrected for stating a
rate from too few points. So: **4 of 5 forks read so far carry no operator
commit; 39 forks remain unread; no rate is claimed.** The number goes in the
record because it will be checkable against the other 39, not because it means
something yet.

**What a bookmark still tells you.** Nothing about the operator's code, and
something about their reading: what they thought worth keeping a copy of, and
when. That is real information and this corpus cannot hold it — a fork with zero
commits produces zero rows, so the *act of forking* leaves no trace in the store
at all. Whether that act belongs in the memory is a question for the operator,
not for the extractor, and it is written down here rather than answered.

### 6.64 The archived app store: 1,012 drafts, a lesson shape, and §6.22 arriving as a live case in the operator's own fiction — **measured**, cross-repository comparison **open**

*Run 2026-08-06 against `safe-app-store-private-archive-20260608` (created
2026-04-26), rung 13. Private; structure and counts only. A snapshot taken
before a cleanup, so it holds things the live repository may not.*

| shape | drafts |
|---|---|
| docstring | 805 |
| definitional tables | 142 |
| rubric | 35 |
| lesson (exemplar → design claim) | 19 |
| stack (exemplar → what it is built with) | 18 |
| persona (name → what it is for) | 9 |
| **total** | **1,012 draft, 0 sealed** |

> **Corrected at rung 17 (§6.69): 1,023, not 1,012.** `SKILL.md` front matter
> became a shared shape once it had appeared in four of the operator's
> repositories, and this one holds eleven such rows that the run did not then
> claim.

Document coverage 25/150; docstring coverage 805/2,712 — **30%**, a fifth point
below the band §6.58 already had to be corrected for. 506 rows under 74 headers
declined and printed.

**The lesson shape is the most checkable row this corpus has produced.** A design
study of existing terminal applications ends each record with a claim — *"when
there are dozens of resource types, command mode beats menu navigation, but you
must ship tab-completion or only the author will know what's possible."* That is
falsifiable, drawn from something that shipped, and separated deliberately from
the `stack` row beside it: the lesson can stay true long after the stack it was
learned from is stale, and merging them would let one rot the other.

**And then the rung produced the case §6.22 described in the abstract.** Two
names appear in both this repository and rung 1's `SAFE`, three months apart,
under different schemas:

| | rung 1 · 2026-01-05 · `Domain/Voice/Function/Direction` | rung 13 · 2026-04-26 · `Lineage/Type/Core function` |
|---|---|---|
| **Gerald** | "Core voice. Opens doors through absurdity that serious frameworks cannot." | "Exists. Witnesses. Occasionally intervenes…" — *Type: Enlightened rotisserie chicken* |
| **Professor Oakenscroll** | "Academic satire. 97% ratio vs 17% for serious content." | "Documents. Explains. Files working papers about things that haven't happened yet…" |

**Neither pair is a contradiction, and that is the whole point.** Rung 1
describes an *operational role* — what this voice does for the operator's work,
with an engagement ratio attached. Rung 13 describes a *character's function
inside a fiction*. Both are true. They are not two answers to one question; they
are one name carrying two different kinds of claim, which is exactly what §6.22
recorded as having no field, and what `docs/carried-strings.md` argued about
using the word *Nestor* itself. The corpus has now generated a live instance,
from the operator's own material, of the design gap this project documented and
declined to fix.

A store cannot help here. Given both rows it would either collide them — wrongly,
since neither answer is incorrect — or hold them apart in different domains and
say nothing, which is what happened.

**The structural finding, and it is now the largest open question in the
exercise.** *This comparison was impossible for any store to make.* The corpus is
**thirteen separate stores**, one per rung. `ConflictingDraftError` fires within a
store and cannot fire across them, so every drift between repositories — the
whole reason for reading a chronology in order — is invisible to the machinery
and visible only to a script somebody writes by hand, as this one was.

Thirteen rungs in, the corpus can detect that a repository disagrees with itself
and cannot detect that the author disagrees with themselves. That inverts the
stated purpose. **Open:** whether the rungs merge into one store with the
repository as a domain tag, or stay separate with a comparison pass over their
exported bundles. The second is cheaper and keeps each rung independently
rebuildable; the first is the only one that would let the store, rather than a
person, notice.

### 6.65 The comparison pass: what thirteen stores could not see about each other — **shipped**

*Built 2026-08-06 on the operator's decision. §6.64 left two ways to close the
gap — merge the rungs into one store, or compare their exported bundles. The
second was chosen: cheaper, and each rung stays independently rebuildable.*

`scripts/corpus/compare.py` reads every store in `data/corpus`, keys every row
through **Nestor's own normalizer** so it matches the way the store matches, and
groups by key across repositories. It reads bundles, seals nothing, writes
nothing — a comparison that mutated its inputs would make the next one
unrepeatable.

```
13 store(s), 3,029 row(s) total
keys present in more than one repository: 40
  (a key can earn more than one label, so these need not sum)
  drift           25
  two kinds        6
  restated        11
sealed rows across the whole corpus: 0
```

**The classification is the substance.** *drift* is the same key answered
differently within one kind of claim. *two kinds* is one name doing two jobs —
§6.22's case, not an error. *restated* is agreement, which is not a problem and
is the cheapest kind of drift to create, since nothing disagrees yet and nothing
ever warns.

**It produced a security dashboard nobody built.** The rubric rows, invisible in
any single store, line up across seven repositories:

| check | verdicts across repositories |
|---|---|
| No hardcoded dev paths | 5 × PASS, **1 × FAIL** (aionic), 1 × FIXED |
| requirements.txt pinned | 3 × PASS, 2 × WARN, **1 × MISSING** (aionic), 1 × FIXED |
| Race conditions | 7 × PASS |

Twenty-five keys drift. Most are rubric checks whose answers genuinely differ
per repository — which is not disagreement but *state*, and the pass currently
cannot tell those apart from a real contradiction. That distinction is the next
thing this tool needs.

**Two defects in the pass, both mine, both found by running it:**

1. **The classifier returned one label and hid a real finding under a rarer
   one.** `Ratification` drifts *within* `term→term` — willow-1.9 says "Sean
   explicitly approves merge to default branch", Willow says "the formal
   approval process by which a proposal becomes binding law" — *and* appears as
   `decision→authority`. Labelled once, it came out as "two kinds" and the drift
   vanished. Drift is now judged per kind of claim and "two kinds" across them;
   a key can earn both.
2. **It missed the exact case it was built for.** Rung 1's facet key was
   `Gerald (Absurdist dispatches, squeakdogs, The Binder)` — name *plus* domain —
   so it could never match a bare `Gerald`. This is §6.52 and §6.57 pointing the
   other way: those keys were too coarse, this one was too **specific**, and both
   directions produce a confident wrong answer. The key is now the identifier
   and the domain moved to `reason`, where it was always context rather than
   identity.

**And with both fixed it beat the hand analysis that motivated it.** §6.64
compared Gerald across two rungs by hand and found two descriptions. The
repeatable pass finds **three** — a `facet` in SAFE, a `persona` in the archive,
and a `term` in the archive's own dramatis personae table, the last of which sits
in the *same repository* as the second and was invisible to a person reading two
stores side by side.

That is the argument for the mechanism over the inspection, made by the
mechanism, against the inspection that asked for it.

### 6.66 safe-app-willow-grove: a corrections table, and the first rung to run the comparison pass on arrival — **measured**

*Run 2026-08-06 against `rudi193-cmd/safe-app-willow-grove` (created 2026-05-03),
rung 14. Private; structure and counts only. First rung read with
`compare.py` in place, so drift is checked the day the rows enter rather than
thirteen rungs later.*

| shape | drafts |
|---|---|
| docstring | 406 |
| definitional tables | 205 |
| rubric | 17 |
| **correction** (claim → verdict) | 16 |
| goal | 14 |
| **total** | **657 draft, 0 sealed** |

Document coverage 28/73; docstring coverage 406/1,386 — **29%**, a sixth point,
now well below the band §6.58 was corrected for once already.

**The corrections table is the most on-subject shape this corpus has met.**
`Claim | Status` lists what an earlier revision of this repository's own audit
asserted, and what a later reading did to each assertion:

```
 5  withdrawn        1  wrong        1  fixed        1  closed
 7  corrected (to a different severity, a different verdict, a different count)
```

Read one row: *"Scope 'Total Python files ~45' — **Wrong.** 117 tracked `*.py`."*
Another: *"G-KART-01 — unsigned Kart tasks (P1) — **Withdrawn.** No Kart worker
in this repo."* A P1 finding, retracted, because the file it was about was not
there.

Nestor exists to answer whether a human checked something. This is a human
recording that they checked, and were **wrong** — sixteen times, in one table,
against their own prior work. Those rows are worth more than agreeing ones, and
they are the first in the corpus that carry their own refutation. They were
declined as noise on the first run and recovered from the declined-header report,
which is now the fourth time that mechanism has produced the rung's best content.

**The plan schema moved to `common.labelled`** — `Goal` / `Architecture` /
`Tech Stack`, first met at rung 6 and again here. Two repositories sharing a
schema makes it the author's convention rather than one repository's feature, the
same argument that moved `findings` at rung 5 and `rubric` at rung 6. Rung 6
re-runs to the same 1,340 rows with the same 16/3/12 shape counts afterwards.

**And a disagreement inside one repository, surfaced by the store rather than by
reading:** `CLAUDE.md` and `README.md` both document the commands, and they
differ — *"Main Textual dashboard (active, full-featured)"* against *"Main
Textual dashboard"*; *"Standalone Textual DM app"* against *"Standalone DM app"*.
Not contradictions. Two documents describing one thing, one of them staler than
the other, which is the condition that precedes a contradiction.

**The comparison pass, run on arrival:**

```
14 stores, 3,686 rows
keys in more than one repository: 121   drift 46 · two kinds 26 · restated 61
```

One rung added 657 rows and tripled the cross-repository key count, from 40 to
121. That is not this repository being unusually derivative — it is the first
evidence that **shared keys grow faster than rows do**, because every new rung
can collide with all thirteen before it. If that holds, the comparison pass gets
more valuable per rung as the corpus grows, and the decision to build it at
thirteen rather than at fifty was worth the interruption.

### 6.67 claude-deep-review: the fourth bookmark — **measured**

*Run 2026-08-06 against `rudi193-cmd/claude-deep-review` (created 2026-05-09),
rung 15, a fork.*

```
delta: 0 of 224 commit(s) by rudi193@gmail.com, touching 0 file(s)
0 pair(s): 0 draft, 0 sealed
```

> **Corrected at rung 19 (§6.71): 7 commits, not 0; 2 files; 25 rows.** And the
> sentence below is wrong twice over: five forks had been read and *all five*
> carried operator commits.

Five forks read, four with no operator commit. The store is gitignored and the
run produced no code change, so this rung's only artefact is this entry — which
is the correct outcome and worth stating: **a rung that finds nothing still
costs a branch, a run, and a paragraph.** §6.61 argued that skipping the
extractor on a fork that "obviously" has nothing would be an assumption dressed
as a result. The cost of honouring that is exactly this: three lines of output
and a commit that changes one file.

The one forward-looking note is unchanged from §6.61 and still unanswered: the
delta is selected by a single author email with a name match as a second check.
Four zeroes now rest on that assumption.

### 6.68 willow-tech-manual: 23 rows from 46 documents, and the bias the corpus has been carrying all along — **measured**

*Run 2026-08-06 against `rudi193-cmd/willow-tech-manual` (created 2026-05-12),
rung 16. Public. A Mintlify documentation site written as a **workshop manual** —
`03-fault-diagnosis`, `appendix-c-torque-settings`,
`12-carburation-and-fuel-system` — with no Python at all.*

```
23 pair(s): 23 draft, 0 sealed
coverage: 4/46 document(s) produced at least one row
```

**Four of forty-six.** The lowest coverage of any rung, and the rows it did
produce are a file-layout table: `docs/introduction/` → *"Chapter 1 —
orientation and map"*. The manual's actual content — how to diagnose a fault,
what torque to use, what to do when the thing will not start — produced nothing.

**This is a bias the corpus has had since rung 1 and has only now been forced to
notice.** Every shape it knows keys on a *declared* structure: a table header, a
field label, front matter, a docstring, a commit message. Prose that carries its
meaning in sentences is invisible. Thirteen rungs of increasing yield made that
look like competence, when much of it was the repositories happening to be
schema-heavy.

The honest statement of what this corpus is: **not a memory of what the operator
knows, but a memory of what the operator wrote down in a shape a machine could
key on.** Those are different sets and nothing until now has shown where they
diverge. A 46-document manual that yields 23 rows shows it precisely.

Worth separating from a quality judgement, twice over. The manual is not
deficient — a workshop manual is *supposed* to be prose, and a torque figure in
a sentence is not worse than a torque figure in a table. And the extractor is not
broken; it declined 55 rows under ten headers and printed every one, which is how
this is legible at all. The gap is between what the format can hold and what the
document contains, and no amount of extractor work closes it. Only a different
kind of reading would, and that reading would no longer be *checked, not
inferred*.

**Recorded rather than fixed.** The rule this project runs on is that a row
exists only where a heading or a cell put it. Extracting claims from prose means
inferring them, which is the line every rung so far has refused to cross. So the
finding stands as a limit: coverage numbers per rung have been measuring the
repositories' formatting habits at least as much as the extractor's reach, and
§6.55's *"only coverage detects omission"* now needs a companion — **coverage
detects omission only within what the format can express.**

### 6.69 tui-scaffold: four skills invisible to a parser choice, and the docstring ratio finally withdrawn — **measured**

*Run 2026-08-06 against `rudi193-cmd/tui-scaffold` (created 2026-05-12), rung 17.
Private; structure and counts only.*

| shape | drafts |
|---|---|
| docstring | 30 |
| definitional tables | 10 |
| skill (name → what it is for) | 4 |
| **total** | **44 draft, 0 sealed** |

Document coverage 6/16; docstring coverage 30/52.

**The four skills were declared, and the extractor could not see them.** Their
front matter writes the description as a folded block scalar:

```yaml
name: tui-layout-screens
description: >-
  Textual screen composition: when adding or refactoring screens, routing,
  modal flows, or push_screen/pop_screen behavior in this repo.
```

`common.frontmatter` skipped every key whose value was not a scalar on one line —
a deliberate choice, documented as refusing to half-read nested structures. But a
folded scalar *is* a plain string; it is just written across lines. The caution
was right about lists and wrong about this, and the cost was every skill in the
repository reported as a silent document.

That is a third variety of the same error. §6.52 and §6.57 were keys too coarse;
§6.65 was a key too specific. This is a **reader too strict** — and like the
others it failed silently, in the direction of confident under-reporting, and was
caught only by the coverage line saying four `SKILL.md` files produced nothing.

**The shape moved to `common.standard`** once counted across the clones: skills
appear in four of the operator's own repositories (26 · 4 · 1 · 1). Rung 13 gains
eleven rows as a result and **is corrected in place above: 1,023, not 1,012.**
Rung 6 is unchanged — its single `SKILL.md` carries no `name`/`description` front
matter at all.

**And the docstring ratio is withdrawn, not weakened.** Seven measurements:

```
29 · 29.5 · 34.5 · 35 · 37 · 42 · 58
```

§6.58 claimed "roughly a third, and it does not move with scale" on three points.
§6.62 corrected it to "between a third and two fifths" on four. Rung 17 is 58%
and breaks that too. **There is no stable ratio.** The right response is not a
third weakening — it is to stop making the claim and report the distribution.

The pattern is worth keeping even though the claim is not: a quantity was stated
at three observations, hedged at four, and abandoned at seven, while the one
*form* the corpus asserted at three — the `### P1:` convention — has held through
seven rungs without a single exception. Forms recur or they do not. Quantities
have distributions, and this project has now paid twice to learn that three
points do not describe one.

### 6.70 willow-2.0: 3,680 drafts, and the consolidation test rung 7 banked — **measured**

*Run 2026-08-06 against `rudi193-cmd/willow-2.0` (created 2026-05-18), rung 18.
Public, and **not archived** — its head moved the day before this run, so the
`repo@commit` pin records one afternoon rather than a settled repository. The
same objection that put `willow-mcp` on the held list; read here on instruction,
with the caveat carried in the rows.*

| shape | drafts |
|---|---|
| docstring | 2,954 |
| definitional tables | 731 |
| skill | 186 |
| sourced-claim (`Claim | Primary sources`) | 68 |
| rule (`Rule | What it means`) | 50 |
| goal · intent · success | 49 |
| rubric | 15 |
| **total** | **3,680 draft, 0 sealed** |

The largest rung: 558 documents, 850 modules, 7,289 table rows in the source.
Docstring coverage 2,955/9,240 — 32%, the eighth point in a distribution this
file has stopped drawing conclusions from.

**The consolidation test, banked at rung 7 and now paid.** `willow-nest` was
folded into this repository. Its 19 docstrings, matched by symbol name:

```
 0  survive at the same path with the same docstring
 5  docstring identical somewhere in willow-2.0
 2  name present, docstring differs
12  name absent entirely
```

Everything moved — expected, that is what consolidation is. What the two changed
rows say is not expected:

**`route_file`** — `router.py` → `apps/nest/router.py`:

> *nest:* "Full intake **for one file**: classify → b17 → store record → move →
> return result. **Raises FileNotFoundError if src doesn't exist.**"
> *2.0:* "Full intake: classify -> b17 -> store record -> move -> return result."

The documented **exception contract was dropped in the move**. Nothing announced
it. A reader of `willow-2.0` alone cannot know the function was ever documented
to raise, and a reader of `willow-nest` alone cannot know it stopped being said.
Two rungs eleven apart, and the corpus is the only place both are visible.

**`classify`** — `classify.py` → `sap/core/nest_rules.py`:

> *nest:* "Return the track for a filename, or None if unknown. **Priority order
> matters — legal before narrative, handoffs before specs.**"
> *2.0:* "Track for a filename, or None if unknown. **Order in the rules file
> wins.**"

That one is a *correct* rewrite recording a real design change — ordering moved
from code into data. But the specific knowledge (legal before narrative,
handoffs before specs) is now stated nowhere in the docstring, only in a file
the docstring points at. The claim got shorter and the reader got further from
the fact.

**And consolidation multiplied the namesakes.** `classify` is one symbol in
`willow-nest` and **four** in `willow-2.0` — a triage lane, a category assigner,
a filename track, and a model-tier picker. §6.57 found bare symbol names to be
bad keys; this shows *why* the problem grows: merging repositories merges
namespaces, and the qualified key that §6.57 introduced is what makes rung 18
readable at all.

**Comparison pass, on arrival:**

```
18 stores, 7,444 rows
keys in more than one repository: 1,214   drift 173 · two kinds 94 · restated 1,032
```

One rung doubled the corpus and took shared keys from 121 to 1,214 — tenfold.
§6.66 guessed that shared keys grow faster than rows; two rungs later the corpus
has doubled and the shared keys have gone up by an order of magnitude. The
guess holds so far, on two observations, which by this file's own hard-won rule
is not enough to state as a rate. It is written down to be checked at rung 25.

### 6.71 Every fork number in this file was wrong, and the fix is one flag — **measured**, five entries corrected in place

*Found 2026-08-06 at rung 19 while reading `sigmap`, the sixth fork. This is the
largest error in the exercise and it invalidated five published entries.*

**The defect.** `extract_fork.py` selected the operator's commits with
`git log --author=…`, which walks **HEAD**. A fork's contribution
characteristically does *not* live on the fork's default branch: it lives on the
pull-request branch it was raised from, which is merged **upstream** and never
into the fork's own main line. Every such commit was invisible.

**How it surfaced.** `sigmap` reported two authored commits, both touching zero
files. One of their messages describes writing `packages/adapters/willow.js` in
detail. That file **exists in the tree** — and `git log --diff-filter=A` credits
it to the upstream maintainer's release commit. A contribution that shipped,
attributed to somebody else, reported by this corpus as two empty commits. Asking
why produced `git log --all`, and `--all` produced this:

| fork | reported | actual | files | rows |
|---|---|---|---|---|
| hermes-agent | 2 | **12** | 7 | 295 |
| python-sdk | 0 | **9** | 0 | 0 |
| litellm | 0 | **7** | 5 | 81 |
| claude-deep-review | 0 | **7** | 2 | 25 |
| claude_code_RLM | 0 | **1** | 0 | 0 |
| basic-memory | — | 10 | 13 | 230 |
| awesome-claude-skills · sigmap · ngrok-python · DontFeedTheAI · engram | — | 5 · 4 · 3 · 3 · 2 | | |

**There are no bookmarks.** All eleven forks read carry operator commits. §6.60,
§6.61, §6.63 and §6.67 each argued at length about what a zero *means* — "the
difference between a repository this operator built and one they bookmarked, as a
number rather than an impression" — and the number was an artefact of a missing
flag. All five entries are corrected in place above rather than edited quietly.

**What makes this worse than a bug.** §6.61 stated the limitation exactly:
*"if a contribution arrived by a merged pull request attributed upstream, this
method scores it zero and would say so with the same confidence it says it
here."* That sentence was written, published, and then not acted on for four
rungs, while four more zeroes were reported with full confidence beneath it.
**Naming a limitation is not the same as testing for it**, and this file now
contains the proof — written by the same process that named it.

**The second phenomenon, which the fix reveals rather than hides.**
`python-sdk` has 9 authored commits touching 0 files; `claude_code_RLM` has 1
touching 0. Those commits are real and their diffs are empty, because the work
landed upstream and the fork's copy is an artefact. So the honest categories are
three, not two: *contributed here*, *contributed through here to upstream*, and
*never touched* — and the corpus can distinguish the first from the other two
but not yet the second from the third.

**What the whole method now rests on.** Author identity, still one email. The
by-name scan disagrees with the by-email scan on six of eleven forks, so the true
counts are floors rather than totals. Written down and not fixed, because the
lesson of the last hour is that writing a limitation down is where the work
starts.

### 6.72 The identity widened, and the vetting mattered more than the widening — **measured**

*Run 2026-08-06 immediately after §6.71, closing the last assumption the fork
method rested on.*

§6.71 ended by saying the corrected counts were **floors rather than totals**,
because the delta was selected by one email while a name-based scan disagreed on
six of eleven forks. The obvious fix was to match on the name as well. It would
have been wrong.

**Enumerating the identities first is what made the difference.** Every author in
all eleven forks whose name or address could plausibly be the operator, with
counts:

| identity | verdict |
|---|---|
| `Sean  Campbell <rudi193@gmail.com>` (two spaces) | the operator |
| `Sean Campbell <rudi193@gmail.com>` | the operator |
| `rudi193-cmd <rudi193@gmail.com>` | the operator |
| `rudi193-cmd <…@users.noreply.github.com>` | the operator |
| `Sean Marsh Glover <s.glover12@gmail.com>` | **somebody else** |
| `Sean Walker <root@seankwalker.com>` | **somebody else** |
| `salt-555 <seanalt555@gmail.com>` | **somebody else** |
| `davidcampbelldc <…>` | **somebody else** |

Three display names, two addresses, one person. And four other people who share
a first or last name with them. **A name match would have swept in all four and
still missed `rudi193-cmd`**, which is the identity carrying most of the
commits. The disagreement §6.71 flagged was not the email scan missing
contributions — it was the name scan finding strangers.

**So the widening is by address, and it is small:**

```
hermes-agent  12 -> 13     every other fork: unchanged
```

One commit, under the GitHub noreply address. Total across eleven forks: **64
authored commits**. These are now totals rather than floors, and the difference
between saying that and assuming it is one enumeration that took a minute.

**The lesson is the inverse of §6.71's and worth having both.** §6.71 was a
limitation named and not tested, for four rungs. This was a limitation named and
tested immediately — and the test said the obvious fix was harmful. *Both* halves
matter: an untested limitation is a liability, and an untested **fix** is the
same liability wearing a solution's clothes. The corpus is now at 8,057 rows and
the only reason any of them are attributable is that a name was never used as a
key.

Which is, exactly, §6.22 and §6.65 again — a name is not an identifier — arriving
for the third time, in the one place where getting it wrong would have
misattributed another person's work to this operator.

### 6.73 Three forks, and the largest delta the corpus has read — **measured**

*Run 2026-08-06 against `smallcode`, `ghgrab` and `mcp-memory-service` (all
created 2026-05-21), rung 20. Read together at the operator's request.*

| fork | commits | files | rows | with a stated reason |
|---|---|---|---|---|
| smallcode | 2 | 2 | 34 | 2/2 |
| ghgrab | 1 | 4 | 26 | 1/1 |
| **mcp-memory-service** | **26** | **24** | **491** | 17/26 |

`mcp-memory-service` is the largest fork contribution in the corpus by every
measure, and it would have read as **zero** under the extractor as it stood four
rungs ago. Twenty-six commits, of 2,865, on a repository whose tree is somebody
else's — the delta rule and the `--all` fix between them are the entire reason
those 491 rows exist rather than several thousand rows about the upstream
author.

**The identity vetting earned itself again, immediately.** A fifth namesake
appears here — `Sean K <logikal@users.noreply.github.com>` — with one commit in
`mcp-memory-service`. Not the operator, and correctly excluded, because §6.72
settled that the identity is a set of *addresses*. Had the name-based widening
gone in, this rung would have credited a stranger's commit to this chronology on
its first run.

**The first fork with enough commits for the reason-rate to mean anything:**
17 of 26 commit messages carry a body beyond the subject — **65%**. Recorded as
a single observation, not a rate. This file has now been burned twice by
quantities asserted from too few points, and one fork is one point.

**Second measurement of the split §6.59 nearly got wrong:**

```
mcp-memory-service   created here 10/22 (45%)   modified only 472/569 (83%)
hermes-agent         created here  3/5  (60%)   modified only  17/21 (81%)
```

The blended figure would have been 482/591 — **82%** — and it is upstream's
number both times. The two upstream columns agree closely (81%, 83%) and the two
operator columns do not (60%, 45%), which is what a distribution looks like when
one side is thousands of files by many hands and the other is twenty-six files
by one. No claim is made from it. It is here so that when a third fork lands,
there is something to compare against.

### 6.74 willow-config: a third persona schema that shares no names, and a refusal I nearly made from an assumption — **measured**

*Run 2026-08-06 against `rudi193-cmd/willow-config` (created 2026-05-24), rung
21. Private; structure and counts only. 617 markdown documents, three Python
modules — a configuration and handoff repository.*

| shape | drafts |
|---|---|
| capability (`Capability` → `Location`) | 760 |
| definitional tables | 65 |
| risk (`Risk` → `Mitigation`) | 40 |
| docstring | 16 |
| mandate (agent → what it does) | 8 |
| prohibition (agent → what it must not) | 7 |
| **total** | **772 draft, 0 sealed** |

**I nearly refused the 811-row capability table, and the reasoning was sound and
the premise was invented.** The argument written down before checking: a table
appearing in 138 session handoffs is one rolling snapshot restated, not 811
declarations, and extracting it would fill the store with time-series noise the
corpus has no shape for. Then it was counted: **653 distinct capability names**,
most-repeated six times. An accumulating inventory, not a redrawn one. The
refusal would have been the largest single act of under-extraction in this
exercise, and it would have shipped with a paragraph of justification and no
number under it — which is the precise shape of every error §6.51 through §6.72
records.

**A mandate and a prohibition are stored as separate pairs**, not folded
together. They fail differently: one is broken by inaction and the other by
action, and a store that merges them cannot say which was violated. That is also
this project's own covenant restated in somebody else's repository — *what you
may do* and *what you may not* as two claims rather than one.

**The third persona schema, and it shares nothing with the first two.**

| rung | schema | entries |
|---|---|---|
| 1 · SAFE | `Domain` / `Voice` / `Function` / `Direction` | 21 |
| 13 · app-store archive | `Lineage` / `Type` / `Core function` | 9 |
| 21 · willow-config | `Register` / `Mandate` / `Namespace` | 8 |

Overlap, measured: rungs 1∩13 share **two** names (Gerald, Professor
Oakenscroll — §6.64's case). Rungs 1∩21 share **none**. Rungs 13∩21 share
**none**.

Three schemas, four months, thirty-eight entries, and the later two describe an
entirely different population from the first. The obvious reading — that one
cast of characters was redescribed as the schema evolved — is **false**, and only
a set intersection could say so. What actually happened is that a vocabulary for
describing *voices* was reused to describe *agents*, and the corpus is the only
place both are visible under one lens.

**Comparison pass:** 21 stores, 9,380 rows, 1,237 shared keys (186 drift · 108
two kinds · 1,032 restated). Rung 21 added 772 rows and only 23 shared keys —
against rung 18, which added 3,680 rows and 1,093 shared keys. §6.66's guess
that shared keys outgrow rows now has a clear counter-example: **it depends
entirely on whether the rung talks about the same things as its predecessors.**
A configuration repository full of one-off capability names collides with
nothing. The guess is withdrawn before it was ever a claim.

### 6.75 Eight more forks, and the first quantity this file has earned the right to state — **measured**

*Run 2026-08-06 against `stash`, `statewave`, `holon`, `ogham-mcp`, `mengram`,
`ShibaClaw`, `ctxvault` and `vcspull` (all created 2026-05-25), rung 22.
`sean-data-vault`, created the same day, stays on the held list.*

| fork | commits | files | rows |
|---|---|---|---|
| stash | 5 | 4 | 3 |
| ctxvault | 4 | 19 | 32 |
| holon | 4 | 3 | 4 |
| vcspull | 2 | 10 | 30 |
| ogham-mcp · ShibaClaw · statewave · mengram | 1 each | 3 · 2 · 2 · 1 | 39 · 36 · 1 · 1 |

Nineteen commits. **Twenty-two forks read; twenty-two carry operator commits.**
The word "bookmark" has now been wrong every single time it was used.

**And with twenty-two observations, the reason-rate is finally reportable.**
Of 112 authored commits across the forks, **75 carry a body beyond the subject —
66%**. The per-fork distribution:

```
0 · 0 · 40 · 42 · 50 · 60 · 65 · 66 · 75 · 75 · 85 · 100 ×10
```

This file has withdrawn two quantities for being asserted from three or four
points (§6.62, §6.69) and withdrawn a third guess before it became a claim
(§6.74). This one is different in a way worth naming precisely: **112 events
across 22 independent repositories, with the distribution printed rather than
summarised.** The mean is 66% and it is not the interesting number — the
interesting number is that ten of twenty-two forks are at 100% and two are at 0%,
which is not a spread around a centre but two populations.

The two zeroes are `python-sdk` (9 commits) and `claude_code_RLM` (1) — the same
two forks §6.71 identified as having commits that touch **no files**. Their
messages are subjects with no bodies because the commits are merge artefacts of
work that landed upstream. So the 0% is not a habit of writing thin commit
messages; it is an artefact wearing one, and the honest statement of the
distribution excludes them: **of 102 commits that changed something, 75 state a
reason — 74%, with no fork below 40%.**

That is the first quantity in this exercise supported well enough to survive
being written down, and it took twenty-two repositories, one flag fix, one
identity vetting, and two prior withdrawals to get there.

### 6.76 Four repositories, two of them empty, and a counter that has been overstating every shape for twenty rungs — **measured**

*Run 2026-08-06 against `community` (fork), `rudi193-cmd`,
`rudi193-cmd.github.io` and `quiet-corner` (created 2026-05-26 to 05-30),
rung 23.*

| repository | rows | note |
|---|---|---|
| quiet-corner | 90 | 89 definitions from 257 adds |
| community (fork) | 19 | **11 of 19 commits are the operator's** |
| rudi193-cmd | 0 | profile README, coverage 0/1 |
| rudi193-cmd.github.io | 0 | one page, coverage 0/1 |

**`community` is the operator's fork by majority.** Eleven of nineteen commits —
58%, against a fork median nearer 1% — touching 64 files. Every earlier fork was
a small delta on somebody else's tree. This one is mostly theirs, and the delta
rule handles it without modification: the unit was always the operator's
commits, and here the operator's commits are most of the repository.

**Two repositories yield nothing and should.** A GitHub profile README and a
one-page site declare no structure because they *are* the declaration. §6.68
established that this corpus holds what was written in a shape a machine can key
on; a profile page is prose about a person. Coverage 0/1 twice, printed, and
correct.

**The counter has been lying by a name.** Each shape printed the number of
accepted `add_pair` calls, labelled as drafts, beside a row total that came from
`memory.stats`. Those differ whenever a source restates a claim verbatim, because
`add_pair` returns the stored row rather than raising. `quiet-corner` makes the
gap impossible to miss: **257 adds became 89 rows.**

The repeats are SQL schema tables — `id → INTEGER PK` in **32** separate tables,
`created_at → TIMESTAMP` in 18. Both directions of the defect matter:

* **The report was wrong.** Twenty rungs printed adds beside rows without
  remarking that they disagree. The load loop now prints `89 row(s) from 257
  add(s)`, so the gap is visible where it exists and silent where it does not.
  Earlier entries' per-shape numbers are *adds*; their totals were always rows
  and were always right.
* **The key is wrong, for the fourth time.** `id` is not an identifier — it is a
  column name scoped to a table, and thirty-two tables each declare their own.
  §6.52 (table cell), §6.57 (bare symbol), §6.65 (name plus domain), and now a
  schema column: **every key this corpus has gotten wrong has been a string that
  looked unique in the document it came from and was not unique in the corpus.**
  That is now a rule with four instances behind it, and it is the single most
  reliable finding this exercise has produced.

Not re-keyed here. Qualifying definition keys by their table heading would change
every rung's rows, and the honest move at rung 23 is to record the fourth
instance and decide the re-key deliberately rather than mid-batch.

### 6.77 Four forks, and nine namesakes in one repository — **measured**

*Run 2026-08-06 against `openclaw`, `kanon`, `commcare-nova` and `claudeclaw`
(all created 2026-06-04), rung 24.*

| fork | total commits | operator | files | rows |
|---|---|---|---|---|
| openclaw | **70,860** | 9 | 8 | 1 |
| claudeclaw | 763 | 4 | 6 | 2 |
| commcare-nova | 894 | 1 | 1 | 0 |
| kanon | 43 | 1 | 3 | 1 |

Twenty-six forks read; twenty-six carry operator commits.

**`openclaw` is the strongest vindication the identity rule will get.** Its
history holds **nine** author identities that a name-based match would have
claimed for this operator:

```
J. Campbell <fork42@mac.com>          Sean McLellan <Oceanswave@…>
Sean <sy1754222911@gmail.com>         Sean McLellan <oceanswave@clawdbot.lan>
Sean Coley <sean@senza.work>          Sean Sun <1194458432@qq.com>
clawSean <sean@openclaw.ai>           clawSean <seancrustacean@gmail.com>
seans-openclawbot <seandai.apps@gmail.com>
```

One repository, nine strangers, and exactly one identity that is the operator.
§6.71 fixed a missing `--all` that had been costing contributions; §6.72 rejected
the obvious follow-up of matching names too, on the evidence of four namesakes
across eleven forks. Here are nine more in a single checkout. **Had the name
match gone in, this rung would have attributed a 70,860-commit project's
contributors to one person** and the corpus would have said so with a straight
face.

**And openclaw is the sharpest case of the ratio the delta rule exists for.**
Nine commits out of 70,860 — 0.013%. A tree extraction would have produced tens
of thousands of rows about a large open-source project and filed them under this
chronology at position twenty-four. The nine commits produce **one** row, because
only one of them carries a body. That single row is the honest yield, and the
distance between one row and tens of thousands is the entire argument of
`docs/corpus-order.md` in a single number.

**One observation against §6.75's reason-rate, deliberately not folded in.**
`openclaw` is 1/9 — 11%, below the 40% floor §6.75 reported across 22 forks.
Adding it moves the corpus figure from 75/102 to 76/111, and the floor claim
("no fork below 40%") is now **false**. Recorded here rather than by editing
§6.75: that entry's numbers were correct for the 22 forks it measured, and this
is the twenty-third disagreeing. The claim was always about a sample and this is
what a sample growing looks like.

### 6.78 Two before-and-after pairs: a redaction verified complete, and a docstring diff that turns out to be a question — **measured**

*Run 2026-08-06 against `willow-1.9-local-archive-20260608` and
`safe-app-store` (both 2026-06-08), rung 25. Each is the counterpart of a
repository already read, which makes this the first rung that is entirely
comparison.*

**Pair one: `willow-1.9` public, against the private pre-cleanup archive.**

```
in both: 1,340    answers differing: 0    public only: 0    archive only: 1
```

One thousand three hundred and forty rows identical, and the archive holds
**exactly one thing the public repository does not**:
`tools/nest_watcher.py::_send_commit_alert`. The file exists in both; the
function does not. What it does is read a legal-matter manifest — case number,
session date, file count, summary — and broadcast it to a channel.

So the cleanup removed one function, and it was the function handling legal case
data. **The corpus can now say a redaction was complete**, not by trusting it but
by diffing 1,341 rows and finding the single difference to be the one that should
be there. That is a use for this thing nobody designed it for, and it is the most
directly valuable output of twenty-five rungs.

**Pair two: the app store archive (2026-04-26) against the live repository
(2026-06-08).**

```
archive 1,023 rows · live 2,472
in both 969   answers differing 38   live only 1,503   archive only 54
```

Six weeks, and the store more than doubled. Thirty-eight docstrings changed. One
of them, checked rather than reported:

> `apps/the-squirrel/db/fragments.py::init_schema`
> *archive:* "Create fragments, tree_branches, **fragment_lattice_cells**. Idempotent."
> *live:* "Create fragments, tree_branches. Idempotent."

A table vanished from the sentence. Checked in the code: `fragment_lattice_cells`
goes from **7 mentions and a `CREATE TABLE` to zero**. The docstring did not rot —
it tracked a real removal, exactly.

**And that is the finding, because rung 18 looked identical and was not.**
There, `route_file` lost "Raises FileNotFoundError if src doesn't exist" while the
behaviour stayed. Same signature — a docstring gets shorter between two snapshots
— and opposite meanings: one is documentation decaying, the other is
documentation keeping up.

**A docstring diff is a question, not an answer.** The corpus surfaces it, and
resolving it takes reading the code. Every one of the 38 is currently unresolved,
and reporting them as "drift" would be exactly the §6.52 error at a new altitude:
a signal that is evidence of *something happened here* being written up as
evidence of *something went wrong here*. Thirty-eight questions is a genuinely
useful output. Thirty-eight findings would have been a lie.

### 6.79 The June pile: thirteen forks, and a writing repository that the corpus cannot read — **measured**

*Run 2026-08-06 against `DispatchesFromReality` and the thirteen forks created
2026-06-12 to 06-30, rung 26.*

| fork | commits | files | rows |
|---|---|---|---|
| mex | 4 | 2 | 3 |
| codejail | 3 | 4 | 29 |
| sshelf · mcp-local-rag · cowsay-files · glapagos | 2 each | 6 · 9 · 2 · 2 | 26 · 2 · 1 · 4 |
| ctx · codejail · PDFMathTranslate · HeatWatch · mcp-mem0 · LightAgent · codebase-memory-mcp · Tauon | 1 each | | 30 · 11 · 8 · 6 · 1 · 1 · 1 |

Twenty-two commits. **Thirty-nine forks read; thirty-nine carry operator
commits.** `Tauon` is the second 9,749-commit upstream to yield a single row.

**`DispatchesFromReality` is the sharpest case yet of the bias §6.68 named**, and
the first time it lands on a repository the operator wrote *entirely themselves*:

```
15 pair(s)   coverage: 3/56 document(s)   460 rows declined under 72 headers
```

Fifty-six documents of professional writing, and the corpus takes fifteen rows —
all from tables. §6.68 found this in a manual somebody else's format made
schema-light. Here the subject *is* prose: essays are the artefact, and there is
no table to key on because there was never any reason to write one.

Three rungs now — 16, 23 and this — say the same thing from different angles, and
together they are strong enough to state plainly: **this corpus is a memory of
the operator's *structured* output, and the proportion of their work that is
structured varies from near-100% (a governance repository, a skills library) to
near-zero (a manual, a profile, a body of essays).** Any claim of the form "the
corpus holds N rows about X" carries an unstated denominator that changes by two
orders of magnitude depending on what X was written in.

That is not a defect to fix. It is the shape of the instrument, and the fifty-six
silent documents are the only reason it is visible at all.

### 6.80 The almanac org: eleven repositories with zero divergence, and a template that has walked away from all of them — **measured**

*Run 2026-08-06 against the fourteen `almanac-data` repositories (created
2026-06-29 to 07-24), rung 27. The first rung that is a template and its
instances.*

| repository | rows | docstring coverage |
|---|---|---|
| almanac-template | 38 | 30/151 |
| eleven `*-almanac` instances | **21 each** | **21/77 each** |
| almanac-data · .github | 0 | — |

**Eleven repositories, and every extracted row is identical.** Not "the same
count" — the same rows. Compared as sets against `climate-almanac`: **11/11
identical**, across climate, health, economy, environment, civic, education,
science, energy, agriculture, transportation and justice.

This is the corpus's first measurement of *perfect* consistency, and it is
worth noticing that it took eleven stores to see. Any single almanac says
nothing; the eleventh identical one says the generator worked and nobody has
edited an instance since.

**And the template has walked away from all of them.** The instances are a strict
subset: **17 template rows appear in no instance, and 0 instance rows are absent
from the template.** The seventeen are maintenance tooling —

```
scripts/check_recovery_rot.py          present in 0/5 instances checked
scripts/alert_on_revision_drift.py     present in 0/5
.github/workflows/recovery-bot.yml     present in 0/5
```

— scripts that detect *rot* and *drift* in the almanacs' own data, plus the
weekly workflow that runs them. So the template gained the machinery for
noticing when an almanac goes stale, and eleven almanacs never received it.

The finding states itself without help: **the drift-detection tooling has
drifted.** And it is the exact failure this corpus keeps meeting under different
names — §6.54's linter that passes none of its subjects, §6.68's coverage that
only sees what the format expresses. A check that exists in one place and runs
in none is indistinguishable from no check, and only counting across all twelve
repositories makes the difference visible.

**A note on what "zero divergence" costs to establish.** Eleven identical stores
contribute 231 rows, of which 21 are distinct. The comparison pass counts 2,063
restated keys corpus-wide, and this rung is responsible for a large share of the
growth — repositories that agree perfectly inflate the *restated* bucket exactly
as much as repositories that were carefully kept in sync by hand. The bucket
counts agreement; it cannot tell generated agreement from maintained agreement,
and after this rung most of it is generated.

### 6.81 The early-July batch: five repositories, no new shapes, and the ratio's full spread — **measured**

*Run 2026-08-06 against `jeles-remote`, `awesome-sovereign-software`,
`kartikeya`, `safe-design` and `willow-gate` (created 2026-07-01 to 07-10),
rung 28.*

| repository | rows | document coverage | docstring coverage |
|---|---|---|---|
| kartikeya | 121 | 0/3 | 121/308 — 39% |
| willow-gate | 118 | 1/5 | 102/290 — 35% |
| safe-design | 34 | 1/1 | 28/66 — 42% |
| awesome-sovereign-software | 7 | 0/4 | 7/13 — 54% |
| jeles-remote | 1 | 0/1 | 1/5 — 20% |

281 rows. **None of the five declares a shape the corpus had not already met**,
so all five ran through `extract_standard.py` unmodified — the second time that
has been true of a whole batch (rung 7 was the first, for one repository).

**Document coverage is near-zero across all five: 2 of 14 documents.** These are
working code repositories with a README and little else, and almost everything
extracted came from Python. That is the mirror image of rungs 1 and 21, which
were nearly all documents and almost no code, and it is the same instrument
reading two different halves of the same person's output.

**The docstring ratio, with fourteen points, has the spread it always had:**

```
11 · 20 · 29 · 29.5 · 32 · 34.5 · 35 · 35 · 37 · 39 · 42 · 42 · 54 · 58
```

Low 11 (`quiet-corner`), high 58 (`tui-scaffold`), and no clustering worth the
name. §6.58 asserted "roughly a third, and it does not move with scale" on three
of these; §6.62 hedged it on four; §6.69 withdrew it on seven. Fourteen points
later the withdrawal reads as the only defensible move available, and the
distribution is printed here rather than summarised because a mean over that
range would be a number with no referent.

The useful residue is negative and worth keeping: **there is no such thing as
this operator's docstring rate.** What there is, is a rate per repository, which
varies by a factor of five, and which the corpus can report per rung and should
never average.

### 6.82 The corpus reads Nestor, and finds it nearly unreadable — **measured**

*Run 2026-08-06 against `willow-data-vault`, `willow-grove`, `Jeles`, `UTETY`,
`corpus-lens` and **`nestor`** (created 2026-07-12 to 07-16), rung 29. Nestor is
read at `master` (`1c88057`), the same as every other repository is read at its
default branch — so this session's thirty entries are not in it.*

| repository | rows | document coverage | docstring coverage |
|---|---|---|---|
| **nestor** | **870** | **2/28** | 862/1773 — 49% |
| Jeles | 450 | 1/5 | 436/744 — 59% |
| UTETY | 119 | 1/12 | 117/415 — 28% |
| corpus-lens | 43 | 0/6 | 43/163 — 26% |
| willow-grove | 28 | 2/6 | 5/16 — 31% |
| willow-data-vault | 0 | 0/1 | — |

**Two of twenty-eight.** Of Nestor's 870 rows, **862 come from Python** and
eight from documents — four from `IDEAS.md` and four from `docs/releasing.md`.
Silent: `README.md`, `CLAUDE.md`, `TODO.md`, `QUESTIONS.md`, both `FINDINGS-*`
files, `docs/code-review-lessons.md`, and twenty more.

`IDEAS.md` is 3,891 lines. `README.md` is 1,408. Together with `QUESTIONS.md`
and the review lessons that is **5,673 lines of the densest argument in the
entire corpus**, and it yields four rows — all four from one illustrative table
inside §6.18, of the form ``supersede_pair`` → ``ValueError``.

**This is §6.68's bias landing on the instrument itself, and it is worth stating
without softening.** The repository whose entire subject is *"has a human checked
this, and how would you know"* contributes almost nothing to a corpus of checked
claims, because it makes its claims in sentences. Every lesson this exercise has
produced — four wrong keys, a missing `--all`, an untested limitation, the
withdrawal of three quantities — is written in prose that the machinery built to
find such things cannot see.

Not a paradox and not an indictment of either side. A precise statement of what
the corpus is: **it holds what was written in a shape a machine can key on, and
the most valuable thinking in these 105 repositories is not written that way.**
That has been true since rung 1 and provable only now, because only Nestor could
be measured against a full reading of what it actually contains.

**The honest consequence for everything above.** Every rung's yield has been
reported as a number of rows. Rung 29 shows the ratio that number bears to the
underlying material is not stable, not knowable in advance, and — for the one
repository where both sides can be inspected — about **1 row per 700 lines of
prose against 1 row per 2 lines of code**. Row counts compare repositories to
themselves over time, which is what rungs 18 and 25 used them for and where they
work. They do not measure how much a repository knows.

### 6.83 The first real bookmark, and a whole category of authorship the method cannot see — **measured**, attribution **open**

*Run 2026-08-06 against `redential-cli`, `Imageination`, `multimodels-mcp` and
`willow-compose` (created 2026-07-17 to 07-20), rung 30. `mealie` is excluded at
the operator's request and recorded in `docs/corpus-order.md`.*

| repository | commits | files | rows |
|---|---|---|---|
| redential-cli (fork) | 13 | 30 | 29 |
| willow-compose (private) | — | — | 36 |
| multimodels-mcp (fork) | 2 | 3 | 0 |
| **Imageination (fork)** | **0** | 0 | 0 |

**`Imageination` is the first true bookmark.** Four commits in the whole history:
an initial commit by the upstream author, and three by `Claude
<noreply@anthropic.com>`. No operator identity appears anywhere. §6.71 declared
"there are no bookmarks" across eleven forks and that was true of those eleven;
forty forks in, here is one.

**Except it probably is not one, and that is the finding.** The fork was created
2026-07-17. The three agent-authored commits are dated 2026-07-17. They add
engineering standards, CI, lint config and a CONTRIBUTING file — the shape of
somebody setting up a repository they have just taken. Almost certainly the
operator's work, delegated, and **invisible to every scan this corpus performs**,
because the author field says `Claude` and the identity rule is a set of the
operator's addresses.

**Measured across every clone in the session** — commits authored by an agent
identity (`Claude`, `cursoragent`, `noreply@anthropic.com`):

```
litellm 613 · basic-memory 93 · DispatchesFromReality 22 · openclaw 11
quiet-corner 7 · python-sdk 6 · Imageination 3 · redential-cli 2
mcp-memory-service 2 · hermes-agent 1
```

Two populations again, and this time they are not separable by inspection.
`litellm`'s 613 are upstream's — a large project whose maintainers use agents.
`DispatchesFromReality`'s 22 and `quiet-corner`'s 7 are in the operator's **own**
repositories and are certainly theirs. `Imageination`'s 3 are on a fork, the day
it was taken, and could be either.

**This is not a bug to fix quietly.** §6.72 established that identity is a set of
addresses because names are ambiguous, and that ruling was right — it excluded
thirteen namesakes across two rungs. It also, necessarily, excludes delegation:
an agent committing under its own identity is not the operator's address, and no
amount of address-matching will find it.

The question is the operator's, not the extractor's: **when your agent commits
under its own name, on your repository, is that your contribution?** A defensible
yes and a defensible no, with different corpora on either side. Recorded and
unanswered, because guessing it would silently change forty rungs of counts —
and §6.71's whole lesson was what happens when a counting assumption goes
untested.

### 6.84 Delegation counts, and the inference I made about it was wrong — **shipped**, one fork **open**

*Ruled 2026-08-06 by the operator, closing §6.83. Two rulings: a commit their
agent makes on their repository is their contribution, and a fork holding only
delegated commits is a contribution rather than a bookmark.*

**In the operator's own repositories this required no change**, and saying so is
the point. Own repositories are read whole-tree by `extract_standard.py`, which
never filters by author — `DispatchesFromReality`'s 22 agent commits and
`quiet-corner`'s 7 have been contributing rows since the day they were read.
The question only ever bit on forks, where authorship is the filter.

**The rule, and the date that makes it decidable.** An agent commit that
*predates* the fork belonged to upstream before the operator existed in that
history; one that postdates it is on their side. Five of eight forks carrying
agent commits resolved on that alone — every one of theirs predates the fork.

| fork | was | now | delegated |
|---|---|---|---|
| Imageination | 0 commits, 0 rows | **3 commits, 4 rows** | 3 |
| redential-cli | 13 commits, 29 rows | **15 commits, 31 rows** | 2 |

`Imageination` was the corpus's only bookmark for exactly one rung. **Forty
forks read, forty contributions.**

**And I was wrong about `redential-cli`, in a way worth recording.** I proposed
its two agent commits were upstream's, reasoning that they were dated the fork
day, sat before the operator's own commits, and had subjects like *"Add
ai/mcp to taxonomy.json (1.5.1 → 1.6.0)"* — a version bump, which I called "a
maintainer's release act". The operator says they are theirs. The inference was
tidy, the evidence was real, and the conclusion was wrong, because **what a
commit looks like is not evidence of who authored it** — I was reading style and
calling it provenance. That is the fourth-key error (§6.76) in yet another
costume: a string that looked like it identified something and did not.

The corrected rule takes no view on subject matter at all. Date and identity
only.

**One fork is left open and is not being guessed at.** `litellm` holds 86
post-fork agent commits among **1,372 third-party** post-fork commits — the
signature of a repository synced from an upstream that itself uses agents
heavily. Counting them would add 86 commits of somebody else's work; not
counting them may drop a few of the operator's. Given that I have just been
wrong once by inferring from what commits *look* like, the honest move is to
leave it to the person who knows, and it stays excluded until they say
otherwise.

### 6.85 litellm dropped, and the record remembers three where the operator remembers one — **measured**

*Excluded 2026-08-06 on the operator's instruction: "I think I had one
contribution there, that never got merged." Store deleted, exclusion recorded in
`docs/corpus-order.md`.*

Dropping it also settles §6.84's open question — the 86 post-fork agent commits
are moot — and it is the cheapest possible resolution: the only person who could
adjudicate them removed the repository instead.

**The instruction's premise does not match the history, and that is the finding.**
The seven commits found under the operator's addresses sit on **three separate
branches**:

```
feat/custom-finetuned-gguf-cookbook   3 commits, 2026-04-22 to 05-21
fix/botocore-optional-import          2 commits, 2026-05-18
pr-26307                              2 commits, 2026-05-19
```

Three attempts, not one. One of them carries *"fix: address PR review feedback
on cookbook"*, so it was read by somebody before it stalled. Another carries a
merge from `upstream/main`, so it was kept current for a while.

**This is the first time in seventy-five entries that the corpus has contradicted
the operator about their own work**, and it is exactly the case the whole
exercise was built for — not a machine catching an error, but a record holding
detail a person had no reason to keep. Two of three attempts left no trace in
memory because neither landed. The one that did leave a trace is the one they
still recall.

Recorded and the exclusion stands. **The operator's instruction is not
invalidated by the finding**: dropping a repository whose contributions never
merged is a decision about what belongs in the corpus, and it survives the count
being three rather than one. It is reversible in a single command if the three
branches turn out to be worth keeping.

### 6.86 The late-July batch, and three kinds of nothing — **measured**

*Run 2026-08-06 against `oakenscrolls-office`, `safe-app-common-package`,
`terpsi-music`, `rudi193-cmd/.github`, `Forge` and `quick-stupids` (created
2026-07-23 to 08-02), rung 31.*

| repository | rows | document coverage | docstring coverage |
|---|---|---|---|
| terpsi-music | 677 | 7/55 | 637/1045 — 61% |
| oakenscrolls-office | 53 | 1/1 | 45/135 — 33% |
| safe-app-common-package | 14 | 0/1 | 14/37 — 38% |
| rudi193-cmd/.github | 0 | 0/6 | — |
| quick-stupids | 0 | 0/5 | — |
| **Forge** | 0 | 0/0 | — |

`terpsi-music` is the second-largest single-repository yield outside the willow
line, and its 61% docstring coverage is the highest measured anywhere.

**Three repositories return zero, and they are three different things.** The
corpus has been reporting `0 rows` as one outcome for thirty rungs; here the
distinction becomes unavoidable:

| | | |
|---|---|---|
| `.github` | 6 documents, none keyed | **prose** — community health files, all sentences |
| `quick-stupids` | 5 documents, none keyed | **prose** — the same |
| `Forge` | **0 documents, 0 files** | **empty** — created 2026-08-02, never populated |

`Forge`'s coverage line reads `0/0`, and that is not the same statement as
`0/6`. One says *nothing here was in a shape I could read*; the other says
*there was nothing here*. A denominator of zero is the only honest way to write
the second, and it only exists because coverage is reported as a fraction rather
than a percentage — a formatting choice made at rung 4 for a different reason
that turns out to carry the distinction for free.

**A fourth kind of nothing, from earlier, now has a name.** Rungs 9–15 reported
`0 rows` for forks with no *operator* commits — a fourth case, meaning *there was
plenty here and none of it was yours*. So `0` has meant four different things
across this exercise:

```
nothing existed          Forge
nothing was keyable      .github, quick-stupids, willow-data-vault
nothing was yours        the fork zeroes (all since corrected — §6.71)
nothing reached the store  the duplicate skills of §6.54
```

The fourth is the dangerous one, because it is the only one where the number is
wrong rather than merely terse — and it is the one that took nine rungs and a
missing `--all` to find.

### 6.87 The homestead batch, three more empty repositories, and three the session cannot read at all — **measured**, three repositories **blocked**

*Run 2026-08-06 against `homestead-law`, `homestead`, `homestead-ledger` and the
three private organisation profiles (created 2026-08-03 to 08-04), rung 32 — the
last rung of the chronology before the operator's three holds.*

| repository | rows | document coverage | docstring coverage |
|---|---|---|---|
| homestead | 361 | 1/14 | 356/522 — **68%** |
| homestead-law | 0 | 0/0 | — |
| homestead-ledger | 0 | 0/0 | — |

`homestead`'s 68% is the highest docstring coverage in the corpus, and it is the
newest substantial repository in the chronology. Whether that is a trend or the
sixteenth point in a distribution that spans 11–68% is not a question fourteen
prior withdrawals leave any appetite for answering.

**Three of the five newest repositories are empty.** `Forge` (2026-08-02),
`homestead-law` (2026-08-04 15:45) and `homestead-ledger` (2026-08-04 21:59) hold
no files at all. `homestead-ledger` was created **two minutes** after `homestead`,
which had content immediately — a name reserved beside a repository that was
being started, and not yet filled.

That is a real shape at the end of a chronology and it would be invisible in any
other view. A repository list shows six repositories in five days; the corpus
shows three repositories and three reservations. `0/0` says it, and `0/6` would
not have.

**Three repositories cannot be read in this session, and the reason is
structural.** The private organisation profiles —
`Die-Namic-Systems/.github`, `hornbook-knowledge/.github`,
`willow-memory/.github` — are refused by `add_repo`:

> *repository name ".github" begins with '.', so its clone directory would be a
> hidden path … Repositories whose names begin with '.' cannot be attached.*

Confirmed rather than assumed: a direct clone fails with
`could not read Username for 'https://github.com'` — the anonymous lane serves
public repositories, and these are private. `rudi193-cmd/.github` was readable
only because it is public.

So the chronology's coverage is **102 of 105 repositories**, with three excluded
by the operator and three unreadable by the tooling. Recorded as a gap in the
corpus rather than as an absence in the record: those three organisations have
profiles, this corpus does not know what they say, and it should not be possible
to read this file later and mistake one for the other.

### 6.88 willow-mcp: a fourth persona schema, and twenty documents that exist twice — **measured**

*Run 2026-08-06 against `rudi193-cmd/willow-mcp` (created 2026-04-18), rung 33.
Held since rung 7 as active production and read on the operator's instruction.
**Its head is dated the day of this run** — the pin records one afternoon, which
is what the hold was about and is now carried in 1,887 rows instead of avoided.*

| shape | rows |
|---|---|
| docstring | 1,537 |
| definitional tables | 296 |
| rubric | 15 |
| permission (`Tool` → required grant) | 11 |
| state · persona · boundary · intent | 10 · 6 · 6 · 6 |
| **total** | **1,887 draft, 0 sealed** |

Docstring coverage 1,537/4,332 — 35%.

**A fourth schema for describing an agent**, after three already met:

| rung | schema |
|---|---|
| 1 · SAFE | `Domain` / `Voice` / `Function` / `Direction` |
| 13 · app-store archive | `Lineage` / `Type` / `Core function` |
| 21 · willow-config | `Register` / `Mandate` / `Namespace` |
| 33 · willow-mcp | `Voice` / `Posture` / `Boundaries` |

**`Voice` is the only field present in all four**, across seven months. Everything
else was invented, used, and replaced. `Boundaries` is stored separately from the
persona for §6.74's reason — a boundary and a description fail differently.

**Twenty documents exist twice, and the counter found it.** Every shape reported
`N rows from exactly 2N adds`: persona 6/12, boundary 6/12, permission 11/22,
intent 6/12. The cause is that `skills/` and `docs/templates/` are **vendored
into `src/willow_mcp/bundle/`** so the package ships its own documentation —
20 of 126 markdown files are byte-identical pairs.

Checked rather than assumed, because the interesting failure would be a stale
copy: **every bundled copy is byte-identical to its source.** No drift. The
vendoring is currently honest.

That check exists only because §6.76 changed the load loop to print rows beside
adds. Before that change this rung would have reported 12 personas and 22
permissions — doubled counts, with nothing to indicate why — and the vendoring
would have been invisible. **A reporting fix made three rungs ago found a
structural fact about a repository it was not looking for**, which is the second
time honest counting has paid out as discovery rather than as accuracy (§6.56
was the first).

**And the vendored copies are exactly what a later drift would break.** Twenty
pairs, byte-identical today, maintained by a build step nobody re-runs by hand.
The corpus now holds both sides; a future run that reports `12 rows from 12 adds`
instead of `6 from 12` is reporting that a bundled copy has diverged, without
anyone needing to think to look.

### 6.89 yggdrasil: a corpus already in pair form, of which 29,002 rows are refused — **measured**

*Run 2026-08-06 against `rudi193-cmd/yggdrasil-training-data` (created
2026-04-15), rung 34. Private; structure and counts only. Held since rung 5 as a
data archive and read on the operator's instruction.*

**The only source in the chronology that was already a pair corpus.** Sixteen
JSONL files, 65 MB, in the shape `prompt` / `chosen` / `rejected` — this
project's own subject, in another vocabulary, four months earlier.

| | rows | verdict |
|---|---|---|
| `slm_baseline` · `slm_positive` · `slm_voice` · `slm_negative` | 28,432 | harvested from `SESSION_*` transcripts — **refused** |
| `sft_v8` (`llm_generated`) · `slm_refusal` | 566 | model-generated — **refused** |
| `slm_governance` (48) · `sft_v8` (`handcrafted`, 50) | 98 | **taken** |
| `corrections/` | 32 | **taken** |
| **total** | **137 rows, 29,002 refused** | |

**The refusal is the finding.** Those 28,432 rows are instruction/response pairs
whose *response* side is an assistant's output, captured from conversations.
Importing them would file model output under this operator's name — and at 60% of
the entire corpus it would be §6.59's error (a population that looks like the
author's and is not) at the largest scale available anywhere in these 105
repositories. They are counted, printed by source, and declined.

**A label lied, and both fields had to agree.** The first run took 176 authored
rows. Seventy-eight of them came from `slm_refusal.jsonl`, which marks its rows
`source_type: governance` while their `source` field reads
`refusal-synthetic-77HE`. Synthetic rows wearing an authored type. Taking the
type at its word would have imported 78 generated rows as the operator's
writing — **the fifth time in this exercise that a string which looked like it
identified something did not** (§6.52, §6.57, §6.65, §6.76, and now a metadata
field contradicting its neighbour). The fix is the same shape every time: require
a second field to agree, and never let one string carry identity alone.

**The 32 corrections are the most on-subject material in the whole chronology.**
Each is a human correcting an agent mid-session: the prompt, what the agent
should have said, what it did say, an error type (`ambiguous`,
`drift_from_mandate`), and `correction_absorbed` recording whether the agent took
it. That is the entire premise of this product, captured live, by the operator,
before this product existed.

**And 880 recorded rejections are deliberately not imported as rejections.**
`dpo_pairs.jsonl` and `corrections/` carry a `rejected` field — real answers a
real person turned down. Nestor has verbs for precisely that, and `CLAUDE.md`
reserves them for a human's no. The operator made those decisions; writing them
into a store is nonetheless an act, and it is theirs. Every row lands as a
**draft**, with the rejected text and error type preserved in `reason` where a
curator can see them. Promoting them is a question for `nestor.ui`.

That is the covenant doing real work rather than being quoted: the one rung where
the machine had, in hand, 880 human decisions it could have written down as
decisions, and did not.

### 6.90 sean-data-vault, under an allowlist — and the chronology closes at 100 of 105 — **measured**

*Run 2026-08-06 against `rudi193-cmd/sean-data-vault` (created 2026-05-25),
rung 35, the last. A 2.4 GB personal archive, and the only rung read under an
allowlist.*

**The operator's premise was that it would be mostly duplicate. It is not.**

```
vault markdown files                      151
byte-identical to something already read   29   (19%)
found nowhere else in the corpus          122   (81%)
```

The duplication is real and it is in the 2.4 GB of Postgres dumps, Google Drive
legacy and repository extras — not in the prose. So the question was never
duplication; it was **category**. Every other rung extracted things the operator
*declared*. This one holds things they *accumulated*: PDFs, images, Windows
backups, a legacy Drive export.

That is a judgement about someone's material, not about data, so it went to
them. Taken: `personal-research`, `professional`, `willow-store`, `experiments`,
`github-repo-extras`, `made-by-willow`. Left out and named rather than dropped:
`provided-by-sean/stories`, `claude-code-sessions` (transcripts, declined for
the same reason 28,432 were at rung 34), and every binary.

| shape | rows |
|---|---|
| definitional tables | 135 |
| docstring | 15 |
| constraint | 5 |
| **total** | **155 draft, 0 sealed** |

632 rows under 116 headers declined and printed. The 29 known duplicates are
kept, not filtered — they surface in `compare.py` as `restated`, which is what
an archive is *for*.

### 6.91 The log, fed to the thing it is about — 119 claims, and a status the legend defines and nobody has ever used — **measured**

*Run 2026-08-07 with `scripts/corpus/extract_ideas.py` over `IDEAS.md` at two
refs — `origin/master` (`4f9b1f7`) and the corpus stack's tip (`e2632be`) —
into a fresh store, `data/corpus/ideas.db`. Not a repository rung: the
operator's instruction was "the whole log, and a fresh one."*

**Why by hand.** §6.82 measured this file at four rows from 3,891 lines. The
corpus cannot read its own findings, because they are prose and every shape the
extractor knows requires a declared structure. So this extractor takes the one
structure `IDEAS.md` really does declare — the `### N.N Claim — **status**`
heading — and lifts four fields without interpreting any of them: the heading is
the claim, the bolded status words are the verdict, the italic line each entry
opens with is the reason, and the number goes in `origin`.

Pulling the *argument* out of an entry's body would mean deciding what the prose
meant, which is the line all thirty-five rungs refused to cross.

```
187 headings across two refs  ->  119 rows, 0 collisions
  shared by both refs   68   (§1–§5's 29, plus §6.1–§6.39)
  master only           10
  stack only            41
```

**The 68 are the branch point, measured rather than assumed** — and not one of
them collided, so no shared entry was silently edited on either side while the
stack ran.

**The key is the claim, never the number.** At the time of the run, ten numbers
— the ten now holding §6.40 through §6.49 above — held two different findings
each: master kept writing entries while this stack wrote its own, and neither
could see the other. That is §6.76's lesson at the scale of a file. The claims
never conflicted; only the labels did, which is why the store reports the
collision as a fact rather than resolving it.

**Corrected 2026-08-07, after the operator's decision to put this on master.**
The paragraph above originally ended *"the reason the collision is reported here
rather than resolved by renumbering"* — and then it was resolved by renumbering,
because master's ten are merged and this stack's are not. Entries 6.40–6.81
shifted to **6.50–6.91**; 138 cross-references in this file and 27 in eleven
extractor docstrings moved with them. The claim that the collision did not need
resolving lasted one instruction.

Re-run after the shift, as a check on it: **0 numbers used twice**, and the same
68 claims still shared between the two refs — so the renumbering moved headings
and altered no heading text.

What survives the shift is the point the entry was making. The 119 rows are
keyed on the claim, so not one of them moved; their `origin` still reads
`6.61@e2632be`, and that is still true, because a number pinned to a commit
names a slot that existed. A number pinned to nothing would now be a lie in 41
rows.

**What the store found that reading top to bottom does not.** With the verdicts
in a column instead of scattered across the 6,011 lines the run read:

| status | entries | in the legend? |
|---|---|---|
| measured | 62 | yes |
| shipped | 48 | yes |
| open | 27 | yes |
| *no status at all* | 9 | — |
| verified | 2 | yes |
| **partly** | 2 | **no** |
| **blocked** | 1 | **no** |
| **hypothesis** | **0** | **yes — with a definition** |

`hypothesis` is defined at line 12 — *"Plausible, untested — do not cite as
fact"* — used seven times in prose, and has never once tagged an entry. The
status the vocabulary exists to isolate is the status nothing is ever filed
under, while two statuses it does not offer carry three entries. All nine
untagged entries are in §1–§5, which predate §6's tagging rule; §6 is 80 for 80.
The rule holds exactly where it was declared and the vocabulary it declares is
not the one in use.

**The caveat, which is not small.** This is the one rung where the extractor
reads its own author's output — "checked, not assumed" has no independent check
here, and a claim of mine that was wrong arrives in the store still wearing the
verdict I gave it. Several entries above are corrections of earlier ones
(§6.71, §6.76, §6.69); the withdrawn versions are in this store too, as drafts,
which is the only reason that is safe. Sealing one would put a known-false claim
in the memory permanently. 119 draft, 0 sealed.

---

## The chronology, closed

| | |
|---|---|
| repositories in the list | **105** |
| read | **100** |
| excluded by the operator | 2 — `mealie`, `litellm` |
| unreadable by the tooling | 3 — the private org `.github` profiles (§6.87) |
| **rows** | **18,924 across 99 stores** |
| **sealed** | **0** |

```
keys in more than one repository: 2,427
  drift 336 · two kinds 149 · restated 2,088
```

**Zero sealed rows, after thirty-five rungs.** Not one row in eighteen thousand
claims a human checked it, because not one has. The queue at `nestor.ui` is
where that changes, and it has never been opened. That is the covenant surviving
contact with a corpus large enough to make breaking it convenient — including at
rung 34, where 880 of the operator's own recorded rejections were held as drafts
rather than written down as decisions.

**What the exercise actually produced.** Not a memory of what the operator knows
— §6.82 measured that against the one repository where both sides could be
inspected and found roughly 1 row per 700 lines of prose against 1 per 2 lines
of code. What it produced is a record of *what was written in a shape a machine
could key on*, plus a list of the ways a machine gets that wrong:

- five strings that looked like identifiers and were not (§6.52, §6.57, §6.65, §6.76, §6.89)
- one flag that turned eleven contributions into zeroes (§6.71)
- one limitation named and left untested for four rungs (§6.61 → §6.71)
- three quantities asserted from too few points and withdrawn (§6.58 → §6.69)
- one counter that reported adds as rows for twenty rungs (§6.76)

Every one was found by a mechanism built to report what it refused, rather than
by anybody being careful.

---

### 6.92 Three findings from the §6.40/§6.41 audits that were deferred, and were living only in merged-PR prose — **measured**, fix **shipped**

*Recorded 2026-08-07 at the end of the session that produced them. Each was
found by an adversarial audit of PR #60 or #61, judged out of scope for the PR
in hand, and written into that PR's "Out of scope" section. That is the wrong
place: a merged pull request is not where this repo keeps its queue, and none of
the three appeared in `IDEAS.md`, `TODO.md` or `QUESTIONS.md`. Filing them here
is the whole of this entry — the analysis below is the auditors', reproduced so
it survives the branch.*

**1. The portable bundle carries a domain's tags and not its matcher. — shipped**

`portable.import_bundle` trusts `row["source_norm"]` from the file and never
renormalizes, which is **correct and must stay**: `signing.seal_is_valid`
verifies against that norm, so recomputing it would invalidate every seal
signature in transit. The gap is that nothing recorded or checked *which* matcher
produced those norms. `export_bundle` filtered on `source_lang`/`target_lang`
only, `PAIR_FIELDS` has no matcher field, and `verify_bundle` requires
`source_norm` without any provenance for it.

So importing a `StringMatcher` bundle into a `SerialMatcher` domain with matching
tags landed rows in a key space the destination will never compute, and reported
`{"sealed": n}` with no warning — §6.40's symptom arriving through `/api/import`.
This PR pair's own thesis is that *a domain is its tags **and** its matcher*; the
portable format still modelled a domain as its tags alone.

Shipped as the entry framed it — a warning, not a refusal. `export_bundle`
records a bundle-level `matcher` label from `matcher_audit_fields`; `import_bundle`
compares it against the destination's matcher and, on a mismatch, warns and
records `matcher_mismatch`/`source_matcher`/`dest_matcher` in the report (a field,
not only a warning — Python dedupes warnings by code location and an HTTP caller
reading JSON never sees one, the same reasoning `partial_pairs` follows). It can
only ever be a warning — the field is explicitly not a stable identifier, so it
cannot bear a refusal, and two agreeing matchers that were renamed will trip it
— but a warning beats silence. The label lives in the envelope and **not the
digest**, for the same reason: an integrity check cannot rest on an unstable
label. Regressions in `tests/test_findings_2026_08_07_deferred.py`; the decision
is `docs/dogfood/decisions/0073-a-bundle-carries-its-matcher-label.json`.

*Wiring correction (same day, from an adversarial audit of the fix's own
commit).* The first version threaded `_domain_matcher` on the UI **export** path
and left the CLI on the bare process default, and both mislabelled: the "Export
bundle" button sends no tags, so `_domain_matcher("","")` returned `None` and
relabelled a custom surface's own rows with the process default — the mislabel
this finding closes, on the export side — and `nestor export`/`import` had no
`--matcher` at all. Fixed: `ui._bundle` labels an unscoped whole-store export
with `app.matcher` (scoped requests still route through `_domain_matcher`, so the
§6.40 guard holds), and the CLI grows `--matcher` on both subcommands
(`answer.load_matcher`, default unchanged). The new tests drive the button and
the CLI directly, because the original four exercised `export_bundle`/
`import_bundle` with an explicit `matcher=` and so gated the mechanism but never
the wiring. Decision `0075`. Residual: a multi-domain store behind a
single-domain surface still cannot carry one label — the envelope field is
singular — which is left open.

**2. `_domain_matcher` compares domain tags with exact string equality. — shipped**

`ui._domain_matcher` and `serve.Server.domain_matcher` both decide "is this
request about my domain?" with `==`. A caller sending `Incident` against a
surface configured `incident` falls back to the process-wide matcher and answers
`pending` rather than refusing — the §6.40 failure, reachable by a capitalisation
typo, and silent in the same way.

Not obviously a bug fix: case-folding tags is a behaviour change with its own
consequences for a store that may hold two domains differing only in case. The
alternative is to refuse a near-miss rather than fall back. Either is better than
the current silence, and neither is free.

Shipped the second alternative, not the first. Case-folding the tags stayed off
the table for the reason above: two domains in one store differing only by case
are a real possibility this entry cannot rule out, and folding would silently
merge them into one key space, which is the exact failure shape this whole §6
is about, one level up. Instead `_domain_matcher`/`domain_matcher` gained one
more branch, ahead of the existing fall-through: tags equal to the surface's own
under `.casefold()` but not exactly equal — both tags, not just one, because a
request that agrees on one tag and genuinely differs on the other is a different
domain, not a typo of this one — now raise rather than return `None`. `ui.py`
raises `ApiError(400, ..., code="domain_case_mismatch")`, caught by `dispatch`'s
existing handler exactly like every other refusal (a `ConflictingSealError`, an
unknown pair), so it reaches the browser as a 400 with a message and never as a
traceback. `serve.py` raises `ValueError`, mirroring `_resolve_matcher`'s own
refusal on the same class of mistake; `Server.handle`'s `tools/call` branch
already catches `(ValueError, PermissionError, RuntimeError)` and turns it into
an `isError` tool result a model can read, rather than a JSON-RPC protocol
error. Both messages name the tags received and the surface's real domain —
"differs from 'incident'/'incident' only in case. Did you mean...?" — so the
refusal is actionable rather than just a stop.

The exact-match and genuinely-different-domain paths are unchanged: an exact
match still returns the surface's own matcher, and a real other domain (one tag
not even case-insensitively equal) still returns `None` and defers to the
process-wide matcher, which is the §6.40 guard this fix must not break. Every
call site threads the matcher as a call argument evaluated before the write it
guards runs (`memory.add_pair`, `memory.reject_match`, `cascade.
graduate_segment`, `cascade.reject_segment`), so a near-miss reject or seal
raises before anything lands in the store — confirmed for `/api/seal` and
`/api/reject-match` directly, not just inferred from argument order. Regressions
in `tests/test_findings_2026_08_07_deferred.py`, run against the unfixed
revision first and observed to fail (a near-miss returned 200 / did not raise);
decision `0076`.

*Residual, filed by an audit rather than left silent.* The refusal sits behind
the pre-existing `if app.matcher is None: return None`, so it fires only on a
surface that has its own matcher. A **default** surface (`matcher=None`, ordinary
translation) still answers `pending` for the same case-only tag typo, because the
store keys on the *exact* domain tag (`sqlite_store` `source_lang=?`) and a
mis-cased tag misses regardless of matcher. That is scoped correctly to the §6.40
failure — which needs a custom matcher to occur at all — but it leaves the same
typo refused on a custom surface and silent on a default one, a consistency seam
worth naming. Widening (moving the near-miss check ahead of the `matcher is None`
return so it refuses everywhere) was declined: it changes behaviour for every
default deployment, and the miss it would close is the exact-tag store key, which
is a decision about tag identity, not this per-request guard. See decision `0076`.

**3. `memory.add_pair`'s race retry drops `reason=`. — shipped**

At `memory.py:475-480`, the retry taken when a concurrent insert wins the race
re-called itself without forwarding `reason`, so a seal that lost that race
silently lost its recorded rationale and skipped the `memory_set_reason` refusal
path. Pre-existing and unrelated to the matcher work; noticed while reading that
function because the §6.40 fix now depends on it forwarding `matcher=`, which it
does correctly.

Fixed by adding `reason=reason` to the retry call. The regression is in
`tests/test_findings_2026_08_07_deferred.py`: the race is made deterministic by
lying to the first `memory_find` so the seal takes the insert path and collides
with a draft already in the store — the exact window the retry exists for. On
retry it upgrades that draft to a seal, and its `reason` must ride along. The
test was run against the unfixed revision first and observed to fail (the sealed
row came back with an empty `reason`). All three findings have since shipped —
this one was the clean bug fix; 1 and 2 each carried a design choice this entry
declined to make on 2026-08-07 and resolved later (decisions 0073/0075 and
0076).

---

**Why this entry exists at all, which is the part worth keeping.** Both audits
were run deliberately and both found real defects; the failure was afterwards.
"Out of scope" written in a PR body reads like a decision and behaves like a
deletion — the PR merges, the prose stops being anybody's inbox, and the finding
is gone from every surface a future session would search. The rule that follows:
a finding deferred is a finding filed, in the queue this repo actually keeps, in
the same change that defers it.

### 6.93 The browser signer, and a same-day bug it was possible to write while wiring it — **shipped**

*Proposed and implemented 2026-08-09, closing Nestor#17's last cell (decisions `0074`, `0077`, `0078`).*

`nestor/ui_page.py` gained a third "acting as" mode: WebCrypto Ed25519,
generated non-extractable directly in the browser (or imported, as raw
32-byte hex, for a key minted elsewhere — a verifier's own migration path off
a server-held key), persisted in IndexedDB or held only for the tab, enrolled
by printing `nestor keys add NAME --type ed25519 --public HEX` for a human to
run out of band. Sealing reconstructs the frozen `signing._message` in
JavaScript from three human-approved values — target and verifier as shown on
screen, and `source_norm` from a new read-only `/api/normalize` endpoint,
DISPLAYED in a confirm dialog before signing rather than trusted blindly —
and signs client-side. `tests/test_client_signed_seals_browser.py` proves it
against a real Chromium tab (Playwright, `PLAYWRIGHT_BROWSERS_PATH`
preconfigured, no `playwright install`): generate in-browser, enroll the
exported public key exactly as printed, drive a real seal through the Ask
view, and check the recorded row with `signing.seal_is_valid` — the actual
verification function, not a special-cased one.

**The JS/Python byte-encoding question, checked rather than assumed.**
`JSON.stringify` is not relied on for the signed message: `pyJsonString` hand-
encodes each string the way `json.dumps(..., separators=(",",":"),
ensure_ascii=False)` does, verified side by side against live CPython 3.11
and this Chromium build (six cases: ASCII, non-ASCII, an embedded quote, raw
control bytes 0x00/0x1f/0x7f, a backslash, a non-BMP emoji — matching strings
AND matching UTF-8 bytes in every case) before being relied on. The one case
that cannot agree — an unpaired UTF-16 surrogate, which Python's
`str.encode("utf-8")` refuses outright but `TextEncoder` silently mangles to
U+FFFD — is detected and refused client-side with a clear message rather than
silently signing bytes Python could never have produced from the same string.

**A privilege-escalation bug, introduced and caught in the same session.**
Wiring `_verifier_for_seal` (the session bypass a valid `seal_sig` earns) into
`/api/queue/seal` at first resolved the verifier ONCE, before the endpoint's
two branches split — but only the EDITED branch forwards `seal_sig` to
`memory.add_pair`; the as-drafted branch calls `cascade.graduate_segment`,
which signs SERVER-SIDE and checks no signature at all. The result, verified
directly against that code before fixing it: `POST /api/queue/seal` with
`verifier="sam"` (an ordinary HMAC keyring entry) and ANY non-empty
`seal_sig` — a random Ed25519 keypair signing the literal bytes
`b"anything"`, nothing to do with sam, the segment, or the wire contract at
all — returned 200 and a genuinely, validly sealed row attributed to sam,
server-signed with his real key, with no session ever presented. A full
authentication bypass for every HMAC or private-half verifier in the
keyring, from an endpoint that looks, on a shallow read, like it already
checks a signature. Fixed by resolving the verifier PER BRANCH — `_verifier`
(session required) for the as-drafted path, `_verifier_for_seal` only where
the signature is actually forwarded and checked — and pinned by
`tests/test_client_signed_seals_ui.py::test_queue_seal_as_drafted_still_needs_a_session_not_a_signature`,
run against the vulnerable code first and confirmed to return 200 (forged
seal accepted) before the fix, 401 after. Exactly the shape
`docs/agent-guide.md` names: a condition checked in one place, a write it
does not actually guard reachable from another branch of the same function.

Scope stays exactly decision `0077`'s: `/api/seal`, `/api/seal-draft`, and
the edited path of `/api/queue/seal`. A browser-key-only verifier cannot
unseal, reject, restore, or seal an entity/numeric answer from this UI — those
endpoints have no signature to authenticate against, and a session remains
the only proof available for them. Stated in the page's own copy, not
implied to be closed.

### 6.94 The decision store answers its own questions well, except where its matcher cannot tell two decisions apart — **measured**, fix **open**

*Measured 2026-08-09 by `demo/the_dogfooding.py`; decision `0079`.*

Pointing the retrieval question at Nestor's own decision memory — every row
in `docs/dogfood/decisions/`, asked back — measured three ways on this
checkout (a 216-decision corpus), each a `claim()` the demo fails the build
on. The demo re-measures live, so the corpus-size counts grow with the store;
the shapes below are what hold:

- **Verbatim:** every decision queried in the words it was sealed under is
  served back. 216/216, 0 wrong. The floor holds.
- **Paraphrased:** ten short reworded queries — a person asking the gist
  months later — return **2 served, 8 pending, 0 wrong**. Most come back
  pending because nothing sealed matched closely enough to clear the 0.92
  bar. That is the threshold refusing to serve a decision it is not sure it
  was asked, not the memory failing.
- **Authoring-free sweep:** every multi-sentence question queried by its
  first sentence alone — 50 of them — returns **4 served, 46 pending, 0
  wrong**. Recall falls off a cliff as the question is compressed, and it
  falls toward *pending*, never toward *wrong*.

So the store holds everything it was told, refuses most of what it is not
asked in the same words, and — with one measured exception — never serves
the wrong decision.

**The exception, and the open question.** `scripts/dogfood_store.py` keys the
decision store with the default `StringMatcher` (character difflib). Decision
text is prose *about* code, which is the population `recipes/patch_review.py`
built `DefectMatcher` for. Measured: StringMatcher admits **two serve-bar
collisions** — `docs/dogfood/decisions/0051` and `0053`, whose questions
differ by one word ("The **new** gap assertions pass" vs "The **eight** gap
assertions pass") but carry different committed answers, scored **0.94** — so
asking one would serve the other's answer as verified. `DefectMatcher`
separates them (zero collisions). But it is **not a free win**: its
identifier-weighted keying lowers paraphrase recall (2/10 → 1/10), and the
shipped `SEAL_THRESHOLD` of 0.92 was calibrated for StringMatcher, not for a
`score()`-based matcher (`nestor.memory` warns exactly this; the demo catches
and narrates the warning). The choice is fewer-wrong-serves **or** more
recall, and neither at the shipped bar without a per-matcher `nestor
calibrate` run.

**Open** because a machine may propose and may not confirm: the finding is
filed as a draft on the review desk by the demo, re-measured on every run,
for a human to weigh the three real options — the identifier-weighted matcher
(fewer wrong serves, no better recall), semantic embeddings via the
`[semantic]` extra (recall, at a dependency), or shorter canonical questions
(recall, by hand).

### 6.95 `nestor calibrate` warns about a too-small corpus in the README's prose, not in the output a parser reads — **measured**, fix **shipped**

*Measured 2026-08-10 during the documentation refresh (`FINDINGS-2026-08-10-docs-refresh.md`).*

Against a one-pair memory, `nestor calibrate --from en --to es --target 0.01`
prints `threshold 0.80 — 0 collisions — 0.00% ←recommended`: fewer pairs means
fewer collisions, so the *lowest* swept cutoff clears any target, and the
command recommends it in a machine-parseable line. The README now documents the
caveat — "a small memory recommends low, and means nothing by it … treat a
recommendation from a few dozen pairs as noise" — and the *applying* half
(`seal_threshold=` per call, or rebinding `memory.SEAL_THRESHOLD`) shipped. What
did not ship is any floor in the **command's own output**: `grep` of
`calibrate.py` for a corpus-size guard finds only threshold-floor references, no
`sampled < N` minimum.

**Where it bites:** an agent automating setup runs `calibrate` early — memory
smallest, recommendation cheapest — parses `←recommended 0.80`, and sets the
serving threshold below default with measured-looking justification. It read the
output, not the prose two sections away. This is `FINDINGS-2026-08-05` §7,
half-closed: the honesty is now in the docs but not where the parser looks.

**Open, and deliberately not fixed in the docs pass that found it.** The fix is
a change to `calibrate.py`'s output — one line when `sampled` is below a floor
(a few dozen), *"N pairs is below what this measure stabilizes on; treat this as
noise"* — which is a product change that carries its own test, run against the
unfixed revision, not a sentence in the README. Filed here so it is not lost;
`docs/agent-guide.md` says a follow-up not written down did not happen.

**Shipped 2026-08-10 (same PR, once the operator asked for the code change).**
`STABLE_SAMPLE_FLOOR = 30` in `nestor.calibrate`; `calibrate()` returns
`stable`/`sample_floor`, and `summarize()` — where a parser reads — annotates the
recommendation as `←recommended (unstable — too few pairs)` and prints an `!`
caution line whenever `sampled` is below the floor. Deliberately narrow: the
number itself is unchanged (a caller may still want it), only the honesty around
it moved to where the output is read. `tests/test_calibrate.py` proves the split
— both new tests fail on the unfixed revision (no `STABLE_SAMPLE_FLOOR`, no
caution) — and the claim is about the *rule*, so the stable-corpus test confirms
the caution vanishes once there are enough pairs. Decision `0080`.

### 6.96 Local Ollama embeddings as a shipped matcher (`--matcher ollama`) — **shipped**

*Shipped 2026-08-10.* The fleet already runs `nomic-embed-text` under Ollama
(`willow-mcp` nest embed). Nestor's `semantic` path required `fastembed` and a
HuggingFace model download — a different dependency shape from "daemon already
on loopback." Added `nestor.ollama_embed` (stdlib `/api/embeddings`) and the
shipped name `ollama` via `SemanticMatcher(backend="ollama")`. Embedding cache
stays keyed by `model_name`, so nomic vectors never collide with
`BAAI/bge-small-en-v1.5`. Document prefixes only (symmetric `score` / `scores_against`).
Default `SEAL_THRESHOLD` is still character-ratio space — calibrate before serving.

### 6.97 `detailPanel` renders two literal `null` text nodes into the provenance card — **verified**, fix **open**

*Found 2026-08-12, by standing the UI up and looking at it.* The Provenance card
in `nestor.ui` shows the string `nullnull` between the answer and the chip row,
on ordinary rows.

`h()` is careful about this — `ui_page.py:534` skips a child that is `null`,
`undefined` or `false`, which is why the chip row's `p.status === "sealed" ? … :
null` leaves no trace. `detailPanel` then builds its card with the **native**
`card.append(...)`, which does not skip: DOM `append()` stringifies `null` to a
text node. Two of its arguments return null for an ordinary row —
`commitmentPanel(p)`, and the `(p.reason || origin.startsWith("willow:gap")) ? …
: null` context panel — so the two land adjacent and read as one word.

Verified in a real Chromium against a live server rather than by reading:
querying the card's direct child text nodes returns `['null', 'null']`. It needs
a row with no commitment choices and no reason, which is what an imported bundle
produces — 221 of 221 rows in the dogfood store show it.

Two shapes of fix, and they are not equal. Filtering at each call site is the
one that will regress: the same mixed idiom (`h()` for some children, native
`append` for others) is used in several panels, so the next null-returning
helper reintroduces it. The mechanism-level fix is to stop having two append
paths with different null semantics — route card assembly through the helper
that already has the rule. This is `docs/agent-guide.md`'s "when a guard fails,
remove the interaction — do not add a condition", and the guard here is `h()`'s
line 534 being bypassed rather than being wrong.

### 6.98 `bench/` and `scripts/audit_*.py` inherit the ambient keyring, and report a false `FAILS` — **measured**, fix **open**

*Found 2026-08-12, while standing up an instance with per-verifier keys on.*
With `NESTOR_KEYRING` exported — which is the correct configuration for a real
deployment — `scripts/audit_against_constitution.py --repo <charter>` reports
**2 failing**. With it unset, the same command on the same tree reports
**0 failing**. Both numbers were run; the second is the true one.

The probes seal under synthetic verifiers (`someone` in the constitution audit,
`bench` in `bench_accuracy.py`) that are deliberately not people and so are
deliberately not in anybody's keyring. `keyring.signing_entry` raises
`UnknownVerifierError`, the probe catches its own failure, and the harness
reports the clause as failing. The failure is real and it is the harness's, not
the clause's — but the verdict does not distinguish those, so an operator
running the audit the documented way is told the constitution fails.

This is a shape the repo already refuses elsewhere. `scripts/dogfood_store.py`
has a gate for exactly it — `test_dogfood_store.py` installs a poisoned ambient
store and proves none of it reaches the build, because "a memory whose rows came
from somewhere nobody can see is not an audit trail". A measurement harness that
reads ambient config is the same defect one layer over, and these two have no
such guard.

The fix is isolation, not a caveat in the docs: a harness that seals under a
synthetic verifier should build its own keyring in its own temp root and ignore
`NESTOR_KEYRING`, the way it already ignores the ambient store. Failing that,
the probe should distinguish "the clause failed" from "the probe could not run"
— they are printed identically today, and only one of them is about the subject.
`docs/local-fleet.md` carries the workaround until one of those lands.

**A second false verdict, found later, and the reason it was still standing.**
The session that recorded this entry re-ran the *constitution* audit clean and
corrected it from 2 failing to 0. It did not re-run `audit_against_jeles.py`,
which had been run in the same shell, under the same exported keyring, and had
reported:

```
FAILS  JELES-INDEPENDENCE          2 satisfied · 2 differently · 1 failing
```

Re-run with the keyring unset, that clause reads **`differently`**, and the
audit reads **0 failing**. So a second cross-repository verdict — that jeles
fails an independence clause — was published from a false positive and left
uncorrected through several rounds, in the same session that had already
diagnosed the cause.

That is the part worth generalising past this defect. Finding an environmental
fault that falsifies a result creates an obligation to **re-run everything that
ran under it**, not only the case that surfaced it. The instinct is to fix the
example in front of you, and the example is the one you already know about.
Nothing here flagged the second audit: it had completed, exit 0, with a verdict
formatted exactly like a true one.

### 6.99 An LLM standing in for the embedder is self-consistent inside a conversation and drifts between them — **measured**, fix **open**

*Measured 2026-08-12, because both real backends were unreachable.* `[semantic]`
needs weights from `huggingface.co` and the `ollama` backend needs a daemon from
`ollama.com`; egress policy denies both, so the semantic seam could not be
exercised in this container at all. A small model was stood up as a scoring
service in place of the embedder — not producing vectors, but answering the
`score(raw_a, raw_b) -> float` half of the Matcher seam directly.

**What it buys, and the number is large.** Asking for `willow-gate` and reaching
its own one-line description scores **0.098** under `StringMatcher` — invisible,
below every threshold, unreachable by character ratio — and **0.900** under the
stand-in. The inverse holds too: `homestead-law` against `homestead-ledger`
scores **0.741** on characters, the highest non-identical score in the sample,
and drops to 0.600 on meaning. That pair of failures is the whole argument for a
semantic matcher in this store, and neither was measurable here until now.

**What it is not is deterministic, and the first measurement said it was.** The
agent re-scored four pairs and reproduced all four exactly — same floats, same
note strings verbatim. That looked like a stable function and was not: it had
been resumed from its own transcript and could read its previous answers. A
fresh instantiation of the identical protocol moved every non-identical pair:

| pair | recalled | fresh | drift |
|---|---|---|---|
| `willow-gate` / `willow-config` | 0.500 | 0.450 | −0.050 |
| `homestead-law` / `homestead-ledger` | 0.600 | 0.550 | −0.050 |
| `quiet-corner` / `quick-stupids` | 0.175 | 0.150 | −0.025 |
| store brief / kartikeya brief | 0.475 | 0.400 | −0.075 |

Mean absolute drift 0.050, max 0.075, and **every one moved down** — a bias
between instantiations rather than noise around a value. Two invariants
survived: identical strings return exactly 1.000 in both, and a deliberate
contradiction in the rubric reproduced identically in both, which is what
identifies it as a prompt defect rather than agent drift.

> **Amended after a third instantiation (2026-08-12, same session).** Two of the
> three claims in the paragraph above are wrong, and both were wrong because they
> were drawn from n=2.
>
> | pair | recalled ×3 | fresh #1 | fresh #2 | spread |
> |---|---|---|---|---|
> | `willow-gate` / `willow-config` | 0.500 | 0.450 | 0.300 | 0.200 |
> | `homestead-law` / `homestead-ledger` | 0.600 | 0.550 | 0.300 | **0.300** |
> | `quiet-corner` / `quick-stupids` | 0.175 | 0.150 | 0.150 | 0.025 |
> | store brief / kartikeya brief | 0.475 | 0.400 | 0.450 | 0.075 |
>
> - **"Every one moved down" is false.** The store/kartikeya pair moved *up* in
>   the third run. It is dispersion, not bias, and "bias rather than noise" was
>   the more interesting of the two readings, which is presumably why it got
>   written.
> - **The spread is 3–4× larger than reported.** Mean 0.150 against 0.050, max
>   0.300 against 0.075. One more sample quadrupled the measured instability, so
>   the original figures were not a measurement with error bars, they were the
>   smallest number two points can produce.
> - **The rubric contradiction does not reproduce.** Fresh #2 scored both
>   look-alike pairs at 0.300 — *obeying* the ≤0.35 clause the other two
>   instantiations ignored, with notes reading "Shared prefix, different
>   concepts". The diagnosis (the rubric contradicts itself) survives; the
>   evidence offered for it does not. Two runs agreeing was reported as
>   reproduction, and the third picked the other clause.
>
> What holds unchanged across all five passes: **identical strings return exactly
> 1.000**, and **recall is exact** — the resumed agent returned the same floats
> and the same note strings three times over many intervening turns.
>
> The consequence stated below needs restating with the real number. At a 0.92
> threshold, a spread of 0.300 exposes roughly **0.62–1.00**, not 0.85–0.99 —
> which is most of the range where a semantic matcher would ever be asked to
> decide anything.

**The consequence is in `embedding_store.py`.** The cache keys vectors by
`model_name`, and a key is a promise that the function behind it is fixed. Keyed
to a model that is re-instantiated per call, a cache hit and a fresh call are not
interchangeable, and the row that was cached is not the row a re-run produces.
Nothing here flips a seal at the shipped 0.92 — all observed drift is far below
it — but a pair scoring inside roughly 0.85–0.99 could land on either side
depending on which instantiation scored it. Six pairs is too few to put a rate
on that, and saying which pairs sit in that band needs a corpus, not a sample.

The honest reading is that this is a **measuring instrument, not a backend**: it
makes the seam's value visible where nothing else could, and it must not key a
cache or key a seal.

### 6.100 One gate for every change class, and what that costs a session with a human waiting in it — **measured**, fix **open**

*Observed 2026-08-12, from the outside.* `AGENTS.md` prescribes one verification
step and prescribes it unconditionally: `bash scripts/ci-lint.sh` and `python -m
pytest -q` before you push. That is correct for a change to `nestor/`, and it is
the only instruction offered, so a change touching nothing but `IDEAS.md` and
`docs/dogfood/decisions/*.json` pays the identical price.

Measured on this tree today:

| gate | scope | cost |
|---|---|---|
| `python -m pytest -q` | 979 tests | 96.6–107.3s across four runs |
| `test_docs` + `test_open_findings` + `test_dogfood_store` | 46 tests | 7.2s (16.0s wall) |
| `dogfood_store.py --verify` | the digest gate | 0.6s |

Those 46 are the tests a documentation or decision-file change can actually
break — the README layout gates, the IDEAS status gate, and the store's own
rebuild check. Nothing else in the suite reads those files. Three full runs were
spent today on changes of exactly that shape, which is roughly five minutes
bought nothing.

**The second cost is the one that does not show up in a timing table.** In an
interactive session the gate is not a background job; it is a wall between the
operator's last instruction and their next one. A session running an ordered
sequence of small steps pays it *per step*, and the agent — which experiences no
duration — will keep choosing the maximal gate because the guidance says to and
because it is never the party waiting. The operator here named it directly, and
the agent had not noticed across four consecutive rounds of doing it.

Both halves are the same defect: **the guidance names one gate and no change
classes**, so there is no way to be correct and cheap at once, and the failure
mode is silent because over-verifying always passes.

What a fix looks like, none of it written: a change-class table in `AGENTS.md`
mapping touched paths to the gate they owe; a `scripts/ci-lint.sh` sibling that
runs the docs subset; and, for the interactive case, the standing default that
anything over ~10s goes to the background rather than in front of the next
prompt. The last one is a working agreement rather than code, which is exactly
why it belongs written down where the next session reads it — nothing enforces
it, and the agent that just learned it will not be the agent in the room.

### 6.101 The corpus extractors do not fail closed, and the test named for them covers a different family — **verified**, fix **open**

*Found 2026-08-12, by running all seventeen of them for the first time in one
session.* Point any `scripts/corpus/extract_*.py` at a repository that does not
exist and it reports:

```
  0 pair(s): 0 draft, 0 sealed
  store: /tmp/…db
```

and exits **0**. That is byte-identical to what it prints for a checkout that is
present and declares nothing. Seven of the eight extractors aimed at absent
checkouts behaved this way; the eighth (`extract_fork.py`) exited 2 on a missing
`--name`, which is argparse refusing an argument rather than the reader refusing
a corpus.

**This exact defect was already found, argued and fixed one directory up.**
`scripts/feed_jeles_sources.py` carries the fix in its docstring — an unreadable
registry and an empty one used to print the same words — and
`scripts/feed_all.py` exists to keep the distinction across several feeds at
once, stating it plainly: *"nothing matched and I could not look are different
sentences."* `tests/test_corpus_readers_fail_closed.py` is the gate.

That gate covers four scripts: `feed_willow_constitution.py`,
`feed_willow_migrations.py`, `feed_willow19_plans.py`, `feed_jeles_sources.py`.
All four are `feed_*`. **`grep` finds no test anywhere in `tests/` that mentions
`scripts/corpus/` at all** — seventeen extractors, zero coverage — and the file
that would obviously be the place to add it is *already named*
`test_corpus_readers_fail_closed.py`, which reads like the job is done.

The name is the trap. A gate named for corpus readers, which does not cover the
directory called `corpus/`, is worse than no gate: it answers the question "is
this covered?" wrongly and cheaply.

**Why it went unnoticed until now.** The extractors were written against a
`/workspace/...` layout that no longer exists, and each was run once, by hand,
against a path its author had just confirmed. A reader is only asked to
distinguish absent from empty when somebody runs it against something that is
not there — which is what a sweep does and a single authoring session never
does. The same sweep found `extract_data_vault.py` reporting 0 rows against
`willow-data-vault` because its allowlist names `sean-data-vault`'s
directories: a wrong-target run that is indistinguishable, in the output, from a
repository that declares nothing.

The fix is the one the feed family already took — refuse before reading, in
words that name which of the two happened — plus rows in the existing table so
the seventeen are covered by the gate that claims their name.

### 6.102 The extractors walk the working tree, so following this repo's own setup instructions poisons its corpus — **verified**, fix **open**

*Found 2026-08-12, in the same sweep as §6.101.* `extract_standard.py` against
this repository produced 19,804 rows. **18,665 of them — 94% — came from
`.venv/lib/python3.11/site-packages/`**: Pillow, numpy and httpx docstrings,
filed with origins reading

```
Nestor@f1fea81:.venv/lib/python3.11/site-packages/PIL/BlpImagePlugin.py#decode_dxt1
```

The real count for this repository is **1,139**.

**The provenance is not noisy, it is wrong.** `Nestor@f1fea81:` asserts that a
row is a shape declared by this repository at that commit. None of those 18,665
files are in that commit, or in any commit — `.venv/` is gitignored. A corpus
whose whole purpose is to carry where a claim came from filed eighteen thousand
claims under a repository and a revision that never contained them. Everything
downstream inherits it: `compare.py` classifies agreement *between* repositories,
and two repos with the same dependency installed would now "agree" on numpy's
docstrings, attributed to both.

**The reason it only bit here is the sharp part.** Of twenty-six stores built in
this sweep, exactly one is contaminated, and it is contaminated because
`AGENTS.md` and `docs/agent-guide.md` instruct every agent to run `python -m venv
.venv` **at the repo root** before doing anything else. The other twenty-five
repositories were never set up that way in this box, so they are clean. Following
this repository's documented setup is the thing that breaks this repository's
extractor, which is why a clean checkout can never reproduce it and why it
survived seventeen scripts and a documented corpus-order exercise.

Two further consequences, both already visible in the run:

- **It is why the run timed out.** The first attempt was killed at 300s having
  written 11,105 rows — a prefix silently presented as a store. Walking
  site-packages is the cost; `bench/README.md` already warns *"check `complete`
  before citing a number"*, and this family has no such flag at all.
- **The summary statistic is about the wrong software.** The run reports
  *"docstring coverage: 21065/59930 (35%) definition(s) carry one"*. Nestor's
  package is roughly thirty modules; 59,930 definitions is Pillow and numpy. The
  number reads as a fact about this codebase and is a fact about its
  dependencies.

The fix is to take the file list from `git ls-files` rather than from a
filesystem walk — the tree the origin string already claims to be quoting. A path
allow/deny list would also work and is weaker: it needs updating for every new
build artifact directory, and `.venv` was not the first and will not be the last.
`extract_data_vault.py` (§6.101) shows the other end of the same class — an
allowlist naming directories that no longer exist, reporting 0 rows that read as
an empty repository.

**Confirmed by re-running the same extractor against a clean `git worktree`**
(same commit, no `.venv`, nothing else changed):

| | working tree | clean worktree |
|---|---|---|
| rows | 19,804 | **1,139** |
| vendored | 18,665 | **0** |
| real rows | 1,139 | 1,139 |
| wall time | >300s (first attempt killed) | **1.371s** |
| docstring coverage | 21065/59930 (35%) | **1125/2238 (50%)** |

The real key sets are **identical** — 0 new, 0 gone — so the walk was adding
noise and nothing else, and the diagnosis is exact rather than approximate. Two
practical consequences. A `git worktree` is a working stand-in for the real fix
and needs no code change, which is how the number above was obtained. And the
**published coverage figure was not merely diluted but wrong in the direction
that flatters nobody**: this package documents half its definitions, not a
third, and the 35% would have been quoted as a fact about work still to do.

### 6.103 A model survey of vendors got two licences exactly backwards, in the same row — **verified**, fix **open**

*Measured 2026-08-12.* Five small-model agents surveyed twenty-five repositories
for machinery built in-house where an Apache-2.0-compatible vendor exists. They
returned roughly forty capability rows, each naming a licence they were told —
and repeatedly reminded — they could not verify. Twenty-one of those claims were
then checked against the PyPI metadata.

Most were right. The two that were wrong were in **the same row, and inverted**:

| vendor | claimed | actual |
|---|---|---|
| celery | LGPL-3.0 | **BSD-3-Clause** |
| dramatiq | BSD-3-Clause | **LGPL-3.0-or-later** |

One error in each direction, which is what makes it worth an entry. The
false-restrictive half only costs an option: Celery is excluded from
consideration and nobody is harmed. The false-permissive half is the one that
ships — dramatiq was offered as the recommended alternative *because* it appeared
to pass an Apache-2.0 filter, and adopting it on that basis puts an LGPL
dependency in an Apache-2.0 tree. **A licence filter applied by a model is not a
licence filter; it is a list of candidates for one.**

Two rows named projects that do not exist as described — a ledger vendor
"Chronicle (EtherLedger-based)" whose only PyPI namesake is a logging utility,
and "merkle-tree primitives from tree-sitter", which is a parser generator. Both
survived an instruction not to invent projects. One row was correct and stale:
`whoosh` is BSD-2 as claimed and its last release is v2.7.4, which no reader of
the row would guess.

**The citation errors are not uniform, which is the useful part.** Three lanes
cited `quick-stupids/PRIOR_ART.md` sections for content those sections do not
contain (§5 called "embedding tooling" is rasterisation; §3 called clustering is
property-based testing). The trust lane's citations to §6 were **correct** —
PRIOR_ART line 228 does survey OPA/Rego + Conftest and line 236 does survey
in-toto/SLSA, both marked *Apache-2.0 (verified)*, and both with recorded
reservations the surveying agent could not have known. So the failure is not "the
model cannot cite"; it is that a wrong citation and a right one are written in
identical confident prose, and only opening the file separates them.

That last point generalises past licences. The survey's value was real — it found
hash-chained ledgers implemented four to six times across the fleet, three
mutually incompatible trust-tier models, and persona definitions scattered across
three repositories. None of those needed verifying to be useful, because they are
claims about *this* box, checkable in minutes. Every claim about the *outside
world* needed checking and roughly one in ten was wrong. **Fan-out is cheap for
finding things and unreliable for asserting them**, and the split runs exactly
along that line.

Standing consequence: the fleet already has a vendor survey with a
*"what to adopt, what stays ours"* conclusion (PRIOR_ART.md line 328). Any
adoption argument starts there, not from a fresh model survey — and no licence
reaches a dependency file without the registry metadata read by a human or a
script.
