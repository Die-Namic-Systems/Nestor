#!/usr/bin/env python3
"""Feed willow-mcp's specialist registry into Nestor — agent id in, role scope out.

    python scripts/feed_willow_roles.py --registry /path/to/bundle/config/specialists.json
    python scripts/feed_willow_roles.py --repo /path/to/willow-mcp
    python scripts/feed_willow_roles.py --repo … --keep DIR

The willow-mcp bundle carries the fleet's specialist registry at
``src/willow_mcp/bundle/config/specialists.json`` (schema
``specialist_registry_v1``): six dispatched specialists plus one non-dispatched
``orchestrator_seat``. The doc mirror at ``docs/ROLES.md`` is a view, not the
source — this feeder reads the JSON.

**Two shapes, one file.** Every ``specialists[]`` row and the top-level
``orchestrator_seat`` becomes ``add_pair(agent_id, "<FUNCTION>: <job>",
status="draft")``. Permissions, deny_tools, ``human_only`` and the
``receive_dispatch`` flag are carried as ``reason=``, so a reader looking at a
matched row learns not just what the seat *is* but what it *may not do* — the
denial half of the contract is the half that goes silent otherwise.

**The orchestrator seat is tagged distinctly.** Its ``human_only=true`` and
``receive_dispatch=false`` set it apart from the dispatched specialists; the
row's origin marks it, and the console output prints it in its own section so
"agents cannot run this seat" (ROLES.md) is visible at ingest time, not
buried in a permissions field.

**Read by parsing, never by importing.** ``json.load`` only.

**Absent, empty, and unreadable are three different sentences.** A missing
registry is unreadable (exit 1); a well-formed file with no specialists and no
orchestrator seat is empty (exit 0); anything is fed (exit 0).
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

DOMAIN = "specialist"
TARGET = "role_scope"
ORIGIN = "willow-mcp:specialist-registry"
MATCHER = patch_review.MATCHER

BOLD, DIM, GREEN, AMBER, RED, OFF = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m")

_REQUIRED = ("agent_id", "function", "job")


def resolve_registry(repo: str = "", registry: str = "") -> pathlib.Path | None:
    """Locate ``specialists.json`` under ``--registry`` or a ``--repo`` root."""
    if registry:
        path = pathlib.Path(registry)
        return path if path.is_file() else None
    if not repo:
        return None
    candidate = (pathlib.Path(repo) / "src" / "willow_mcp" / "bundle"
                 / "config" / "specialists.json")
    return candidate if candidate.is_file() else None


def parse(path: pathlib.Path) -> tuple[list[dict], dict | None] | None:
    """Return ``(specialists, orchestrator_seat)`` from the registry, or None."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(doc, dict):
        return None
    specialists = [s for s in doc.get("specialists", []) if isinstance(s, dict)]
    seat = doc.get("orchestrator_seat")
    if not isinstance(seat, dict):
        seat = None
    return specialists, seat


def _scope(row: dict) -> str:
    """The target text: FUNCTION + job — a one-line role scope."""
    return f"{row['function']}: {' '.join(row['job'].split())}"


def _reason(row: dict, is_seat: bool) -> str:
    """The denial half. What this row must NOT do, plus its dispatch stance."""
    permit = ", ".join(row.get("permissions", []) or []) or "(none)"
    deny = ", ".join(row.get("deny_tools", []) or []) or "(none)"
    not_job = " ".join((row.get("not_job") or "").split())
    entry = row.get("entry_mode") or "(unset)"
    dispatch = "human_only" if is_seat or row.get("human_only") else "dispatched"
    parts = [f"entry={entry}", f"stance={dispatch}"]
    if not_job:
        parts.append(f"not_job='{not_job}'")
    parts.append(f"permit=[{permit}]")
    parts.append(f"deny=[{deny}]")
    return " | ".join(parts)


class RolesIngestMismatch(RuntimeError):
    """The store holds something other than what was parsed."""


def ingest(specialists: list[dict], seat: dict | None, store) -> tuple[int, int]:
    written_s = 0
    for s in specialists:
        if not all(s.get(k) for k in _REQUIRED):
            continue
        memory.add_pair(
            s["agent_id"], _scope(s), DOMAIN, TARGET,
            status="draft",
            origin=f"{ORIGIN}:specialists",
            reason=_reason(s, is_seat=False),
            store=store, matcher=MATCHER,
        )
        written_s += 1
    written_seat = 0
    if seat and all(seat.get(k) for k in _REQUIRED):
        memory.add_pair(
            seat["agent_id"], _scope(seat), DOMAIN, TARGET,
            status="draft",
            origin=f"{ORIGIN}:orchestrator_seat",
            reason=_reason(seat, is_seat=True),
            store=store, matcher=MATCHER,
        )
        written_seat = 1
    return written_s, written_seat


def verify_ingested(specialists: list[dict], seat: dict | None, store) -> int:
    expected = {s["agent_id"]: memory._sha(_scope(s))
                for s in specialists if all(s.get(k) for k in _REQUIRED)}
    if seat and all(seat.get(k) for k in _REQUIRED):
        expected[seat["agent_id"]] = memory._sha(_scope(seat))
    landed = {c["source_text"]: c["target_text"]
              for c in store.memory_candidates(DOMAIN, TARGET)
              if str(c.get("origin", "")).startswith(ORIGIN)}
    problems = []
    for agent_id, want_sha in expected.items():
        if agent_id not in landed:
            problems.append(f"specialist never ingested: {agent_id}")
            continue
        got_sha = memory._sha(landed[agent_id])
        if got_sha != want_sha:
            problems.append(
                f"role_scope hash mismatch for '{agent_id}' "
                f"({got_sha} != {want_sha})")
    if problems:
        raise RolesIngestMismatch(
            f"{len(problems)} ingested row(s) do not match the registry:\n  "
            + "\n  ".join(problems))
    return len(expected)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--registry", default="",
                    help="path to a specialists.json (specialist_registry_v1)")
    ap.add_argument("--repo", default="",
                    help="willow-mcp checkout; resolves "
                         "src/willow_mcp/bundle/config/specialists.json under it")
    ap.add_argument("--keep", default="", help="leave the store behind here")
    args = ap.parse_args()
    if not args.registry and not args.repo:
        ap.error("one of --registry or --repo is required")

    path = resolve_registry(repo=args.repo, registry=args.registry)
    if path is None:
        print(f"{RED}no specialists.json found{OFF}")
        print(f"   {DIM}'I could not look' — refusing rather than reporting "
              f"zero specialists.{OFF}")
        return 1

    parsed = parse(path)
    if parsed is None:
        print(f"{RED}specialists.json at {path} is not readable JSON{OFF}")
        return 1
    specialists, seat = parsed

    if not specialists and not seat:
        print(f"\n{BOLD}willow roles → nestor{OFF}")
        print(f"   {AMBER}{path} declares 0 specialists and no orchestrator seat{OFF}")
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

    print(f"\n{BOLD}willow roles → nestor{OFF}  "
          f"{DIM}{DOMAIN}→{TARGET}, read by parsing{OFF}")
    print(f"   {DIM}registry: {path}{OFF}")

    written_s, written_seat = ingest(specialists, seat, store)
    skipped_s = len(specialists) - written_s
    print(f"   {len(specialists)} specialist(s), {written_s} written"
          + (f", {RED}{skipped_s} malformed{OFF}" if skipped_s else ""))
    print(f"   orchestrator seat: "
          + (f"{GREEN}1 written{OFF}" if written_seat
             else f"{AMBER}absent or malformed{OFF}"))

    try:
        verified = verify_ingested(specialists, seat, store)
    except RolesIngestMismatch as exc:
        print(f"\n{RED}ingest verification FAILED — refusing{OFF}")
        print(f"   {DIM}{exc}{OFF}\n")
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)
        raise
    print(f"   {GREEN}{verified} row(s) verified against the registry{OFF}")
    print()
    print(f"   {BOLD}dispatched specialists{OFF}")
    for s in specialists:
        if not all(s.get(k) for k in _REQUIRED):
            continue
        deny = ", ".join(s.get("deny_tools", []) or []) or "(none)"
        print(f"   {AMBER}~{OFF} {BOLD}{s['agent_id']:14}{OFF} {s['function']}")
        print(f"        {DIM}job     {OFF}{s['job']}")
        print(f"        {DIM}deny    {OFF}{deny}")
    if seat:
        print(f"\n   {BOLD}orchestrator seat (not dispatched){OFF}")
        deny = ", ".join(seat.get("deny_tools", []) or []) or "(none)"
        entry = seat.get("entry_mode") or "(unset)"
        print(f"   {RED}★{OFF} {BOLD}{seat['agent_id']:14}{OFF} {seat['function']}  "
              f"{DIM}entry={entry}, human_only={seat.get('human_only', False)}{OFF}")
        print(f"        {DIM}job     {OFF}{seat['job']}")
        print(f"        {DIM}not_job {OFF}{seat.get('not_job', '(none)')}")
        print(f"        {DIM}deny    {OFF}{deny}")

    print(f"\n{BOLD}do any two roles collide?{OFF}  "
          f"{DIM}threshold {memory.SEAL_THRESHOLD}{OFF}")
    all_rows = list(specialists) + ([seat] if seat else [])
    ids = [r["agent_id"] for r in all_rows
           if all(r.get(k) for k in _REQUIRED)]
    worst = (0.0, "", "")
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            score = round(MATCHER.score(a, b), 3)
            if score > worst[0]:
                worst = (score, a, b)
            if score >= memory.SEAL_THRESHOLD:
                print(f"   {RED}{score:.3f}  {a} ↔ {b}{OFF}")
    if worst[1]:
        below = worst[0] < memory.SEAL_THRESHOLD
        print(f"   closest pair: {worst[0]:.3f}  {worst[1]} ↔ {worst[2]}  "
              + (f"{GREEN}below the bar{OFF}" if below
                 else f"{RED}AT OR ABOVE THE BAR{OFF}"))

    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        print(f"\n   {RED}agent_ids used more than once: {', '.join(dupes)}{OFF}")

    sealed = sum(1 for r in store.memory_candidates(DOMAIN, TARGET)
                 if r["status"] == "sealed")
    chain = (work / "ledger.jsonl")
    lines = [x for x in chain.read_text(encoding="utf-8").splitlines()
             if x.strip()] if chain.exists() else []
    print(f"\n{BOLD}what is in the store{OFF}")
    print(f"   {written_s + written_seat} row(s), {AMBER}{sealed} sealed{OFF}, "
          f"{len(lines)} chain entrie(s)")
    print(f"   {DIM}Every row is a draft. Whether the permissions the registry{OFF}")
    print(f"   {DIM}names match what the running fleet actually enforces is a{OFF}")
    print(f"   {DIM}separate check — a person's job.{OFF}")

    if args.keep:
        print(f"\n   {DIM}kept: {work}{OFF}\n")
    else:
        shutil.rmtree(work, ignore_errors=True)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
