# The evidence edge

*Design memo for the issue "The evidence edge: Nestor can say who checked a
claim, but not what the claim rests on" (design, question). Written 2026-08-17.
The argument below is one a human can reject. Recorded as
[decision 0142](dogfood/decisions/0142-the-evidence-edge.json), draft.*

> **Landed 2026-08-17 (draft), after a human said the relation is wanted.** The
> core relation + report + CLI of proposals #1 and #2 are built:
> a `decision_evidence` table, an `EvidenceStorage` capability, `nestor/evidence.py`,
> the `attach_evidence` ledger kind, and `nestor evidence attach|report`. See
> [decision 0143](dogfood/decisions/0143-the-evidence-relation-lands.json), also
> draft — the direction came from a human but the decision is sealed only in
> `nestor ui`. What stayed open stayed open: the report has **no exemptions** and
> attaching evidence carries **no signature** (it grants no authority), attribution
> records a plain `attached_by` without resolving the multi-agent locus, and the
> UI surface and the `rejection_signals` taxonomy (proposal #3) are **not** in
> this pass. Bundle carriage — first deferred, then flagged by the audit — landed
> in [decision 0145](dogfood/decisions/0145-evidence-bundle-carriage.json): a
> version-3 bundle carries evidence for its pairs, inside the integrity digest,
> and import re-attaches it. The measure-demand-first caution below still stands;
> the relation shipped ahead of it on the human's call.

The issue's one-sentence claim: `sealed`/`draft`/`pending` answers *has a human
checked this?* and says nothing about *what is this resting on?* — the two are
orthogonal, a sealed row can be groundless and a draft perfectly evidenced, and
Nestor has no relation that tells them apart. This memo checks that claim
against the tree, weighs the proposed fix against the doctrine this repo already
wrote for the same shape of problem, and states what it does not settle.

It reaches four conclusions:

1. **The gap is real and distinct from provenance.** Measured below: every
   `provenance` path means *who verified and what suggested*, never *what
   supports*. There is no citation/document/source/evidence relation.
2. **The proposed fix is the house pattern, already derived twice.** A report,
   not a seal gate — the same conclusion `seal-staleness-and-quorum.md` reached
   independently for aged seals: *belongs in the queue, not in the score.*
3. **There is nothing to build it against yet.** This checkout holds 387 draft
   rows and 0 sealed, and no deployment ledger. The report's corpus is empty,
   which is the same "no users shown to exist" state that has kept N-of-M
   parked. Measure before hardening a schema.
4. **The two cautions are the sharp parts**, and one of them — the structural
   exemption — is a specific instance of the defect this codebase keeps
   deleting.

---

## 1. The gap is real, measured

`provenance` appears throughout the package and means one thing.
`answer.provenance()` ([`nestor/answer.py:440`](../nestor/answer.py)) is
documented *"Who verified a pair, when, and every rejection recorded against
it"* and delegates to `Curator.get()`. The UI's provenance fold, `Curator.get`,
the Memory chips — all of them answer *who verified this, and what suggested
it*. None answers *what supports it*. A grep for `citation`, `document`,
`source`, `evidence` finds no relation from an answer to the thing behind it.

The one near-miss is worth naming so it is not mistaken for the feature.
`ProposedEdge` carries an `evidence` field
([`nestor/triage/report.py:126`](../nestor/triage/report.py)) — but it is
evidence *for an edge* (why decision A supersedes B), computed by the matcher,
not evidence *behind a claim*. The word is spoken for in one narrow place; the
relation the issue asks for does not exist.

So the two axes are orthogonal in fact, not just in principle. The spike in §3
makes that executable: a groundless sealed row and an evidenced draft, told
apart by a query seal state cannot answer.

## 2. The fix is the house pattern — a report, not a gate

The issue proposes three things. The first two are one move: an append-only
evidence relation on a pair, and a read-only report answering *which sealed rows
have no evidence*, offered to the curator and **not** a blocker on sealing.

That shape is not novel here. It is the conclusion
[`seal-staleness-and-quorum.md`](seal-staleness-and-quorum.md) reached, from a
different starting point, for a different question:

> Neither staleness nor quorum should change what gets served silently. Both
> belong in the queue, not in the score. An aged or under-signed seal is work
> for a human, not a number that quietly stops clearing a threshold.

Swap "aged or under-signed" for "unevidenced" and it is the same argument. The
README sells one structural fact — *a human checked this* — and the staleness
memo's core objection to a decay multiplier applies verbatim to an evidence
gate: a gate would convert that structural fact back into a confidence score,
and it would withhold a verified answer on a basis nobody sealed. An evidence
*report* does none of that. It keeps serving unchanged, adds a curator queue,
and every transition off that queue (attach evidence, re-verify, supersede,
reject) stays a thing a person did, on the record, under their key.

The precedent is not only in a memo. Decision 0138 landed a **read-only**
decision triage at the review desk; decision 0068 ships
`due_for_reverification.py`, a *listing* threshold rather than a *serving* one;
`triage/report.py` writes only proposed edges and never seals. The evidence
report is the next member of a family the repo already maintains: surface a
queue, write only drafts, let the human act.

**Consequence for sequencing.** Proposal #3 — growing `rejection_signals`
(the package's one learned-from-no's failure taxonomy) toward a named taxonomy
with evidence as an input — must come *after* the relation exists, or it would
have to invent the input it is meant to read, which inverts the dependency and
re-introduces the declare-classes-up-front habit that signal was careful to
avoid.

## 3. The report is four lines — and has nothing to run on yet

The issue's central mechanism claim is that the check is tiny. It is. A
throwaway spike ([`scratchpad/evidence_report_spike.py`], not product code)
mirrors the row shape plus a hypothetical `tm_evidence` join and runs the
report as one subquery:

```sql
SELECT id, source_norm FROM tm_pairs
WHERE status = 'sealed'
  AND id NOT IN (SELECT pair_id FROM tm_evidence)
```

Output, on five pairs where one sealed row is groundless and one *draft* is
evidenced:

```
sealed rows with NO evidence attached (the curator queue):
  p2  'cure period'
1 of 3 sealed rows are groundless.
cross-check -- an evidenced *draft* is NOT in the queue: True
```

The groundless seal is caught; the evidenced draft is correctly absent. The two
axes are orthogonal, executably.

**But there is no corpus to point it at.** Measured on this checkout:

| store | rows |
|---|---|
| `docs/dogfood/nestor.db` | 387 draft, **0 sealed** |
| `data/ledger.jsonl`, `data/nestor.db` | do not exist |

The report answers "which *sealed* rows lack evidence"; with zero sealed rows
and no deployment ledger, it returns nothing, and there is no chain to measure
whether unevidenced seals are a real problem in practice or a hypothesised one.
This is precisely the position the staleness memo's step 2 names: *"designing
[a schema change] for users who have not been shown to exist is how a field ends
up carrying a distinction the mechanism does not otherwise make."* The issue's
evidence *for* the problem is strong but external — a Postgres case DB where the
analogous view caught 25 defects in one session. That argues the problem shape
is real; it does not yet measure it inside a Nestor deployment.

## 4. Cost, and the two cautions

**Cost is asymmetric across the proposals.**

- The **report alone** is cheap and reversible — a read-only view, removable
  without a migration, in the shape the repo already ships three times.
- The **relation** is a persistence change to the audited path. Per
  `CLAUDE.md` that means an adversarial read before any PR, the same bar the
  `tm_seals` quorum table has not yet cleared. It touches the Storage Protocol
  every host implements, `memory.py`, the portable bundle, and the ledger kinds.
  It is not a weekend change, and the report depends on it.

**Caution A — multi-agent attribution.** `draft` records that *a* machine
produced a row, not *which*. In one-model deployments that is free; with several
agents proposing into one store — and an evidence relation landing drafts from
each — it is the whole attribution question. This is the one question here with
no defensible default, so this memo proposes none. It only marks the deadline:
decide the locus (here, or a sibling package) *before* the schema hardens,
because attribution is a column other rows come to depend on.

**Caution B — the exemption must be structural.** Whatever marks a row as
not-needing-evidence must key on a durable fact (authorship, or the seal key the
store cannot forge), never a list of sealer-name strings. The issue reports the
counter-example from its own session: a seal exemption guarded by a blocklist of
ten names, walked by sealing as `'gemini'`, fixed by keying on authorship.

This is not a new lesson here — it is *the* lesson the staleness memo already
generalised: **a condition checked in Python, guarding a decision the store
cannot re-assert**, is "the defect this codebase keeps deleting", with three
worked examples on one day in July. A name-list exemption is exactly that shape:
a guard anyone who can write the string can satisfy, invisible when wrong.
Nestor already binds trust to keys the store cannot forge; the evidence report,
a fresh surface prone to growing a convenience list, must not walk it back.

---

## What to do next, in order

1. **Decide the question, not the schema.** The seal/report shape is
   well-argued and low-risk; the schema is not the near-term ask. The human
   decision this memo exists to support is narrow: *is the evidence axis worth a
   first-class relation, or is it covered well enough by putting a document
   locator in a pair's existing note/origin fields?* Seal or reject 0142 on that
   question.
2. **If yes, measure first.** Before the relation, stand a real store with
   sealed rows and check how many carry no recoverable basis — the analogue of
   staleness step 2. A number replaces the intuition, and it is a `grep`-scale
   task once any sealed corpus exists.
3. **Then ship the report as a pure view**, over whatever locator the pilot in
   step 1 used (even the note field), so the shape is reviewable before the
   relation hardens anything.
4. **Design the relation against the store, not a Python guard**, if steps 2–3
   say it earns its place: append-only `tm_evidence` in the ledger, exemption
   keyed on authorship, adversarial read first. Settle Caution A before this
   step, not during it.

## What this memo does not settle

- **Whether the relation is wanted**, versus a locator in the existing note
  field. Step 1 is the cheapest way to stop guessing; §3 shows there is no data
  behind either answer yet.
- **Where multi-agent attribution belongs.** Caution A — open on purpose.
- **The evidence taxonomy.** `document`/`url`/`prior_seal`/`human_statement` is
  the issue's starting set, not an argued closed set; picking the members is
  work for after step 2, against real references.
