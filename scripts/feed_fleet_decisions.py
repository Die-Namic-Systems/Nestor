#!/usr/bin/env python3
"""Feed a fleet decision record into Nestor — question in, ratified commitment out.

    python scripts/feed_fleet_decisions.py --record /path/to/stores/decisions/fleet.json
    python scripts/feed_fleet_decisions.py --repo /path/to/safe-app-store
    python scripts/feed_fleet_decisions.py --repo … --keep DIR

The safe-app-store carries the fleet's ratified decision record at
``stores/decisions/fleet.json`` (schema `_contract` + `decisions[]` +
`rejections[]`). ``scripts/nestor_decisions_probe.py`` next to it seeded a
scratch store to *ask* questions of; this feeder is the persistent complement
— every question a row you can ``nestor decision check`` against.

**Two shapes come out of one file.** ``decisions[]`` are ``add_pair(question,
commitment, status="draft")`` — proposed for a person to seal in Nestor's UI,
even though the record has already been ratified by the fleet elsewhere.
``rejections[]`` are ``reject_match(question, option, reopen_when=...)`` — the
recorded no's, with ``reopen_when`` distinguishing NEVER from NOT YET
(docs/decision-memory.md N5).

**Why draft.** Ratification in the safe-app-store's git record is not the same
event as sealing in a Nestor keyring — a different human, a different key, a
different chain. The fleet's ``verified_by`` is preserved as ``reason`` on the
row; a person moving these to sealed in Nestor is a second, deliberate step
that this feeder must not shortcut. See the constitution feeder's header for
the same rule stated the same way.

**Read by parsing, never by importing.** ``json.load`` only — no arbitrary
code runs to get the rows. Every row traceable to a key in a merged PR.

**Absent, empty, and unreadable are three different sentences.** A missing
``fleet.json`` is unreadable (exit 1); a file with ``decisions: []`` and
``rejections: []`` is empty (exit 0, loud); a well-formed file with any rows
is fed (exit 0). This is the same distinction ``feed_all.py`` was written to
preserve.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

os.environ.setdefault("NESTOR_SEAL_KEY", "feed-fixture-key-not-a-secret")

from nestor import cascade, memory, storage          # noqa: E402
from nestor.sqlite_store import SqliteStore          # noqa: E402
from recipes import patch_review                     # noqa: E402

DOMAIN = "decision"
TARGET = "decision"  # same on both sides — mirrors dogfood_store.DOMAIN
ORIGIN = "safe-app-store:fleet-decisions"
MATCHER = patch_review.MATCHER

BOLD, DIM, GREEN, AMBER, RED, OFF = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m")

_REQUIRED_DECISION = ("question", "commitment", "reason", "verified_by", "date")
_REQUIRED_REJECTION = ("question", "option", "reason", "verified_by", "date")


def resolve_record(repo: str = "", record: str = "") -> pathlib.Path | None:
    """Locate ``fleet.json`` under ``--record`` or a ``--repo`` root."""
    if record:
        path = pathlib.Path(record)
        return path if path.is_file() else None
    if not repo:
        return None
    candidate = pathlib.Path(repo) / "stores" / "decisions" / "fleet.json"
    return candidate if candidate.is_file() else None


def parse(path: pathlib.Path) -> tuple[list[dict], list[dict]] | None:
    """Return ``(decisions, rejections)`` from a fleet.json, or None on parse fail."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(doc, dict):
        return None
    decs = [d for d in doc.get("decisions", []) if isinstance(d, dict)]
    rejs = [r for r in doc.get("rejections", []) if isinstance(r, dict)]
    return decs, rejs


class FleetIngestMismatch(RuntimeError):
    """The store holds something other than what was parsed."""


def _reason_for(row: dict) -> str:
    """The one-line reason field — carries the ratification provenance and why."""
    who = row.get("verified_by") or "(unknown verifier)"
    when = row.get("date") or "(undated)"
    why = " ".join((row.get("reason") or "").split())
    return f"ratified by {who} on {when} — {why}"


def ingest(decs: list[dict], rejs: list[dict], store) -> tuple[int, int]:
    """Write decisions as drafts, rejections via reject_match."""
    d_written = 0
    for d in decs:
        if not all(d.get(k) for k in _REQUIRED_DECISION):
            continue
        memory.add_pair(
            d["question"], d["commitment"], DOMAIN, TARGET,
            status="draft",
            origin=f"{ORIGIN}:decisions",
            reason=_reason_for(d),
            store=store, matcher=MATCHER,
        )
        d_written += 1
    r_written = 0
    for r in rejs:
        if not all(r.get(k) for k in _REQUIRED_REJECTION):
            continue
        memory.reject_match(
            r["question"], DOMAIN, TARGET,
            target_text=r["option"],
            verifier=r["verified_by"],
            reason=" ".join((r.get("reason") or "").split()),
            reopen_when=r.get("reopen_when") or "",
            store=store, matcher=MATCHER,
        )
        r_written += 1
    return d_written, r_written


def verify_ingested(decs: list[dict], store) -> int:
    """Hold what landed to the hash of what was parsed; raise on any mismatch."""
    expected = {d["question"]: memory._sha(d["commitment"])
                for d in decs if all(d.get(k) for k in _REQUIRED_DECISION)}
    landed = {c["source_text"]: c["target_text"]
              for c in store.memory_candidates(DOMAIN, TARGET)
              if str(c.get("origin", "")).startswith(f"{ORIGIN}:decisions")}
    problems = []
    for q, want_sha in expected.items():
        if q not in landed:
            problems.append(f"decision never ingested: {q[:64]}…")
            continue
        got_sha = memory._sha(landed[q])
        if got_sha != want_sha:
            problems.append(
                f"commitment hash mismatch for '{q[:48]}…' "
                f"({got_sha} != {want_sha})")
    if problems:
        raise FleetIngestMismatch(
            f"{len(problems)} ingested row(s) do not match fleet.json:\n  "
            + "\n  ".join(problems))
    return len(expected)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--record", default="",
                    help="path to a fleet.json (stores/decisions/fleet.json shape)")
    ap.add_argument("--repo", default="",
                    help="repo root; resolves stores/decisions/fleet.json under it")
    ap.add_argument("--keep", default="", help="leave the store behind here")
    args = ap.parse_args()
    if not args.record and not args.repo:
        ap.error("one of --record or --repo is required")

    path = resolve_record(repo=args.repo, record=args.record)
    if path is None:
        print(f"{RED}no fleet.json found{OFF}")
        print(f"   {DIM}'I could not look' — refusing rather than reporting "
              f"zero decisions.{OFF}")
        return 1

    parsed = parse(path)
    if parsed is None:
        print(f"{RED}fleet.json at {path} is not readable JSON{OFF}")
        return 1
    decs, rejs = parsed

    if not decs and not rejs:
        print(f"\n{BOLD}fleet decisions → nestor{OFF}")
        print(f"   {AMBER}{path} declares 0 decisions and 0 rejections{OFF}")
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

    print(f"\n{BOLD}fleet decisions → nestor{OFF}  "
          f"{DIM}{DOMAIN}→{TARGET}, read by parsing{OFF}")
    print(f"   {DIM}record: {path}{OFF}")

    d_written, r_written = ingest(decs, rejs, store)
    d_skipped = len(decs) - d_written
    r_skipped = len(rejs) - r_written
    print(f"   {len(decs)} decision(s), {d_written} written"
          + (f", {RED}{d_skipped} malformed{OFF}" if d_skipped else ""))
    print(f"   {len(rejs)} rejection(s), {r_written} written"
          + (f", {RED}{r_skipped} malformed{OFF}" if r_skipped else ""))

    try:
        verified = verify_ingested(decs, store)
    except FleetIngestMismatch as exc:
        print(f"\n{RED}ingest verification FAILED — refusing{OFF}")
        print(f"   {DIM}{exc}{OFF}\n")
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)
        raise
    print(f"   {GREEN}{verified} decision row(s) verified against fleet.json{OFF}")
    print()
    for d in decs:
        if not all(d.get(k) for k in _REQUIRED_DECISION):
            continue
        print(f"   {AMBER}~{OFF} {BOLD}{d['date']}{OFF} "
              f"{DIM}({d.get('verified_by', '?')}){OFF}")
        print(f"        {DIM}Q {OFF}{d['question'][:96]}")
        print(f"        {DIM}A {OFF}{d['commitment'][:96]}")
    for r in rejs:
        if not all(r.get(k) for k in _REQUIRED_REJECTION):
            continue
        reopen = r.get("reopen_when") or ""
        tag = f"{AMBER}not-yet{OFF}" if reopen else f"{RED}never{OFF}"
        print(f"   {RED}✗{OFF} {BOLD}{r['date']}{OFF} {tag}")
        print(f"        {DIM}Q {OFF}{r['question'][:96]}")
        print(f"        {DIM}× {OFF}{r['option'][:96]}")
        if reopen:
            print(f"        {DIM}reopen when {OFF}{reopen[:96]}")

    print(f"\n{BOLD}do any two questions collide?{OFF}  "
          f"{DIM}threshold {memory.SEAL_THRESHOLD}{OFF}")
    qs = [d["question"] for d in decs
          if all(d.get(k) for k in _REQUIRED_DECISION)]
    worst = (0.0, "", "")
    for i, a in enumerate(qs):
        for b in qs[i + 1:]:
            score = round(MATCHER.score(a, b), 3)
            if score > worst[0]:
                worst = (score, a[:48], b[:48])
            if score >= memory.SEAL_THRESHOLD:
                print(f"   {RED}{score:.3f}  '{a[:48]}…' ↔ '{b[:48]}…'{OFF}")
    if worst[1]:
        below = worst[0] < memory.SEAL_THRESHOLD
        print(f"   closest pair: {worst[0]:.3f}  '{worst[1]}…' ↔ '{worst[2]}…'  "
              + (f"{GREEN}below the bar{OFF}" if below
                 else f"{RED}AT OR ABOVE THE BAR{OFF}"))

    sealed = sum(1 for r in store.memory_candidates(DOMAIN, TARGET)
                 if r["status"] == "sealed")
    chain = (work / "ledger.jsonl")
    lines = [x for x in chain.read_text(encoding="utf-8").splitlines()
             if x.strip()] if chain.exists() else []
    print(f"\n{BOLD}what is in the store{OFF}")
    print(f"   {d_written} decision(s), {r_written} rejection(s), "
          f"{AMBER}{sealed} sealed{OFF}, {len(lines)} chain entrie(s)")
    print(f"   {DIM}Every decision row is a draft. Ratification in the fleet's{OFF}")
    print(f"   {DIM}git record is not sealing in Nestor's keyring — a person's job.{OFF}")

    if args.keep:
        print(f"\n   {DIM}kept: {work}{OFF}\n")
    else:
        shutil.rmtree(work, ignore_errors=True)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
