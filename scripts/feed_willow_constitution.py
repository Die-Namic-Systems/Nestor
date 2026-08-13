#!/usr/bin/env python3
"""Feed the charter's constitution case cards into Nestor — clause in, forbidden act out.

    python scripts/feed_willow_constitution.py --cases /path/to/governance/compliance/cases
    python scripts/feed_willow_constitution.py --repo /path/to/willow   # resolves …/governance/compliance/cases
    python scripts/feed_willow_constitution.py --cases … --keep DIR

Declarative cards live in the willow charter
(``governance/compliance/cases/``): each ``const_*.py`` declares a ``TRACE_ID``,
a ``CLAUSE``, and a docstring ending *"The forbidden act, in one line: …"*
(or ``Forbidden act:``). Executable willow-2.0 probes are archived; these
files are constants only.

**The pair is clause → forbidden act**, and the question a seal would answer is
the one nobody currently asks: *does the act this probe actually attacks match
the rule the clause states?* A compliance probe is worth its name only if those
two agree, and they are prose on both sides — no test can check prose against
prose, which is exactly the shape of thing this package is for.

**Read by parsing, never by importing.** :func:`extract` uses `ast` and reads
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
ORIGIN = "willow:constitution"
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


def resolve_cases_dir(repo: str = "", cases: str = "") -> pathlib.Path | None:
    """Locate ``const_*.py`` cards under ``--cases`` or a charter / legacy ``--repo``."""
    if cases:
        path = pathlib.Path(cases)
        return path if path.is_dir() else None
    if not repo:
        return None
    root = pathlib.Path(repo)
    for rel in (
        "governance/compliance/cases",
        "constitution/cases",
    ):
        candidate = root / rel
        if candidate.is_dir():
            return candidate
    return None


class ConstitutionIngestMismatch(RuntimeError):
    """The store holds something other than what was parsed — contamination,
    surfaced as an error rather than swallowed as 'nothing found'."""


def _target_for(row: dict) -> str:
    """The exact target text a row is ingested under — the placeholder
    substitution is part of the value, so verification must key off the same
    string add_pair was handed, not the raw ``forbidden``."""
    return row["forbidden"] or "(the docstring names no forbidden act)"


def ingest_rows(rows: list[dict], store) -> None:
    """Write each clause → forbidden-act pair as a draft. One place, so the
    string add_pair receives and the string :func:`verify_ingested` re-hashes
    are produced by the same code and cannot drift apart."""
    for r in rows:
        memory.add_pair(r["clause"], _target_for(r), DOMAIN, TARGET, status="draft",
                        origin=f"{ORIGIN}:{r['file']}", store=store, matcher=MATCHER,
                        reason=f"{r['trace_id']} — {r['doc_first']}")


def verify_ingested(rows: list[dict], store) -> int:
    """Hold what landed to the hash of what was parsed; raise on any mismatch.

    This is the ``got != digest`` shape ``scripts/dogfood_store.py --verify``
    uses on the committed store, per row: recompute the digest from the source
    of truth (the parsed cards) and refuse when the store disagrees. It reuses
    :func:`nestor.memory._sha` — the same digest the store itself writes — so
    there is one hash definition, not a parallel one bolted on here.

    A corrupted, partial, or mismatched ingest — a clause the store dropped, a
    forbidden act it stored other than the one parsed — becomes a loud error,
    never a silent pass that reads as "no findings". Returns the row count on a
    clean match.
    """
    expected = {r["clause"]: memory._sha(_target_for(r)) for r in rows}
    landed = {c["source_text"]: c["target_text"]
              for c in store.memory_candidates(DOMAIN, TARGET)
              if str(c.get("origin", "")).startswith(ORIGIN)}
    problems = []
    for clause, want_sha in expected.items():
        if clause not in landed:
            problems.append(f"clause never ingested: {clause[:64]}…")
            continue
        got_sha = memory._sha(landed[clause])
        if got_sha != want_sha:
            problems.append(
                f"forbidden-act hash mismatch for clause '{clause[:48]}…' "
                f"({got_sha} != {want_sha})")
    if problems:
        raise ConstitutionIngestMismatch(
            f"{len(problems)} ingested row(s) do not match the parsed cards:\n  "
            + "\n  ".join(problems))
    return len(expected)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cases", default="",
                    help="directory of declarative const_*.py cards "
                         "(charter governance/compliance/cases)")
    ap.add_argument("--repo", default="",
                    help="charter or legacy willow-2.0 checkout; resolves cases under it")
    ap.add_argument("--keep", default="", help="leave the store behind here")
    args = ap.parse_args()
    if not args.cases and not args.repo:
        ap.error("one of --cases or --repo is required")

    # Absent and empty are different facts. An earlier version printed one
    # message for both, which is the same conflation the jeles feeder had —
    # found by running these against an empty repository.
    cases_dir = resolve_cases_dir(repo=args.repo, cases=args.cases)
    if cases_dir is None:
        print(f"{RED}no compliance cases directory found{OFF}")
        print(f"   {DIM}'I could not look' — refusing rather than reporting "
              f"zero cases.{OFF}")
        return 1
    cases = sorted(cases_dir.glob("const_*.py"))
    if not cases:
        print(f"\n{BOLD}charter constitution → nestor{OFF}")
        print(f"   {AMBER}{cases_dir} exists and holds 0 const_*.py files{OFF}")
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

    print(f"\n{BOLD}charter constitution → nestor{OFF}  "
          f"{DIM}{DOMAIN}→{TARGET}, read by parsing{OFF}")
    print(f"   {DIM}cases: {cases_dir}{OFF}")

    rows = [c for c in (extract(p) for p in cases) if c]
    skipped = len(cases) - len(rows)
    print(f"   {len(cases)} case file(s), {len(rows)} parsed"
          + (f", {RED}{skipped} without TRACE_ID/CLAUSE{OFF}" if skipped else ""))

    no_act = [r for r in rows if not r["forbidden"]]
    ingest_rows(rows, store)

    # Verify what it ingested. A corrupted or partial ingest — a clause the
    # store dropped, a forbidden act it stored other than the one parsed — is a
    # loud error here, never a silent pass. Contamination surfaces as an error,
    # not as "no findings".
    try:
        verified = verify_ingested(rows, store)
    except ConstitutionIngestMismatch as exc:
        print(f"\n{RED}ingest verification FAILED — refusing{OFF}")
        print(f"   {DIM}{exc}{OFF}\n")
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)
        raise
    print(f"   {GREEN}{verified} row(s) verified against the parsed cards{OFF}")
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
