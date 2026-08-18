"""Shapes declared by archived `rudi193-cmd/willow-2.0` — rung 18 (historical).

    python scripts/corpus/extract_willow_20.py \
        --repo ~/github-archive-greenfield-2026-08-10/archive/legacy-flat-2026-08-10/willow-2.0 \
        --out data/corpus/willow-2.0.db

**Not a live join.** ``willow-2.0`` is tier F — not cloned for day-to-day work.
Point ``--repo`` at the greenfield archive tree (or ``WILLOW_20_REPO``), never at
the charter. Living constitution case cards are in
``willow/governance/compliance/cases/``, not here.

The largest checkout in the sequence: 558 markdown documents, 850 Python
modules, 186 `SKILL.md`, 7,729 table rows. It is also the repository
`willow-nest` (rung 7) was consolidated into, which makes it the first chance to
ask whether a consolidation preserved what it absorbed.

Beyond the shared shapes it declares two worth naming:

* **rule** — `Rule | What it means`, ten rows. A rule can be wrong by firing
  when it should not, which no definition can; §6.62 argued this at rung 11.
* **sourced claim** — `Claim | Primary sources`, ten rows. A claim paired with
  the evidence for it is the nearest thing in this whole corpus to what the
  product is for, and the pairing is the author's, not the extractor's.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import common                                                    # noqa: E402
import provenance                                                # noqa: E402

from nestor.sqlite_store import SqliteStore                      # noqa: E402

NAMED = {("rule", "what it means"): ("rule", "rule", "meaning"),
         ("claim", "primary sources"): ("sourced-claim", "claim", "sources")}


def named_tables(root: pathlib.Path) -> dict[str, list[tuple]]:
    out: dict[str, list[tuple]] = {shape: [] for shape, _, _ in NAMED.values()}
    for path, heading, header, row in common.tables(root):
        spec = NAMED.get(tuple(header[:2]))
        if not spec or len(row) < 2:
            continue
        shape, _sl, _tl = spec
        if len(row[0]) < 3 or len(row[1]) < 4:
            continue
        out[shape].append((row[0], row[1][:600], f"table: {heading}", path, heading))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--name", default="willow-2.0")
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
    tables = named_tables(root)
    plan = [("rule", tables["rule"], "rule", "meaning"),
            ("sourced-claim", tables["sourced-claim"], "claim", "sources"),
            ("goal", common.labelled(root, "Goal"), "plan", "goal"),
            ("success", common.labelled(root, "Success"), "plan", "success"),
            ("intent", common.labelled(root, "Intent"), "plan", "intent"),
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
