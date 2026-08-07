#!/usr/bin/env python3
"""Shapes declared by `rudi193-cmd/willow-config` — rung 21.

    python scripts/corpus/extract_willow_config.py --repo /workspace/willow-config \
        --out data/corpus/willow-config.db

617 markdown documents and three Python modules: a configuration and handoff
repository, mostly session records. Two shapes are worth naming and one is
worth refusing.

* **mandate** — `personas/*.md` give each agent a `**Mandate:**`. This is the
  **third** schema this corpus has met for describing the same kind of thing:
  rung 1 used `Domain`/`Voice`/`Function`/`Direction`, rung 13 used
  `Lineage`/`Type`/`Core function`, and this uses `Register`/`Mandate`/
  `Namespace`. Whether the descriptions agree is a question for `compare.py`,
  not for this file.
* **prohibition** — the same documents carry `**What you do not do:**`, and it
  is stored as a *separate* pair rather than folded into the mandate's reason.
  A mandate and a prohibition fail differently: one is broken by inaction, the
  other by action, and a store that merges them cannot say which was violated.
  It is also, exactly, the shape of this project's own covenant.

* **capability** — `Capability | Location | Status`, 811 rows across 138 handoff
  documents. This was very nearly refused on the reasoning that a table repeated
  in every session handoff is one rolling snapshot rather than 811 declarations.
  Counting first showed **653 distinct capability names**, most-repeated six
  times: an accumulating inventory, not a redrawn one. The refusal would have
  been the largest single act of under-extraction in the corpus, and it would
  have been justified in a paragraph, from an assumption, without a count.
* **risk** — `Risk | Mitigation`, 43 rows. A named risk and what is being done
  about it.

**Refused: the handoff metadata.** `Session:` (40), `Written:` (29) and
`Entry mode:` (27) are the most frequent labels here and none is a claim — an
identifier, a timestamp and an enum. Declined deliberately, and this paragraph
is the record of that being a decision rather than an oversight.

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


NAMED = {("capability", "location"): "capability", ("risk", "mitigation"): "risk"}


def named_tables(root: pathlib.Path) -> dict[str, list[tuple]]:
    out: dict[str, list[tuple]] = {v: [] for v in NAMED.values()}
    for path, heading, header, row in common.tables(root):
        shape = NAMED.get(tuple(header[:2]))
        if not shape or len(row) < 2 or len(row[0]) < 3 or len(row[1]) < 3:
            continue
        why = f"status: {row[2]}"[:300] if len(row) > 2 else ""
        out[shape].append((row[0], row[1][:400], why, path, heading))
    return out


def _persona_name(path: pathlib.Path, text: str) -> str:
    """The document's H1 if it has one, else the filename stem."""
    for line in text.splitlines():
        if line.startswith("# "):
            return " ".join(line[2:].split())
    return path.stem


def personas(root: pathlib.Path) -> tuple[list[tuple], list[tuple]]:
    """``(mandates, prohibitions)`` — what an agent does, and what it must not."""
    mandates, prohibitions = [], []
    for path in common.docs(root):
        text = path.read_text(encoding="utf-8")
        mandate = common.field(text, "Mandate")
        if not mandate:
            continue
        name = _persona_name(path, text)
        why = " | ".join(x for x in (
            f"Register: {common.field(text, 'Register')}" if common.field(text, "Register") else "",
            f"Namespace: {common.field(text, 'Namespace')}" if common.field(text, "Namespace") else "",
        ) if x)
        mandates.append((name, mandate[:600], why, path, name))
        never = common.field(text, "What you do not do")
        if never:
            prohibitions.append((name, never[:600], "stated prohibition", path, name))
    return mandates, prohibitions


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--name", default="willow-config")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    root = pathlib.Path(args.repo).resolve()
    out = pathlib.Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    origin = provenance.Origin(args.name, root, __file__)
    mandates, prohibitions = personas(root)
    plan, declined, symbols, defined = common.standard(root)
    tables = named_tables(root)
    plan = [("mandate", mandates, "agent", "mandate"),
            ("prohibition", prohibitions, "agent", "prohibition"),
            ("capability", tables["capability"], "capability", "location"),
            ("risk", tables["risk"], "risk", "mitigation"),
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
