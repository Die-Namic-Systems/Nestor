#!/usr/bin/env python3
"""Shapes declared by `rudi193-cmd/safe-app-willow-grove` — rung 14.

    python scripts/corpus/extract_willow_grove.py --repo /workspace/safe-app-willow-grove \
        --out data/corpus/safe-app-willow-grove.db

A terminal dashboard: 73 markdown documents against 120 Python modules. It
carries the **plan schema** — `Goal` / `Architecture` / `Tech Stack` — first met
in rung 6, which is why that shape moved into `common.labelled` rather than
being copied here. Two repositories sharing a schema makes it the author's
convention; the same argument moved `findings` at rung 5 and `rubric` at rung 6.

Beyond that it declares nothing the standard four do not cover, so this file is
the plan shapes and a call.

**The source is private.** Store to gitignored `data/`; nothing committed.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import common                                                    # noqa: E402
import provenance                                                # noqa: E402

from nestor.sqlite_store import SqliteStore                      # noqa: E402


def corrections(root: pathlib.Path) -> list[tuple]:
    """`Claim | Status` — an audit revision retracting its own earlier findings.

    The most on-subject shape this corpus has met. Each row is a claim a previous
    revision made, and the verdict a later reading gave it: *Withdrawn* (the file
    is not in this repository), *Wrong* (the count was 45, it is 117), *Fixed*.

    A verification memory exists to answer whether a human checked something.
    This table is a human recording that they checked, and were wrong. Those
    rows are worth more than agreeing ones and they are the first in the corpus
    that carry their own refutation.
    """
    rows = []
    for path, heading, header, row in common.tables(root):
        if header[:2] != ["claim", "status"] or len(row) < 2:
            continue
        verdict = row[1]
        mark = verdict.split(".")[0].strip("* ").lower()
        rows.append((row[0], verdict[:600], f"verdict: {mark}", path, heading))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--name", default="safe-app-willow-grove")
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
    plan, declined, symbols, defined = common.standard(root)
    plan = [("correction", corrections(root), "claim", "verdict"),
            ("goal", common.labelled(root, "Goal"), "plan", "goal"),
            ("success", common.labelled(root, "Success"), "plan", "success"),
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
