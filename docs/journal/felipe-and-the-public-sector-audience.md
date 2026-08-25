# Felipe and the public-sector audience

Not a reference doc — a working record. The reference tree should not carry
strategy notes; strategy notes should not sit in a PR that says it fixes a
bug. Both stay honest by being kept apart, and that is what `docs/journal/`
is for.

Written on 2026-08-25 while PR #205 was still merging — the read is fresh and
the code claims made below are marked *verified* or *asserted* individually,
because otherwise a strategy note turns into a pitch, and a pitch is what
Nestor exists to refuse from itself.

---

## 1. What triggered this

A LinkedIn thread with **Felipe Castro Quiles**, screenshot-relayed by the
operator on 2026-08-25. Two lines matter:

> *"governments may actually be one of the strongest markets for this. Let me
> put together a couple of potential engagements and clean up my calendar, and
> then we can connect to discuss how we might collaborate"*
> — Felipe, in reply to the operator's mention of the Die-Namic-Systems org.

> *"So, a bit of full circle on this one. This started as that semantic
> translator I pitched you months back. It's Nestor now: the translation core's
> still in there, wrapped in the whole 'has a human checked this?' part. I've
> had sights on the bigger fish since I started this path, and I'm glad you
> can see the potential as well."*
> — the operator, in reply.

Felipe's newest role, from a LinkedIn Experience screenshot the operator
supplied:

> **U.S. Speaker Program Speaker — Artificial Intelligence & Innovation.**
> U.S. Department of State · Contract · Jul 2026 – Present · Worldwide · On-site.
>
> *"Selected to serve as a U.S. Department of State U.S. Speaker Program
> expert, representing the United States in international public diplomacy
> initiatives. Deliver keynote presentations, executive briefings, and
> strategic dialogues on artificial intelligence, responsible AI, innovation
> ecosystems, digital transformation, technology commercialization, and
> workforce development.*
>
> *Engage government, academic, and private-sector leaders worldwide in
> collaboration with U.S. embassies and consulates to strengthen international
> partnerships, innovation, and economic competitiveness."*

That is not USG procurement. That is a U.S. voice on AI walking into foreign
ministries, national AI strategy offices, university policy centres, and
tech-regulator meetings — on their soil, for the length of the contract.

His pre-existing profile (from `WebSearch` — his own sites returned
`EGRESS_BLOCKED` from this seat, so this is snippet-level, not full-page):
Puerto Rican, CEO of **GENIA Latinoamérica** (public benefit corporation
connecting LatAm and the Caribbean to AI research and development, since
2019), CEO of **Emerging Rule** (AI in K–12), Fellow at **Singularity
University**, speaker at **ITU AI for Good**, Advisory Board seat at
**Forbes AI**, certificates in ML from Stanford and **Global Diplomacy
from SOAS University of London** — so the diplomacy training is already
on file, and the State role fits an existing trajectory rather than
diverting one.


## 2. Why the room that role puts him in cares about Nestor

The rooms Felipe walks into next have a governance question they cannot
answer without an audit surface:

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

Because it matters for a pitch shape, the operator drew the line explicitly.
This is that line, kept in one place so the pitch does not silently drift.

### Verified from runs done during the session that produced this note

- **Hash-chained ledger.** `docs/dogfood/nestor.db.ledger.jsonl` rows carry
  `"prev": "<sha256>"` linking to the previous entry. Quoted line from
  `git diff docs/dogfood/nestor.db.ledger.jsonl` on 2026-08-25:
  `{"ts": "...", "prev": "aafbe5b1a91ba5699bf7379a849a12c4055f8c4603262e3fa53aeb065b3ccef1", "kind": "entity_resolve", ...}`.
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
  `nestor stats` printed *"domains: decision→decision (519)"* on 2026-08-25.
  Individual sealed rows in tests use `decision → commitment`; the shipped
  dogfood corpus's aggregate header does not.

### Asserted in-session, not verified — must not go into a pitch unchecked

- *"Local-first, no phone-home."* The SessionStart tag *"LOCAL-FIRST SEAT"*
  is about the workflow this seat runs, not a network-egress guarantee. No
  test in the tree currently asserts Nestor opens no socket to anything but
  the local ledger and store. If we want this claim in the pitch, it has
  to become a checkable one first — a test that would fail if the process
  called out to anything else.
- *"Air-gap friendly."* Same shape. Assertion, no gate.
- *"Sovereign deployment."* Same shape. Assertion, no gate.

The exact defect Nestor exists to catch is the drift from *"probably true"*
to *"stated as fact"*; this section is here so the pitch does not do that
about the product it is a pitch for.


## 4. What we might build toward, ordered by leverage

Not commitments — a menu the operator picks from. Each item is one shipping
unit (its own PR, its own decision file).

1. **Sovereign-deployment claims made checkable.** A test file that gates
   the pitch claims we currently cannot make. What sockets does Nestor open
   during a full CLI/UI/serve session? Which of them can be pointed at
   localhost? Which are required for what recipe? Answer each with a test
   that names the boundary — the pattern
   `tests/test_corpus_extractors_git_scoped.py` established for §6.101/§6.102
   and `tests/test_corpus_boundary.py` established for #97. **Order first
   because §3 makes every item after it easier.**

2. **A policy-audience one-pager** at `docs/policy-brief.md` (or similar).
   Audience is a non-engineer chief-of-staff or a procurement officer, not
   an operator. The argument: verifier attribution + ledger + refusal
   covenant + (once §1 lands) sovereign posture = *AI a ministry can defend
   using*. Distinct from the operator guide and the README.

3. **A demo store that speaks the audience's language, literally.**
   `nestor demo --seed policy` or a new subcommand seeds a small `en ↔ es`
   (and maybe `pt ↔ es`) store with policy-shaped sealed pairs: a treaty
   phrase → verified translation, an entity like *IMF → International
   Monetary Fund*, a numeric baseline like a national statistic with a
   tolerance. When Felipe opens `nestor ui` on stage, the audience sees
   their own subject matter, not `"buenas noches"`.

4. **A 90-second transcript walk-through.** Scripted: a model proposes an
   answer → `nestor ask` returns **pending** because nothing verified
   matched → `nestor_propose` queues it → a human seals it in `nestor ui`
   → next `ask` serves verified with the human's name attached. The
   argument for the covenant, told in commands and screenshots, not
   adjectives. Lives at `docs/walk-through-covenant.md` or as a
   `demo/` runnable script — probably both.

5. **Multi-language matcher story.** The current dogfood corpus is
   `decision → decision`; the shipped translation surface handles arbitrary
   domain tags. A short doc showing `en ↔ es`, `en ↔ fr`, `en ↔ ar` with
   sealed policy examples would let Felipe pick a language for the room
   he is actually in. Not blocked on §1 but reads much better after §3.


## 5. What we need from Felipe before item 3 or 5 gets scoped

- **Is he handing what we built to foreign audiences, or is he using the
  elevator pitch and pointing at the org?** A one-pager and a policy demo
  are two different asks, and the sequence changes accordingly.
- **What is the first country / region on his schedule?** If LatAm, `es ↔ en`
  is the demo priority; MENA is a different story; a global tour means
  the demo has to be language-neutral (which pushes item 3 further out and
  item 4 further forward).
- **Which "couple of potential engagements" is he assembling?** A briefing
  at a foreign ministry, a keynote at a national AI strategy event, and a
  procurement pilot are three very different shapes; they each want a
  different first artifact.

The operator has offered to take these to Felipe directly. This note is
here so that when the answer comes back, the sequencing above is already
argued out and we are not re-deriving it from a Slack message.


## 6. What is not in this note

- **A commitment.** Nothing here is sealed. Every item in §4 is a proposal;
  the operator picks or declines.
- **A market claim about government adoption.** The claim was Felipe's; the
  claim about *why* it lands (§2) is the operator's read of Nestor's
  covenant against the audience Felipe is walking into. Neither has been
  checked against a real procurement conversation yet. When one happens,
  this note gets a §7 with the read from the room.
- **Anything at all about Emerging Rule or GENIA Latinoamérica in
  particular.** Felipe wears several hats; the collaboration shape belongs
  to a conversation the operator has not had yet.
