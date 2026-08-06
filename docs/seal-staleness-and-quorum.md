# Seal staleness and quorum

*Design memo for [`IDEAS.md`](../IDEAS.md) §1.4. Written 2026-08-06. Nothing
here is implemented; the deliverable is an argument that can be rejected.*

§1.4 states the problem in two clauses: **every seal is equally authoritative
forever, and one verifier is enough.** Neither is obviously right for a
regulated buyer, and neither has been argued through. This is the argument.

It reaches three conclusions, one of which contradicts the entry that
commissioned it:

1. **The data §1.4 assumes exists does not exist.** Nestor records the first
   seal and drops concurrence on the floor. Measured below.
2. **Decay must not be a stored weight**, and the reason is not taste — the
   column is unsigned, so a decayed weight is a number anyone can put back.
3. **Neither staleness nor quorum should change what gets served silently.**
   Both belong in the queue, not in the score. An aged or under-signed seal
   is work for a human, not a number that quietly stops clearing a threshold.

---

## 1. What is actually recorded, measured

§1.4 closes with: *"The ledger already records who sealed what and when, so the
data is there — nothing consumes it."*

The first half is true of **one** seal per pair. It is not true of agreement.

Two verifiers, same source, same target, on a file-backed store with signing on:

```
after rita : verifier='rita' weight=1.0 sig=07e4bf0dd287...
after sam  : verifier='rita' weight=1.0 sig=07e4bf0dd287...
rows for this source: 1
```

and the ledger, in full, after both calls:

```
{'kind': 'seal', 'verifier': 'rita'}
```

Sam's seal raised nothing, wrote nothing, and appended nothing. It is not on the
row, not in the chain, and not recoverable. The mechanism is
[`nestor/memory.py:374`](../nestor/memory.py):

```python
if status == "sealed" and (
    existing["status"] != "sealed" or existing["target_text"] != target_text
):
```

A seal writes only when the row is not already sealed, **or** the target
differs. Two people agreeing satisfies neither arm, so the branch is skipped and
the stored row is returned to the caller as though they had sealed it.

Three things follow, and the third is the one that matters.

**Nestor records dissent and discards concurrence.** Disagreement is loud —
`ConflictingSealError` names both verifiers and both targets and refuses. Agreement
is silent. The system is better instrumented for the case where reviewers fight
than the case where they concur, which is exactly backwards for a quorum
feature.

**This failure mode is already named in this file, for drafts.** Fifteen lines
below the branch above, `ConflictingDraftError` exists because a draft over a
different draft *"silently returned the stored row"*, and the comment says
plainly that this is worse than either alternative. The concurring-seal path
does the same thing and has no error, because until quorum was contemplated
there was no reason to distinguish "already sealed by someone else" from "you
sealed it."

**So quorum cannot be computed from history.** There is no history. Any N-of-M
design has to start by creating the evidence, and a migration cannot backfill
countersignatures that were never written down.

---

## 2. Why a decaying `weight` is the wrong mechanism

`tm_pairs` has carried a `weight REAL NOT NULL DEFAULT 1.0` since the beginning
([`sqlite_store.py:56`](../nestor/sqlite_store.py)). It is threaded through
`add_pair`, `memory_seal`, `graduate_segment`, `entity.seal` and the portable
bundle. It is the obvious place to put decay, and it should not be used for it.

**It is read by nothing.** Grepping `weight` across `nestor/` finds writes,
plumbing and two comments about dead vectors. Ranking never consults it;
`best_sealed` scores on similarity alone. Today the column is a value the system
carries and does not use.

**It is not signed.** `signing._message` takes the HMAC over exactly
`[source_norm, target_text, verifier]` — a structured JSON array, chosen so no
field can collide by shifting a delimiter. `weight` is not in it. Neither is
`created_at`.

Put those together. If decay is a number stored in `weight` and consulted at
serve time, then the thing deciding whether a verified answer still counts is a
mutable, unsigned, un-chained integer sitting in the same table as the data it
governs. Anyone who can write the row can write `1.0` back into it, and every
signature still verifies, because the signature never covered it. The seal
audit would pass on a row whose staleness had been quietly reset.

That is the defect this codebase keeps deleting: **a condition checked in
Python, guarding a decision the store cannot re-assert.** `TODO.md`'s closing
note and review-lessons §8–§9 are three worked examples of it. Adding decay to
`weight` would be a fourth, with the aggravating feature that the guard is
invisible — a wrong weight looks exactly like a right one.

**Derived, not stored.** Age is a function of a timestamp, and Nestor has two:
`tm_pairs.created_at` and the `ts` on the ledger's `seal` entry. The row's is
unsigned like `weight`. The ledger's is covered by the hash chain, which is the
only timestamp in the system that cannot be moved without the chain saying so.

So if staleness is ever computed, it is computed **from the ledger at read
time**, and there is nothing to tamper with independently, because there is
nothing stored. The cost is that the ledger must be readable on the serving
path, which it currently is not — an honest price, and a smaller one than a
silently resettable dial.

---

## 3. What staleness should *do* — and the answer is not a multiplier

The tempting design is a decay curve feeding a score multiplier: a seal loses
weight with age, its effective score drops, and eventually it stops clearing
`SEAL_THRESHOLD`.

This is wrong for Nestor specifically, and the README's first paragraph says why
before the feature is even proposed:

> Not as a confidence score — as a structural fact you can audit.

A decay multiplier converts the one structural fact the system sells — *a human
checked this* — back into a confidence score, which is the thing every other
system already offers and the thing Nestor was built to replace. Worse, it does
it **silently**: an answer a named person verified stops being served, on a
date nobody chose, because a curve crossed a line. Nobody rejected it. Nobody
superseded it. The audit trail records no decision, because no decision was
made. "Why did this stop being served?" would have no answer in the ledger,
which is the one question the ledger exists to answer.

**Staleness belongs in the queue.** The shape that fits is the one Nestor
already uses for deferred refusals: `reopen_when` on a rejection records a
*trigger* rather than an automatic reversal, and a human acts on it. The
staleness equivalent:

- an aged seal keeps serving, and keeps saying who sealed it and when — §6.10
  already ships relative age on the Memory chips, so the display half exists;
- it additionally appears in the curator as **due for re-verification**;
- a human re-verifies it, which is an ordinary seal by an ordinary verifier and
  lands in the chain like every other decision;
- or a human decides it is stale and rejects or supersedes it, which is also an
  ordinary decision and also lands in the chain.

Every transition stays a thing a person did, on the record, under their key.
Nothing changes what is served except a human changing it. The policy question
"how old is too old" becomes a *listing* threshold rather than a *serving*
threshold, which is a much cheaper thing to get wrong: a badly tuned queue wastes
review time, a badly tuned serving cutoff withholds verified answers.

---

## 4. Quorum is a schema change, and it should refuse rather than downgrade

**There is nowhere to put the second signature.** `tm_pairs` has one `verifier`
and one `seal_sig`. N-of-M needs a `tm_seals(pair_id, verifier, sig, at)` table,
with the pair's `verifier`/`seal_sig` becoming a denormalized head of it. That is
a persistence change to the audited path, which per `CLAUDE.md` means an
adversarial read before any PR, and it is why this memo does not come with a
diff.

**The guard shape matters more than the count.** The naive version is a Python
check — count the signatures, compare to N, refuse to serve below it. That is
reachable-around by construction: it lives in the serving path, and every other
path into the store (import, `graduate_segment`, a host's own writer) would need
to remember it. This repo has four worked examples of that going wrong on
2026-07-31 alone.

The version that holds: **sub-quorum is not a weaker seal, it is not a seal.**
A domain requiring two verifiers has a pair that stays `draft` until the second
signature lands, and `draft` is already never served as verified, by a rule the
store enforces rather than a rule callers honor. Quorum then costs no new
serving guard at all — it changes when a row is allowed to *become* sealed, which
is one place, not many. The three states keep meaning exactly what the README
says they mean, and "sealed" does not acquire a silent second tier.

This also disposes of the weight question from the other direction. There is no
"70% sealed". A pair with one of two required signatures is a draft with one
signature on it, and the UI can say so precisely without inventing a scale.

---

## 5. What to do next, in order

1. **Stop discarding concurrence.** This is the only step that is cheap, is
   useful on its own, and is a prerequisite for everything else. A second
   verifier sealing an already-sealed pair with the *same* target should append
   a ledger entry rather than returning silently. No schema change, no new
   table, no behaviour change to serving — it makes an event that currently
   vanishes into a line in the chain.

   It also fixes a real asymmetry today, independent of quorum: a reviewer who
   countersigns believes they did something, and nothing anywhere records that
   they did. That is the `ConflictingDraftError` complaint, unaddressed for
   seals.

2. **Then measure whether anyone countersigns.** With step 1 shipped, the
   question "does N-of-M have any users" becomes answerable from a real
   deployment's chain instead of from intuition. §1.4 has been open since it was
   written partly because nobody knows whether it is wanted; that is a
   measurement, and it is now a cheap one.

3. **Do not ship weight decay.** Not in `weight`, not anywhere. If staleness is
   wanted before step 2 concludes, ship the *listing* — curator surfaces seals
   older than a configured age — which changes nothing about what is served and
   can be removed without a migration.

4. **Design N-of-M against the store, not the serving path**, if and when step 2
   says it is wanted: `tm_seals`, and sealing gated on signature count so
   sub-quorum rows are drafts. Adversarial read first.

---

## What this memo does not settle

- **How old is too old.** Deliberately: it is a policy per domain, and picking a
  default here would be inventing a number with no corpus behind it, which is
  the failure mode `nestor calibrate` exists to replace.
- **Whether a regulated buyer actually asks for either.** §1.4 asserts neither
  is "obviously right", which is true and is not the same as evidence that
  either is wanted. Step 2 above is the cheapest way to stop guessing.
- **Ed25519 interaction.** `TODO.md` §1 would make a seal evidence a server
  could not have manufactured. A `tm_seals` table full of HMACs is a table of
  claims the deployment could have written itself, so a quorum of shared-secret
  signatures is a quorum only against outsiders. If both are wanted, the
  asymmetric work comes first — otherwise N-of-M buys less than it appears to.
