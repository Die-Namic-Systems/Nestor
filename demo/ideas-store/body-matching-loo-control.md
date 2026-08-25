# The leave-one-out false-seal control — body matching serves the wrong answer

[Body-matching](body-matching-measurement.md) won on recall and rank, and left
one thing unmeasured: **precision** — what does it serve when the true answer is
*absent*? This is that control, the §3.4 stage-4 measurement. It refuses
body-matching as a serving mechanism.

Instrument boundary unchanged: nothing sealed, no cache keyed, all rows draft.

## Method

Leave-one-out: for each probe, remove its correct referent, then ask whether the
best *remaining* entry clears the 0.92 bar — if it does, the system would serve a
**wrong** entry as verified. No new stand-in calls are needed: `score(probe,
chunk)` is independent of which entries are present, so the already-collected
body scores give the LOO answer directly (referent removed, max over every other
entry's chunks).

Two honesty notes on scope. The 29-entry slice is the **near-neighbour** subset
(each probe's top competitors), so this is a *conservative lower bound*: the full
143-corpus rate can only be **≥** what is shown, because more entries is more
chances to clear the bar. And it is one instantiation — §6.99 drift applies.

## Result

| probe (correct referent removed) | best wrong entry | score | verdict |
|---|---|---|---|
| two reviewers seal same phrase (−§1.8) | §1.4 Seal staleness and quorum | 0.90 | clean *(by 0.02)* |
| measure false-verification rate (−§1.3) | §1.1 Margin, not just magnitude | **0.95** | **FALSE SEAL** |
| import reviving a rejected pair (−§1.7) | §1.2 Negative seals | 0.90 | clean *(by 0.02)* |
| may a model verify itself (−§5.7) | §6.44 nestor_propose drops an arg | 0.85 | clean *(by 0.07)* |
| audit-log tamper check (−§5.3) | §5.5 Newest ledger entry vouched by nothing | **0.95** | **FALSE SEAL** |

**LOO false-seal rate: 2/5 at the bar — and this is the lower bound.** The three
"clean" verdicts sit **0.02–0.07 under 0.92**, which is inside §6.99's 0.150/0.300
drift band: on a second instantiation they are coin-flips, not passes. Read
honestly, body-matching's serving precision on this corpus is **not
demonstrated safe on a single probe** — two fail outright and three are within
noise of failing.

## Why it fails, and it is the corpus's own §1.1

Every wrong entry that clears or approaches the bar is a **genuine topical
neighbour**, not crowding noise:

- false-verification-rate → §1.1 *Margin* (0.95): both are literally about the
  false-seal rate.
- audit-tamper → §5.5 *newest ledger entry vouched by nothing* (0.95), with
  §6.98 (0.92), §5.8 (0.90), §1.7 (0.90) right behind — five entries about
  ledger integrity, all genuinely near the question.

This is **IDEAS §1.1's own finding**, reproduced by a different matcher: *"a false
seal comes from a genuine near-duplicate … so the margin is wide precisely when
the answer is wrong, and the signal inverts."* §1.1 measured it for character
matching; body-matching makes it **worse**, because a rich body matches a
topical question strongly whether or not it is *the* entry. On a corpus of
closely-related engineering notes, near-duplication is the substance, not an
artifact — and no threshold separates "the answer" from "its neighbour."

## Verdict — the three rounds, closed

| variant | recall / rank | serving precision (LOO) |
|---|---|---|
| title | poor | — |
| + surfaces | no better, sometimes worse | — |
| **body chunks** | **best (serves 5/5, rank 1 in 4/5)** | **fails: ≥2/5 false seals, rest in drift** |

Body-matching is established as a **ranking** mechanism and **refused as a
serving** one — exactly the line every prior round drew, now with a false-seal
number behind it rather than a suspicion. The correct product shape for this
corpus is the one the store already is: **rank the drafts into a human's review
queue; seal nothing at a threshold.** That is not a limitation to fix — it is
§4.2's whole thesis (a machine drafts, a human seals) meeting a corpus too
self-similar for any similarity score to adjudicate.

**If a serving number at scale is ever wanted**, the honest next step is the same
control on the full 143-corpus with per-chunk provenance — but its result is
already bounded below by 2/5 here, and the mechanism explanation above says it
rises with corpus size, so the measurement would sharpen a conclusion it will not
overturn.
