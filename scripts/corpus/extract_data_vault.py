#!/usr/bin/env python3
"""Shapes declared by `rudi193-cmd/sean-data-vault` — rung 35, the last.

    python scripts/corpus/extract_data_vault.py --repo /workspace/sean-data-vault \
        --out data/corpus/sean-data-vault.db

A 2.4 GB personal archive, and the only rung read under an **allowlist**.

**Why an allowlist, when every other rung read everything.** The operator
expected this repository to be mostly duplicate. Measured, 122 of its 151
markdown files exist nowhere else in the corpus — the duplication is in the
Postgres dumps, the Google Drive legacy and the repository extras, not the
prose. So the question was never duplication; it was **category**. Every other
rung extracted things the operator *declared*; this one holds things they
*accumulated* — PDFs, images, Windows backups, a legacy Drive export.

The operator drew the line. Taken:

    personal-research  professional  willow-store  experiments
    github-repo-extras  made-by-willow

Left out, deliberately and not by oversight: `provided-by-sean/stories`
(personal writing), `claude-code-sessions` (transcripts — declined for the same
reason 28,432 of them were declined at rung 34), and every PDF, image and binary
archive.

The 29 known duplicates are kept rather than filtered. They will surface in
`compare.py` as `restated`, which is the signal an archive is *for*: where a
snapshot and its live repository agree, and where they do not.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import common                                                    # noqa: E402
import provenance                                                # noqa: E402

from nestor.sqlite_store import SqliteStore                      # noqa: E402

ALLOWED = ("personal-research", "professional", "willow-store", "experiments",
           "github-repo-extras", "made-by-willow")


def allowed_files(root: pathlib.Path) -> set:
    """Every file under the operator's chosen directories, resolved."""
    out = set()
    for name in ALLOWED:
        base = root / name
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if path.is_file() and ".git" not in path.parts:
                out.add(path.resolve())
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--name", default="sean-data-vault")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    root = pathlib.Path(args.repo).resolve()
    out = pathlib.Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    only = allowed_files(root)
    origin = provenance.Origin(args.name, root, __file__)
    plan, declined, symbols, defined = common.standard(root, only=only)
    plan = [("constraint", common.constraints(root, only), "constraint", "constraint"),
            *plan]

    store = SqliteStore(str(out))
    store.memory_init()
    try:
        common.load(store, plan, origin, declined)
        print(f"\n  allowlist: {len(ALLOWED)} directories, {len(only)} file(s)")
        if defined:
            print(f"  docstring coverage: {len(symbols)}/{defined} "
                  f"({len(symbols) / defined:.0%}) definition(s) carry one")
    finally:
        store.close()
    print(f"\n  store: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
