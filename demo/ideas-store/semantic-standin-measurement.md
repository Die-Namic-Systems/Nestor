# What semantic retrieval would buy on the `idea` corpus — measured with a Haiku stand-in

`fastembed` and `ollama` are both egress-blocked in this container, so the
semantic seam cannot be exercised. Per [`../embedder-stand-in.md`](../embedder-stand-in.md)
(PR #72), a language model stands in as a **measuring instrument** — it answers
`score(a, b) → float` on the doc's rubric, and by that doc's boundary it **may
not key the embedding cache and may not stand behind a seal**. Nothing here is
sealed and no store row changed; every one of the 143 pieces stays a draft.

Following `scripts/feed_fleet_repos.py`'s precedent, the instrument was **five
parallel Haiku subagents**, one per probe, each scoring its probe against all
143 `idea` source titles blind to the expected answer. Raw scores are committed
under [`standin-scores/`](standin-scores/) so the ranks below are reproducible
from the numbers, not just asserted.

## The question

§6.106 (and §6.94 before it) found StringMatcher retrieval on decision-shaped
corpora is *fine for content-bearing questions and collapses for question-shaped
ones*. This measures the same thing on the new `idea` corpus, and asks whether
the semantic seam repairs the collapse. Probes are deliberately question-shaped.

## The result

`string rank` from `scripts/retrieval_rank.py --matcher string`; `haiku rank`
computed the same way from the stand-in's scores. Bar is the shipped 0.92.

| probe | string rank | haiku rank | haiku score | serves @0.92 | stand-in's rank-1 (if wrong) |
|---|---|---|---|---|---|
| Can two reviewers seal the same phrase at once? | 1/143 (0.667) | **1** | 1.000 | **yes** | — (correct) |
| How do I measure the false-verification rate? | **20**/143 (0.333) | **2** | 0.750 | no | §1 Correctness (0.900) |
| What stops an import reviving a rejected pair? | 1/143 (0.621) | **1** | 0.900 | no | — (correct) |
| Is a model allowed to verify its own output? | 1/143 (0.468) | **51** | **0.000** | no | §6.47 witness (0.900) |
| How do I know the audit log wasn't tampered with? | **122**/143 (0.208) | **3** | 0.900 | no | §6.44 nestor_propose (0.950) |

## What it says

**1. Semantic buys rank, not service — the same shape §3.4 stage 3 found for the
string matcher on prose.** Four of five correct rows land in the top 3 (two of
them recovered from rank 20 and rank 122). But only **one of five clears 0.92**,
and that one already ranked first under StringMatcher. For the review queue —
where "the right answer, first, at 0.90" is worth something — this is a clear
win. For auto-serving at a safe bar, it is not.

**2. The lift on the question-shaped collapse is the real finding.** The two
probes StringMatcher buried — 20/143 and 122/143 — come back at 2 and 3. That is
exactly the §6.106 failure the semantic seam is supposed to answer, and on this
corpus it answers it *for ranking*.

**3. It trades one failure mode for another — see the model-verify probe.**
StringMatcher had the correct row (§5.7 "A model had no way in") at rank 1, by
accident, on the shared token "model". The stand-in scored that cryptic title
**0.000** and put a *wrong* row first: §6.47 "A claim's own source counts as an
independent witness" at 0.900. Semantic is not strictly better — where a title
carries none of the probe's meaning, semantic confidently promotes a wrong row
while the string matcher stumbles onto the right one.

**4. The rank-1 row is wrong in two of five cases, and scores high.** The
audit-tamper probe recovers the correct row from 122 to 3, but §6.44
`nestor_propose` sits above it at **0.950** — above the bar. Lowering the
threshold to serve the recovered row would serve that wrong row instead. This is
precisely the hazard `retrieval_rank.py` exists to make visible: *rank 3 below
the bar is not the same as rank 1 below the bar.*

## Why this is an instrument reading, not a number

Per §6.99, the stand-in drifts **0.150 mean / 0.300 max** between fresh
instantiations. The 0.900 and 0.950 values that decide "serves / doesn't" sit
squarely in that band around the 0.92 bar, so the *serve* column for the import
and audit probes would not reproduce on a second run. Only the identical-string
1.000 (the two-reviewers probe) is stable across instantiations, and it is the
one that serves. That is the whole reason for the doc's boundary: this measures
what the seam would buy, and may not become the seam.

**Next, if this were to be pursued:** the cheapest real win is not a matcher
swap but **better source text** — the model-verify miss (finding 3) is a cryptic
*title* problem, not a matcher problem. Sealing a surface or two per entry
(§3.4's authored-surfaces mechanic) would give the semantic seam something to
match that the terse heading does not carry. Measured, not built.

> **Now measured, and this paragraph was mostly wrong** —
> [`authored-surfaces-measurement.md`](authored-surfaces-measurement.md).
> Authored surfaces helped 1 of 5 probes, were neutral on 2, and *hurt* 2. The
> model-verify miss got worse, because §5.7 is not a cryptic phrasing of the
> probe — it is a different claim, and no honest surface makes an entry mean a
> question it does not. Kept verbatim above so the overreach is checkable.
