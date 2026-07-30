# Stage 3 prediction — human-authored surfaces, real corpus (terpsi-music)

Written BEFORE any extraction agent ran, and deliberately kept OUTSIDE both
repository trees so no authoring agent can read it. Stage 2's first authoring
pass was discarded for exactly this reason.

## What stage 3 changes

Stage 1: generator authored surfaces AND probes. Ceiling.
Stage 2: Claude authored surfaces, Claude authored the independent probes.
         Same model family on both sides — the unresolved 0.377/0.670 gap.
Stage 3: **a human authored every string on both sides.** The surfaces and the
         probes are verbatim spans from terpsi-music's prose, written by one
         person across 14 documents over time, with no knowledge that any of it
         would be used for matching. Claude's only role is to *label* which
         existing human phrase refers to which file — annotation, not authorship
         — and the labelling is gated by a mechanical verbatim-substring check
         that an inventing agent fails.

Also: `aliased` could only test **derivation** (manipulate the canonical string).
This corpus contains the **knowledge** case — `"the sensitivity ladder"` ->
`docs/SENSITIVITY.md` at sim 0.615, `"the eight text-only checks"` -> `craft` at
0.067. Nothing about the canonical string gets you there.

## Predictions (StringMatcher, threshold 0.92 / 0.96)

1. **Canonical-only recall @0.92: 0.00-0.03.** Hand-sampled 13 human aliases;
   the highest scored 0.839 and the median ~0.45. Zero should clear 0.92.
   Confidence: high. If this is wrong the corpus is not what I think it is.

2. **Multi-surface recall @0.92, probes from held-out documents: 0.10-0.25.**
   Well below stage 2's 0.670. The reason is the coverage-not-bridging finding
   applied to real prose: recall is bounded above by the fraction of the probe
   distribution whose *surface* was sealed, and human prose has a Zipf tail of
   one-off descriptive references ("the reading order", "this document's
   parent") that no finite seal set covers. `aliased`'s five stable families
   flattered the mechanism.
   Confidence: medium. This is the number I most expect to be wrong.

3. **The gap between arms will still be large in ratio terms** — multi-surface
   beats canonical-only by >5x — so §3.4's load-bearing claim survives a real
   corpus even if the absolute numbers are poor.
   Confidence: high.

4. **False seals will rise relative to stage 1/2.** Human doc-referring phrases
   share vocabulary ("the X model", "the X map", "§N of the capability map"),
   so absent probes have plausible near-neighbours in a way synthetic company
   names did not.
   Confidence: medium.

5. **A meaningful fraction of extracted spans will be rejected by the verbatim
   gate.** If the rejection rate is 0%, suspect the gate, not the agents.
   Confidence: medium-low — agents told to quote may quote correctly.

## What would falsify §3.4 here

Multi-surface failing to beat canonical-only by a clear margin at either
threshold. Prediction 2 being low is NOT falsification — low absolute recall
with a large ratio still says "one surface per meaning is not enough."

---

# Outcome — appended after the run, prediction above left unedited

**1. Canonical-only recall @0.92: predicted 0.00-0.03. Measured 0.000.** Right,
   and for a bigger reason than predicted — see 2.

**2. Multi-surface recall @0.92: predicted 0.10-0.25. Measured 0.000.** Wrong,
   and wrong in the direction that matters. Not "lower than stage 2" — *zero*,
   in every arm, both splits, both variants. The highest similarity any probe
   achieves against any sealed row anywhere in the corpus is **0.878**. Nestor's
   shipped thresholds are not reachable on this corpus at all.

   My reasoning was right and incomplete. I predicted a Zipf tail of one-off
   phrasings would cap coverage. What actually happens is that *no* phrasing
   pair clears the bar, common or rare.

**3. Multi-surface beats canonical-only by a clear margin: predicted yes.**
   Right, but it had to be read off `rank@1` — which the harness did not report
   until the all-zero result forced it in. At the threshold both arms are 0.000
   and indistinguishable. Ranked, human surfaces win in all four split x variant
   cells (0.333->0.500, 0.780->0.805, 0.333->0.500, 0.357->0.429) and the
   negative control collapses to 0.024-0.167.

**4. False seals rise: predicted medium confidence.** Unmeasurable. Nothing
   clears any threshold, so the false-seal rate is 0.000 for the same reason
   recall is. Neither number carries information here.

**5. Verbatim gate rejects a meaningful fraction: predicted medium-low.**
   Right: 5 NOT VERBATIM of 106, plus 5 generic anaphora. The gate bites,
   including on a *recased* span, which is the failure mode a careless reviewer
   would wave through.

## What I got wrong about the harness, not the hypothesis

Two things, both found only because the result was implausible:

- **`best_match_fast(floor=FLOOR)` censors every score below the lowest
  threshold.** On a corpus that lives entirely below it, that turns the evidence
  into zeros. The first run printed 0.000 with no way to tell "the matcher cannot
  see it" from "the threshold is above where it lives". Rescored at `floor=0.0`.
- **`normalize` collapses `CAPABILITY-MAP` to `capabilitymap`** — one token where
  the probe has two — so the baseline arm was paying a hyphen penalty that has
  nothing to do with aliasing. Worth +0.0195 mean similarity, and it favoured my
  hypothesis, so it is removed and the size is reported.

An earlier cross-document dedup rule also silently starved whichever side of the
split sorted later. Replaced with an exact-match drop computed at split time and
counted in the output.
