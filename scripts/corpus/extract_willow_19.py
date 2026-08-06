#!/usr/bin/env python3
"""Shapes declared by `rudi193-cmd/willow-1.9` — rung 6.

    python scripts/corpus/extract_willow_19.py \
        --repo /workspace/rudi193-cmd/willow-1.9 --out data/corpus/willow-1.9.db

The largest checkout in the sequence so far — 134 markdown documents against 279
Python modules — and archived, which is why it is safe to read: an archived
repository has a head that will not move under the `repo@commit` pin every row
carries.

The document schema is a **plan**: `**Goal:**` says what is to be built,
`**Success:**` says how you would know, and `**When:**` (on the powers rather
than the plans) says when the thing fires. Those are three different claims
about one document and are stored as three shapes, for the same reason rung 4
split `*Measure:*` from `*Reference:*` — a document can keep one promise and
break another, and a store that merges them cannot say which.

Public, archived.
"""
from __future__ import annotations

import argparse
import collections
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import common                                                    # noqa: E402
import provenance                                                # noqa: E402

from nestor.sqlite_store import SqliteStore                      # noqa: E402

DEFN_KEYS = ("term", "concept", "field", "name", "command", "tool", "env var",
             "option", "table", "key", "module", "file")


def title(path: pathlib.Path, text: str) -> str:
    """The document's own H1, falling back to its filename."""
    m = re.search(r"^#\s+(.+)$", text, re.M)
    return " ".join(m.group(1).split()) if m else path.stem


def _labelled(root: pathlib.Path, label: str, minimum: int = 12) -> list[tuple]:
    """`(document title -> **label:** value)` wherever the label appears."""
    rows = []
    for path in common.docs(root):
        text = path.read_text(encoding="utf-8")
        value = common.field(text, label)
        if len(value) < minimum:
            continue
        why = " | ".join(x for x in (
            f"Architecture: {common.field(text, 'Architecture')[:200]}"
            if common.field(text, "Architecture") else "",
            f"Tech Stack: {common.field(text, 'Tech Stack')[:120]}"
            if common.field(text, "Tech Stack") else "",
        ) if x)
        rows.append((title(path, text), value[:600], why, path, label.lower()))
    return rows


def goals(root: pathlib.Path) -> list[tuple]:
    return _labelled(root, "Goal")


def successes(root: pathlib.Path) -> list[tuple]:
    return _labelled(root, "Success")


def whens(root: pathlib.Path) -> list[tuple]:
    return _labelled(root, "When")


def definitions(root: pathlib.Path) -> list[tuple]:
    rows = []
    for path, heading, header, row in common.tables(root):
        if header[0] not in DEFN_KEYS:
            continue
        tgt = " · ".join(c for c in row[1:] if c)
        if len(row[0]) < 2 or len(tgt) < 4:
            continue
        rows.append((row[0], tgt, f"columns: {' | '.join(header)}", path, heading))
    return rows


def declined(root: pathlib.Path) -> collections.Counter:
    out: collections.Counter = collections.Counter()
    for _p, _h, header, row in common.tables(root):
        if header[0] in DEFN_KEYS or header[:2] == ["#", "check"]:
            continue
        if len(row[0]) < 2 or len(" · ".join(row[1:])) < 4:
            continue
        out[" | ".join(header)] += 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    root = pathlib.Path(args.repo).resolve()
    out = pathlib.Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    origin = provenance.Origin("willow-1.9", root, __file__)
    symbols, defined = common.docstrings(root)
    plan = [
        ("goal", goals(root), "plan", "goal"),
        ("success", successes(root), "plan", "success"),
        ("when", whens(root), "power", "trigger"),
        ("docstring", symbols, "symbol", "docstring"),
        ("rubric", common.rubric(root), "check", "verdict"),
        ("finding", common.findings(root), "finding", "fix"),
        ("definition", definitions(root), "term", "term"),
    ]

    store = SqliteStore(str(out))
    store.memory_init()
    try:
        common.load(store, plan, origin, declined(root), root)
        print(f"\n  docstring coverage: {len(symbols)}/{defined} definition(s) carry one")
    finally:
        store.close()
    print(f"\n  store: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
