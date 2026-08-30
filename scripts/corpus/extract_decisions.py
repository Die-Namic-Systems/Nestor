#!/usr/bin/env python3
"""Decision records — the shape this corpus exists for and has never been fed.

    python scripts/corpus/extract_decisions.py --repo . --name decisions \
        --out data/corpus/decisions.db

Measured 2026-08-30: the corpus held 72 ``decision -> authority`` claims and
every one came from ``willow``, a repository tombstoned RETIRED. The live
decisions — 78 under ``docs/dogfood/decisions/``, 100 under ``docs/archive/`` —
were never extracted, because ``extract_standard.py`` reads docstrings, rubrics,
findings and tables, and a decision record is none of those.

So the one lane the corpus is *for* was the one lane nothing filled.

A decision record is already a pair. ``{"question", "commitment", "why"}`` maps
onto source, target and reason without interpretation, which is why this
extractor is short: the structure was there, nobody was reading it.

The warrant travels as its own row. A warrant is not the decision — it is what
would let someone else check it — so it is emitted under an explicit
``· warrant`` suffix with the ``check_procedure`` as its reason, never folded
into the commitment. Conflating "what was decided" with "how you would verify
it" is the collapse this whole store exists to prevent.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import common
import provenance

from nestor.sqlite_store import SqliteStore


def records(root: pathlib.Path) -> tuple[list, int, int]:
    """Rows from every ``*/decisions/*.json`` under ``root``. Drops are counted."""
    rows, files, dropped = [], 0, 0
    for path in sorted(root.rglob("decisions/*.json")):
        if ".venv" in path.parts or "node_modules" in path.parts:
            continue
        files += 1
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            dropped += 1
            continue
        if not isinstance(doc, dict):
            dropped += 1
            continue
        stem = path.stem

        for entry in doc.get("decisions") or []:
            if not isinstance(entry, dict):
                dropped += 1
                continue
            q = str(entry.get("question", "")).strip()
            c = str(entry.get("commitment", "")).strip()
            if not (q and c):
                dropped += 1
                continue
            rows.append((f"{stem} · {q}", c,
                         str(entry.get("why", "")).strip() or "no rationale recorded",
                         path, q))

        w = doc.get("warrant")
        if isinstance(w, dict) and w.get("authority"):
            rows.append((f"{stem} · warrant", str(w["authority"]).strip(),
                         str(w.get("check_procedure", "")).strip()
                         or f"kind={w.get('kind', 'unstated')}, no check procedure recorded",
                         path, "warrant"))

        note = str(doc.get("note", "")).strip()
        if note:
            rows.append((f"{stem} · note", note,
                         f"branch {doc.get('branch', 'unrecorded')}, pr {doc.get('pr', 'unrecorded')}",
                         path, "note"))
    return rows, files, dropped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    root = pathlib.Path(args.repo).resolve()
    if not common.require_checkout(root):
        return 1
    rows, files, dropped = records(root)
    print(f"  {files} decision file(s), {len(rows)} row(s)"
          + (f", {dropped} dropped" if dropped else ""))
    if not rows:
        print("error: no decision records — refusing to write an empty store", file=sys.stderr)
        return 1

    out = pathlib.Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    origin = provenance.Origin(args.name, root, __file__)
    store = SqliteStore(str(out))
    store.memory_init()
    try:
        common.load(store, [("decision", rows, "decision", "commitment")], origin)
    finally:
        store.close()
    print(f"  store: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
