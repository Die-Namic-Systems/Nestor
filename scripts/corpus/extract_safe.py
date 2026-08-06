#!/usr/bin/env python3
"""Shapes declared by `rudi193-cmd/SAFE` — rung 1 of the chronology.

    python scripts/corpus/extract_safe.py --repo /workspace/safe --out data/corpus/safe.db

Three shapes, each counted in the source before it was written: 5 identified
constraints, 21 four-field entries, and the definitional tables. Nothing is
inferred from prose — a row exists only where a heading or a table cell put it.

Every row lands as a **draft**. The extractor is a machine and may propose.

**The source is private and names minors.** The store this writes belongs in
gitignored `data/`, and nothing it produces should be committed without its
owner's decision. See IDEAS §6.41.
"""
from __future__ import annotations

import argparse
import collections
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import common                                                    # noqa: E402
import provenance                                                # noqa: E402

from nestor.sqlite_store import SqliteStore                      # noqa: E402

SKIP_HEADERS = {("field", "value"), ("beat", "function")}


def constraints(root: pathlib.Path) -> list[tuple]:
    """``HS-*`` / ``GOV-*`` blocks: the constraint, and what happens on trigger."""
    rows = []
    for path in common.docs(root):
        text = path.read_text(encoding="utf-8")
        for heading, block in common.sections(text):
            ident = heading.split(":")[0].strip()
            if not ident.startswith(("HS-", "GOV-")):
                continue
            constraint = common.field(block, "Constraint")
            # A stop states its commitment as a Response, or as Rules where the
            # commitment is a list. HS-005 is shaped the second way.
            target = common.field(block, "Response") or common.field(block, "Rules")
            if not (constraint and target):
                continue
            trigger = common.field(block, "Trigger")
            rows.append((f"{ident} — {constraint}", target,
                         f"Trigger: {trigger}" if trigger else "", path, ident))
    return rows


def facets(root: pathlib.Path) -> list[tuple]:
    """Entries carrying the four-field schema: Domain, Voice, Function, Direction."""
    rows = []
    for path in common.docs(root):
        for heading, block in common.sections(path.read_text(encoding="utf-8")):
            function = common.field(block, "Function")
            domain = common.field(block, "Domain")
            if not (function and domain):
                continue
            why = " | ".join(x for x in (
                f"Voice: {common.field(block, 'Voice')}" if common.field(block, "Voice") else "",
                f"Direction: {common.field(block, 'Direction')}" if common.field(block, "Direction") else "",
            ) if x)
            rows.append((f"{heading} ({domain})", function, why, path, heading))
    return rows


def definitions(root: pathlib.Path) -> tuple[list[tuple], collections.Counter]:
    """Two-column tables, minus the metadata ones. Declined rows are counted."""
    rows, declined = [], collections.Counter()
    for path, heading, header, row in common.tables(root):
        src, tgt = row[0], " · ".join(c for c in row[1:] if c)
        if len(src) < 2 or len(tgt) < 4:
            continue
        if tuple(header) in SKIP_HEADERS:
            declined[" | ".join(header)] += 1
            continue
        rows.append((src, tgt, f"columns: {' | '.join(header)}", path, heading))
    return rows, declined


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True, help="checkout of rudi193-cmd/SAFE")
    ap.add_argument("--out", required=True, help="store to write (overwritten)")
    args = ap.parse_args()

    root = pathlib.Path(args.repo).resolve()
    out = pathlib.Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    origin = provenance.Origin("safe", root, __file__)
    defs, declined = definitions(root)
    plan = [
        ("constraint", constraints(root), "constraint", "constraint"),
        ("facet", facets(root), "facet", "facet"),
        ("definition", defs, "term", "term"),
    ]

    store = SqliteStore(str(out))
    store.memory_init()
    try:
        common.load(store, plan, origin, declined)
    finally:
        store.close()
    print(f"\n  store: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
