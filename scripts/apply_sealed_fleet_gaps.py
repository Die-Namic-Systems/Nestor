#!/usr/bin/env python3
"""Apply Nestor-sealed fleet-gap decisions to Willow SOIL + dispatch desk.

When the operator seals a fleet-gap pair in Nestor (origin ``willow:gap:<id>:<dispatch>``),
that commitment is the signal to:
  - record in ``governance/decisions`` (charter store)
  - ``gap_resolve`` on the SOIL gap with the sealed line
  - ``dispatch_send`` to hanuman when the seal assigns build work

Idempotent via ``--ledger`` (default next to nestor.db): skips pairs already applied.

Example::

  export WILLOW_STORE_ROOT=~/github/willow/.willow/store
  export WILLOW_HOME=~/github/.willow
  python scripts/apply_sealed_fleet_gaps.py \\
    --db ~/.willow/nestor-phase1-gaps/nestor.db
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ORIGIN_RE = re.compile(r"^willow:gap:([a-f0-9]+):([A-F0-9]{8})$", re.I)
BUILD_RE = re.compile(r"assign Hanuman|grant Loki|grant.*frank", re.I)


def _parse_origin(origin: str) -> tuple[str, str] | None:
    m = ORIGIN_RE.match((origin or "").strip())
    if not m:
        return None
    return m.group(1), m.group(2).upper()


def _sealed_rows(db_path: Path) -> list[dict]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, source_text, target_text, origin, verifier, created_at
        FROM tm_pairs
        WHERE status = 'sealed'
          AND source_lang = 'fleet-gap'
          AND target_lang = 'fleet-gap'
        ORDER BY created_at ASC
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _load_applied(ledger: Path) -> set[str]:
    if not ledger.is_file():
        return set()
    done: set[str] = set()
    for line in ledger.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            done.add(json.loads(line)["nestor_pair_id"])
        except (json.JSONDecodeError, KeyError):
            continue
    return done


def _append_applied(ledger: Path, record: dict) -> None:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _assignment_md(
    *,
    gate_line: str,
    source_title: str,
    gap_id: str,
    dispatch_id: str,
    nestor_pair_id: str,
    verifier: str,
) -> str:
    return f"""# Work order (from Nestor seal)

**Operator seal:** {gate_line}
**Verifier:** {verifier or "—"}
**Nestor pair:** `{nestor_pair_id}`
**SOIL gap:** `{gap_id}` · Loki audit `{dispatch_id}`

## Context
{source_title}

## Done when
- Change is on a branch with tests where applicable.
- Handoff references this dispatch id and the gap id.
- Reply to willow with evidence paths (not assertions).

## References
- `$WILLOW_HOME/dispatch/{dispatch_id}/handoff.json`
- `$WILLOW_HOME/dispatch/{dispatch_id}/evidence-pack.md`
- `~/github/willow/design/willow-2.0-decommission-plan.md`
"""


def apply_row(row: dict, *, dry_run: bool) -> dict:
    parsed = _parse_origin(row.get("origin") or "")
    if not parsed:
        return {"skipped": True, "reason": "origin not willow:gap"}
    gap_id, dispatch_id = parsed
    target = (row.get("target_text") or "").strip()
    verifier = (row.get("verifier") or "").strip()
    pair_id = row["id"]
    title = row.get("source_text") or ""

    out: dict = {
        "nestor_pair_id": pair_id,
        "gap_id": gap_id,
        "dispatch_id": dispatch_id,
        "sealed": target,
        "verifier": verifier,
    }

    if dry_run:
        out["dry_run"] = True
        out["would_dispatch_hanuman"] = bool(BUILD_RE.search(target))
        return out

    from willow_mcp import gaps as gap_mod
    from willow_mcp.server import dispatch_send

    app_id = "willow"
    note = (
        f"Nestor seal ({verifier or 'operator'}): {target} "
        f"[pair={pair_id}]"
    )
    gap_result = gap_mod.resolve(gap_id, note=note)
    out["gap_resolve"] = gap_result

    charter_root = Path(
        os.environ.get("WILLOW_PROJECT_ROOT", "~/github/willow")
    ).expanduser()
    decisions_dir = charter_root / "governance" / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = decisions_dir / f"nestor-seal-{gap_id}-{stamp}.json"
    path.write_text(
        json.dumps(decision := {
            "kind": "nestor_fleet_gap_seal",
            "nestor_pair_id": pair_id,
            "gap_id": gap_id,
            "dispatch_audit": dispatch_id,
            "source_title": title,
            "commitment": target,
            "verifier": verifier,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }, indent=2)
        + "\n",
        encoding="utf-8",
    )
    out["governance_file"] = str(path)

    if BUILD_RE.search(target):
        brief = _assignment_md(
            gate_line=target,
            source_title=title,
            gap_id=gap_id,
            dispatch_id=dispatch_id,
            nestor_pair_id=pair_id,
            verifier=verifier,
        )
        disp = dispatch_send(
            app_id=app_id,
            to_app="hanuman",
            assignment_md=brief,
            summary=title[:120],
            role="builder",
            phase="operate",
            priority="normal",
            context_refs=[
                {"kind": "soil_gap", "id": gap_id},
                {"kind": "dispatch_audit", "id": dispatch_id},
                {"kind": "nestor_pair", "id": pair_id},
            ],
        )
        out["dispatch"] = disp
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", required=True, help="Nestor sqlite db path")
    ap.add_argument(
        "--ledger",
        default="",
        help="applied-id ledger (default: <db-dir>/applied-seals.jsonl)",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser()
    if not db_path.is_file():
        print(f"no such db: {db_path}", file=sys.stderr)
        return 1
    if not os.environ.get("WILLOW_STORE_ROOT", "").strip():
        print("WILLOW_STORE_ROOT must be set (charter SOIL store)", file=sys.stderr)
        return 1

    ledger = Path(args.ledger).expanduser() if args.ledger else db_path.parent / "applied-seals.jsonl"
    applied = _load_applied(ledger)
    rows = _sealed_rows(db_path)
    if not rows:
        print("no sealed fleet-gap pairs in db")
        return 0

    n = 0
    for row in rows:
        if row["id"] in applied:
            continue
        try:
            result = apply_row(row, dry_run=args.dry_run)
        except Exception as exc:
            print(f"FAILED {row['id']}: {exc}", file=sys.stderr)
            return 1
        if result.get("skipped"):
            continue
        print(json.dumps(result, indent=2))
        if not args.dry_run:
            _append_applied(ledger, result)
        n += 1

    print(f"applied {n} seal(s)" + (" (dry-run)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
