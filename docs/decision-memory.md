# Decision memory — the missing half

*Carried over from the SAFE App Store
(`safe-app-store:docs/design/nestor-decision-memory.md`, authored 2026-08-05),
where it was drafted while this repo was read-only from that seat. This copy is
canonical now — the change lands here. The narrative around it — why this wall
stands — is
[`the-fourth-store.md`](https://github.com/rudi193-cmd/safe-app-store/blob/claude/boogie-beat-context-j450h4/docs/the-fourth-store.md),
sealed by the operator 2026-08-05.*

**The question this answers:** how do decisions get made, rejected, **modified**,
and how does that affect **future** decisions — held in a way that survives the
conversation that produced it.

---

## The finding

Nestor is a **verified-answer memory**, and it is very good at that. The schema
says what it is:

- `nestor/sqlite_store.py` — `tm_pairs`, keyed `(source_norm, source_lang, target_lang)`
- `_UNIQUE_KEY` — a **UNIQUE** index over that key: one source, one target
- `tests/test_seal_replacement.py` — *"The memory keeps exactly one row per
  normalized source, so re-sealing an already-sealed source destroys the previous
  human decision with nothing left in the store to show for it."*

Four verbs are wanted. Nestor has two:

| Verb | Status | Where it lives |
|---|---|---|
| **made** | ✅ | `seal` — signed, ledgered, portable |
| **rejected** | ✅ | `tm_rejections`, with a `reason` column, signed |
| **modified** | ❌ | destructive overwrite; lineage survives only as an append-only ledger line |
| **affects future** | ❌ | no edge relates any pair to any other pair — there is no graph |

The comparison that names it, given where the design conversation started:

> **Git keeps the lineage and throws away the rejections. Nestor keeps the
> rejections — signed, with reasons — and models no lineage.**

Each holds one half. This document is how they come together, *inside Nestor*.

A third asymmetry falls out of the same read: `tm_rejections` has `reason`;
`tm_pairs` has none. Nestor records **why you said no** and not **why you said
yes**. For decisions that is backwards — the rationale behind what was chosen
is exactly what a future proposal must argue against.

---

## The mapping — a decision is already a Nestor pair

No new engine. The SAFE store's `stores/almanac/nestor-seam.md` states the
fleet rule: *"a new recipe over the shelf, not a new engine — the same lesson
as Heartwood."*

| Decision concept | Nestor primitive today |
|---|---|
| the open question | `source_text` / `source_norm` |
| the commitment | `target_text` |
| a proposal | `status = 'draft'` |
| a ratified decision | `status = 'sealed'` + `seal_sig` + `verifier` |
| **a rejected alternative** | `tm_rejections(query_norm, target_text, reason, reject_sig)` |
| the audit trail | `cascade` hash-chained ledger |
| taking it elsewhere | `portable.export_bundle` / import with signature re-verification |

The fifth row is the one worth staring at. **Nestor's rejection table is already
a rejected-alternatives record** — "for question Q, answer T was refused,
because R, signed by V." It has simply never been read that way. The half the
git flow throws away is already sitting in the schema, durable and signed.

What is genuinely absent is only: **lineage, reasons-for-yes, reopen conditions,
and edges.**

---

## N1 — "where does a decision start?" is a Matcher, not an ontology

The SAFE store's `stores/checkpoint_memory.py` records this as its D8 open
question and correctly declines to answer it. It does not need a global answer.

Nestor's entire architecture puts domain-specific code behind one two-method
seam: *"What it compares … is decided by a `Matcher`, a two-method seam holding
the only domain-specific code in the system."* So:

> **The unit of a decision is whatever the `DecisionMatcher` normalizes to the
> same key.**

Two differently-worded questions are the same decision iff the matcher says so.
That dissolves the ontology question into a component that already exists, and
it makes the unit *tunable and measurable* (`bench/`) rather than a
philosophical commitment made once in a schema.

**Load-bearing risk, stated plainly:** this is also the weakest joint. The
cold-agent failure is a proposal that is the *same decision wearing different
words*. A `StringMatcher` will miss that. `nestor/semantic_matcher.py` exists
and is the intended matcher here — but N1's accuracy must be **measured**, not
assumed, before anything depends on it (see Build order, step 5).

---

## Core changes — one new optional capability

Per `nestor/storage.py`'s capability table, Nestor extends by **optional
capability**, each gated by a predicate, each all-or-nothing, *"partial
implementation counts as none."* The decision graph enters the same way — as a
fourth capability, so every store predating it keeps working.

### N2 — `supports_lineage(store)`

New predicate alongside `supports_rejection` / `supports_curation` /
`supports_queue`. Without it, `supersede()` **raises** rather than silently
overwriting — exactly the rejection precedent (*"`reject_*` raises rather than
dropping a human's 'no'"*). Destroying a prior human decision quietly is the
failure this whole document exists to close; it must not be the fallback.

### N3 — `tm_pairs.superseded_by`, and a *partial* unique index

```sql
ALTER TABLE tm_pairs ADD COLUMN superseded_by TEXT NOT NULL DEFAULT '';

CREATE UNIQUE INDEX idx_tm_pairs_key_live
    ON tm_pairs(source_norm, source_lang, target_lang)
    WHERE superseded_by = '';
```

**Why this specific shape.** `storage.py` is explicit that the uniqueness is a
concurrency guard, not housekeeping: *"Nestor's conflict guards
read-then-write, so that uniqueness is what makes 'one row per source' hold when
two reviewers seal the same phrase at the same moment."* A partial index keeps
that guarantee **exactly**, because two concurrent seals both write *live* rows
and still collide. Superseded rows fall out of the index and accumulate as
history.

The serve path gains one predicate — `AND superseded_by = ''`. Nothing else on
the hot path changes.

Migration follows the `tm_embeddings` precedent (`PRAGMA table_info` then
conditional `ALTER`), and the `_UNIQUE_KEY` precedent of building the index
**outside** `_SCHEMA` so a database with pre-existing duplicates cannot be
bricked by an idempotent init.

### N4 — `tm_pairs.reason`

One column, symmetric with `tm_rejections.reason`. Closes the say-no/say-yes
asymmetry. Cheap, and correct independent of everything else here.

### N5 — `tm_rejections.reopen_when`

The SAFE store's `stores/pending.json` already discovered this locally and
Nestor has no equivalent. Its entries carry `blocked_on` — the condition under
which a deferred decision becomes live again — and an explicit guard that you
resolve it by answering the question, *"not by editing this file to make the
question disappear."*

Nestor's rejection is permanent by design (*"a wrong match is never served
again"*), which is right for a bad translation and **wrong for a decision**.
Most rejections are *not yet, because X*. A memory that cannot distinguish
**never** from **not yet** will confidently enforce stale law — the exact
pathology this is meant to prevent, with a signature on it.

`reopen_when` empty = never. Non-empty = a deferral, and `constraints_on`
surfaces it as a condition to check rather than a closed door.

---

## N6 — the graph

The one genuinely new table. Recipe-owned, behind `supports_lineage`.

```sql
CREATE TABLE IF NOT EXISTS decision_edges (
    id         TEXT PRIMARY KEY,
    src_id     TEXT NOT NULL,          -- tm_pairs.id (the later decision)
    dst_id     TEXT NOT NULL,          -- tm_pairs.id (the one it relates to)
    kind       TEXT NOT NULL,          -- supersedes | refines | depends_on | contradicts
    reason     TEXT NOT NULL DEFAULT '',
    verifier   TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    edge_sig   TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_decision_edges_dst ON decision_edges(dst_id, kind);
CREATE INDEX IF NOT EXISTS idx_decision_edges_src ON decision_edges(src_id, kind);
```

`edge_sig` is not decoration. **An edge is itself a ratifiable claim** — "this
supersedes that" is a human judgment of the same weight as the seal, and under
the covenant the machine may propose it and may not confirm it. Same key, same
`nestor.signing`, same rule: an edge whose signature does not verify is
surfaced to the curator, never traversed as fact.

### N7 — ledger kinds

`cascade` gains `supersede` and `edge_seal` entry kinds, so the hash chain
covers the graph as it already covers seals and rejections. `nestor ledger
verify` then keeps being the whole-record CI gate it already is.

---

## N8 — the recipe: `nestor/decision.py`

Mirrors `entity.py` exactly — the shape is proven, and the SAFE store's
`checkpoint_memory.py` already consumes it from the other side:

```python
class DecisionMemory:
    def __init__(self, store, domain="decision", matcher=None, ...)

    def propose(question, commitment, rationale) -> draft   # machine may
    def seal(question, commitment, reason, verifier)        # human only
    def reject(question, option, reason, reopen_when="")    # durable, signed
    def supersede(old_id, commitment, reason, verifier)     # seals new + edge
    def constraints_on(question) -> Constraints             # ← the traversal
```

`Constraints` is the whole point of the exercise. Not "what is the answer" but
**"what does what we already committed to constrain about what I am proposing":**

- the **live** decision (if any), with its `reason`
- its **lineage** — every superseded predecessor, each with the reason it was
  replaced (this is what git's merged-PR history gives you and Nestor lost)
- the **rejected alternatives**, each with its reason (this is what git throws
  away and Nestor already has)
- any rejection whose `reopen_when` is non-empty, surfaced as **a condition to
  re-check**, not a refusal
- `depends_on` / `contradicts` neighbours

`domain` rides in the language tags exactly as `EntityResolver` does, so one
store holds disjoint decision graphs (`decision:architecture`,
`decision:the-forge`) without cross-talk.

---

## N9 — the push half: an oracle cannot fix an unasked question

Everything above is storage, and storage does not solve the actual failure.
Nestor is an **oracle** — `nestor_ask`, `nestor_resolve`, `nestor_check` — and
oracles must be consulted. The cold-agent failure mode is not a wrong answer.
It is a proposal that felt obviously right, so nobody queried for objections to
it. **No schema change reaches that.**

Nestor cannot force an agent to ask. What it can do is sit in a chokepoint that
is *already mandatory*:

1. **`nestor decision check` — a CI gate.** Exit non-zero when a change touches
   a question carrying a live rejection or an unmet `reopen_when`. Nestor
   already ships exactly this pattern: *"`nestor ledger verify` … exit 1 on a
   broken chain, for CI"* (`cli.py`). This is the same move, pointed at the
   decision graph — a required status check aimed at reasoning rather than at
   code.
2. **`nestor_propose` returns constraints before accepting a draft.** The MCP
   tool exists. Today it takes a proposal. It should hand back
   `constraints_on(question)` *with* the accepted draft, so the objection
   arrives in the same breath as the proposal, unasked-for.
3. **Session boot.** The SAFE store's CLAUDE.md already makes `/startup`
   mandatory. A cold agent that reads live decisions and open `reopen_when`
   conditions on the way in starts with the institutional memory it otherwise
   cannot have.

**(1) is the highest-value bite and the cheapest.** It is the only one of the
three that fires without anyone choosing to consult anything.

---

## Rejected alternatives

*Recorded here rather than discarded — the document practices its own thesis.*

- **Relax the UNIQUE index entirely** — rejected. `storage.py` documents it as
  the concurrent-seal race guard. A partial index (N3) keeps that guarantee
  intact for live rows; dropping it trades a correctness property for a
  convenience.
- **A separate `tm_pair_history` archive table** — rejected. It produces a
  graveyard, not a link. `superseded_by` makes lineage a first-class traversable
  edge; an archive table makes it a second place to look.
- **Build decisions as a new engine / separate package** — rejected against the
  fleet's stated lesson (*"a new recipe over the shelf"*) and against
  `entity.py`'s worked precedent. Everything needed is already on the shelf
  except the edges.
- **Put the decision graph in SAPS1/Willow instead of Nestor** — *arguable, not
  dismissed.* SAPS1 already has atoms **and edges**, which is more than Nestor
  has today. Rejected here on one ground: SAPS1 has no seal, no signature, and
  no hash chain, so a decision recorded there is **asserted** rather than
  **ratified** — and separating proposing from ratifying is the whole reason
  this exists. Revisit if SAPS1 grows a ratification primitive; that condition
  is this entry's `reopen_when`.

---

## Follow-ups

Logged in [`IDEAS.md`](../IDEAS.md) §6.11–§6.12, per §6's own rule that a
follow-up suggested to the operator goes in the list, not only in chat.

---

## Open questions

1. **Does an edge need its own seal ceremony,** or does it ride the seal of the
   decision that created it? N6 assumes its own signature; that may be one
   ratification too many in practice.
2. **N1 accuracy is unmeasured.** If the matcher cannot recognize the same
   decision in different words, `constraints_on` silently returns nothing and
   the system is worse than useless — it is *reassuring*. Must be benched
   before N9(1) becomes a gate anyone trusts.
3. **Multi-question decisions** — one commitment settling several open questions
   has no representation. Possibly `refines` edges suffice; untested.
4. **Who is the human here?** The covenant says the machine proposes and the
   operator seals. In a fleet where agents make most proposals, the seal queue's
   throughput becomes the binding constraint. Not a Nestor problem, but it is
   the one that decides whether this gets used.

---

## Build order

1. **N4 + N5** — two columns, no behaviour change. Independently correct.
2. **N2 + N3** — the capability predicate and the partial index. Revision stops
   destroying. This alone closes the **modified** verb.
3. **N6 + N7** — edges and ledger kinds. Closes **affects future**.
4. **N8** — the recipe over 1-3.
5. **Bench N1** — measure whether the matcher recognizes a re-worded decision.
   *Gate: no further work until there is a number.*
6. **N9(1)** — the CI gate. The first point at which any of this catches
   something nobody asked it to catch.

Steps 1-2 are worth doing whether or not the rest is ever built: they fix a
destructive overwrite that `test_seal_replacement.py` already identifies as a
bug in the translation recipe, with nothing to do with decisions.

---

*Git keeps the lineage. Nestor keeps the rejections. The brain needs both.*
