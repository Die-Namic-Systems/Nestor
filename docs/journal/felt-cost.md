# Felt cost — one sentence, read closely

The operator said one thing about friction in an eight-hour session. Not a bug
report, not a review — an interruption, mid-flow, in irritation:

> *"do you realize how much friction there is in me having to wait 5 minutes for
> you to run a test on a test between every prompt"*

This memo takes that sentence apart and asks what it implies about how Nestor
feels to use right now. §4 is the part that says what cannot be concluded from
it, and it is not a formality.

---

## 1. What is in the sentence

**"do you realize"** — they had to ask. Four consecutive rounds had gone by. The
cost was being paid every turn and was visible to exactly one of the two parties.
Nothing in the system surfaced it: no timer, no warning, no line in any output.
The only instrument pointed at it was the operator's patience, which is the
instrument §6.100 identifies as the sole detector for that whole class of defect.

**"in me having"** — the cost lands on the human. This is worth stating flatly
because the machine's costs are all instrumented and the human's is not. A run
records its wall time, its row counts, its digest, its chain head. Nothing
records that a person sat still for it.

**"having to wait"** — waiting, not working. Not *"this is slow"* but *"I am
blocked."* The agent had made the operator's next move depend on the agent's
current one, which is a structural choice and was not theirs.

**"5 minutes"** — see §2. The number is the interesting part.

**"a test on a test"** — the sharpest phrase in the sentence, and the one that
is about Nestor rather than about the agent. Not *"running tests"*. A test **on**
a test. Verification of verification. That is not a description of a slow suite;
it is a description of recursion that does not advance. And it is, structurally,
what this package is: a mechanism for checking whether a thing was checked, with
a ledger that verifies itself, a gate over the store, and a gate over the gate.

**"between every prompt"** — per-interaction, not per-session. The tax is not
amortised over the work; it is charged at every step.

---

## 2. The measured number and the felt number differ by about three times

The full suite ran between 96 and 114 seconds across four runs that day. The
operator said five minutes. Both are right, and the gap is the finding.

The suite is not what they waited through. A turn was: the agent thinking, four
to eight tool calls, a store rebuild, a re-import, a commit, a push, and a
written reply — with the suite somewhere in the middle. Three to five minutes is
a fair account of that. **The instrumented number measured the part the machine
cared about; the felt number measured the part the operator lived through.**

This repository already knows the shape of that error. `quick-stupids` states it
as a rule — *"state the aggregation whenever you quote a statistic"* — after a
rank correlation reached four documents without saying what it was grouped by,
and a reviewer reproduced a different figure and concluded the first was wrong.
Both were right. Same here: 100 seconds and 5 minutes are different aggregations
of the same wait, and only one of them has an instrument.

**Nestor measures provenance exhaustively and measures its operator not at all.**
There is no field anywhere in the store for what a decision cost the person who
made it.

---

## 3. What it implies about the experience, today

Stated as inference, with the state that supports each one.

**The ceremony is fully priced and the payout has not started.** At the end of
the session the live store held **300 pairs, 0 sealed**. Every gate ran, every
chain verified, every digest matched, every decision was recorded as a draft. Not
one answer was served as verified, because serving requires a seal and sealing is
a human act that never happened. The operator has paid the entire cost of a
verification system and has so far received the thing a filing cabinet gives you.

**The one act reserved for the human is the one the session never reached.** The
covenant — *you may propose, you may not confirm* — means the human's role is to
seal. Across eight hours, the human was asked to wait many times and to seal
none. Their contribution was routed into `docs/dogfood/decisions/` as drafts
about their own judgment, which is a record *of* their authority rather than an
exercise of it.

**"A test on a test" names the product's own recursion, not just the agent's
habit.** The agent chose the maximal gate every time, and that is §6.100. But the
phrase lands because the recursion is real and shipped: a ledger that verifies
itself, `--verify` over the builder, a gate over the write gate, and a test named
`test_corpus_readers_fail_closed` guarding the readers that fail open. A user who
is being asked to wait on that recursion, without yet receiving an answer from
it, is describing it accurately.

**And it is close, which is why it is irritating rather than dismissible.**
§6.106 measured the correct row at **rank 1 of 263** for two of three
content-bearing questions. The store nearly answers. What stands between it and
answering is a signature and a calibrated bar, neither of which is a large piece
of work. Frustration of this shape usually attaches to things that almost work.

---

## 4. What cannot be concluded from it

This is one sentence, said once, in irritation, and it was **about the agent's
behaviour, not about the product**. They were objecting to how a session was
being run. Every inference in §3 extends that to how Nestor feels to use, and
that extension is mine, not theirs.

The reason to flag it rather than nod at it: this same session logged two
findings about precisely this error. §6.104 — quoting a table from the top of a
feeder's output and missing the paragraph below it that disproved it. §6.106 —
inspecting one probe's top five and telling the operator the store could not
retrieve its own answers, when the right row was rank 1 for two of three. Both
were *stop at the first plausible reading, assert the general case*, ninety
minutes apart. A memo inferring a user's felt experience of a product from one
sentence about something else is the same move a third time, and saying so is the
only honesty available, since no third observation exists to check it against.

The counter-evidence is worth as much as the sentence and is easier to overlook,
because it is behaviour rather than words: they kept going. After the complaint
came four more loops, another survey, a request to log the gaps, a request to
commit everything that needed to survive, a pull request, and two more documents.
Nobody spends an evening that way on something they have written off. **The
statement is not a verdict on Nestor. It is what being invested in something that
has not paid out yet sounds like.**

---

## 5. The one thing to change, if only one

Not the suite runtime; that is §6.100 and it is bounded. The thing this sentence
actually points at is that **the store has never once answered a question for the
person who filled it.** Three hundred rows, none sealed, none served.

The shortest path from here to a first served answer is one human sealing one
row, on a question whose right answer is already rank 1, with a bar calibrated
for the matcher that keyed it. That is not a roadmap. It is the smallest thing
that would turn the sentence above from a description of cost into a description
of price.
