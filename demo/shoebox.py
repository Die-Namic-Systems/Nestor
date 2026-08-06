#!/usr/bin/env python3
"""The shoebox — one verifier, her own archive, and the two things nobody shows her.

    python demo/shoebox.py                 # the walk-through
    python demo/shoebox.py --keep DIR      # leave the store and ledger behind

**This is fiction.** Nieves Aguirre-Toll does not exist, her grandmother did not
exist, and no sentence in here is a decision a human made. Every row carries
``origin="fixture:consuelo-shoebox"``, the store and ledger are temporary, and
nothing outside this script's working directory is touched. A fixture that could
be mistaken for a real trail is a forged record, and this is an audit-trail
product.

Why she exists
--------------
Every review surface in this package was designed against a *team*: two people
who can disagree, a queue that arrives from somewhere, a compliance story. The
covenant — a machine may propose, only a human confirms — was built and tested
in that shape. Nobody had asked what the surfaces show when there is exactly one
human and she is also the only reader.

So: Nieves is 38, in Bristol. Her grandmother Consuelo died fourteen months ago
in Cádiz, and what came back was a shoebox — 61 letters, a recipe notebook, and
the backs of photographs. She reads Spanish the way you read a menu: she gets
the shape and misses the load-bearing word. Her daughter is seven and has no
Spanish at all, which is the actual deadline.

She is not keeping a memory for consistency across a team. She is keeping one
for **consistency across time with herself** — she settles a phrase in March,
meets it again in June, and cannot remember what she chose or why. Some of it is
not translation at all: a nickname, a joke, a word Consuelo used wrong on
purpose. Those are rulings, and once she makes one she wants it to hold.

What she finds, and why it took a person to find it
---------------------------------------------------
Two records this package keeps carefully and shows to nobody:

* **A revision.** ``supersede_pair`` retains the old row — text, verifier,
  signature, reason — and ``memory_lineage`` walks back to it. Nothing in
  ``nestor/`` calls ``memory_lineage``. ``Curator.replaced_seals`` reads
  ``kind="seal_replaced"``, which is the *destructive* ``add_pair`` overwrite;
  ``supersede_pair`` writes ``kind="supersede"``, so the view built to answer
  "what did I change, and why" is blind to the verb that shipped as the safe way
  to change things.

* **A deferral.** ``reject_match(reopen_when=...)`` is N5's never-vs-not-yet.
  It is stored, versioned into the bundle digest, and carried to another
  instance on export. No human-facing surface reads it. Its own docstring says
  *"a reader that surfaces rejections should surface a non-empty reopen_when as
  a condition to re-check"* — describing a reader that does not exist.

Neither is invisible in the strict sense: both are in the raw ledger, and she
can scroll it. The chain shows her reason in full and the text she replaced as a
**digest**. So she can learn *that* she changed her mind and *why*, and not
*what she changed it from*, on any shipped surface.

For a team, both gaps are nearly harmless — a colleague's overrule is the
high-signal event and that surface works, and a deferral is one row in an
aggregate. For Nieves, self-correction is the *only* revision that can ever
happen, so ``conflicts_only=True`` is empty by construction, forever. The
surfaces are not wrong about teams. They were never asked about her.

Each claim below is asserted as it runs. If one stops holding, this exits
non-zero — which is the good outcome, and means somebody closed a gap and should
update this script and ``IDEAS.md`` §6.35.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

# Its own key, so the seals below are really signed and the walk-through does not
# depend on what the caller exported. Named for what it is: a fixture's key is
# not a secret, and a demo that quietly runs with signing off would be showing
# seals nobody could have made.
os.environ.setdefault("NESTOR_SEAL_KEY", "shoebox-fixture-key-not-a-secret")

# Through ui.dispatch rather than Curator directly: the claim is about what she
# can see on a screen, and a demo that reached past the surface to the library
# would be proving something she cannot check.
from nestor import cascade, memory, storage, ui           # noqa: E402
from nestor.sqlite_store import SqliteStore               # noqa: E402

BOLD, DIM, GREEN, AMBER, RED, OFF = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m")

ORIGIN = "fixture:consuelo-shoebox"
HER = "nieves"
ES, EN = "es", "en"

_FAILURES: list[str] = []


def beat(n: int, title: str) -> None:
    print(f"\n{BOLD}{n}. {title}{OFF}")


def say(text: str = "") -> None:
    print(f"   {text}" if text else "")


def note(text: str) -> None:
    say(f"{DIM}{text}{OFF}")


def claim(condition: bool, what: str) -> None:
    """A demo that narrates something that did not happen is worse than none."""
    if not condition:
        _FAILURES.append(what)
        print(f"   {RED}DEMO CLAIM FAILED: {what}{OFF}")


def gap(condition: bool, what: str) -> None:
    """A claim that a gap is still open.

    Distinguished from :func:`claim` because failing here is *good news*: the
    surface grew a reader. The exit code is the same — this script is now wrong
    and says so rather than narrating a gap that somebody closed.
    """
    if not condition:
        _FAILURES.append(f"(gap closed, update this script) {what}")
        print(f"   {GREEN}GAP CLOSED — update demo/shoebox.py and IDEAS §6.35: "
              f"{what}{OFF}")


def build(store) -> None:
    """Fourteen months of one person's evenings, in the order she did them."""
    def seal(src, tgt, reason):
        return memory.add_pair(src, tgt, ES, EN, status="sealed", verifier=HER,
                               origin=ORIGIN, reason=reason, store=store)

    # Months 1-2, when she thought this would be quick.
    seal("Un abrazo muy fuerte", "A great big hug",
         "How every letter ends. Settled it once so I stop looking at it.")
    seal("Que Dios te bendiga", "God bless you",
         "She was not religious in any way I saw. She wrote it anyway, every time.")
    seal("no te preocupes por mi", "don't you worry about me",
         "'Don't worry about me' is the sentence. The 'you' is her voice.")

    # A ruling, not a translation. The row that made her keep the tool.
    seal("mi terremoto", "my earthquake",
         "Her name for me until I was about nine. Not 'my little earthquake' "
         "and not 'my whirlwind'. She meant the damage.")

    # The one that took forty minutes, for a reason no term base can hold.
    seal("a punto de nieve", "to stiff peaks",
         "Standard cookery term, took me forty minutes. She named me after the "
         "word and never once mentioned it. I do not know if she knew.")

    # Recipe measures: real ambiguity, no right answer, decided anyway.
    seal("un vaso de aceite", "a glass of oil (about 200ml)",
         "It is a measure, not a glass. Kept the literal and put the number in "
         "brackets so my daughter can actually cook it.")
    seal("a ojo", "by eye",
         "Resisting 'to taste'. She did not mean taste, she meant look at it.")

    # The queue. Things she cannot face yet.
    memory.add_pair("ya no me acuerdo de su cara", "I don't remember his face any more",
                    ES, EN, origin=ORIGIN, store=store,
                    reason="From the last letter. Whose face. Leaving it.")
    memory.add_pair("la casa de la esquina", "the corner house", ES, EN,
                    origin=ORIGIN, store=store, reason="Which corner. Which house.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--keep", default="",
                    help="write the store and ledger here and keep them")
    args = ap.parse_args()

    workdir = (pathlib.Path(args.keep) if args.keep
               else pathlib.Path(tempfile.mkdtemp(prefix="nestor-shoebox-")))
    workdir.mkdir(parents=True, exist_ok=True)
    cascade.set_ledger_path(workdir / "ledger.jsonl")
    cascade._verified_ledgers.clear()
    store = SqliteStore(str(workdir / "nestor.db"))
    store.init_db()
    store.memory_init()
    storage.set_store(store)
    app = ui.App(store=store, source_lang=ES, target_lang=EN,
                 db_path=str(workdir / "nestor.db"))

    print(f"\n{BOLD}The shoebox{OFF} — Nieves, her grandmother's letters, and one "
          f"verifier who is also the only reader.")
    note("Fiction. Every row is tagged fixture:consuelo-shoebox; the store is temporary.")

    beat(1, "Fourteen months of evenings.")
    build(store)
    st = memory.stats(store=store)
    say(f"{st['sealed']} sealed, {st['draft']} still in the queue.")
    note("The drafts are not a backlog. They are the two she cannot face yet.")

    beat(2, "A ruling, not a translation.")
    hit = memory.best_sealed("mi terremoto", ES, EN, store=store)
    claim(hit is not None, "her own ruling is served back to her")
    say(f"{GREEN}✓{OFF} mi terremoto → {BOLD}{hit['pair']['target_text']}{OFF}")
    note(f"why: {hit['pair']['reason']}")
    note("No dictionary produces this. It is hers, and the point of sealing it "
         "is that she never has to decide it twice.")

    beat(3, "Month 9. She was wrong about something that mattered.")
    memory.add_pair("me hago cargo", "I'll take care of it", ES, EN,
                    status="sealed", verifier=HER, origin=ORIGIN,
                    reason="First reading. Sounded like her.", store=store)
    say(f"March:  me hago cargo → {DIM}I'll take care of it{OFF}")
    memory.supersede_pair(
        "me hago cargo", "I understand", ES, EN, verifier=HER, origin=ORIGIN,
        reason="She is writing about burying her own mother, and 'hacerse cargo' "
               "there is not an offer to help — it is her saying she has taken "
               "it in. I had her being brisk at her own mother's funeral for "
               "eight months.",
        store=store)
    say(f"Month 9: me hago cargo → {BOLD}I understand{OFF}")
    live = store.memory_find("me hago cargo", ES, EN)
    claim(live["target_text"] == "I understand", "the correction is what serves now")
    lineage = store.memory_lineage(live["id"])
    claim([r["target_text"] for r in lineage] == ["I'll take care of it"],
          "the store still holds what she replaced")
    note("She did it the safe way — supersede_pair, nothing destroyed. The old "
         "row keeps its text, its signature and her first reason.")

    beat(4, "So where can she see that she changed her mind?")
    _, default_view = ui.dispatch(app, "GET", "/api/replaced-seals", {})
    _, all_view = ui.dispatch(app, "GET", "/api/replaced-seals", {"all": "1"})
    say(f"/api/replaced-seals            {RED}{len(default_view['replaced'])} rows{OFF}")
    say(f"/api/replaced-seals?all=1      {RED}{len(all_view['replaced'])} rows{OFF}")
    gap(not default_view["replaced"] and not all_view["replaced"],
        "the replaced-seals view is blind to supersede")
    note("It reads kind=\"seal_replaced\" — the destructive add_pair overwrite. "
         "supersede_pair writes kind=\"supersede\". And conflicts_only, the "
         "default, wants a *different* verifier: for her there is no such person,")
    note("so that view is empty by construction and will be for as long as she "
         "is the only one holding a key.")

    _, chain = ui.dispatch(app, "GET", "/api/ledger", {"kind": "supersede"})
    entry = chain["entries"][0]
    claim(entry["reason"].startswith("She is writing about"),
          "the chain does carry her reason, in full")
    say(f"\n   The raw ledger tab has it: {GREEN}reason in full{OFF}, and the text "
        f"she replaced as {AMBER}{entry['replaced_target_sha'][:16]}…{OFF}")
    note("She can learn that she changed her mind, and why. Not what she changed "
         "it from — no shipped surface calls memory_lineage.")

    beat(5, "And a deferral, which is not the same as a no.")
    memory.reject_match("mi terremoto", ES, EN, target_text="my little earthquake",
                        verifier=HER, store=store,
                        reason="Not little. She never once called me little.")
    memory.reject_match("la casa de la esquina", ES, EN, verifier=HER, store=store,
                        target_text="the house on the corner of Calle Sacramento",
                        reason="I am guessing at the street because I want it to "
                               "be that one.",
                        reopen_when="if I find the photo with the address on the back")
    say("One permanent no, and one that is only a no for now:")
    note("  reopen_when = \"if I find the photo with the address on the back\"")

    _, rejections = ui.dispatch(app, "GET", "/api/rejections", {})
    shown = "reopen_when" in json.dumps(rejections)
    say()
    say(f"/api/rejections carries it?    {GREEN}yes{OFF}" if shown
        else f"/api/rejections carries it?    {RED}no{OFF}")
    gap(not shown, "no human-facing surface reads reopen_when")
    note("It is stored, it is versioned into the bundle digest, and it travels "
         "to another instance on export. The one person who wrote the condition "
         "down is the one person never shown it.")

    beat(6, "What the fixture is for.")
    say("Neither gap is a bug in how this handles teams. Both are surfaces that "
        "were never asked about one person working alone over time —")
    say("which is the shape of every archive, every estate, every notebook "
        "somebody is trying to finish before their kid stops asking.")
    note("IDEAS §6.35. Both open.")

    if not args.keep:
        shutil.rmtree(workdir, ignore_errors=True)
    else:
        print(f"\n   {DIM}kept: {workdir}{OFF}")

    if _FAILURES:
        print(f"\n{RED}{len(_FAILURES)} claim(s) no longer hold:{OFF}")
        for f in _FAILURES:
            print(f"  - {f}")
        return 1
    print(f"\n{GREEN}Every claim above held.{OFF}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
