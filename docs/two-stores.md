# Two stores, one problem

*Round 2 of the jeles/Nestor exchange, 2026-08-06. Read against jeles at
`ed48de7` — the same revision [`covenant-lineage.md`](covenant-lineage.md) pins.*

**This is a reading, not a run.** Round 1
([`scripts/audit_against_jeles.py`](../scripts/audit_against_jeles.py)) could
execute its probes, because the thing under test was this package. This round
points the other way, and the only honest instrument for somebody else's design
is reading it with citations somebody can open. Every claim below names a file
and a line. None of it was produced by importing, running, or writing to jeles,
and nothing here has been filed on their side.

It was written expecting to find that jeles' corpus vouches for itself. Four
claims went in; **three were wrong**, and the fourth turned out to be the least
interesting thing on the page.

---

## What the round expected, and what is actually there

| expected | actual |
|---|---|
| `put_nugget` writes a human-verified nugget with no human | `verified_by` is **required**; the write is refused without it (`corpus.py:416`) |
| the `verification_kind="human"` default is a hole | it is documented as *"for in-process callers, which are the operator's own code"*, validated against `_KIND_RANK`, and pinned to `"asserted"` at the MCP boundary (`corpus.py:395-401`, `370`) |
| a lower rung can overwrite a higher one | refused, with the remedy in the message (`corpus.py:408`) |
| the corpus is not tamper-evident | true — and it is the least of it |

The `verification_kind` default falls the unsafe way and it costs jeles nothing,
because every path that a stranger can reach pins the rung explicitly. That is a
real difference from this package — `add_pair` defaults to `draft` — and it is
not the weakness it looks like from the signature alone.

---

## 1. The defect both repos hit, separately

`corpus.py:168-174`, on why the overwrite guard runs *inside* the write
transaction:

> The guard has to be in here rather than in the caller: a check that reads the
> prior record, returns, and only then writes is a read-modify-write with
> nothing holding the gap — **the same shape that lost 36 of 50 gap counts.**

That is this repo's recurring defect, in another repository, with a measured
cost attached. [`CLAUDE.md`](../CLAUDE.md) states it as:

> a condition checked in Python, guarding a write that cannot re-assert it

and records three criticals of that shape in one session, fixed the same way
each time — *the precondition in the `WHERE` clause*, and *two walks each bounded
by construction* rather than one walk with a filter. jeles' fix is the same move
in a different mechanism: the guard is a callable handed to `_put` and invoked
inside `with _write(conn)`, so the read and the write cannot be separated by a
caller who forgets.

Neither repo borrowed this from the other. Two codebases with the same author
and no shared code arrived at the same failure and the same correction, and both
wrote down what it cost. That is worth more than either fix.

---

## 2. Where they split

Both packages know that *who verified this* is unforgeable only if something
makes it so. They do different things about it, and each says so in its own
source.

**jeles keeps the fact beside the claim.** `corpus.py:403-405`:

> `verified_by` is a claim: whatever string the writer supplied. `written_by` is
> the fact beside it — which app actually made the write — and is what
> `to_search_hit` shows for an asserted nugget, **because a caller can type any
> name it likes into the first one.**

**Nestor binds the claim to a key.** `signing.seal_is_valid` accepts a seal only
under the key belonging to the verifier *named on it*, so an unknown verifier is
refused before the store is touched — measured in Round 1: `verifier=""` under a
keyring raises `UnknownVerifierError`, rendered `'(empty)'`.

These are not competing answers to one question. They are answers to two:

| | jeles | nestor |
|---|---|---|
| who *claims* to have verified | `verified_by`, a string | `verifier`, a string |
| who *actually wrote it* | `written_by`, recorded beside | `origin`, recorded beside |
| can the claim be forged | yes, and the docstring says so | not under a keyring |
| can a past record be edited undetectably | yes — `INSERT OR REPLACE`, no chain | no — hash-chained ledger |
| does the caller learn what really happened | **yes** — see §3 | **no** — see §3 |

The last row is the one that goes the other way, and it is the reason this round
was worth doing.

---

## 3. jeles is ahead on receipts, and it is the gap this package already had open

Two places where jeles tells a caller something this package does not.

**The rung comes back.** `corpus.py:466`:

> The kind comes back in the receipt: **a caller that asked for one rung and got
> another should not have to re-read the record to find out.**

**A refused argument is named.** `conflict_scan.py:386` — an argument outside the
allow-list "produces an error receipt naming what was refused. It is **not
silently dropped**, and it does not stop the rest of the list."

[`IDEAS.md`](../IDEAS.md) §6.44 is exactly this, found from the other direction
one round earlier: `nestor_propose` discards `status`, `verifier` and
`verification_kind` and returns an unqualified success. The escalation fails,
which is the part that matters, and the caller is not told. Two independent
routes to the same finding, and jeles got there first.

There is a third, smaller one worth keeping. A soft-deleted id looked absent to
`_get`, so a write reported `"created"` while landing on a tombstoned row no
reader would return. jeles did **not** refuse it — refusing "would let anyone who
can soft-delete a record permanently deny the id" — and instead reports
`updated_tombstoned` (`corpus.py:189-196`). That is the shape this package keeps
reaching for and does not always reach: when a guard would create a worse
failure, say what happened rather than adding a condition.

---

## 4. What this package should take, and what it should not

**Take:** the receipt discipline. §6.44's fix is to name the discarded keys, and
jeles has now demonstrated the same rule twice in two different mechanisms. That
is corroboration in the sense this repo's own `count_countersignatures.py` cares
about — two independent observations, not one repeated.

**Do not take:** the rung ladder. `_KIND_RANK = {"asserted": 1, "machine": 2,
"human": 3}` is a good fit for a corpus fed by search results, where a
machine-corroborated finding is genuinely a middle state. This package has three
states on a *different axis* — `sealed` / `draft` / `pending` describe whether a
human has decided, not how strong the evidence is — and
[`seal-staleness-and-quorum.md`](seal-staleness-and-quorum.md) §4 already argues
that a second tier under `sealed` is the wrong shape: *sub-quorum is not a weaker
seal, it is not a seal.* Importing a ladder would give `sealed` a silent second
meaning, which is the one thing the three states exist to prevent.

**Not settled here:** whether jeles wants a chain. It has `INSERT OR REPLACE`
semantics, a rung guard and tombstone reporting, which is a coherent design for
a corpus that is rebuilt from sources. A hash chain answers "was this edited",
and nothing in jeles claims to answer that, so the absence is a tradeoff rather
than a gap. Saying otherwise would be this package grading another one against
its own product pitch.

---

## What would settle the open question

§6.44's fix — naming the discarded keys in `nestor_propose`'s reply — is a wire
contract with any MCP host, so it is a change to make deliberately and not
inside an audit branch. jeles has already paid for the design twice. The
remaining work here is choosing the shape: an `ignored: [...]` field beside the
existing note, or a refusal. jeles chose the receipt over the refusal, and gave
its reason: it "does not stop the rest of the list."
