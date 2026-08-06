#!/usr/bin/env python3
"""The four standard shapes, for any repository that declares nothing new.

    python scripts/corpus/extract_standard.py --repo /workspace/willow-bot \
        --name willow-bot --out data/corpus/willow-bot.db

Docstrings, the security rubric, identified findings, definitional tables —
the four that have now appeared in every source repository this corpus has read.
A repository needs its own extractor only when it carries a shape these do not
cover; when it does not, it needs a name and a path.

Rung 7 got a bespoke file for exactly this and its whole body was a call. Rung
11 would have been a second copy of the same file with one string changed, which
is where a third copy becomes inevitable. `extract_willow_nest.py` is deleted in
favour of this: `--name willow-nest` reproduces its 35 rows.

For forks use `extract_fork.py` instead — a fork's tree is upstream's work and
the unit is the delta. See `docs/corpus-order.md`.
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
    ap.add_argument("--name", required=True, help="corpus name, used in origins")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    root = pathlib.Path(args.repo).resolve()
    out = pathlib.Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    origin = provenance.Origin(args.name, root, __file__)
    plan, declined, symbols, defined = common.standard(root)

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
