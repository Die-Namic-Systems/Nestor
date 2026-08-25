#!/usr/bin/env python3
"""Rebuild the corpus from the repositories that are on THIS box, post-move.

    python scripts/rebuild_corpus.py --list      # what would run, and against what
    python scripts/rebuild_corpus.py             # run it

The 35-rung chronology (docs/corpus-order.md, IDEAS §6.50-§6.90) ran 2026-08-06/07
and its findings survive in docs/agent-log.md and 34 merged corpus/NN-* branches.
The OUTPUT did not: `data/` is gitignored, so the ~10,300 rows those rungs
produced are not in this checkout. This rebuilds what can be rebuilt from the
repositories that still exist locally after the 2026-08-10 org-layout move.

**This is not the chronology.** The rungs were ordered oldest-first and each
branched from the one beneath, so a rung carried every rung below it. This runs
flat, against current heads, on the subset that is cloned. It reproduces the
CONTENT, not the sequence — and the sequence was load-bearing for the exercise's
own argument, so nothing here should be read as re-running it.

Reports per repo, in the discipline `feed_all.py` established, because
"the corpus was empty" and "I could not read it" are different sentences:

    fed          rows extracted
    empty        read successfully, declares nothing
    unreadable   extractor failed, with the reason
    skipped      no extractor and no standard fallback
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
CORPUS = REPO / "data" / "corpus"
PY = sys.executable

G = "/home/sean-campbell/github"
V = "/home/sean-campbell"

#: repo name -> (checkout path, bespoke extractor or None for the standard four)
TARGETS: dict[str, tuple[str, str | None]] = {
    "willow":                 (f"{G}/willow-memory/willow",              "extract_willow.py"),
    "willow-mcp":             (f"{G}/willow-memory/willow-mcp",          "extract_willow_mcp.py"),
    "willow-grove":           (f"{G}/willow-memory/willow-grove",        "extract_willow_grove.py"),
    "willow-gate":            (f"{G}/willow-memory/willow-gate",         None),
    "willow-data-vault":      (f"{G}/willow-memory/willow-data-vault",   None),
    "kartikeya":              (f"{G}/willow-memory/kartikeya",           None),
    "corpus-lens":            (f"{G}/willow-memory/corpus-lens",         None),
    "Jeles":                  (f"{G}/hornbook-knowledge/Jeles",          None),
    "UTETY":                  (f"{G}/hornbook-knowledge/UTETY",          None),
    "oakenscrolls-office":    (f"{G}/hornbook-knowledge/oakenscrolls-office", None),
    "nestor":                 (f"{G}/Die-Namic-Systems/nestor",          None),
    "terpsi-music":           (f"{G}/terpsi-programs/terpsi-music",      None),
    "redential-cli":          (f"{G}/workshop/redential-cli",            None),
    "codebase-memory-mcp":    (f"{G}/workshop/codebase-memory-mcp",      None),
    "DispatchesFromReality":  (f"{G}/workshop/DispatchesFromReality",    None),
    "courtlistener-mcp":      (f"{G}/workshop/courtlistener-mcp",        None),
    "homestead":              (f"{G}/homestead-affairs/homestead",       None),
    "homestead-law":          (f"{G}/homestead-affairs/homestead-law",   None),
    "homestead-health":       (f"{G}/homestead-affairs/homestead-health", None),
    "homestead-ledger":       (f"{G}/homestead-affairs/homestead-ledger", None),
    "awesome-sovereign-software": (f"{G}/homestead-affairs/awesome-sovereign-software", None),
    "Forge":                  (f"{G}/forge-play/Forge",                  None),
    "safe-app-store-public":  (f"{G}/safe-app-store-public",             "extract_safe.py"),
    "sean-data-vault":        (f"{V}/sean-data-vault",                   "extract_data_vault.py"),
}


def rows_in(db: pathlib.Path) -> int | None:
    """Row count via nestor's own API — never raw sqlite against a store."""
    try:
        sys.path.insert(0, str(REPO))
        from nestor.sqlite_store import SqliteStore
        from nestor import curator as _c
        s = SqliteStore(str(db))
        n = len(_c.Curator(store=s).browse(limit=1_000_000))  # default 50 truncates
        s.close()
        return n
    except Exception:
        return None


def run_one(name: str, path: str, extractor: str | None) -> tuple[str, str]:
    p = pathlib.Path(path)
    if not p.is_dir():
        return "unreadable", f"checkout missing: {path}"
    out = CORPUS / f"{name}.db"
    if extractor:
        cmd = [PY, str(HERE / "corpus" / extractor), "--repo", path, "--out", str(out)]
    else:
        cmd = [PY, str(HERE / "corpus" / "extract_standard.py"),
               "--repo", path, "--name", name, "--out", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        tail = (r.stderr or r.stdout).strip().splitlines()
        return "unreadable", (tail[-1][:150] if tail else f"exit {r.returncode}")
    n = rows_in(out)
    if n is None:
        return "unreadable", "wrote a store that could not be read back"
    return ("fed" if n else "empty"), f"{n} rows"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--only", help="one repo name")
    a = ap.parse_args()

    CORPUS.mkdir(parents=True, exist_ok=True)
    items = TARGETS.items() if not a.only else [(a.only, TARGETS[a.only])]

    if a.list:
        for name, (path, ex) in items:
            print(f"  {name:26} {ex or 'extract_standard.py':30} {path}")
        return

    tally: dict[str, int] = {}
    total = 0
    print(f"{'repo':26} {'verdict':11} detail")
    print("-" * 74)
    for name, (path, ex) in items:
        verdict, detail = run_one(name, path, ex)
        tally[verdict] = tally.get(verdict, 0) + 1
        if verdict == "fed":
            total += int(detail.split()[0])
        print(f"{name:26} {verdict:11} {detail}")
    print("-" * 74)
    print("  " + "  ".join(f"{k}={v}" for k, v in sorted(tally.items())))
    print(f"  total rows: {total}")
    print(f"  stores in:  {CORPUS}")


if __name__ == "__main__":
    main()
