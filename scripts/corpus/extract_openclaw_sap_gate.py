#!/usr/bin/env python3
"""Shapes declared by `rudi193-cmd/openclaw-sap-gate` — rung 5.

    python scripts/corpus/extract_openclaw_sap_gate.py \
        --repo /workspace/rudi193-cmd/openclaw-sap-gate --out data/corpus/openclaw-sap-gate.db

The first rung whose repository is mostly **code** — 2 markdown documents and
four Python modules. Two consequences, both of which generalise to most of the
remaining hundred:

* **Docstrings are a declared shape.** The author wrote what a thing is for,
  beside the thing. That is a pair, and it is a declaration rather than an
  inference. Its coverage is reported separately from the document coverage,
  because 15 docstrings across 41 definitions is a different fact from
  2 documents out of 2.
* **The rubric is claimed at last.** `# | Check | Status | Notes` was declined
  as noise in rungs 3 and 4 — fifteen rows in each — and is the author's
  standing security rubric. It became visible only because declined rows are
  printed by header rather than dropped.

Public repository.
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

DEFN_KEYS = ("term", "concept", "field", "name", "command", "option", "env var")


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

    origin = provenance.Origin("openclaw-sap-gate", root, __file__)
    symbols, defined = common.docstrings(root)
    plan = [
        ("docstring", symbols, "symbol", "docstring"),
        ("rubric", common.rubric(root), "check", "verdict"),
        ("finding", common.findings(root), "finding", "fix"),
        ("definition", definitions(root), "term", "term"),
    ]

    store = SqliteStore(str(out))
    store.memory_init()
    try:
        common.load(store, plan, origin, declined(root), root)
        print(f"\n  docstring coverage: {len(symbols)}/{defined} definition(s) "
              f"carry one")
    finally:
        store.close()
    print(f"\n  store: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
