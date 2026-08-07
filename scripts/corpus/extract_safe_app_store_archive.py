#!/usr/bin/env python3
"""Shapes declared by `safe-app-store-private-archive-20260608` — rung 13.

    python scripts/corpus/extract_safe_app_store_archive.py \
        --repo /workspace/safe-app-store-private-archive-20260608 \
        --out data/corpus/safe-app-store-archive.db

A snapshot taken before a cleanup, so it holds things the live repository may no
longer. Three shapes beyond the standard four:

* **lesson** — `.agents/skills/tui-design/references/exemplar-apps.md` studies
  existing terminal applications and ends each study with a `**Lessons:**`
  sentence. Those are design claims: *"when there are dozens of resource types,
  command mode beats menu navigation."* A claim about what works, drawn from
  something that shipped, is the most checkable kind of row this corpus has met.
* **stack** — the same records name what each exemplar is built with. Separate
  from the lesson on purpose: the lesson can be right while the stack is stale.
* **persona** — numbered character cards carrying `Lineage` and `Type`. These
  matter beyond their content because **rung 1 held the same characters under a
  different schema** (`Domain`/`Voice`/`Function`/`Direction`, three months
  earlier), which makes this the corpus's first chance to ask whether one
  author's description of one thing held still.

**The source is private.** Store to gitignored `data/`; nothing committed.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import common                                                    # noqa: E402
import provenance                                                # noqa: E402

from nestor.sqlite_store import SqliteStore                      # noqa: E402


def studies(root: pathlib.Path) -> tuple[list[tuple], list[tuple]]:
    """``(lessons, stacks)`` from the exemplar records."""
    lessons, stacks = [], []
    for path in common.docs(root):
        text = path.read_text(encoding="utf-8")
        if "**Lessons:**" not in text:
            continue
        for heading, block in common.sections(text):
            lesson = common.field(block, "Lessons")
            stack = common.field(block, "Stack")
            name = re.sub(r"^\d+[.)]\s*", "", heading).strip()
            if len(lesson) > 20:
                lessons.append((name, lesson[:700], "design study", path, heading))
            if len(stack) > 4:
                stacks.append((name, stack[:300], "exemplar stack", path, heading))
    return lessons, stacks


def personas(root: pathlib.Path) -> list[tuple]:
    """Numbered character cards: the name, and what it is for."""
    rows = []
    for path in common.docs(root):
        text = path.read_text(encoding="utf-8")
        if "**Lineage:**" not in text:
            continue
        for heading, block in common.sections(text):
            lineage = common.field(block, "Lineage")
            if not lineage:
                continue
            name = re.sub(r"^\d+[.)]\s*", "", heading).strip()
            function = (common.field(block, "Core function")
                        or common.field(block, "Function"))
            kind = common.field(block, "Type")
            if len(function) < 12:
                continue
            rows.append((name, function[:600],
                         f"Lineage: {lineage}" + (f" | Type: {kind}" if kind else ""),
                         path, heading))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--name", default="safe-app-store-archive")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    root = pathlib.Path(args.repo).resolve()
    out = pathlib.Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    origin = provenance.Origin(args.name, root, __file__)
    lessons, stacks = studies(root)
    plan, declined, symbols, defined = common.standard(root)
    plan = [("lesson", lessons, "exemplar", "lesson"),
            ("stack", stacks, "exemplar", "stack"),
            ("persona", personas(root), "persona", "function"),
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
