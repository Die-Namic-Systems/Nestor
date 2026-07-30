<!-- Draft entry for IDEAS.md §3, to sit after §3.3. -->

### 3.4 Model-authored surfaces — **four stages; the matcher mattered more than the surfaces**

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
