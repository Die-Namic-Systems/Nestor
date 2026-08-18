#!/usr/bin/env python3
"""Shapes declared by `rudi193-cmd/willow-bot` — rung 11.

    python scripts/corpus/extract_willow_bot.py --repo /workspace/willow-bot \
        --name willow-bot --out data/corpus/willow-bot.db

This rung was run first with `extract_standard.py`, on the assumption that a
25-module bot declared nothing new. Its declined-row report said otherwise
within one run: two tables, eleven rows, both of the form *when this, do that*.

* `Trigger | Condition | Action` — eight named triggers (Lokasenna, Mistletoe,
  Web of Anansi, Cattle of Hermes …) each with the condition that fires it and
  what happens when it does. A rule set with identifiers, the same shape as
  SAFE's `HS-001`, so the pair is keyed the same way: `name — condition` on one
  side, the action on the other.
* `Event | Local action` — three webhook events mapped to what the bot does on
  disk.

Neither is a definition and neither is a finding. A rule is its own kind of
claim: it can be wrong by firing when it should not, which is a failure mode no
definitional row has.

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

RULE_HEADERS = (("trigger", "condition", "action"), ("event", "local action"))


def rules(root: pathlib.Path) -> list[tuple]:
    """`when this, do that` — however the table happens to spell it."""
    rows = []
    for path, heading, header, row in common.tables(root):
        shape = tuple(header[:3])
        if shape == RULE_HEADERS[0] and len(row) >= 3:
            source, target, why = f"{row[0]} — {row[1]}", row[2], f"trigger: {row[0]}"
        elif tuple(header[:2]) == RULE_HEADERS[1] and len(row) >= 2:
            source, target, why = row[0], row[1], "webhook event map"
        else:
            continue
        if len(source) < 3 or len(target) < 3:
            continue
        rows.append((source, target, why, path, heading))
    return rows


def declined(root: pathlib.Path) -> "common.collections.Counter":
    out = common.unclaimed(root)
    for header in (" | ".join(h) for h in RULE_HEADERS):
        out.pop(header, None)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--name", default="willow-bot")
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
    plan, _stock_declined, symbols, defined = common.standard(root)
    plan = [("rule", rules(root), "condition", "action"), *plan]

    store = SqliteStore(str(out))
    store.memory_init()
    try:
        common.load(store, plan, origin, declined(root), root)
        if defined:
            print(f"\n  docstring coverage: {len(symbols)}/{defined} "
                  f"({len(symbols) / defined:.0%}) definition(s) carry one")
    finally:
        store.close()
    print(f"\n  store: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
