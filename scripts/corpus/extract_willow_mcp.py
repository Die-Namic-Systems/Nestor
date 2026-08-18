#!/usr/bin/env python3
"""Shapes declared by `rudi193-cmd/willow-mcp` — rung 33.

    python scripts/corpus/extract_willow_mcp.py --repo /workspace/rudi193-cmd/willow-mcp \
        --out data/corpus/willow-mcp.db

Held out of the sequence at rung 7 as **active production**, and read here on the
operator's instruction. The reason for holding it has not gone away: the head
moved on the day of this run, so the `repo@commit` pin every row carries records
one afternoon rather than a settled repository. Rows from an archived repository
and rows from this one are not the same kind of fact, and only the pin says so.

Three shapes beyond the standard four:

* **persona** — the **fourth** schema this corpus has met for describing an
  agent: `Voice` / `Posture` / `Boundaries`, after rung 1's
  `Domain`/`Voice`/`Function`/`Direction`, rung 13's `Lineage`/`Type`/`Core
  function` and rung 21's `Register`/`Mandate`/`Namespace`. `Voice` is the only
  field that has survived all four.
* **boundary** — `**Boundaries:**` is stored separately from the persona, for the
  reason §6.74 gave when it split mandate from prohibition: they fail
  differently, and a store that merges them cannot say which was crossed.
* **permission** — `Tool | Permission`, the authorization each tool requires.
  A permission table is the most directly checkable claim in this repository:
  it is either what the code enforces or it is not.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import common                                                    # noqa: E402
import provenance                                                # noqa: E402

from nestor.sqlite_store import SqliteStore                      # noqa: E402

NAMED = {("tool", "permission"): "permission", ("intent", "willow-mcp call"): "intent",
         ("state", "meaning"): "state"}


def personas(root: pathlib.Path) -> tuple[list[tuple], list[tuple]]:
    """``(voices, boundaries)`` — how an agent speaks, and what it must not do."""
    voices, bounds = [], []
    for path in common.docs(root):
        for heading, block in common.sections(path.read_text(encoding="utf-8")):
            voice = common.field(block, "Voice")
            if not voice:
                continue
            posture = common.field(block, "Posture")
            voices.append((heading, voice[:600],
                           f"Posture: {posture[:300]}" if posture else "",
                           path, heading))
            edge = common.field(block, "Boundaries")
            if edge:
                bounds.append((heading, edge[:600], "stated boundary", path, heading))
    return voices, bounds


def named_tables(root: pathlib.Path) -> dict[str, list[tuple]]:
    out: dict[str, list[tuple]] = {v: [] for v in NAMED.values()}
    for path, heading, header, row in common.tables(root):
        shape = NAMED.get(tuple(header[:2]))
        if not shape or len(row) < 2 or len(row[0]) < 2 or len(row[1]) < 2:
            continue
        why = f"notes: {row[2]}"[:300] if len(row) > 2 else ""
        out[shape].append((row[0], row[1][:400], why, path, heading))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--name", default="willow-mcp")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    root = pathlib.Path(args.repo).resolve()
    if not common.require_checkout(root):
        return 1
    out = pathlib.Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    origin = provenance.Origin(args.name, root, __file__)
    voices, bounds = personas(root)
    tables = named_tables(root)
    plan, declined, symbols, defined = common.standard(root)
    plan = [("persona", voices, "agent", "voice"),
            ("boundary", bounds, "agent", "boundary"),
            ("permission", tables["permission"], "tool", "permission"),
            ("intent", tables["intent"], "intent", "call"),
            ("state", tables["state"], "state", "meaning"),
            *plan]

    store = SqliteStore(str(out))
    store.memory_init()
    try:
        common.load(store, plan, origin, declined, root)
        if defined:
            print(f"\n  docstring coverage: {len(symbols)}/{defined} "
                  f"({len(symbols) / defined:.0%}) definition(s) carry one")
    finally:
        store.close()
    print(f"\n  store: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
