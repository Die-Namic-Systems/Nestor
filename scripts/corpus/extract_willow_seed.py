#!/usr/bin/env python3
"""Shapes declared by `rudi193-cmd/willow-seed` — rung 4.

    python scripts/corpus/extract_willow_seed.py --repo /workspace/willow-seed \
        --out data/corpus/willow-seed.db

A small repository — 8 markdown documents — and the honest consequence is a
small extraction. Only two structures repeat enough to be worth naming:

* **grading** — `GRADING.md` asks ten numbered questions and answers each twice,
  once with a `*Measure:*` and once with a `*Reference:*`. Those are different
  claims and are stored as different pairs: how you would measure it, and what
  number somebody actually got. Conflating them would lose the distinction the
  document is built on.
* **finding** — `SECURITY_AUDIT.md` carries identified findings with a severity
  and a recommended fix. The shape is shared (`common.findings`); it has since
  turned up unchanged in a third checkout, which makes it the author's
  convention rather than this repository's feature.

Everything else here is prose that declares no schema, and it is left alone.
The coverage line in the output is the honest report of that.

**The source is private.** Store to gitignored `data/`; nothing committed.
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

DEFN_KEYS = ("term", "concept", "field", "name", "question", "check")
# `*Label:* value` — this repository italicises its field labels where SAFE and
# Willow bolded theirs. Same shape, different markup.
ITALIC = r"\*{}:\*\s*(.+?)(?=\n\*[A-Z]|\n\n|\n#|\n---|\Z)"


def _italic(block: str, name: str) -> str:
    m = re.search(ITALIC.format(re.escape(name)), block, re.S)
    return " ".join(m.group(1).split()) if m else ""


def grading(root: pathlib.Path) -> tuple[list[tuple], list[tuple]]:
    """Ten questions, each answered twice. Returns (measures, references)."""
    path = root / "GRADING.md"
    if not path.exists():
        return [], []
    text = path.read_text(encoding="utf-8")
    measures: list[tuple] = []
    references: list[tuple] = []
    # `**1 · Question?**` opens each block and runs to the next one.
    parts = re.split(r"^\*\*(\d+) · (.+?)\*\*$", text, flags=re.M)[1:]
    for i in range(0, len(parts) - 2, 3):
        num, question, block = parts[i], parts[i + 1].strip(), parts[i + 2]
        anchor = f"Q{num}"
        measure = _italic(block, "Measure")
        reference = _italic(block, "Reference")
        lead = " ".join(block.split("*Measure:*")[0].split())
        if measure:
            measures.append((question, measure, f"asks: {lead[:300]}", path, anchor))
        if reference:
            references.append((question, reference, "reference point, N=1 operator",
                               path, anchor))
    return measures, references


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

    origin = provenance.Origin("willow-seed", root, __file__)
    measures, references = grading(root)
    plan = [
        ("grading-measure", measures, "question", "measure"),
        ("grading-reference", references, "question", "reference"),
        ("finding", common.findings(root), "finding", "fix"),
        ("rubric", common.rubric(root), "check", "verdict"),
        ("definition", definitions(root), "term", "term"),
    ]

    store = SqliteStore(str(out))
    store.memory_init()
    try:
        common.load(store, plan, origin, declined(root), root)
    finally:
        store.close()
    print(f"\n  store: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
