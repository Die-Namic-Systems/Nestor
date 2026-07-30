# Stage 2 — prediction, recorded before the run

Written and committed to disk **before any surface was authored**, because the
interpretation step is where a preferred answer gets rationalised. If the
numbers land outside this, the prediction was wrong and stays on the page.

## What stage 2 changes

Stage 1 sealed surfaces straight from `corpora.aliased`, which means the corpus
generator had **perfect knowledge of the probe distribution** — probes are drawn
from the same five families the surfaces came from. That is a ceiling, not a
forecast.

Stage 2 shows a model **only the canonical form** (family 0, e.g.
`jarvale robotics group 41`) and asks it to author the alternates. It never sees
the other families, the probe, or this bench. Everything else — rows, meanings,
probes, seed, threshold sweep — is identical, so the difference between stages
is the model.

## The prediction

The generator's five families are `full`, `short`, `acronym`, `ticker`,
`legacy`. Four are **derivable** from the canonical form by string manipulation.
`legacy` is a rename — `caldwell bros 41` for `jarvale robotics group 41` — and
carries no derivable relationship to the canonical at all.

So:

1. **Stage-2 recall lands at roughly 0.8 × stage-1 recall at K=5.** The model
   should recover the four derivable families and cannot recover `legacy`, so
   ~1/5 of the probe distribution becomes unreachable. Stage 1 K=5 measured
   0.652 @0.92 and 0.492 @0.96, so **predict ≈0.52 and ≈0.39**.
2. **At K=3 the gap is much smaller — possibly zero.** With only three surfaces
   to spend, both the generator's priority order and a sensible model should pick
   derivable, common forms first. Stage 1 K=3 measured 0.440 / 0.344; predict
   stage 2 within ~0.05 of that.
3. **False seals stay in the same band or drop slightly.** Model surfaces should
   be *less* adversarial than the generator's, which emits near-collision-prone
   short strings (`JR0`, `JRVL0`) by construction.
4. **Zero false seals at 0.96 survives.** That was the headline of stage 1 and it
   is the claim most worth breaking.

## Why this corpus is unfriendly to stage 2, and what that means

`aliased` is synthetic, so stage 2 measures **derivation** — can a model
manipulate a string into its plausible alternates. It does **not** measure
**knowledge**, which is what the real case needs: `Amazon` → `AWS` / `AMZN`
requires knowing the world, not transforming characters. A model has that
knowledge for real entities and cannot have it for `jarvale robotics group 41`.

So a stage-2 result here is a **lower bound** on real-world alias quality, and
the `legacy` family is an unwinnable 1/5 of the distribution by construction.
Reporting stage-2 recall as "what model-authored aliases achieve" without that
caveat would be the same error as quoting a rank correlation without its
aggregation.

## Known contamination risk

I know the generator's families and I am writing the authoring prompt. That is a
live route for leaking the answer into the question. Controls:

- The prompt must not use the words *acronym*, *ticker*, *abbreviation*,
  *initials*, or *former/previous name*, and must not say how many kinds of
  variant exist.
- The prompt is recorded verbatim in `bench/results/authored_surfaces.json` so
  the leak can be audited rather than trusted.
- One instruction does leak generator structure deliberately: the canonical form
  ends with a numeric disambiguator, and the model is told to preserve it on
  every variant. Without that, authored surfaces would drop the tag while every
  probe keeps it, and stage 2 would score near zero for a formatting reason
  rather than a semantic one. This is a formatting instruction, not a hint about
  what kinds of surface to produce, and it is noted here because the line matters.

---

# Outcome — recorded after the run

## The prediction was wrong

Predicted stage-2 recall ≈0.52 @0.92 at K=5, on the reasoning that four of five
families are derivable and only `legacy` is not. Measured against the
generator's probe families: **0.377**. Below the prediction, and wrong for a
reason the prediction did not anticipate.

Per-family recall @0.92, K=5:

| family | generator | model-authored |
|--------|----------:|---------------:|
| full | 0.94 | **1.00** |
| short | 0.45 | **0.82** |
| acronym | 1.00 | 0.00 |
| ticker | 0.58 | 0.00 |
| legacy | 0.56 | 0.00 |

The prediction assumed the misses would be *derivability* failures. Two of the
three are not.

**The model produced an acronym for every single meaning** — `JRG 0`, `QFL 1`,
`PMC 2`, `MAI 3` — arguably better ones than the generator's, since they include
the legal-suffix initial the way real acronyms do. The generator's acronym is
`JR0`: place and trade initials only, tag jammed on with no space.
`sim("JRG 0", "JR0") = 0.750`, under threshold, scores zero. Ticker is the same
story and worse: `JRVL0` is first-four-consonants, a convention nobody derives.

So `acronym = 0.00` is a **corpus artifact, not a model failure**. Only `legacy`
was a genuine miss, exactly as predicted, and it is 1/5 of the distribution —
the prediction was right about the one thing and wrong about the rest.

## The deeper problem: stage 1 and stage 2 need different corpora

`corpora.aliased` is self-consistent because the generator authors both the
sealed surfaces and the probe families. That is fine for stage 1. The moment a
*different* author supplies one side, every arbitrary convention the generator
invented becomes an unguessable barrier, and the bench measures convention
matching rather than alias quality.

This is the third blindness in this investigation, and a new kind: the corpus is
valid for one stage and invalid for the next, with nothing about it changing.

## Re-scored against an independent probe author

An agent that saw neither the generator's families nor the sealing model's
output was asked to write what a hurried employee would type into a search box.
Probes drawn from that; both arms scored against it:

| arm | K | rows | recall@0.92 | fs@0.92 | recall@0.96 | fs@0.96 |
|-----|--:|-----:|------------:|--------:|------------:|--------:|
| canonical only | 1 | 300 | 0.117 | 0.000 | 0.023 | 0.000 |
| generator families | 5 | 1500 | 0.430 | 0.028 | 0.293 | 0.000 |
| model-authored | 5 | **1402** | **0.670** | 0.032 | **0.570** | 0.004 |

Model-authored surfaces beat the generator's own families — on **fewer rows**,
because 98 of 300 wasted a slot on a case-variant of the canonical that
normalization erases.

## What is actually established, and what is not

**Not established: how good model-authored aliases are.** The two framings
disagree by a factor of ~1.8 (0.377 vs 0.670) and *neither is the answer*.
Scored against the generator, the model is punished for not guessing arbitrary
conventions. Scored against another agent, it is rewarded for agreeing with
itself — probe author and surface author are the same model family, so their
convergence on "drop the suffix, abbreviate the suffix, use the bare prefix" is
partly one system agreeing with itself. A real user is not Claude. The truth is
somewhere between and this design cannot locate it. **Human-authored probes are
the only thing that closes this**, and that is the honest next step.

**Established, and robust across both framings: one surface per meaning is not
enough.** Canonical-only scores 0.056 against generator probes and 0.117 against
independent ones — badly, either way, regardless of who wrote the queries or
which conventions they used. Every multi-surface arm beats it substantially in
every framing. That is the load-bearing claim of §3.4 and it does not depend on
the disputed comparison.

**Also established: authored surfaces waste slots.** 98 of 300 meanings (33%)
received a variant identical to the canonical after normalization. A third of the
model's budget bought nothing. That is a real quality cost and it is measurable
before sealing — a dedup check at authoring time would recover it.
