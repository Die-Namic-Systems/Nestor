#!/usr/bin/env python3
"""Step 2 of the quorum memo — count who countersigns, over a real chain.

    python scripts/count_countersignatures.py --ledger /path/to/ledger.jsonl

`docs/seal-staleness-and-quorum.md` §5 lists four steps toward N-of-M sealing.
Step 1 shipped (IDEAS §6.26 — concurrence stopped being discarded). Step 2 is
the one the memo ends on, in three words: **"Nobody has run it."** Everything
below it in that list is blocked on the answer, because N-of-M is a schema
change to the audited path and designing one for users who have not been shown
to exist is how a field ends up carrying a distinction nothing else makes.

This runs it. It reads a chain and answers *how many distinct people
countersign*, which is not the same as how many countersignature entries there
are, and not the same as whether anybody wants quorum.

**Distinct actors is the measurement; entries are the evidence.** The memo
raises this before anybody runs it, and it is the whole reason this is a script
rather than a `grep -c`: a seal is idempotent and a countersignature is not.
Sealing three times as `rita` records one entry; countersigning three times as
`sam` records three, deliberately — three attestations with three timestamps and
three signatures, which an append-only chain exists to keep rather than
collapse. So a raw line count is inflated by every UI retry and flaky client.
Both numbers are printed, because the gap between them is the thing that would
have made the naive answer wrong.

**A zero can mean two entirely different things, and only one of them is data.**

    nobody countersigned, and somebody could have  →  evidence about quorum
    nobody countersigned, and nobody else was there →  evidence about nothing

The discriminator is in the chain: count the distinct people who ever decided
anything in it. A chain with one named actor could not have produced a
countersignature under any circumstances — `add_pair` requires ``first and
verifier and first != verifier`` before it logs one — so a zero from that chain
says nothing about whether reviewers concur. Reporting it as "no demand for
quorum" would be the `feed_all.py` mistake with different nouns: *nothing
matched* and *I could not look* are different sentences, and so are *they did
not* and *they could not*.

**It reads the chain and nothing else.** No store, no matcher, no process-wide
globals, no writes. Point it at a deployment's ledger and it cannot disturb it.
The chain is verified first, and a chain that does not verify gets no count at
all — a tally over an entry somebody may have edited is worse than no tally,
because it looks like a measurement.

**A note on what "two verifiers" is worth.** jeles reaches the same bar of 2 by
a different road (`jeles/_independence.py`, MIN_INDEPENDENT_SOURCES) and is
careful to say what it is not: two distinct domains can still be one actor who
bought both, so the count is "a cheap heuristic, deliberately weaker" than its
constitution's Independent Witness. The same caveat lands harder here. jeles at
least has ``registrable_domain`` to collapse two pages on one site into one
source. There is no such function for people, and two names in the ``verifier``
column can be one person with two keys. This counts names.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from nestor import ledger                              # noqa: E402

BOLD, DIM, GREEN, AMBER, RED, CYAN, OFF = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[36m", "\033[0m")

#: The bar step 4 would enforce, if step 2 ever says quorum is wanted. Named
#: here rather than imported from anywhere: nothing in the package enforces it
#: yet, so importing a constant would imply a mechanism that does not exist.
QUORUM = 2

#: The four things this can conclude. Only ``MEASURED`` is data about quorum.
UNREADABLE = "could not look"
BROKEN = "chain does not verify"
NO_OPPORTUNITY = "no second reviewer"
MEASURED = "measured"


def read(path: pathlib.Path) -> list[dict] | None:
    """Chain entries, or ``None`` if it could not be read.

    ``None`` is *I could not look*. An empty list is *the chain is empty*, which
    is a fact about the chain. Keeping those apart is the same distinction
    ``scripts/feed_all.py`` exists to hold, and the reason it exists is that an
    earlier pair of feeders printed one sentence for both.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    entries = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            got = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(got, dict):
            return None
        entries.append(got)
    return entries


def measure(entries: list[dict]) -> dict:
    """The counts, with the inflated one kept beside the real one.

    ``countersign_entries`` is what ``grep -c`` would report. ``countersign_acts``
    is distinct ``(pair_id, verifier)`` — the number the memo asks for. They
    differ by exactly the repeat attestations, which is why both are returned
    rather than one being quietly preferred.
    """
    # Every named actor, whatever kind of decision they made. Deliberately not a
    # per-kind allow-list: that would be a second table of ledger kinds to keep
    # in step with cascade.LEDGER_KINDS, and a kind missing from it would
    # under-count the very population that decides whether a zero means
    # anything. An entry that names a verifier had somebody behind it.
    actors = {str(e["verifier"]) for e in entries
              if isinstance(e.get("verifier"), str) and e["verifier"].strip()}
    # `countersigned` names the first sealer, so a countersignature identifies
    # both parties on its own. That matters for a chain written with audit=False
    # on the seal path, where the `seal` entry is absent and the countersignature
    # is the only record either of them was there.
    actors |= {str(e["countersigned"]) for e in entries
               if isinstance(e.get("countersigned"), str) and e["countersigned"].strip()}

    counters = [e for e in entries if e.get("kind") == "countersign"]
    acts = {(str(e.get("pair_id") or ""), str(e.get("verifier") or ""))
            for e in counters}

    # Who attested to each pair — the sealer plus everyone who countersigned it.
    attesters: dict[str, set] = collections.defaultdict(set)
    for e in entries:
        pair_id = str(e.get("pair_id") or "")
        if not pair_id:
            continue
        if e.get("kind") == "seal" and e.get("verifier"):
            attesters[pair_id].add(str(e["verifier"]))
        elif e.get("kind") == "countersign":
            for field in ("verifier", "countersigned"):
                if e.get(field):
                    attesters[pair_id].add(str(e[field]))

    at_quorum = {p: who for p, who in attesters.items() if len(who) >= QUORUM}
    by_person = collections.Counter(v for _, v in acts)
    return {
        "entries": len(entries),
        "actors": sorted(actors),
        "seals": sum(1 for e in entries if e.get("kind") == "seal"),
        "countersign_entries": len(counters),
        "countersign_acts": len(acts),
        "countersigners": by_person,
        "pairs_attested": len(attesters),
        "pairs_at_quorum": len(at_quorum),
        "at_quorum": at_quorum,
    }


def verdict(found: dict) -> str:
    """Which of the four conclusions the numbers support."""
    if len(found["actors"]) < QUORUM:
        return NO_OPPORTUNITY
    return MEASURED


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ledger", required=True, help="a ledger.jsonl to read")
    ap.add_argument("--quiet", action="store_true", help="the numbers, no prose")
    args = ap.parse_args()

    path = pathlib.Path(args.ledger)
    print(f"\n{BOLD}who countersigns?{OFF}  {DIM}{path}{OFF}")

    entries = read(path)
    if entries is None:
        print(f"   {RED}{UNREADABLE}{OFF} — no readable chain at that path")
        print(f"   {DIM}Not 'nobody countersigns'. Nothing about this chain "
              f"is known.{OFF}\n")
        return 1

    ok, detail = ledger.verify(str(path)) if entries else (True, "")
    if not ok:
        print(f"   {RED}{BROKEN}{OFF} — {str(detail)[:70]}")
        print(f"   {DIM}Refusing to count over a chain somebody may have "
              f"edited. A tally on a broken{OFF}")
        print(f"   {DIM}trail is worse than none: it reads as a "
              f"measurement.{OFF}\n")
        return 1

    found = measure(entries)
    said = verdict(found)

    print(f"   {found['entries']} entrie(s), chain verifies, "
          f"{len(found['actors'])} named actor(s), {found['seals']} seal(s)")

    print(f"\n{BOLD}countersignatures{OFF}")
    raw, real = found["countersign_entries"], found["countersign_acts"]
    print(f"   {raw:4} entrie(s)          {DIM}what `grep -c countersign` "
          f"would say{OFF}")
    print(f"   {real:4} distinct (pair, verifier)   "
          f"{DIM}what step 2 asks for{OFF}")
    if raw != real:
        print(f"   {AMBER}{raw - real} repeat attestation(s){OFF} {DIM}— the gap "
              f"the raw count would have hidden.{OFF}")
    for who, n in found["countersigners"].most_common():
        print(f"        {who:24} {n} pair(s)")

    print(f"\n{BOLD}pairs at a bar of {QUORUM}{OFF}  "
          f"{DIM}distinct people attesting to one pair{OFF}")
    print(f"   {found['pairs_at_quorum']} of {found['pairs_attested']} "
          f"attested pair(s)")
    for pair_id, who in sorted(found["at_quorum"].items())[:8]:
        print(f"        {pair_id[:8]}…  {', '.join(sorted(who))}")

    print(f"\n{BOLD}verdict{OFF}")
    if said == NO_OPPORTUNITY:
        print(f"   {AMBER}{NO_OPPORTUNITY}{OFF} — "
              f"{len(found['actors'])} named actor(s) in the whole chain")
        if not args.quiet:
            print(f"   {DIM}A countersignature needs two people who both named "
                  f"themselves: add_pair logs one{OFF}")
            print(f"   {DIM}only when `first and verifier and first != "
                  f"verifier`. This chain never had the{OFF}")
            print(f"   {DIM}second one, so its zero is not evidence that "
                  f"reviewers decline to concur —{OFF}")
            print(f"   {DIM}it is evidence that nobody was asked. Step 2 stays "
                  f"open, and needs a chain{OFF}")
            print(f"   {DIM}from a deployment with more than one reviewer "
                  f"in it.{OFF}")
    else:
        print(f"   {GREEN}{MEASURED}{OFF} — {len(found['actors'])} people "
              f"decided things here, so a countersignature was available")
        if not args.quiet:
            if real == 0:
                print(f"   {CYAN}and none of them took it.{OFF} {DIM}That is "
                      f"the data step 2 wanted: the opportunity{OFF}")
                print(f"   {DIM}existed and went unused. One chain is one "
                      f"deployment, not a finding about{OFF}")
                print(f"   {DIM}the feature.{OFF}")
            else:
                print(f"   {DIM}{real} countersignature(s) by "
                      f"{len(found['countersigners'])} person/people. Step 4 "
                      f"designs N-of-M against{OFF}")
                print(f"   {DIM}the store rather than the serving path — "
                      f"sub-quorum stays a draft, which is{OFF}")
                print(f"   {DIM}already never served as verified.{OFF}")

    print(f"\n   {DIM}Counting names, not people. Two verifiers can be one "
          f"person with two keys, and{OFF}")
    print(f"   {DIM}nothing here can tell — jeles has registrable_domain() to "
          f"collapse two pages into{OFF}")
    print(f"   {DIM}one site; there is no such function for humans.{OFF}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
