# Public-sector audience and the checkable covenant

Not a reference doc — a working record. The reference tree should not carry
strategy notes; strategy notes should not sit in a PR that says it fixes a
bug. Both stay honest by being kept apart, and that is what `docs/journal/`
is for.

Written on 2026-08-25 while PR #205 was still merging — the read is fresh
and the code claims made below are marked *verified* or *asserted*
individually, because otherwise a strategy note turns into a pitch, and a
pitch is what Nestor exists to refuse from itself.

Deliberately name-free and org-free. The read below is about the *shape*
of a market and audience, not about any particular person's calendar or any
particular organisation's roadmap; the specifics belong in a private note
the operator keeps offline. Any concrete introduction, meeting, or
collaboration this note motivates is out of scope for a git-tracked
document.

---

## 1. The audience shape

A public-diplomacy-style speaker rotation — an expert on AI sent by a
national government to speak with foreign ministries, national AI strategy
offices, university policy centres, and tech regulators on their soil, over
the length of a contract. The topic list on those rotations is standard:
responsible AI, innovation ecosystems, digital transformation, technology
commercialization, workforce development.

That is not procurement. It is a room full of people who will have to
*decide whether their institution adopts something like Nestor*, and who
therefore have a governance question first and a feature question second.


## 2. Why the governance question maps onto Nestor's covenant

The rooms above have three recurring questions no product-side pitch can
answer for them:

- *"If we adopt AI in a ministry, how do we not lose the ability to say
  what we said?"*
- *"When an assistant or a translator produces a policy sentence, who
  verified it, and can we audit that later?"*
- *"Can we run this without the model provider seeing our text?"*

Nestor's one-sentence answer — **"has a human checked this?"** — with a
hash-chained ledger, per-verifier attribution, and a *refuse-to-serve-what-
isn't-verified* covenant, lands differently in that room than it does in a
devtool review. It is not a feature list; it is the answer to a question
that room already has.


## 3. What was actually verified, and what was asserted

Because it matters for a pitch shape, the operator drew the line
explicitly. This is that line, kept in one place so the pitch does not
silently drift.

### Verified from runs done during the session that produced this note

- **Hash-chained ledger.** `docs/dogfood/nestor.db.ledger.jsonl` rows carry
  `"prev": "<sha256>"` linking to the previous entry. Quoted shape from
  `git diff docs/dogfood/nestor.db.ledger.jsonl` on 2026-08-25:
  `{"ts": "...", "prev": "aafbe5b1a91b...", "kind": "entity_resolve", ...}`
  (full 64-hex `prev` truncated for the secret-scanner).
- **Refuse-to-serve-what-isn't-verified.** `nestor --json ask ... --engine
  offline` returned `{"passage": {"state": "pending", ...}, "verified":
  false, "threshold": 0.92}` when the top match sat below 0.92.
- **Per-verifier attribution exists in the schema.** `nestor/memory.py:574`
  signature `def add_pair(source_text, target_text, source_lang, target_lang,
  status="draft", verifier="", ...)`.
- **Seal bar for this corpus is 0.92.** SessionStart hook: *"seal bar 0.92
  (context 0.55)"*. Also visible as `"threshold": 0.92` in ask/match JSON.
- **Default translation domain is `en → es`.** `nestor/domain.py:31`:
  `DEFAULT_SOURCE_LANG, DEFAULT_TARGET_LANG = "en", "es"`.
- **Dogfood corpus is `decision → decision`, not `decision → commitment`.**
  `nestor stats` printed *"domains: decision→decision (519)"* on
  2026-08-25. Individual sealed rows in tests use `decision → commitment`;
  the shipped dogfood corpus's aggregate header does not.

### Asserted in-session, not verified — must not go into a pitch unchecked

- *"Local-first, no phone-home."* The SessionStart tag *"LOCAL-FIRST SEAT"*
  is about the workflow this seat runs, not a network-egress guarantee. No
  test in the tree currently asserts Nestor opens no socket to anything
  but the local ledger and store. If we want this claim in the pitch, it
  has to become a checkable one first — a test that would fail if the
  process called out to anything else.
- *"Air-gap friendly."* Same shape. Assertion, no gate.
- *"Sovereign deployment."* Same shape. Assertion, no gate.

The exact defect Nestor exists to catch is the drift from *"probably true"*
to *"stated as fact"*; this section is here so the pitch does not do that
about the product it is a pitch for.


## 4. What we might build toward, ordered by leverage

Not commitments — a menu the operator picks from. Each item is one shipping
unit (its own PR, its own decision file).

1. **Sovereign-deployment claims made checkable.** A test file that gates
   the pitch claims we currently cannot make. What sockets does Nestor
   open during a full CLI/UI/serve session? Which of them can be pointed
   at localhost? Which are required for what recipe? Answer each with a
   test that names the boundary — the pattern
   `tests/test_corpus_extractors_git_scoped.py` established for
   §6.101/§6.102 and `tests/test_corpus_boundary.py` established for
   #97. **Order first because §3 makes every item after it easier.**

2. **A policy-audience one-pager** at `docs/policy-brief.md` (or similar).
   Audience is a non-engineer chief-of-staff or a procurement officer,
   not an operator. The argument: verifier attribution + ledger + refusal
   covenant + (once §1 lands) sovereign posture = *AI a ministry can
   defend using*. Distinct from the operator guide and the README.

3. **A demo store that speaks the audience's language, literally.**
   `nestor demo --seed policy` or a new subcommand seeds a small
   `en ↔ es` (and maybe `pt ↔ es`) store with policy-shaped sealed
   pairs: a treaty phrase → verified translation, an entity like
   *international body → canonical name*, a numeric baseline like a
   national statistic with a tolerance. When the demo is opened on stage
   in front of a policy audience, they see their own subject matter, not
   `"buenas noches"`.

4. **A 90-second transcript walk-through.** Scripted: a model proposes an
   answer → `nestor ask` returns **pending** because nothing verified
   matched → `nestor_propose` queues it → a human seals it in `nestor
   ui` → next `ask` serves verified with the human's name attached. The
   argument for the covenant, told in commands and screenshots, not
   adjectives. Lives at `docs/walk-through-covenant.md` or as a `demo/`
   runnable script — probably both.

5. **Multi-language matcher story.** The current dogfood corpus is
   `decision → decision`; the shipped translation surface handles
   arbitrary domain tags. A short doc showing `en ↔ es`, `en ↔ fr`,
   `en ↔ ar` with sealed policy examples would let the demo pick a
   language for the room it is actually in. Not blocked on §1 but reads
   much better after §3.


## 5. What is needed before item 3 or 5 gets scoped

Answers to the following would sharpen the sequence, but none of them are
questions this note can answer:

- **Is the audience being handed what we built, or the elevator pitch?**
  A one-pager and a policy demo are two different asks, and the
  sequencing changes accordingly.
- **What is the first region on the schedule?** LatAm makes `es ↔ en` the
  demo priority; MENA is a different story; a global tour means the demo
  has to be language-neutral (which pushes item 3 further out and item 4
  further forward).
- **What shape are the first engagements?** A briefing at a foreign
  ministry, a keynote at a national AI strategy event, and a procurement
  pilot are three very different shapes; they each want a different first
  artifact.

Those questions are for the operator to run separately. This note is here
so that when answers come back, the sequencing in §4 is already argued out
and we are not re-deriving it from a message.


## 6. What is not in this note

- **A commitment.** Nothing here is sealed. Every item in §4 is a
  proposal; the operator picks or declines.
- **A market claim about government adoption.** Section 2 is the
  operator's read of Nestor's covenant against the shape of audience
  described in §1. Neither has been checked against a real procurement
  conversation yet. When one happens, this note gets a §7 with the read
  from the room.
- **Any named person or organisation.** By construction. Names, calendars,
  private messages, and collaboration specifics belong in a private note
  the operator keeps offline. What survives here is the *shape* of the
  argument and the code claims it depends on, both of which are
  properties of Nestor itself.
