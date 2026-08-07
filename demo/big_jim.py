#!/usr/bin/env python3
"""Big Jim Motors — a live desk, keyed on VIN, for a used-car lot.

    python demo/big_jim.py state                       # what the desk holds
    python demo/big_jim.py ask "the blue Civic"        # what it would serve
    python demo/big_jim.py draft VIN "what you'd tell a buyer"
    python demo/big_jim.py queue                       # what is awaiting a human
    python demo/big_jim.py seal PAIR_ID --verifier jim # a human, confirming
    python demo/big_jim.py reject PAIR_ID --verifier jim --reason "..."

**This is fiction.** Big Jim Motors does not exist and no vehicle below is real.
Rows carry ``origin="fixture:big-jim"``. By default the desk lives in a
temporary directory that is removed on exit; pass ``--home DIR`` to keep one
across runs, which is what makes it usable as an actual desk rather than a
walk-through.

Unlike ``demo/shoebox.py`` this is not a scripted argument with an ending. It is
a **standing desk**: a store, a chain and a surface that keep whatever you put
in them. It exists to be driven a command at a time by somebody playing the
verifier.

Why a car lot is a good fit, in one line each:

* *Sealed means a person checked it.* Odometer, title status, prior accident —
  disclosures, not opinions, with somebody's name attached.
* *The key is the VIN, not the prose.* "94 Civic", "Honda Civic EX" and
  ``1HGEJ6672841`` are one vehicle; :class:`VinMatcher` makes them one row.
* *The covenant is the sales floor.* A machine may draft "runs great, one
  owner". Only a human may confirm it, and the incentive to blur that is
  exactly why the rule is structural rather than advisory.

**Nothing here seals on anybody's behalf.** ``seal`` requires ``--verifier`` on
the command line, with no default and no ``$USER`` fallback, because a name a
script supplied is not a human checking anything (``TODO.md`` §5.1). The seal
goes through ``nestor.ui``, the same dispatch the browser calls.
"""
from __future__ import annotations

import argparse
import difflib
import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

os.environ.setdefault("NESTOR_SEAL_KEY", "big-jim-fixture-key-not-a-secret")

from demo import desks                                   # noqa: E402
from demo.desks import AMBER, BOLD, DIM, GREEN, OFF, RED  # noqa: E402
from nestor import memory                                # noqa: E402

ORIGIN = "fixture:big-jim"
SOURCE, TARGET = "vin", "disclosure"

# A VIN is 17 characters and excludes I, O and Q. Nobody on a forecourt types
# all 17, so this also accepts any long-enough alphanumeric run carrying a
# digit, and keys on its tail — which is how a dealer actually refers to a car.
_ALNUM_RUN = re.compile(r"[A-Z0-9]{6,}")

#: How many trailing characters of the VIN are the key. Six because that is
#: what gets read down a phone, and because the last six of a VIN are its
#: sequential production number — the part that actually distinguishes two cars
#: off the same line. Chosen before anything was measured, and it is a real
#: trade-off rather than a safe default: see `collides` in `state`.
KEY_TAIL = 6


class VinMatcher:
    """Two methods, which is the whole documented seam. Keys a car by its VIN.

    ``normalize`` finds the longest alphanumeric run containing a digit and
    returns its last :data:`KEY_TAIL` characters, so a full VIN and a tail
    quoted down the phone reach the same row. Text with no such run falls back
    to the lowercased prose, which is a **worse** key and is meant to be: a
    description with no VIN in it should not confidently collide with anything.
    """

    def normalize(self, value) -> str:
        packed = re.sub(r"[^A-Z0-9]", "", str(value).upper())
        runs = [r for r in _ALNUM_RUN.findall(packed) if any(c.isdigit() for c in r)]
        if not runs:
            return str(value).strip().lower()
        return max(runs, key=len)[-KEY_TAIL:]

    def similarity(self, a_norm: str, b_norm: str) -> float:
        if a_norm == b_norm:
            return 1.0
        return difflib.SequenceMatcher(None, a_norm, b_norm).ratio()


MATCHER = VinMatcher()


def open_desk(home: str) -> desks.Desk:
    root = pathlib.Path(home)
    return desks.Desk(name="lot", root=root, source_lang=SOURCE,
                      target_lang=TARGET, matcher=MATCHER, origin=ORIGIN).open()


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def cmd_state(desk: desks.Desk, args) -> int:
    rows = desk.rows()
    sealed = [r for r in rows if r["status"] == "sealed"]
    drafts = [r for r in rows if r["status"] == "draft"]
    print(f"\n{BOLD}Big Jim Motors{OFF}  {DIM}{SOURCE}→{TARGET}, keyed on the last "
          f"{KEY_TAIL} of the VIN{OFF}")
    print(f"   store  {len(rows)} row(s): {GREEN}{len(sealed)} sealed{OFF}, "
          f"{AMBER}{len(drafts)} draft{OFF}")
    print(f"   chain  {len(desk.chain())} entrie(s)")
    print(f"   home   {DIM}{desk.root}{OFF}")
    if rows:
        print()
        for r in rows:
            mark = f"{GREEN}✓{OFF}" if r["status"] == "sealed" else f"{AMBER}~{OFF}"
            who = r.get("verifier") or "-"
            print(f"   {mark} {r['source_norm']:>8}  {who:8} {r['source_text'][:44]}")
    # Two cars keyed the same is the trade-off KEY_TAIL makes; say so rather
    # than wait for it to surface as a wrong disclosure.
    keys = [r["source_norm"] for r in rows]
    collides = {k for k in keys if keys.count(k) > 1}
    if collides:
        print(f"\n   {RED}{len(collides)} key(s) held by more than one row{OFF}")
    return 0


def cmd_ask(desk: desks.Desk, args) -> int:
    query = " ".join(args.text)
    key = MATCHER.normalize(query)
    print(f"\n{DIM}query {OFF}{query}")
    print(f"{DIM}key   {OFF}{key!r}")
    hit = desk.best_sealed(query)
    if hit is not None:
        pair = hit["pair"]
        print(f"\n   {GREEN}✓ sealed{OFF}  {pair['target_text']}")
        print(f"   {DIM}verified by {pair.get('verifier')!r}, scored "
              f"{hit['similarity']:.3f}, sealed {pair.get('created_at','')[:10]}{OFF}")
        return 0

    # Not served. Say which not-served this is, in the shipped voice.
    candidates = memory.lookup(query, SOURCE, TARGET, store=desk.store,
                               matcher=MATCHER, context_threshold=0.0)
    print(f"\n   {AMBER}! pending{OFF}")
    if not candidates:
        print(f"   nothing in this domain matched at all — no candidate scored, "
              f"which\n   usually means {SOURCE}→{TARGET} is empty rather than that "
              f"the question\n   was strange")
        return 0
    best = max(candidates, key=lambda c: c["similarity"])
    kinds = ", ".join(sorted({c["pair"]["status"] for c in candidates}))
    if best["similarity"] >= memory.SEAL_THRESHOLD:
        print(f"   matched at {best['similarity']:.3f}, at or above "
              f"{memory.SEAL_THRESHOLD} — but nothing\n   sealed; above the bar "
              f"there is only {kinds}. Close is not the problem\n   here, "
              f"unverified is")
    else:
        print(f"   closest of {len(candidates)} candidate(s) is "
              f"{best['similarity']:.3f}, below {memory.SEAL_THRESHOLD} — the bar "
              f"exists\n   because a near miss served as verified is worse than no "
              f"answer")
    print(f"   {DIM}closest row: {best['pair']['source_text'][:56]}{OFF}")
    return 0


def cmd_draft(desk: desks.Desk, args) -> int:
    """A machine proposing. There is no route to sealed from here."""
    row = desk.propose(args.vin, " ".join(args.disclosure),
                       reason="Drafted by the machine. Nobody has checked it.")
    print(f"\n   {AMBER}~ draft{OFF} queued  {DIM}id {row['id']}{OFF}")
    print(f"   key      {row['source_norm']!r}")
    print(f"   vehicle  {row['source_text']}")
    print(f"   drafted  {row['target_text']}")
    print(f"\n   {DIM}It will not be served as verified. A human seals it or it "
          f"stays here.{OFF}")
    return 0


def cmd_queue(desk: desks.Desk, args) -> int:
    drafts = [r for r in desk.rows() if r["status"] == "draft"]
    if not drafts:
        print(f"\n   nothing is awaiting review — no draft rows in "
              f"{SOURCE}→{TARGET}")
        return 0
    print(f"\n{BOLD}Awaiting a human{OFF}  ({len(drafts)})")
    for r in drafts:
        print(f"\n   {AMBER}~{OFF} {r['id']}")
        print(f"     key      {r['source_norm']!r}")
        print(f"     vehicle  {r['source_text']}")
        print(f"     drafted  {r['target_text']}")
    return 0


def cmd_seal(desk: desks.Desk, args) -> int:
    """A human confirming. --verifier is required and has no default."""
    status, body = desk.seal_draft(args.pair_id, verifier=args.verifier,
                                   reason=args.reason or "")
    if status != 200:
        print(f"\n   {RED}refused ({status}){OFF}  {body}")
        return 1
    pair = body["pair"]
    print(f"\n   {GREEN}✓ sealed{OFF} by {pair.get('verifier')!r}")
    print(f"   key     {pair['source_norm']!r}")
    print(f"   serves  {pair['target_text']}")
    print(f"   {DIM}signed, appended to the chain, and served verbatim from now "
          f"on{OFF}")
    return 0


def cmd_reject(desk: desks.Desk, args) -> int:
    row = desk.store.memory_get(args.pair_id)
    if row is None:
        print(f"\n   {RED}no such pair{OFF}")
        return 1
    status, body = desk.ui_post("/api/reject-match", source=row["source_text"],
                                target_text=row["target_text"],
                                verifier=args.verifier, reason=args.reason or "")
    if status != 200:
        print(f"\n   {RED}refused ({status}){OFF}  {body}")
        return 1
    print(f"\n   {GREEN}recorded{OFF} — {args.verifier!r} says this is the wrong "
          f"answer for that query")
    print(f"   {DIM}signed and in the chain; it will not be served for it "
          f"again{OFF}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--home", default="", help="keep the desk here between runs")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("state", help="what the desk holds")
    a = sub.add_parser("ask", help="what it would serve")
    a.add_argument("text", nargs="+")
    d = sub.add_parser("draft", help="propose a disclosure (always a draft)")
    d.add_argument("vin")
    d.add_argument("disclosure", nargs="+")
    sub.add_parser("queue", help="what is awaiting a human")
    s = sub.add_parser("seal", help="a human confirming a draft")
    s.add_argument("pair_id")
    s.add_argument("--verifier", required=True, help="the person confirming")
    s.add_argument("--reason", default="")
    r = sub.add_parser("reject", help="a human refusing a match")
    r.add_argument("pair_id")
    r.add_argument("--verifier", required=True)
    r.add_argument("--reason", default="")

    args = ap.parse_args()
    import shutil
    import tempfile
    home = args.home or tempfile.mkdtemp(prefix="nestor-big-jim-")
    try:
        desk = open_desk(home)
        return {"state": cmd_state, "ask": cmd_ask, "draft": cmd_draft,
                "queue": cmd_queue, "seal": cmd_seal,
                "reject": cmd_reject}[args.cmd](desk, args)
    finally:
        if not args.home:
            shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
