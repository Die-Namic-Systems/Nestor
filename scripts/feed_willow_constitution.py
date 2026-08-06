#!/usr/bin/env python3
"""Feed willow-2.0's constitution into Nestor — clause in, forbidden act out.

    python scripts/feed_willow_constitution.py --repo /path/to/willow-2.0
    python scripts/feed_willow_constitution.py --repo … --keep DIR

The first repository fed into this store from outside the fleet's own decision
files. `willow-2.0/constitution/cases/` holds five compliance probes, each
declaring a ``TRACE_ID``, a ``CLAUSE`` naming what the constitution requires,
and a docstring ending *"The forbidden act, in one line: …"*.

**The pair is clause → forbidden act**, and the question a seal would answer is
the one nobody currently asks: *does the act this probe actually attacks match
the rule the clause states?* A compliance probe is worth its name only if those
two agree, and they are prose on both sides — no test can check prose against
prose, which is exactly the shape of thing this package is for.

**Read by parsing, never by importing.** These modules import `core.pg_bridge`,
`constitution.compliance` and friends; importing them would need willow's
dependencies and would run willow's code. :func:`extract` uses `ast` and reads
string literals only. That is the same remote-to-local rule
``scripts/dogfood_store.py`` states — every row traceable to a file somebody can
open, and nothing executed to get it.

**Everything lands as a draft.** Nothing here has been checked by a human in
*this* store, and a clause is exactly the kind of text that reads as settled
because it is written in the imperative.

**The matcher is `patch_review.DefectMatcher`, reused deliberately.** Clause text
is prose about mechanisms carrying identifiers — ``ledger_verify``,
``prev_hash``, ``_ratified_is_attested``, ``Article VI`` — which is the
population that matcher was built and benched for. A fourth matcher would have
been a new thing to justify with no evidence it behaves differently on this
text. If a bench ever shows it does, that is the moment to write one.
"""
from __future__ import annotations

import argparse
import ast
import os
import pathlib
import re
import shutil
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

os.environ.setdefault("NESTOR_SEAL_KEY", "feed-fixture-key-not-a-secret")

from nestor import cascade, memory, storage          # noqa: E402
from nestor.sqlite_store import SqliteStore          # noqa: E402
from recipes import patch_review                     # noqa: E402

DOMAIN = "clause"
TARGET = "forbids"
ORIGIN = "willow-2.0:constitution"
MATCHER = patch_review.MATCHER

BOLD, DIM, GREEN, AMBER, RED, OFF = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m")

#: The docstring's closing line. **Two things this got wrong first time**, both
#: of which produced a false finding about somebody else's repository:
#:
#: * the act wraps across lines, and a ``[^*\n]+`` class stopped at the first
#:   newline — CONST-0-3's act was reported cut off mid-clause;
#: * not every case uses the phrase "in one line". ``const_0_3_capability.py``
#:   writes plain ``Forbidden act:``, and requiring the longer form reported it
#:   as stating no forbidden act at all. It states one.
#:
#: So: both openings, and the value runs to the closing asterisk or the next
#: blank line rather than the next newline.
_FORBIDDEN = re.compile(
    r"(?:The\s+)?forbidden\s+act(?:,\s*in\s+one\s+line)?\s*:\s*\*?"
    r"(.+?)\*?(?:\n\s*\n|\Z)",
    re.I | re.S)


def _literal(node: ast.AST):
    """A module-level assignment's value, if it is a plain string literal."""
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        return None


def extract(path: pathlib.Path) -> dict | None:
    """``TRACE_ID``, ``CLAUSE`` and the forbidden act, by parsing. No import."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return None
    found: dict = {"file": path.name}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in ("TRACE_ID", "CLAUSE"):
                value = _literal(node.value)
                if isinstance(value, str):
                    found[target.id.lower()] = " ".join(value.split())
    doc = ast.get_docstring(tree) or ""
    match = _FORBIDDEN.search(doc)
    # Asterisks are the docstrings' emphasis markers, not content, and they
    # occur mid-value where the one-line act is followed by a qualifying clause
    # (CONST-0-4). Stripped everywhere rather than only at the ends.
    act = match.group(1).replace("*", " ") if match else ""
    found["forbidden"] = " ".join(act.split()).rstrip(".")
    found["doc_first"] = doc.splitlines()[0] if doc else ""
    if not found.get("trace_id") or not found.get("clause"):
        return None
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True, help="a willow-2.0 checkout")
    ap.add_argument("--keep", default="", help="leave the store behind here")
    args = ap.parse_args()

    # Absent and empty are different facts. An earlier version printed one
    # message for both, which is the same conflation the jeles feeder had —
    # found by running these against an empty repository.
    cases_dir = pathlib.Path(args.repo) / "constitution" / "cases"
    if not cases_dir.is_dir():
        print(f"{RED}no constitution/cases/ under {args.repo}{OFF}")
        print(f"   {DIM}'I could not look' — refusing rather than reporting "
              f"zero cases.{OFF}")
        return 1
    cases = sorted(cases_dir.glob("const_*.py"))
    if not cases:
        print(f"\n{BOLD}willow-2.0 constitution → nestor{OFF}")
        print(f"   {AMBER}constitution/cases/ exists and holds 0 const_*.py "
              f"files{OFF}")
        print(f"   {DIM}A true empty, not a failure.{OFF}\n")
        return 0

    work = pathlib.Path(args.keep) if args.keep else pathlib.Path(
        tempfile.mkdtemp(prefix="nestor-feed-"))
    work.mkdir(parents=True, exist_ok=True)
    cascade.set_ledger_path(str(work / "ledger.jsonl"))
    store = SqliteStore(str(work / "nestor.db"))
    store.init_db()
    store.memory_init()
    storage.set_store(store)

    print(f"\n{BOLD}willow-2.0 constitution → nestor{OFF}  "
          f"{DIM}{DOMAIN}→{TARGET}, read by parsing{OFF}")

    rows = [c for c in (extract(p) for p in cases) if c]
    skipped = len(cases) - len(rows)
    print(f"   {len(cases)} case file(s), {len(rows)} parsed"
          + (f", {RED}{skipped} without TRACE_ID/CLAUSE{OFF}" if skipped else ""))

    no_act = [r for r in rows if not r["forbidden"]]
    for r in rows:
        target = r["forbidden"] or "(the docstring names no forbidden act)"
        memory.add_pair(r["clause"], target, DOMAIN, TARGET, status="draft",
                        origin=f"{ORIGIN}:{r['file']}", store=store, matcher=MATCHER,
                        reason=f"{r['trace_id']} — {r['doc_first']}")
    print()
    for r in rows:
        mark = AMBER if r["forbidden"] else RED
        print(f"   {mark}~{OFF} {BOLD}{r['trace_id']:14}{OFF} {r['file']}")
        print(f"        {DIM}clause  {OFF}{r['clause'][:96]}…")
        print(f"        {DIM}forbids {OFF}{r['forbidden'] or '(none stated)'}")

    # The Nestor-native question: would this store ever serve one clause for
    # another? Two constitutional rules colliding above the bar is not a
    # curiosity — it is the store answering a question about §0.3 with §0.5.
    print(f"\n{BOLD}do any two clauses collide?{OFF}  "
          f"{DIM}threshold {memory.SEAL_THRESHOLD}{OFF}")
    worst = (0.0, "", "")
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            score = round(MATCHER.score(a["clause"], b["clause"]), 3)
            if score > worst[0]:
                worst = (score, a["trace_id"], b["trace_id"])
            if score >= memory.SEAL_THRESHOLD:
                print(f"   {RED}{score:.3f}  {a['trace_id']} ↔ {b['trace_id']}{OFF}")
    print(f"   closest pair: {worst[0]:.3f}  {worst[1]} ↔ {worst[2]}  "
          + (f"{GREEN}below the bar{OFF}" if worst[0] < memory.SEAL_THRESHOLD
             else f"{RED}AT OR ABOVE THE BAR{OFF}"))

    ids = [r["trace_id"] for r in rows]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        print(f"\n   {RED}trace ids used more than once: {', '.join(dupes)}{OFF}")

    sealed = sum(1 for r in store.memory_candidates(DOMAIN, TARGET)
                 if r["status"] == "sealed")
    chain = (work / "ledger.jsonl")
    lines = [x for x in chain.read_text(encoding="utf-8").splitlines()
             if x.strip()] if chain.exists() else []
    print(f"\n{BOLD}what is in the store{OFF}")
    print(f"   {len(rows)} row(s), {AMBER}{sealed} sealed{OFF}, "
          f"{len(lines)} chain entrie(s)")
    if no_act:
        print(f"   {RED}{len(no_act)} clause(s) state no forbidden act{OFF}: "
              f"{', '.join(r['trace_id'] for r in no_act)}")
    print(f"   {DIM}Every row is a draft. Whether each probe attacks the act its{OFF}")
    print(f"   {DIM}clause names is prose against prose — a person's job.{OFF}")

    if args.keep:
        print(f"\n   {DIM}kept: {work}{OFF}\n")
    else:
        shutil.rmtree(work, ignore_errors=True)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
