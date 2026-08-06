#!/usr/bin/env python3
"""Shapes declared by `rudi193-cmd/willow-nest` — rung 7.

    python scripts/corpus/extract_willow_nest.py \
        --repo /workspace/rudi193-cmd/willow-nest --out data/corpus/willow-nest.db

Ten Python modules and a single markdown document, and it declares **no shape
this corpus has not already met**. So this file adds nothing: it runs
`common.standard` and stops.

That is the finding rather than a shortcut. Rung 7 needed byte-for-byte what
rung 5 needed, which is why the four shapes moved into `common.standard` rather
than being copied a third time — the duplication this exercise exists to notice
was about to be committed by the exercise itself.

Public, archived, and its README says it was consolidated into Willow 2.0. The
repository it was folded into is rung 6's successor, so the corpus will meet the
same code twice; whether the docstrings survived the move intact is a question
for whichever rung reads `willow-2.0`.
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
    out = pathlib.Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    origin = provenance.Origin("willow-nest", root, __file__)
    plan, declined, symbols, defined = common.standard(root)

    store = SqliteStore(str(out))
    store.memory_init()
    try:
        common.load(store, plan, origin, declined, root)
        print(f"\n  docstring coverage: {len(symbols)}/{defined} definition(s) carry one")
    finally:
        store.close()
    print(f"\n  store: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
