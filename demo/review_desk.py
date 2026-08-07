#!/usr/bin/env python3
"""The other desk — Nestor reading what is broken about Nestor.

    python demo/review_desk.py load                    # seed from IDEAS.md
    python demo/review_desk.py open                    # what is still broken
    python demo/review_desk.py bearing "two people share a name"
    python demo/review_desk.py ask "..."               # what it would serve

The second of the two desks: ``demo/big_jim.py`` takes the client's work in,
this one reviews the tool that records it. It runs ``recipes/patch_review.py``
— defect description in, proposed fix out, sealed when a human has read it.

**Seeded from the repository, never from the model.** ``load`` parses the
``### 6.N`` headings of ``IDEAS.md`` in this checkout and nothing else. That is
the same rule ``scripts/dogfood_store.py`` states and gates: a memory whose rows
came from somewhere nobody can see is not an audit trail, and a desk listing
defects an agent remembered is worth less than no desk. Every row here is
traceable to a line in a file that is in the diff.

**Everything lands as a draft**, including rows describing defects that are
demonstrably real. The status of a row is *has a human checked this*, not *is
this true*, and those are different questions — conflating them is the thing
this package exists to stop.

Why the intake desk asks this one first
---------------------------------------
Before serving anything about a person, the useful question is not *what do I
know* but *which of my answers can I not trust*. Several open findings bear
directly on reading a life rather than a spreadsheet — a name shared by two
people, an alias nobody has verified, a decision revised, a decision deferred.
:func:`cmd_bearing` is that lookup: given a risk in plain words, what does the
review desk already hold about it.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

os.environ.setdefault("NESTOR_SEAL_KEY", "review-desk-fixture-key-not-a-secret")

from demo import desks                                    # noqa: E402
from demo.desks import AMBER, BOLD, DIM, GREEN, OFF, RED   # noqa: E402
from hooks.review_receipt import record                   # noqa: E402
from nestor import memory                                 # noqa: E402
from recipes import patch_review                          # noqa: E402

REPO = pathlib.Path(__file__).resolve().parent.parent
IDEAS = REPO / "IDEAS.md"
ORIGIN = "fixture:review-desk"

#: ``### 6.37 Some title — **measured**, fix **open**``
_HEADING = re.compile(r"^### (6\.\d+) (.+?) — (.+)$", re.M)


def findings(text: str) -> list[dict]:
    """Every ``### 6.N`` entry, with the status its own heading claims.

    Deliberately no interpretation: an entry is open because its heading says
    ``open``, not because this module has a view about it.
    """
    out = []
    for num, title, status in _HEADING.findall(text):
        out.append({"num": num, "title": title.strip(),
                    "status": status.strip(),
                    "open": "open" in status.lower(),
                    "shipped": "shipped" in status.lower()})
    return out


def open_desk(home: str) -> desks.Desk:
    return desks.Desk(name="review", root=pathlib.Path(home),
                      source_lang=patch_review.DOMAIN,
                      target_lang=patch_review.DOMAIN,
                      matcher=patch_review.MATCHER, origin=ORIGIN).open()


def cmd_load(desk: desks.Desk, args) -> int:
    rows = findings(IDEAS.read_text(encoding="utf-8"))
    still_open = [f for f in rows if f["open"]]
    added = 0
    for f in still_open:
        defect = f"§{f['num']} {f['title']}"
        try:
            desk.propose(defect, f"open — see IDEAS.md §{f['num']}",
                         reason=f"Heading says: {f['status']}")
            added += 1
        except Exception as exc:                      # already held, or rival
            print(f"   {DIM}skipped §{f['num']}: {type(exc).__name__}{OFF}")
    record(REPO, f"load: {len(still_open)} open")
    print(f"\n   parsed {len(rows)} entrie(s) from IDEAS.md, "
          f"{len(still_open)} still open")
    print(f"   {AMBER}~{OFF} queued {added} draft(s) — none sealed, because "
          f"nobody here has checked them")
    return 0


def cmd_open(desk: desks.Desk, args) -> int:
    rows = desk.rows()
    print(f"\n{BOLD}What is still broken{OFF}  {DIM}({len(rows)} row(s), "
          f"all unverified){OFF}")
    for r in sorted(rows, key=lambda r: r["source_text"]):
        mark = f"{GREEN}✓{OFF}" if r["status"] == "sealed" else f"{AMBER}~{OFF}"
        print(f"   {mark} {r['source_text'][:88]}")
    print(f"\n   {DIM}chain: {len(desk.chain())} entrie(s) — a draft is not a "
          f"decision, so proposing appends nothing{OFF}")
    return 0


def cmd_bearing(desk: desks.Desk, args) -> int:
    """Which known defects bear on a risk described in plain words."""
    risk = " ".join(args.text)
    # Recorded here, before the lookup and before any early return: the receipt
    # attests that somebody asked, not that the answer was interesting. A
    # consultation that comes back empty is still a consultation — and given how
    # badly `bearing` scores on plain-English risks, empty is a common outcome.
    record(REPO, risk)          # clears hooks/before_write for a while
    print(f"\n{DIM}risk {OFF}{risk}")
    hits = memory.lookup(risk, patch_review.DOMAIN, patch_review.DOMAIN,
                         limit=4, store=desk.store, matcher=patch_review.MATCHER,
                         context_threshold=0.0)
    hits = [h for h in hits if h["similarity"] > 0.0]
    if not hits:
        print("\n   nothing in this domain matched at all — no candidate "
              "scored, which\n   usually means the desk is empty rather than "
              "that the question was strange")
        return 0
    print()
    for h in hits:
        pair, sim = h["pair"], h["similarity"]
        mark = f"{GREEN}✓{OFF}" if pair["status"] == "sealed" else f"{AMBER}~{OFF}"
        print(f"   {mark} {sim:.3f}  {pair['source_text'][:80]}")
    print(f"\n   {RED}None of these is served as verified.{OFF} They are "
          f"drafts: the desk\n   holds them because IDEAS.md says so, not "
          f"because anyone here checked.")
    return 0


def cmd_ask(desk: desks.Desk, args) -> int:
    query = " ".join(args.text)
    hit = desk.best_sealed(query)
    print(f"\n{DIM}query {OFF}{query}")
    if hit is None:
        print(f"\n   {AMBER}! pending{OFF} — nothing sealed matches. Every row "
              f"here is a draft,\n   so tier 1 is empty by construction.")
        return 0
    print(f"\n   {GREEN}✓ sealed{OFF}  {hit['pair']['target_text']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--home", default="", help="keep the desk here between runs")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("load", help="seed from IDEAS.md in this checkout")
    sub.add_parser("open", help="what is still broken")
    b = sub.add_parser("bearing", help="which defects bear on a risk")
    b.add_argument("text", nargs="+")
    a = sub.add_parser("ask", help="what it would serve as verified")
    a.add_argument("text", nargs="+")
    args = ap.parse_args()

    import shutil
    import tempfile
    home = args.home or tempfile.mkdtemp(prefix="nestor-review-")
    try:
        desk = open_desk(home)
        return {"load": cmd_load, "open": cmd_open, "bearing": cmd_bearing,
                "ask": cmd_ask}[args.cmd](desk, args)
    finally:
        if not args.home:
            shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
