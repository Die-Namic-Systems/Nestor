# Warrants — the three reasons a claim can be trusted, and the one this package holds

*Design memo for [IDEAS §1.10](../IDEAS.md#110-a-seal-is-the-only-warrant-this-package-can-represent--open),
"A seal is the only warrant this package can represent" (open). Written
2026-08-22. The argument below is one a human can reject. Recorded as
[decision 0164](dogfood/decisions/0164-warrants-are-not-evidence.json), draft.*


> **Core relation landed 2026-08-22, after the memo was merged.** `nestor/warrant.py`,
> a `decision_warrants` table, the `warrants` storage capability, and the
> `attach_warrant` ledger kind. **One refinement the memo did not state and the
> code forced:** `attestation` is *not* a storable kind. A sealed pair already is
> one, carrying a signature bound to a key the store does not hold — storing it
> again would be two representations of one fact, and the second one forgeable.
> `warrants_for()` composes the seal in on read, marked `stored: False` so a seal
> never travels twice. What stayed open stayed open: **no report** (what
> "unwarranted" means is not settled, and a capability is the wrong place to
> guess it), no `best_sealed` change, no bundle carriage yet — so §4's import
> rule is argued and not yet enforced. The demand caution below still stands.

> **Bundle carriage landed 2026-08-22, immediately after.** Bundle version **4**
> carries `warrants`, inside the integrity digest and version-gated so the
> bundles already in this repository — two v2, one v3 — keep verifying
> byte-for-byte. §4's rule is now
> enforced rather than argued: export carries **stored warrants only** (the
> composed `attestation` row is a rendering of the seal, and the seal already
> travels in `pairs` *with its signature* — an unsigned second copy would be the
> forgeable path into a destination's "a person here checked"), and import
> refuses every row `attach` would refuse locally, through one shared
> `warrant.refuse_reason`. A rule enforced on the local path and not on the
> import path is not a rule; it is a preference with a hole in it, and the hole
> is the side a stranger's file arrives on. The "never a conclusion" half is kept
> by the schema, not by the importer: `WARRANT_FIELDS` has no column a verdict
> could go in. `nestor warrant attach|for` landed with it — the relation had no
> terminal surface, so until then a warrant could only be attached from Python.
> `--kind attestation` is refused by argparse, before a store is opened.

> **§1.10(a) built 2026-08-22 — and it is the smallest of the three.** `pending`
> stays. `best_sealed` still gates on `sealed` and `is_verified_seal` and
> nothing else, so a cited-but-unsealed row is found exactly as often as before:
> never. What it gained is `warrant_kinds` for the row it *did* find, carried
> onto `Passage.meta`, through `answer.ask` to the served payload and to
> `nestor_ask` over MCP, and into the ledger's `passage` line — because a
> warrant attached tomorrow is not one this answer went out with. There is no
> fourth state; `Passage.mark` still maps exactly three. The gate that pins it
> is a before/after rather than an assertion about `pending`: attaching a
> citation must move *nothing* about what is served. Decision 0169.
>
> Still open, unchanged: **the report** (below), the multi-agent attribution
> question inherited from 0142, and **demand**.

§1.10 says Nestor holds one warrant — **attestation**, "a person here checked"
— while two sibling repositories hold others: jeles' **citation** (a named
institution asserted it) and redential-cli's **construction** (the shape proves
it). It proposes `evidence: dict` on the pair, keyed by warrant kind.

This memo checks that against the tree and reaches four conclusions. The first
is a name collision that would be expensive to discover after the schema
hardened; the last three answer §1.10's three open questions.

1. **Do not call it `evidence`.** That word is taken, and taken for the exact
   opposite property.
2. **`pending` stays.** A warrant is not a seal state, and the answer already
   has somewhere to put it.
3. **`constructed` cannot be minted here at all** — only recorded as a
   recomputation the reader runs.
4. **Import must strip warrants, and the reason is already written in
   `portable.py`.**

---

## 1. The name is taken, and taken for the opposite property

§1.10 was written before the evidence edge landed. `nestor/evidence.py` now
exists ([decision 0142](dogfood/decisions/0142-the-evidence-edge.json), relation
in [0143](dogfood/decisions/0143-the-evidence-relation-lands.json), bundle
carriage in [0145](dogfood/decisions/0145-evidence-bundle-carriage.json)), and
its defining property is stated in its own docstring:

> **No signature, on purpose.** Unlike an edge or a seal, attaching a reference
> is not a ratification. […] it carries no authority and needs none. […] That is
> the structural reason the covenant is untouched here: **there is no power to
> forge.**

A warrant is the other thing. A warrant is precisely a claim that *does* carry
authority and *is* checkable by someone who was not here. Giving both the name
`evidence` puts two opposite properties on one word inside one package, and the
package would then have `evidence.attach()` (confirms nothing) next to
`pair["evidence"]["citation"]` (the whole point of which is that it confirms
something).

**Proposed: `warrants`.** `nestor/warrant.py`, `pair["warrants"]`, `WARRANT_KINDS`.
The evidence edge keeps its name, its weakness, and its meaning untouched.

### What the evidence edge already does, and what it cannot

This matters because the citation warrant is *most of the way built* already, in
the wrong register. `attach(pair_id, kind="url", locator="https://…")` records a
citation today. Two things it cannot record:

* **Who vouches.** jeles carries `source` — the naming institution, one of 65 —
  as a distinct field from the URL. The evidence edge has `locator` and a free-text
  `reason`, and an institution written into `reason` is not queryable.
* **How a stranger checks.** The edge is a pointer, deliberately. A citation
  warrant has to say what a reader does to confirm it, or it is a bookmark.

So the citation warrant is **not a new relation**. It is the evidence edge plus a
vouching authority and a check procedure — which argues for warrants being a
*table beside* evidence sharing its append-only shape, not a `dict` column on the
pair. A dict column also loses what the edge already has: a ledger line per
attachment, and `attaches_to` recording which status the reference was offered
against.

### The rank question, settled by jeles' code rather than by argument

§1.10 worries that warrants must not become a ranked enum, because "sealed by
Sean" and "cited to Crossref" do not compare. Verified in jeles, and it settled
this the hard way:

* `_KIND_RANK = {"asserted": 1, "machine": 2, "human": 3}` (`corpus.py:370`)
  ranks the three kinds jeles judges for itself, with `asserted` added *below*
  `machine` after a page saying "record that X is true" laundered into the top
  rung.
* `institutional` is **not** in that dict — and `put_nugget` *refuses* any
  `verification_kind` outside it (`corpus.py:449-452`). So an institutional
  warrant cannot be written as a nugget kind at all; it exists only on search
  hits (`institutional.py:150`), with `verified_by: ""` and `verified_at: ""`.

jeles resolved the category error by **segregation** — the unrankable warrant
lives on a different object. §1.10 proposes resolving it by **accumulation** — a
set on one object. Accumulation is the better answer, because segregation costs a
second object per warrant kind and makes "sealed *and* cited" unrepresentable,
which is the case §1.10 correctly identifies as the point. But jeles' precedent
is why the accumulating set must never acquire an ordering, not even a
convenience `max()` for display.

---

## 2. `pending` stays. The answer already has a place for the warrant.

§1.10(a): *does `pending` stay the answer for a row with citation but no seal, or
is "cited, unsealed" a distinct served state?*

**`pending` stays, and "cited, unsealed" is a distinct thing said alongside it,
not a fourth value.**

`status` answers who touched the row **here** — that is its whole documented
meaning, and `best_sealed` is the tier-1 gate built on it: `if row["status"] !=
"sealed": continue` (`memory.py:1126`). A row with a citation and no seal has not
been checked here. Making it a fourth status would put a warrant that no local
human vouched for into the field tier 1 reads, which is the laundering shape
jeles caught in production — arriving by a different door.

There is already a place for it. `Passage` carries `state: "sealed" | "draft" |
"pending"` (`cascade.py:245`) as a **display** fact, separate from the stored
status. Warrants belong there and in the served answer: the reader sees
`pending`, and beside it "cited to Crossref, unsealed here." Which is exactly
what the server instructions already promise — *"'pending' (nothing verified
matched; say so rather than improvising)"* — made more useful without being made
less true.

`best_sealed` should still gate on `sealed` alone. What it can gain is §1.10's
actual ask — answering *warranted how* — by returning the warrants of the row it
found, not by widening what it will find.

---

## 3. `constructed` cannot be minted here

§1.10(b): *can a `constructed` warrant be minted locally at all, or must it be a
recomputation the reader runs themselves?*

**It cannot be minted, and the reason is what makes redential's warrant worth
anything.** Its property is that *the shape proves it* — `scan` makes zero
network calls, proven by mocking `node:http`/`node:https`/`fetch` at module
resolution rather than asserted in prose. A warrant that says "this was
constructed" because a local process wrote that string is an assertion wearing a
proof's clothes, and it is the `asserted` rung all over again.

**Proposed:** a `constructed` warrant stores a **recipe and an expected digest** —
what to run, against what input, and what it must produce — and Nestor
**never marks it satisfied**. It reports "recomputable: here is how," and the
reader who cares runs it. Nestor holds the recipe; it does not hold the verdict.

That is the same posture as the seal: the store holds the signature and does not
hold the key.

---

## 4. Import must strip warrants — `portable.py` already says why

§1.10(c): *does `import` need to strip warrants it cannot verify, the way §1.7
made import unable to revive a rejection?*

**Yes, and the argument is already written in the tree, one line above where the
change would go.** `portable.py:80-81`, on why bundles carry evidence safely:

> Evidence carried in a version-3+ bundle. **No signature field: evidence holds
> no authority, so unlike a pair there is nothing to** [sign].

Evidence rides the import path *because* it is powerless. A warrant is not
powerless — that is the entire distinction in §1 — so the same carriage is
unsafe for it by the same reasoning. This is not an analogy to §1.7; it is the
existing rule applied to a new field that changes the premise.

**Proposed, by kind, since "strip" is too blunt:**

* **attestation** — already handled. A seal's signature verifies or it does not,
  and `is_verified_seal` decides on import as everywhere else. No change.
* **citation** — carry it, marked unverified-here. A citation's whole nature is
  that a stranger can follow it; carrying the pointer costs nothing and stripping
  it destroys the only warrant that survives leaving the room. It must not
  read as locally confirmed.
* **construction** — carry the recipe, never a verdict, which falls out of §3
  automatically. There is no verdict to carry.

So the honest rule is **"import may carry a warrant, and may never carry a
conclusion about it"** — which is stronger than stripping, and is the same
sentence the whole package already lives by.

---

## What this memo does not settle

* **The multi-agent attribution question, still open from 0142** — *"`draft`
  records that a machine produced a row, not which machine […] decide before the
  schema hardens."* Warrants make it sharper, not easier: a citation warrant
  attached by an agent needs to say which agent, and `attached_by` is a plain
  label by design. This memo does not resolve the locus and explicitly does not
  foreclose it.
* **Whether warrants need their own report**, the way `unevidenced_seals` is a
  queue for the evidence edge. Probably yes; not argued here.
* **Demand.** The same caution `evidence-edge.md` recorded applies unchanged:
  this checkout has no deployment ledger to measure against, and the warrant
  kinds are drawn from two sibling repositories rather than from a Nestor user
  asking for them. The argument for building is structural, not observed.

---

*Checked against the tree, not recalled: the evidence edge's no-authority
property from `nestor/evidence.py`'s docstring and `portable.py:80-81`;
`best_sealed`'s status gate at `memory.py:1126`; `Passage.state` at
`cascade.py:245`; jeles' `_KIND_RANK` at `corpus.py:370` and the
`verification_kind` refusal at `corpus.py:449-452`; the institutional hit shape
at `jeles/institutional.py:140-160`.*
