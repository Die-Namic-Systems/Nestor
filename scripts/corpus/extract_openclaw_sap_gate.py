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
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import common                                                    # noqa: E402
import provenance                                                # noqa: E402

from nestor.sqlite_store import SqliteStore                      # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    root = pathlib.Path(args.repo).resolve()
    if not common.require_checkout(root):
        return 1
    out = pathlib.Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    origin = provenance.Origin("openclaw-sap-gate", root, __file__)
    plan, declined, symbols, defined = common.standard(root)

    store = SqliteStore(str(out))
    store.memory_init()
    try:
        common.load(store, plan, origin, declined, root)
        print(f"\n  docstring coverage: {len(symbols)}/{defined} definition(s) "
              f"carry one")
    finally:
        store.close()
    print(f"\n  store: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
