#!/usr/bin/env python3
"""The border — a verification crossing between two repositories, both ways.

    python demo/the_border.py                 # the walk-through
    python demo/the_border.py --keep DIR      # leave both stores behind

Needs `jeles <https://github.com/rudi193-cmd/Jeles>`_ importable. It is not a
dependency of this package and never will be — the recipe under test works
against plain dicts, and this fixture is the one place a *real* corpus is
driven. Absent, it says so and exits 0 rather than faking one: a fixture that
mocks the system under test proves the mock works.

    PYTHONPATH=/path/to/jeles python demo/the_border.py

**This is not fiction**, which makes it the odd one out in this directory. The
two packages are real, the round trip below is real, and every number printed
was produced by running it. What is fictional is only the content of the one
nugget it carries, and the store and the corpus are both temporary.

What it walks
-------------
jeles is the fleet's verified-corpus organ. A **nugget** is
``{question, answer, sources, verified_by, verified_at, tags}``; a miss is a
**gap**. It was written by somebody who had never read this package, and it
independently arrived at three verification rungs, a rank-based overwrite guard,
a ranking-vs-answering split, and *"I don't know yet"* as a first-class output.
Every one has a counterpart here.

The one thing it does not have is a key and a chain, and it says so itself —
``put_nugget``'s docstring reads *"``verified_by`` is a claim: whatever string
the writer supplied."*

So a verification crossing this border loses something in **both** directions,
and the useful part is that neither loss is a defect:

* **inbound** — a nugget jeles holds as ``human`` arrives here as a **draft**,
  because an unsigned claim of verification is exactly what
  ``portable.import_bundle`` already demotes. This store will not serve it.
* **outbound** — a row a human sealed here, under a key, in the chain, goes back
  as ``asserted``: the weakest rung jeles has. Not a downgrade chosen for
  caution — ``put_nugget`` rejects unknown keyword arguments and the stored
  record has eleven fields, none of them for evidence. The signature is dropped
  at the border, so ``human`` would be a claim this package could no longer back.
* **landing** — and then it either duplicates or is refused, depending on
  whether the original id travels with it. Both measured below.

Every step is correct on both sides and the loop still does not close. The
asymmetry is not in the trust models; it is that one of them has a field for a
signature.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

os.environ.setdefault("NESTOR_SEAL_KEY", "the-border-fixture-key-not-a-secret")

BOLD, DIM, GREEN, AMBER, RED, OFF = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m")

QUESTION = "What does a seal bind to?"
ANSWER = "A key the store does not hold."
SOURCES = ["docs/seal-signatures.md"]
THEIRS = "sean"          # the name jeles was given, which it cannot check
OURS = "a-human-who-read-it"

_FAILURES: list[str] = []


def beat(n: int, title: str) -> None:
    print(f"\n{BOLD}{n}. {title}{OFF}")


def say(text: str = "") -> None:
    print(f"   {text}" if text else "")


def note(text: str) -> None:
    say(f"{DIM}{text}{OFF}")


def claim(condition: bool, what: str) -> None:
    if not condition:
        _FAILURES.append(what)
        print(f"   {RED}DEMO CLAIM FAILED: {what}{OFF}")


def gap(condition: bool, what: str) -> None:
    """A claim about the **other** repository's current behaviour.

    Failing here most likely means jeles changed — grew a field for evidence, or
    changed how a downgrade lands. That is good news and still has to stop the
    build, because a fixture describing a neighbour that has moved is a fixture
    telling you something false about somebody else's code.
    """
    if not condition:
        _FAILURES.append(f"(jeles moved, update this script) {what}")
        print(f"   {GREEN}CHANGED ON THEIR SIDE — re-read jeles and update "
              f"demo/the_border.py and recipes/jeles_bridge.py: {what}{OFF}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--keep", default="", help="leave both stores behind here")
    args = ap.parse_args()

    try:
        from jeles import corpus
    except ImportError:
        print(f"\n{AMBER}jeles is not importable, so there is no corpus to "
              f"cross to.{OFF}")
        print(f"{DIM}   It is deliberately not a dependency of this package. "
              f"Clone it and:\n"
              f"   PYTHONPATH=/path/to/jeles python demo/the_border.py{OFF}\n")
        return 0

    work = (pathlib.Path(args.keep) if args.keep
            else pathlib.Path(tempfile.mkdtemp(prefix="nestor-border-")))
    (work / "willow").mkdir(parents=True, exist_ok=True)
    os.environ["WILLOW_STORE_ROOT"] = str(work / "willow")
    os.environ["NESTOR_LEDGER"] = str(work / "ledger.jsonl")

    from nestor import cascade, memory, storage
    from nestor.sqlite_store import SqliteStore
    from recipes import jeles_bridge as JB

    cascade.set_ledger_path(str(work / "ledger.jsonl"))
    store = SqliteStore(str(work / "nestor.db"))
    store.init_db()
    store.memory_init()
    storage.set_store(store)
    # The §6.40 workaround, in the open: nestor.ui cannot be told about a custom
    # matcher, so a seal made at the surface would land under a key this domain
    # never computes. In-process is the only way to seal these correctly today.
    memory.set_matcher(JB.MATCHER)

    print(f"\n{BOLD}The border{OFF}  {DIM}jeles ⇄ nestor, both directions{OFF}")
    note("Two real packages. The nugget's content is invented; nothing else is.")

    # ---------------------------------------------------------------- 1
    beat(1, "jeles holds it, and serves it")
    made = corpus.put_nugget(QUESTION, ANSWER, SOURCES, verified_by=THEIRS,
                             verification_kind="human")
    claim("error" not in made, "jeles accepts a human-kind nugget")
    theirs = corpus.ask_corpus(QUESTION)
    claim(theirs["found"] is True, "and serves it as found")
    n = theirs["nugget"]
    say(f"{DIM}ask  {OFF}{QUESTION}")
    say(f"{GREEN}found{OFF}  {n['answer']}")
    say(f"{DIM}kind={n['verification_kind']!r}  verified_by={n['verified_by']!r}{OFF}")
    note("Which jeles cannot check. Its own docstring: 'verified_by is a claim:")
    note("whatever string the writer supplied.'")

    # ---------------------------------------------------------------- 2
    beat(2, "It crosses, and arrives as a draft")
    inbound = JB.bridge_nuggets([n], store=store)
    claim(inbound["sealed"] == 0, "nothing crosses as sealed")
    claim(inbound["demoted"] == 1, "the human-kind nugget is demoted to draft")
    say(f"{inbound['sealed']} sealed, {AMBER}{inbound['demoted']} demoted to "
        f"draft{OFF}")
    served = JB.answer_for(QUESTION, store=store)
    claim(served is None, "and this store will not serve it")
    say(f"answer_for(...) -> {AMBER}{served}{OFF}")
    row = [r for r in store.memory_candidates(JB.DOMAIN, JB.DOMAIN)][0]
    claim(THEIRS in (row.get("reason") or ""),
          "what jeles believed is kept beside the row")
    note("Demoting is not discarding — kind, both names, date and every citation")
    note("go into the row's reason, for whoever opens the queue.")

    # ---------------------------------------------------------------- 3
    beat(3, "A human reads it and seals it here")
    memory.add_pair(QUESTION, ANSWER, JB.DOMAIN, JB.DOMAIN, status="sealed",
                    verifier=OURS, origin="jeles:corpus", store=store,
                    matcher=JB.MATCHER)
    hit = JB.answer_for(QUESTION, store=store)
    claim(hit is not None, "now it serves")
    pair = hit["pair"]
    claim(memory.is_verified_seal(pair), "and the seal verifies")
    say(f"{GREEN}✓ sealed{OFF} by {pair['verifier']!r}, {hit['similarity']:.3f}")
    say(f"{DIM}seal_sig {pair['seal_sig'][:32]}…{OFF}")
    say(f"{DIM}chain    {len([x for x in (work / 'ledger.jsonl').read_text().splitlines() if x.strip()])} entrie(s){OFF}")
    note("What was signed is 'I checked this', by a named person, under a key")
    note("this store does not hold. A different sentence from the one jeles had.")

    # ---------------------------------------------------------------- 4
    beat(4, "It goes back, and the evidence does not")
    nuggets, dropped = JB.export_sealed(store=store)
    claim(len(nuggets) == 1, "the sealed row is exported")
    out = nuggets[0]
    claim(out["verification_kind"] == "asserted",
          "as an assertion — the weakest rung jeles has")
    say(f"kind={AMBER}{out['verification_kind']!r}{OFF}  "
        f"verified_by={out['verified_by']!r}  written_by={out['written_by']!r}")
    claim(bool(dropped) and "seal_sig" in dropped[0]["lost"],
          "and the signature is named as dropped")
    say(f"{RED}dropped at the border{OFF}: "
        f"{', '.join(sorted(dropped[0]['lost']))}")
    note("Not caution. put_nugget rejects unknown kwargs and the record has")
    note("eleven fields, none for evidence — so 'human' would be a claim this")
    note("package could no longer back once it had crossed.")

    # ---------------------------------------------------------------- 5
    beat(5, "Landing it, route A — without the original id")
    landed = corpus.put_nugget(**out)
    gap(landed.get("action") == "created",
        "a write with no id still creates a second record")
    say(f"put_nugget(...) -> {landed}")
    hits = corpus.search_nuggets(QUESTION, limit=10)
    gap(len(hits) == 2, "so the corpus now holds two records for one question")
    for h in hits:
        mark = GREEN if h.get("verification_kind") == "human" else AMBER
        say(f"   {mark}{h.get('verification_kind'):9}{OFF} by "
            f"{h.get('verified_by')!r}  {h.get('_id')}")
    now = corpus.ask_corpus(QUESTION)
    gap(now["nugget"]["verified_by"] == THEIRS,
        "and jeles still serves the original, because human outranks asserted")
    say(f"jeles serves: {now['nugget']['verified_by']!r} "
        f"({now['nugget']['verification_kind']})")
    note("The round trip's contribution is invisible and the corpus is one row")
    note("bigger. Nothing warned anybody.")

    # ---------------------------------------------------------------- 6
    beat(6, "Landing it, route B — with the original id")
    refused = corpus.put_nugget(**{**out, "nugget_id": n["_id"]})
    gap(refused.get("error") == "kind_downgrade_refused",
        "a downgrade against the original id is refused outright")
    say(f"{RED}{refused.get('error')}{OFF}")
    note(refused.get("detail", ""))
    note("Which is a good guard with a better error message than most, and it")
    note("is the other half of the same wall.")

    # ---------------------------------------------------------------- 7
    beat(7, "Nobody is wrong")
    say("inbound   demoted, because verified_by is unsigned here")
    say("outbound  degraded, because a nugget has nowhere to put evidence")
    say("landing   duplicated, or refused as a downgrade")
    say()
    say(f"{BOLD}Every one of those is correct behaviour on both sides.{OFF}")
    say("The two trust models are nearly identical and were arrived at")
    say("independently, by people who had never read each other's code.")
    say(f"The asymmetry is that {BOLD}one of them has a field for a "
        f"signature{OFF}.")
    say()
    say(f"{DIM}{JB.PROPOSAL}{OFF}")
    claim("propose" in JB.PROPOSAL.lower(),
          "and the fix is proposed rather than made — it is their schema")

    if args.keep:
        print(f"\n   {DIM}kept: {work}{OFF}")
    else:
        shutil.rmtree(work, ignore_errors=True)

    if _FAILURES:
        print(f"\n{RED}{len(_FAILURES)} claim(s) no longer hold:{OFF}")
        for f in _FAILURES:
            print(f"  - {f}")
        return 1
    print(f"\n{GREEN}Every claim above held.{OFF}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
