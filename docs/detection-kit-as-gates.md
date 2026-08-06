# The detection kit as gates, not advice

*Design memo for [`IDEAS.md`](../IDEAS.md) §6.12. Written 2026-08-06. No code.*

§6.12 asks how much of Sagan's baloney-detection kit (*The Demon-Haunted World*,
ch. 12) can become **exit codes** the way `nestor ledger verify` made "is the
chain intact?" into one — and observes that the kit shipped as a book chapter
while the injection side shipped as infrastructure.

The answer is: four of the nine already are, two are blocked on data Nestor
throws away, and three cannot be gated at all. The third group is the one worth
writing down, because a gate that claims to check a thing it cannot check is
itself an item in the catalog.

*Numbering follows §6.12's, which independently placed five of the nine and
agrees with this list at every position.*

---

## The constraint that decides most of it

A gate reads a **record**. The kit governs **reasoning**. Those overlap only
where a piece of good reasoning leaves a structural trace — and the whole
exercise is finding which ones do.

`nestor ledger verify` is the exemplar precisely because "every link in the
chain holds" has an exact structural shadow: a hash chain either verifies or it
does not, and the check needs no opinion about whether the arguments *in* the
chain were any good. Where a tool has no such shadow, the honest output is not a
weaker gate. It is no gate.

Nestor already spends more of its exit-code budget on this than §6.12 credits.
Seven commands return `EXIT_ANSWER_IS_NO` (`1`) rather than printing a caveat —
`ask`, `resolve`, `check`, `match`, `import`, `ledger`, `calibrate`
([`cli.py:46`](../nestor/cli.py) defines the three codes). "The answer is no" is
already a first-class result here, which is the precondition for any of this.

---

## Already an exit code

**#7 — every link in the chain must hold.** `nestor ledger verify`, and
`--expect-head` for a tip held outside the file. Shipped, and the model for the
rest.

**#9 — is it falsifiable, even in principle?** `reopen_when` on a rejection: a
refusal records the condition under which it stops being true. A "no" with a
trigger is a falsifiable "no"; a "no" without one is a permanent claim wearing a
decision's clothes.

Worth noting the repo already applies #9 to itself, in prose rather than in
code: *a test that passes before the fix is a description, not a gate*
(`CLAUDE.md`). That is falsifiability restated for tests, and it is currently a
commit-message convention rather than a check. It is the most plausible new gate
on this list — see below.

**#6 — quantify.** Better served than §6.12 suggests, which is why this memo
checked instead of assuming. `nestor calibrate` does not merely print a number:
`cmd_calibrate` returns `EXIT_ANSWER_IS_NO` when `result["recommended"] is
None`, i.e. when no cutoff on your corpus meets the target rate you asked for.
That is exactly the kit's move — a numerical quantity turned into a
discrimination — and it fails a build rather than advising one.

**#3 — arguments from authority carry little weight.** This looks like a
contradiction at first, because a seal *is* an argument from authority: the
answer is good because a named person said so. The resolution is that the kit's
complaint is not about deferring to people, it is about authority that certifies
itself. Nestor's per-verifier keys mean a seal is checkable evidence about
*which* person, and `NESTOR_REQUIRE_SEAL_KEY=1` turns "we could not tell" from a
warning into a refusal.

But state the limit precisely, because the gap is real: Nestor gates whether an
authority is **named and bound to a key**. It cannot gate whether that authority
is **knowledgeable**. Those are different properties, and treating the first as
evidence of the second is the fallacy the tool names. The keyring buys
attribution, not competence.

---

## Blocked on data Nestor discards — and blocked the same way twice

**#1 — independent confirmation.** Partly shipped: `nestor.frank` mirrors each
ledger line into a chain the local writer cannot reach, and `ledger verify
--expect-head` lets an operator hold the tip somewhere the deployment does not
control. Both are independent confirmation of the *chain*.

Independent confirmation of a *decision* is the thing missing, and it is missing
for a specific reason that turned up in the §1.4 memo: **a second verifier
sealing an already-sealed pair with the same target writes nothing, appends
nothing and raises nothing** ([`IDEAS.md`](../IDEAS.md) §6.26). Concurrence — the
literal object of tool #1 — is the one event Nestor does not record. A gate
asking "was this independently confirmed?" would return "no" for every pair in
every deployment, correctly and uselessly.

**#5 — do not get attached to a hypothesis because it is yours.** §6.12 maps
this to "verifier-differs-from-author", which is the right mapping and is not
implementable: **there is no author field.** `grep author nestor/*.py` returns
four hits, none of them a column, none of them a person. A draft records no
proposer.

Architecturally the separation is usually real — tier 2 is machine-authored,
tier 3 is human-verified, so author ≠ verifier by construction whenever an
engine wrote the draft. But nothing enforces it when a human writes one.
Measured: a draft entered with no verifier, then sealed by `rita`, is accepted
without complaint. Nothing anywhere says whether rita was also the person who
proposed it.

**These two are the same shape, and it is the third time it has appeared.**
§1.4's quorum question, §6.26's countersignature, and #1/#5 here are all blocked
on the same thing — Nestor records *decisions* thoroughly and *the process that
produced them* not at all. That is a coherent design choice, not an oversight;
it is why the ledger is small enough to verify. But it means a whole class of
detection-kit gates is unavailable until some of that process is written down,
and adding an author column for the sake of a gate would be a field carrying a
distinction the mechanism does not otherwise make — §6.17's warning, again.

---

## Not gateable, and saying so is the point

**#2 — substantive debate among knowledgeable proponents of all points of view.**
Not merely unmapped. Nestor is built to make recorded disagreement *impossible*:
`ConflictingSealError` refuses the write when two verifiers assert different
targets for one source. That is correct — the alternative is two live sealed
rows and no way to say which serves, which is the race the partial unique index
exists to close (§1.8) — but the consequence is that the store can hold a
decision or a refusal and never a live disagreement. Debate happens in the UI,
in review, in conversation, and none of it lands.

A gate here would have to check that something happened somewhere the system
cannot see. There is no honest version.

**#4 — spin more than one hypothesis.** §6.12 maps this to `nestor decision
check`, which does not exist: the CLI's subcommand list is `ask, resolve, check,
match, export, db, import, ledger, calibrate, keys, rejections, stats, ui,
serve`, and there is no `decision` among them. §6.11 records decision memory as
**partly** shipped — steps 1–2 — and the CLI surface is one of the steps that
was not. The mapping was written against a planned command.

There *is* a structural shadow:
`revise_draft` keeps the superseded proposal with its reason, and
`supersede_pair` keeps lineage, so a pair's history can show that more than one
answer was considered. But a gate is the wrong instrument, because the absence
of lineage is not evidence of a failure — most pairs are right the first time,
and a build that failed on "only one hypothesis was recorded" would fail on
every correct answer in the corpus. This is a **listing**, not a gate: the same
conclusion the §1.4 memo reaches about staleness, for the same reason.

**#8 — Occam's razor.** Permanently ungateable, and this is the most useful row
in the table. There is no mechanical test for "simpler", and any check claiming
to enforce parsimony would be a number standing in for a judgement — which is
the substitution the entire kit is written to catch. A gate for #8 would be
baloney about baloney detection. The right output is this sentence, in this
file, rather than a metric nobody can defend.

**The fallacy catalog** goes the same way. It is a list of argument shapes, and
arguments are not what Nestor stores.

---

## The one gate worth building

Not from the kit's list directly, but from #9 applied to this repo's own
practice: **a test that cannot fail is a description.**

`CLAUDE.md` requires running every new test against the unfixed revision and
recording the split, and `IDEAS.md` §6.24 records two gates that caught the
author of `persona.py` while it was being written. Both are conventions enforced
by whoever remembers them — which is, precisely, a guarantee that only holds
where somebody thought to look (`TODO.md`'s closing note).

The mechanized version: for a change touching `nestor/`, run the new or modified
tests against `HEAD~1` and fail if none of them fail. That is falsifiability as
an exit code, it needs no new data, and it gates the one claim this repo makes
most often about its own work.

It is proposed here and not built, for the reason §6.12 exists: turning it on
would fail builds for legitimate reasons (a pure guard, a docs change, a
refactor with no behavioural delta) and the exemption rule wants designing
before the gate does. Recorded so it is a decision rather than a good intention.

---

## Summary

| # | Tool | Status |
|---|------|--------|
| 1 | Independent confirmation | **partly** — chain yes (FRANK, `--expect-head`); decision no, §6.26 discards concurrence |
| 2 | Substantive debate | **anti-mapped** — `ConflictingSealError` makes recorded disagreement impossible, on purpose |
| 3 | Authority carries little weight | **shipped, with a stated limit** — keyring gates attribution, not competence |
| 4 | More than one hypothesis | **listing, not gate** — lineage exists; absence is not failure |
| 5 | Not attached because it is yours | **blocked** — no author field; self-sealing a draft is accepted |
| 6 | Quantify | **shipped** — `nestor calibrate` exits 1 when no cutoff meets target |
| 7 | Every link holds | **shipped** — `nestor ledger verify` |
| 8 | Occam's razor | **never** — no mechanical test for simpler; a gate here would be the fallacy |
| 9 | Falsifiability | **shipped** (`reopen_when`); one further gate proposed above |
