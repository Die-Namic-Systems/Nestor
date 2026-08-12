# Do authored surfaces fix the semantic misses? — measured, and mostly no

[`semantic-standin-measurement.md`](semantic-standin-measurement.md) ended on a
proposal: the model-verify miss was *"a cryptic-title problem, not a matcher
problem,"* so sealing a surface or two per entry (§3.4's authored-surfaces
mechanic) should give the semantic seam something to match. This measures that.
**It largely falsifies the proposal**, which is why it is written down.

Still a measuring instrument (Haiku stand-in, [`../embedder-stand-in.md`](../embedder-stand-in.md)):
nothing sealed, no cache keyed, all rows still draft.

## Method (to §3.4's rules, or it measures nothing)

- **Scope: a 29-referent slice** — the 5 probe referents plus every row that
  beat or challenged them in the canonical run, so the ranking stays a real
  contest rather than a rigged one.
- **Surfaces authored blind to the probes.** Two Haiku agents read each entry's
  *body lead* (not its cryptic title) and wrote 2 search-phrasings each. 58
  surfaces; **0 collapsed to the canonical** after normalization (§3.4 measured
  33% waste — these authors avoided it).
- **Negative control (arm C):** each referent is credited with *another*
  referent's surfaces (a fixed rotation). Same intrinsic `score(probe, surface)`
  values, relabeled — so if a lift is real it must survive the surfaces being
  attached to the right referent and collapse when they are not.
- Referent score = max over its rows (canonical title + its two surfaces).

## Result

Rank of the correct referent out of 29, with the stand-in's score and whether it
clears the 0.92 bar. `A` = canonical only, `B` = + authored surfaces, `C` = +
WRONG surfaces (control).

| probe | A canonical | B +surfaces | C +WRONG | verdict |
|---|---|---|---|---|
| two reviewers seal same phrase | 1 · 1.00 · **serves** | 1 · 1.00 · **serves** | 1 · 1.00 | neutral (already served) |
| measure false-verification rate | 2 · 0.75 | **3** · 0.75 | 2 · 0.85 | **hurt** (rank 2→3) |
| import reviving a rejected pair | 1 · 0.90 | **1 · 0.95 · serves** | 2 · 0.90 | **helped** — over the bar |
| may a model verify itself | 19 · 0.00 | **22** · 0.00 | 13 · 0.45 | **hurt** (rank 19→22) |
| audit-log tamper check | 3 · 0.90 | 3 · 0.90 | 4 · 0.90 | neutral |

Helped 1 of 5, neutral 2, **hurt 2**.

## What it says

**Surfaces work only where the entry genuinely means the query and the title was
the sole thing in the way — that is exactly one probe.** §1.7 (import reviving a
rejected pair) went 0.900 → **0.950**, crossing the serving bar, on a crisp
authored surface (*"Import security hole in conflict handling"*). The control
proves it was the surface and not the extra row: attach §1.7's surfaces to the
wrong referent and **§6.29 takes rank 1 at 0.95** while §1.7 falls to rank 2.
That is the mechanic working as designed.

**The miss the proposal was written to fix (may a model verify itself) got
worse, and the reason retires the proposal.** §5.7 "A model had no way in" is
*not* a cryptic phrasing of "can a model mark its own output verified" — it is a
different claim (a model's only write is `propose`; it may never seal). An honest
surface authored from its content scores **0.000** against this probe, because
the entry does not mean the question. Meanwhile genuinely-related entries
legitimately outscore it — §6.47 (a claim's own source as witness), §117
(serving the wrong seal state as verified), §6.44 (`nestor_propose` dropping an
argument). Surfaces cannot rescue a probe whose true answer is a *different*
entry, and because every referent gets surfaces, the competitors get lifted too
— so the correct row sinks from 19 to 22. This was misdiagnosed as a title
problem; it is a **probe-to-entry** problem.

**Adding surfaces is not free even when it does not help (the false-lift cost).**
P2 lost a rank because a competitor's surface climbed past §1.3's canonical.
This is §3.4 stage-1's fixed-rows/fixed-meanings finding in miniature: more rows
per meaning is more chances for the *wrong* meaning to match, and the negative
control (P4 rank-1 at 0.95 in every arm; P3's §6.29 at 0.95) shows how readily a
well-worded surface serves the wrong referent.

## Boundary and reproducibility

Single instantiation. Per §6.99 the stand-in drifts 0.150/0.300 between runs, and
the one win (0.950) and the one bar-crossing sit inside that band — so P3's
"serves" would not reliably reproduce. Read the *direction* (helped 1, hurt 2),
which the negative control anchors, not the individual scores. Raw surfaces and
per-probe scores are under [`standin-scores/`](standin-scores/)
(`surfaces_dedup.json`, `surface_pool.json`, `s1`–`s5`).

## Where this leaves it

The previous doc's "cheapest real win" was wrong on this corpus. The two
remaining failures (P4, P5) are *the wrong entry scores highest*, which surfaces
structurally cannot fix — the honest next steps are **matching against entry
bodies, not titles** (the content the query actually addresses), and accepting
that some question-shaped probes have **no single right entry** and should return
several ranked drafts to a human rather than one served answer. That is the same
place §3.4 landed: for prose-shaped retrieval the mechanic is queue ordering, not
auto-serve — and this corpus agrees.

> **Body-matching was then measured** —
> [`body-matching-measurement.md`](body-matching-measurement.md). Scoring probes
> against chunked entry *bodies* serves the correct referent on 5/5 probes and
> fixes both misses surfaces could not (the model-verify answer was in §5.7's
> body all along). The open problem moves from recall to **precision**: body
> scores cluster high across the corpus, and the leave-one-out false-seal control
> is not yet run.
