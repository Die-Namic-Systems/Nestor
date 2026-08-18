#!/usr/bin/env python3
"""The filing cabinet — a man's papers, a lot's disclosures, and one refusal.

    python demo/filing_cabinet.py              # the walk-through
    python demo/filing_cabinet.py --keep DIR   # leave both desks behind

**This is fiction.** Big Jim Motors does not exist, James Beauregard
McGillicuddy III did not exist, and no sentence in here is a decision a human
made. Every row carries ``origin="fixture:filing-cabinet"``, both stores and
both ledgers are temporary, and nothing outside the working directory is
touched. A fixture that could be mistaken for a real trail is a forged record,
and this is an audit-trail product.

Where it came from
------------------
A session in which the operator played a used-car dealer and this package was
asked to be itself. He installed it for one reason — to prove a named human had
checked an odometer — and then handed over a filing cabinet: bank statements,
four children, three divorce decrees, a draft will, an arrest record, and a
napkin.

It is the third fixture here and the first where the archive belongs to somebody
with a **reason to want the answer to come out a particular way**. ``shoebox.py``
is a granddaughter who wants the truth about her grandmother; the incentives all
point the same direction and the gaps it found were about surfaces nobody had
built. This one is a man whose interests and his record diverge, which turns out
to exercise a different part of the package entirely: not what it shows, but
what it refuses, and what it cannot refuse.

What the cabinet turns out to hold
----------------------------------
**A name that is its own collision** (§6.22). The file opens with a suffix.
``James Beauregard McGillicuddy III`` against ``… II`` scores **0.985** — above
the seal threshold — so the two men are one row and the older man's record
serves as the younger's, reported verified. Meanwhile ``Big Jim``, the name he
is actually called, scores **0.292** and reaches nothing. The name nobody uses
finds the wrong man; the name everybody uses finds nobody.

**A cabinet that cannot tell a draft from a decree.** Three divorce decrees, a
bankruptcy discharge, an arrest record — and a *draft* will, unsigned, filed
next to them and treated as their equal. It is the package's own tier-2/tier-1
confusion, occurring in a drawer, without the package. The one document that
decides who owns the lot is the one that does not yet decide anything.

**A signature bound to a name that was removed.** A napkin contract signed by a
country music star, ``name redacted``. Structurally identical to the forged seal
this package refuses: the row says *signed* and the name it is bound to is
absent, so nothing — not this store, not a court — can verify it.

**Four documents that agree against three.** All four children post-date the
decree ending the marriage to their own mother, and both properties post-date
theirs too. One is a story; six is a systematic error in one field. The
reconciler surfaces the collision and stops: *which* record is wrong is a fact
about a life, not about paperwork, and is not a machine's to settle.

**An alias with one witness, and the witness is dead** (§6.39, closed). His
mother called him *Jamie*. Nobody else ever did and she died in 2010. It cannot
be sealed — no living person can confirm it — and calling it doubtful would be
false. ``EntityResolver.propose()`` records it as a draft: no seal, no verifier,
no ledger entry. The truest name in the cabinet has a verb now.

And the one this fixture exists for
-----------------------------------
He asked, at the end, to be stopped from signing his own mileage rows. Three
independent records across twenty-eight years — a dropped 1998 tampering charge,
an IRS query about 80,000 miles claimed on a car that did not run, fourteen
parking tickets on test-drive vehicles — all concern one field, and it is the
field the deployment exists to attest.

**The package cannot do it.** There is no per-domain verifier policy, no
required-signer list, nothing that binds a domain to a name. Measured below:
``add_pair(status="sealed", verifier="anybody-at-all")`` is accepted and
``is_verified_seal`` returns True, because the only gate is possession of the
seal key. The covenant is enforced by *who holds a key*, not by any rule the
store can express — which is defensible, and is not what he asked for, and the
honest answer was to say so and tell him to give the key away.

That refusal is the whole product, and it is the first time in three fixtures
that the right answer was *no*.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

os.environ.setdefault("NESTOR_SEAL_KEY", "filing-cabinet-fixture-key-not-a-secret")

from demo import desks                                        # noqa: E402
from demo.desks import (AMBER, BOLD, DIM, GREEN, OFF, RED,     # noqa: E402
                        beat, claim, gap, note, say, verdict)
from demo.big_jim import MATCHER as VINS                       # noqa: E402
from nestor import entity, memory                              # noqa: E402
from nestor.matcher import StringMatcher                       # noqa: E402

ORIGIN = "fixture:filing-cabinet"
JIM = "jim"

FULL = 'James "Big Jim" Beauregard McGillicuddy III'
BARE = "James Beauregard McGillicuddy III"
FATHER_LINE = "James Beauregard McGillicuddy II"

VIN = "1HGEJ6672841"
PITCH = "Runs great, one owner, garage kept."
TAIL_QUERY = "that one ending 672841"

#: (child, born, mother, the decree that ended the marriage to her)
CHILDREN = [("Jimmy Jr.", 1980, "Darlene", 1979), ("Sally-Anne", 1985, "Darlene", 1979),
            ("Bobby Ray", 1990, "Brenda", 1987), ("Tiffany Jr.", 2006, "Tiffany", 2005)]
#: (what, bought, with whom, their decree)
PROPERTY = [("ranch house, for Brenda", 1998, 1987), ("lake cabin, with Tiffany", 2005, 2005)]
#: One field, three institutions, twenty-eight years.
MILEAGE = [(1998, "arrest: odometer tampering suspicion, charges dropped"),
           (2017, "IRS: 80,000 miles claimed on a car that did not run"),
           (2026, "14 parking tickets, all on test-drive vehicles")]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--keep", default="", help="leave both desks behind here")
    args = ap.parse_args()

    print(f"\n{BOLD}Big Jim's filing cabinet{OFF}")
    print(f"{DIM}   Fiction. Nobody here exists, no sentence below is a decision a "
          f"human made,\n   and both desks are temporary. Every row is tagged "
          f"{ORIGIN}.{OFF}")

    with desks.Workspace(keep=args.keep, prefix="nestor-cabinet-") as work:
        lot = work.desk("lot", "vin", "disclosure", matcher=VINS, origin=ORIGIN)
        papers = work.desk("papers", "dossier", "reading", origin=ORIGIN)

        # ------------------------------------------------------------ 1
        beat(1, "A question nobody has adjudicated")
        claim(lot.best_sealed(VIN) is None,
              "an unadjudicated vehicle is not served as verified")
        say(f"{DIM}ask  {OFF}{VIN}")
        say(f"Nestor: {AMBER}! pending{OFF} — nothing to offer, said plainly.")
        note("Which is the behaviour everything below exists to protect.")

        # ------------------------------------------------------------ 2
        beat(2, "A perfect score, and still not served")
        draft = lot.propose(VIN, PITCH, reason="Drafted by the machine.")
        hits = memory.lookup(VIN, "vin", "disclosure", store=lot.store,
                             matcher=VINS, context_threshold=0.0)
        best = max(h["similarity"] for h in hits)
        claim(best >= memory.SEAL_THRESHOLD,
              "the draft scores at or above the seal threshold")
        claim(lot.best_sealed(VIN) is None,
              "and is still not served, because nobody has checked it")
        say(f"{DIM}draft{OFF} {PITCH}")
        say(f"scores {BOLD}{best:.3f}{OFF}, at or above {memory.SEAL_THRESHOLD} — "
            f"and Nestor answers {AMBER}! pending{OFF}.")
        note("Close is not the problem here. Unverified is.")

        # ------------------------------------------------------------ 3
        beat(3, "A human seals it, and a phone call reaches it")
        status, body = lot.seal_draft(draft["id"], verifier=JIM,
                                      reason="Checked the title and the odometer.")
        claim(status == 200, "the surface accepts the seal")
        claim(body["pair"]["id"] == draft["id"],
              "the draft is upgraded in place rather than duplicated")
        served = lot.best_sealed(TAIL_QUERY)
        claim(served is not None,
              "the VIN tail quoted down a phone reaches the sealed row")
        say(f"{DIM}ask  {OFF}{TAIL_QUERY}")
        say(f"{GREEN}✓ sealed{OFF}  {served['pair']['target_text']}")
        say(f"{DIM}verified by {served['pair']['verifier']!r}, "
            f"{served['similarity']:.3f}{OFF}")

        # ------------------------------------------------------------ 4
        beat(4, "Then the cabinet arrives, and the name is the first problem")
        # On normalized keys, because StringMatcher offers no `score` — which is
        # the ordinary path for the shipped matcher and the one a name would
        # actually take.
        m = StringMatcher()
        def sim(a: str, b: str) -> float:
            return round(m.similarity(m.normalize(a), m.normalize(b)), 3)

        father, called = sim(BARE, FATHER_LINE), sim(FULL, "Big Jim")
        gap(father >= memory.SEAL_THRESHOLD,
            "a suffix is not enough to separate two men: II and III are one row",
            "§6.22")
        claim(called < memory.SEAL_THRESHOLD,
              "and the name he is actually called reaches neither of them")
        say(f"{BARE}")
        say(f"{FATHER_LINE}   → {RED}{father:.3f}{OFF}  "
            f"{RED}at or above {memory.SEAL_THRESHOLD}{OFF}")
        say(f"{DIM}'Big Jim' against his own full name{OFF}   → {called:.3f}  "
            f"{DIM}below{OFF}")
        note("The name nobody uses finds the wrong man. The name everybody uses")
        note("finds nobody. The file announces this in its first line: 'III'.")

        # ------------------------------------------------------------ 5
        beat(5, "Four documents agreeing against three")
        late = [(c, b, mum, d) for c, b, mum, d in CHILDREN if b > d]
        prop_late = [(w, y, d) for w, y, d in PROPERTY if y >= d]
        claim(len(late) == len(CHILDREN),
              "every child post-dates the decree ending the marriage to their mother")
        claim(len(prop_late) == len(PROPERTY),
              "and both properties post-date theirs too")
        for c, b, mum, d in CHILDREN:
            say(f"{c:12} b.{b}  mother {mum:8} decree {d}   "
                f"{RED}{b - d}y after{OFF}")
        say()
        say(f"{BOLD}{len(late)} of {len(CHILDREN)}.{OFF} One is a story. Four is a "
            f"systematic error in one field.")
        note("Six records point one way and the three decrees stand alone against")
        note("them. Which is wrong is a fact about a life, not about paperwork —")
        note("so it is surfaced, and it is not settled here.")
        for c, b, mum, d in CHILDREN:
            papers.propose(f"{c}, b.{b}, mother {mum}",
                           f"Born {b - d}y after the {d} decree naming {mum}.",
                           reason="Collision between two records in the same file.")

        # ------------------------------------------------------------ 6
        beat(6, "The only document that matters is a draft")
        will = papers.propose(
            "Last Will & Testament (draft)",
            "Unsigned. Tier 2. It decides who owns the lot and it decides nothing "
            "yet.",
            reason="Filed beside three decrees and a bankruptcy discharge, which "
                   "are sealed records with a court's name on them.")
        claim(will["status"] == "draft", "the fixture records it as what it is")
        say("Three decrees, a discharge, an arrest record — all sealed, all with an")
        say(f"institution's name on them. And one {AMBER}~ draft{OFF} filed beside "
            f"them,")
        say("looking exactly like its neighbours.")
        note("The package's own tier-1/tier-2 confusion, happening in a drawer,")
        note("without the package. Sparkplug inherits nothing.")

        # ------------------------------------------------------------ 7
        beat(7, "A signature bound to a name that was removed")
        papers.propose(
            "Napkin, 1984 Bronco, signed by a country music star (name redacted)",
            "A seal whose verifier is absent. Nothing can verify it, including a "
            "court.",
            reason="Structurally identical to the forged seal this package refuses.")
        say("The row says signed. The name it is bound to is not there.")
        note("Which is the one thing this package checks and the one thing a")
        note("napkin cannot carry.")

        # ------------------------------------------------------------ 8
        beat(8, "An alias with one witness, and the witness is dead")
        resolver = entity.EntityResolver(papers.store, domain="person")
        resolver.propose(
            "Jamie",
            "What his mother called him. Nobody else ever did. She died in 2010.",
            reason="Cannot be sealed — no living person can confirm it. Calling it "
                   "doubtful would be false.",
            origin=ORIGIN)
        say("His mother called him Jamie. She was the only one.")
        say(f"It cannot be {GREEN}sealed{OFF} — nobody living can confirm it — and it")
        say("is not doubtful, so calling it a guess would be a lie.")
        note("EntityResolver.propose() — the missing verb (IDEAS §6.39, closed).")
        note("A draft, not a seal. No verifier, no ledger entry.")

        # ------------------------------------------------------------ 9
        beat(9, "What he actually asked for, and the refusal")
        for year, what in MILEAGE:
            say(f"{year}  {what}")
        say()
        say(f"{BOLD}Three institutions, twenty-eight years, one field{OFF} — and it "
            f"is the field")
        say("this deployment exists to attest.")
        say()
        say('He asked to be stopped from signing his own mileage rows.')

        # Caught, not left to propagate: the day somebody adds a verifier policy
        # this call starts raising, and a fixture that died with a traceback
        # would report a crash where it owes a GAP CLOSED. Found by mutating
        # add_pair to enforce exactly that, which is what the mutation was for.
        try:
            anyone = memory.add_pair(
                "mileage 42,000", "confirmed by nobody in particular", "odo",
                "odo", status="sealed", verifier="anybody-at-all", origin=ORIGIN,
                store=papers.store, matcher=StringMatcher())
            unpoliced = memory.is_verified_seal(anyone)
            detail = (f"add_pair(status='sealed', verifier='anybody-at-all') → "
                      f"accepted, is_verified_seal → {unpoliced}")
        except Exception as exc:
            unpoliced = False
            detail = f"refused by {type(exc).__name__} — something now polices this"
        gap(unpoliced,
            "any name at all can be sealed under: there is no verifier policy",
            "no entry yet — see this module's docstring")
        say(f"   {RED}refused.{OFF} There is no verb for it.")
        say(f"   {DIM}{detail}{OFF}")
        say(f"   {DIM}The only gate is who holds the key.{OFF}")
        note("No per-domain verifier policy, no required-signer list, nothing the")
        note("store can express. The honest answer was to say so, and to tell him")
        note("to give the key to somebody else and keep no copy.")

        # ------------------------------------------------------------ 10
        beat(10, "What this fixture is for")
        say("It is the first archive here belonging to somebody with a reason to")
        say("want the answer to come out a particular way. The shoebox was a")
        say("granddaughter after the truth; every incentive pointed one way, and")
        say("what it found were surfaces nobody had built.")
        say()
        say("This one exercises the other half: not what the package shows, but")
        say(f"what it refuses — and the {BOLD}one thing it cannot refuse{OFF}, which is")
        say("a man signing his own name to the number he has been wrong about")
        say("since 1998.")
        drafts = [r for r in papers.rows() if r["status"] == "draft"]
        sealed_here = [r for r in papers.rows() if r["status"] == "sealed"]
        claim(all(r.get("verifier") != JIM for r in drafts),
              "nothing this fixture proposed carries his name")
        claim(not sealed_here,
              "and nothing on the papers desk is sealed at all")
        say()
        say(f"   {AMBER}~{OFF} {len(drafts)} drafts on the papers desk, awaiting "
            f"a human")
        say(f"   {GREEN}✓{OFF} {len(sealed_here)} sealed there. The two seals in "
            f"this run are both")
        say("     demonstrations: beat 3, which he made himself, and beat 9, "
            "which is")
        say("     the one nobody should be able to make.")
        note("A machine may propose. Only a human confirms. Including about the")
        note("man who bought the machine.")

    return verdict()


if __name__ == "__main__":
    raise SystemExit(main())
