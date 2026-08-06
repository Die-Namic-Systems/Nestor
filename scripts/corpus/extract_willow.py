#!/usr/bin/env python3
"""Shapes declared by `rudi193-cmd/Willow` — rung 2 of the chronology.

    python scripts/corpus/extract_willow.py --repo /workspace/rudi193-cmd/willow \
        --out data/corpus/willow.db

Five shapes. Two are worth naming because they are not definitions:

* **bilingual** — ``In computer terms`` / ``In human terms`` is one referent
  stated in two registers, which is a translation pair in everything but name,
  and the first material in this corpus that uses Nestor as built.
* **decision** — ``Decision | Class`` enumerates which acts a machine may apply
  alone and which need an operator key or a quorum. That is this project's own
  question, already answered, in a markdown table nobody wrote for the purpose.

**Named shapes only, deliberately.** The first version of this took every
two-column table: 568 rows, 7% of them from a header naming a term, and it
filed the constitutional decision rows under the same domain tag as a ``P1``
row from a findings list. A generic extractor buries its best rows among its
worst. Everything no shape claims is counted and reported instead. IDEAS §6.42.
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

BILINGUAL = ("in computer terms", "in human terms")
DEFN_KEYS = ("term", "concept", "axis", "article", "word")


def _bilingual_header(header: list[str]) -> bool:
    return all(b in header for b in BILINGUAL)


def bilingual_tables(root: pathlib.Path) -> list[tuple]:
    rows = []
    for path, heading, header, row in common.tables(root):
        if not _bilingual_header(header):
            continue
        ci, hi = header.index(BILINGUAL[0]), header.index(BILINGUAL[1])
        if max(ci, hi) >= len(row):
            continue
        if len(row[ci]) < 8 or len(row[hi]) < 8:
            continue
        rows.append((row[ci], row[hi], f"term: {row[0]}", path, heading))
    return rows


def bilingual_prose(root: pathlib.Path) -> list[tuple]:
    rows = []
    for path in common.docs(root):
        for heading, block in common.sections(path.read_text(encoding="utf-8")):
            comp = common.field(block, "In computer terms")
            hum = common.field(block, "In human terms")
            if len(comp) < 8 or len(hum) < 8:
                continue
            rows.append((comp, hum, f"section: {heading}", path, heading))
    return rows


def patterns(root: pathlib.Path) -> list[tuple]:
    """Governance patterns: the name, and the sentence that is meant to be quoted."""
    rows = []
    for path in common.docs(root):
        for heading, block in common.sections(path.read_text(encoding="utf-8")):
            canonical = common.field(block, "Canonical phrasing")
            if not canonical:
                continue
            prevents = common.field(block, "Failure it prevents")
            rows.append((heading, canonical.strip('*"'),
                         f"prevents: {prevents}", path, heading))
    return rows


def decisions(root: pathlib.Path) -> list[tuple]:
    rows = []
    for path, heading, header, row in common.tables(root):
        if header[:2] != ["decision", "class"]:
            continue
        rows.append((row[0], row[1], row[2] if len(row) > 2 else "", path, heading))
    return rows


def definitions(root: pathlib.Path) -> list[tuple]:
    rows = []
    for path, heading, header, row in common.tables(root):
        if header[0] not in DEFN_KEYS or _bilingual_header(header):
            continue
        tgt = " · ".join(c for c in row[1:] if c)
        if len(row[0]) < 2 or len(tgt) < 4:
            continue
        rows.append((row[0], tgt, f"columns: {' | '.join(header)}", path, heading))
    return rows


def declined(root: pathlib.Path) -> collections.Counter:
    """Rows no shape claims, by header — the 78% this run does not take."""
    out: collections.Counter = collections.Counter()
    for _path, _heading, header, row in common.tables(root):
        if _bilingual_header(header) or header[:2] == ["decision", "class"]:
            continue
        if header[0] in DEFN_KEYS:
            continue
        if len(row[0]) < 2 or len(" · ".join(row[1:])) < 4:
            continue
        out[" | ".join(header)] += 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True, help="checkout of rudi193-cmd/Willow")
    ap.add_argument("--out", required=True, help="store to write (overwritten)")
    args = ap.parse_args()

    root = pathlib.Path(args.repo).resolve()
    out = pathlib.Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    origin = provenance.Origin("willow", root, __file__)
    plan = [
        ("bilingual-table", bilingual_tables(root), "computer", "human"),
        ("bilingual-prose", bilingual_prose(root), "computer", "human"),
        ("pattern", patterns(root), "pattern", "pattern"),
        ("decision", decisions(root), "decision", "authority"),
        ("definition", definitions(root), "term", "term"),
    ]

    store = SqliteStore(str(out))
    store.memory_init()
    try:
        common.load(store, plan, origin, declined(root))
    finally:
        store.close()
    print(f"\n  store: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
