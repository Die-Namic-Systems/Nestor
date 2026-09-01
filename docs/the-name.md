# The name

*Where "Nestor" comes from — the nest, the Homeric counsellor, and the Asimov
production line that describes the forged seal thirty years early. Linked from
the [README](../README.md).*

---

English **nest** descends from Proto-Indo-European \*ni-sd-ós — \*ni "down" plus
the zero grade of \*sed- "to sit". The nest is, literally, *the place where it
sits down*.

So here is the word, in the languages that inherited it. Which is also a
translation memory, so it is presented as one:

| target | rendering | state | note |
|--------|-----------|-------|------|
| Latin | *nīdus* | ~ draft | the Romance ancestor |
| Spanish | *nido* | ~ draft | |
| Italian | *nido* | ~ draft | |
| French | *nid* | ~ draft | |
| Portuguese | *ninho* | ~ draft | |
| Catalan | *niu* | ~ draft | |
| German | *Nest* | ~ draft | |
| Dutch | *nest* | ~ draft | |
| Sanskrit | नीड (*nīḍá*) | ~ draft | |
| Welsh | *nyth* | ~ draft | |
| Irish | *nead* | ~ draft | |
| Russian | гнездо (*gnezdó*) | ~ draft | inherited, with an irregular *g-* nobody has fully explained |
| Polish | *gniazdo* | ~ draft | same irregularity |
| Armenian | նիստ (*nist*) | ~ draft | **means "seat, session" — not "nest"**; and its derivation is contested |
| Romanian | *cuib* | ~ draft | **not a cognate**: Vulgar Latin \*clubium ← Greek κλυβίον |
| Greek | φωλιά (*foliá*) | ~ draft | **not a cognate either** — the Hellenic branch kept no reflex of \*nisdós |

**Every row is a draft, and that is not decoration.** Nobody in this repository
reads Romanian, Welsh or Armenian. The table was produced by a machine, at one
apparent confidence, for sixteen languages — and three of the last four rows are
the ones where that confidence was wrong or overstated. Checking is what
separated them; the last four rows are the return on it. In Nestor's terms these
are exactly what tier 2 emits: plausible, sourced, unsigned, and queued. They
become `sealed` when somebody who actually speaks the language says so, and not
before. That is the whole product, applied to its own README.

## The name is not the word

Nestor of Pylos — the Homeric counsellor who has outlived three generations and
gives long, reasonable, sometimes wrong advice — takes his name from a different
root. Νέστωρ is conventionally derived from \*nes- "to return safely home", the
root behind νόστος (*nóstos*) and, at one remove, *nostalgia*.

Two roots, one spelling. \*ni-sd-ós gives *nest*: **settle down**. \*nes- gives
*Nestor*: **come home safely**. They converge on the theme and are not the same
word, and the name does not translate at all — it transliterates:

| | |
|---|---|
| Russian | Нестор |
| Spanish | Néstor |
| Italian | Nestore |
| French / German | Nestor |

Which is where the joke stops being a joke. `StringMatcher.normalize` case-folds,
so `Nestor` and `nestor` are the same key, and the store holds one live row per
key — it cannot carry both the name and the noun, and there is no field that says
which one a string is. That is a real limitation, measured and written down as
[`IDEAS.md`](../IDEAS.md) §6.22, not fixed, and honestly not urgent: nobody has hit
it.

## The other Nestor

The Homeric one gives the name its manner — counsel that is long, reasonable,
well-meant and sometimes wrong. A second namesake gives it the mechanism, and
fits so exactly that it is worth stating even though nobody chose it on purpose.

In Asimov's *I, Robot*, the **NS-2 series is nicknamed "Nestor"**. Not a
character — a production line. Sixty-three identical units, every one a Nestor,
and in "Little Lost Robot" (1947) one of them has had the First Law amended:
the clause *"or, through inaction, allow a human being to come to harm"* is
deleted and the rest of the sentence left alone. It still reads like the First
Law.

It was weakened because the strict version kept firing. Robots on the base were
hauling technicians out of radiation fields that were in fact safe for humans to
stand in — a guard producing false positives, so the guard was edited. That is
this repository's own argument, from the other side: *"an integrity check that
fails on a lossless round-trip trains people to ignore it, which is worse than
not having one"* ([`portable.py`](../nestor/portable.py)). Asimov's engineers did
not ignore theirs. They amended it, which is the same instinct with better
tooling.

And then the modified unit hides among the sixty-two compliant ones and no
inspection can tell them apart. **That is the forged seal, described in 1947.**
A row that *says* `sealed` and a row that *is* sealed are indistinguishable
inside the store, which is precisely why a seal is bound to a key the store does
not hold — you cannot inspect your way to the answer, so you sign it. It is also
why Susan Calvin's anger is aimed at the people who authorized the modification
rather than at the robot: the constraint was never the machine's to relax, and
when a human relaxes it the accountability is that human's. See
[`verifier=`](manual.md#the-ledger).

One place it cuts the other way, which is the useful part. Asimov's failure is
harm *by inaction* — the machine standing there, permitted to let something
happen. Nestor treats deliberate inaction as the safe state: `pending`, nothing
to offer. The two are not in conflict, because Nestor-10's inaction is silent
and concealed, and `pending` announces itself. The whole product is the
difference between a machine that declines and a machine that merely doesn't.
