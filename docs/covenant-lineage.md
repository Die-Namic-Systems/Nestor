# Where the covenant came from

**You may propose. You may not confirm.**

That rule is not original to this package. It was written down, implemented,
gated and adversarially probed in `willow-2.0` before `nestor/` existed, and it
has an ancestry going back to a Postgres migration in `willow-1.9` dated
**2026-05-18**. This file records that, because `CLAUDE.md` states the rule as
though it were an axiom, and an axiom with a documented history is a different
and more useful thing than one without.

**Read on 2026-08-06, at these revisions.** Everything below is quoted from a
shallow clone at a fixed commit. These are claims about repositories this one
does not control and cannot gate, so they are pinned rather than paraphrased and
they will go stale.

| repo | commit read |
|------|-------------|
| `rudi193-cmd/willow-1.9` (archived) | `b6383f2` |
| `rudi193-cmd/willow-2.0` | `dd780da` |
| `rudi193-cmd/Jeles` | `ed48de7` |

---

## 1. `willow-1.9` — tiers, and a number

`migrations/20260518_evidence_tiers.sql` adds two columns to the knowledge
graph:

```sql
-- tier:       hypothesis | observed | validated  (NULL = legacy, treat as observed)
-- confidence: 0.0–1.0 float (NULL = unscored)
```

Three rungs, ten weeks before this package had three states. The comment on the
column defines `validated` as *"confirmed by multiple sources"* — corroboration,
not a person.

And then the line worth keeping:

```sql
UPDATE knowledge SET tier = 'observed', confidence = 1.0 WHERE tier IS NULL;
```

Every pre-existing atom is promoted to *observed* at **full confidence** by a
migration, because there was nothing else to do with rows that predated the
scheme. Nobody checked them. A machine assigned the tier and the score.

That is the defect this package exists to make impossible, in the author's own
SQL, months before the package was written. It is not a criticism of the
migration — there was no better option available to it. It is the clearest
statement anywhere of why a status has to mean *somebody signed*, and why a
backfill must not be able to reach it.

## 2. `willow-2.0` — what a machine may ratify by itself

`core/ratification.py` is a pure classifier over a pending record, returning
`evidence_based` (safe to auto-ratify) or `judgment_based` (requires human
triage). Its rules, in its own order:

* `tier == "canonical"` → always judgment
* category in `{correction, architecture, decision, canonical}` → judgment
* source containing any of `{correction, feedback, preference, sean}` → judgment
* source containing any of `{code, drift, test, ci}` → evidence
* tier in `{fetched, verified}` **and** `confidence >= 0.90` → evidence
* default → **judgment**

Two things are worth naming. The operator put **his own name in the judgment
set**, so anything sourced from him forces a human. And the default is judgment,
so the classifier fails toward the person. Both are the right instinct.

The gap this package closes is the fifth rule: a **confidence number** is one of
the routes by which a machine may confirm without a human. `0.90` there and
`SEAL_THRESHOLD = 0.92` here are not the same kind of number, and the difference
is the whole design. This package's threshold decides whether two *texts* match.
It has never decided whether something is *verified* — see the README's *"not as
a confidence score, as a structural fact you can audit."*

## 3. `willow-2.0` — the clause itself

`constitution/cases/const_0_2_ratify.py`, quoting §0.2, the eternity clause:

> No agent may promote its own output from proposal to canonical knowledge.
> Proposing and ratifying are separate authorities … An agent may propose
> without limit; it may ratify nothing it authored.

and, on the mechanism:

> A record that merely *claims* `tier: ratified` is DOWNGRADED to `verified`
> unless an attestation the proposer cannot mint for itself already exists
> (`core.intake_promote` + `_ratified_is_attested`, which fails closed: no
> attestation, no reachable DB, no table => not attested).

That is this package's covenant and this package's seal check, stated first and
stated elsewhere. *"A record that merely claims"* is the same sentence as the
README's *"a row that merely **says** `sealed` in the database is not served"*.
The fail-closed enumeration is the same discipline as `is_verified_seal`. And
the file is a **compliance probe** that attacks the real gate read-only to prove
a self-declared canonical record is not honoured — which is what this repo calls
proving a gate by mutation.

`ratification.py` is wired into roughly twenty files and has tests. It shipped.

## 4. `Jeles` — the corpus without a key

Covered in full by `recipes/jeles_bridge.py`; here only for its place in the
sequence. Three rungs again (`human` / `machine` / `asserted`), a rank-based
overwrite guard, and **no confidence score at all**. What it lacks is the
binding: `put_nugget`'s own docstring says *"`verified_by` is a claim: whatever
string the writer supplied."*

---

## The sequence

Each version removes a way for a machine to confirm.

| | how a machine can confirm | what binds a confirmation |
|---|---|---|
| **willow-1.9** | a migration writes `confidence = 1.0` over unchecked rows | nothing |
| **willow-2.0** | auto-ratify for evidence; `confidence >= 0.90` is one route; but `ratified` needs an attestation the proposer cannot mint | an independent attestation record |
| **Jeles** | it cannot — no auto-verification path | nothing; `verified_by` is an unsigned string |
| **nestor** | it cannot, at all, by any route | a signature over a key the store does not hold, in a hash chain |

Two things fall away across it. The **number** goes: scored in 1.9, a
ratification route in 2.0, absent in Jeles, and refused here for verification
status. And the **vocabulary shrinks back**: 1.9 names three tiers, 2.0 grew to
at least six in use (`canonical`, `observed`, `verified`, `validated`,
`hypothesis`, `fetched`), and this package pins three and gates the list.

## What this package actually added

Not the rule. The rule is `const_0_2`.

What is new here is **surface area, and binding**. §0.2 is correct and it is
buried in a repository with a knowledge graph, an MCP server, a skill system, a
journal, agents and a constitution. This package is that clause with everything
else removed until it could be made small enough to be checked: one loop, three
states, no runtime dependencies, and a covenant that fits in a four-row table.

And where §0.2 requires *an attestation the proposer cannot mint*, this requires
a **signature over a key the store does not hold**, appended to a chain that
indicts itself if edited. That is the same idea made cryptographic rather than
relational — a stronger claim, and one that survives leaving the database.

## Why this file exists

`IDEAS.md` §6's rule is that a thing raised in conversation and not written down
did not happen. This was raised in conversation on 2026-08-06, and the agent
that read those three repositories would otherwise have been the only thing that
knew the covenant had a birthday.

It also corrects a tone. Stating **you may propose, you may not confirm** as a
first principle invites the reading that it arrived whole. It did not. It was
arrived at four times, each time by removing something, and the earliest version
of it is a `UPDATE ... SET confidence = 1.0` that somebody had to write before
they could see why it was wrong.
