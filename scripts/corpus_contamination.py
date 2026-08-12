#!/usr/bin/env python3
"""Which rows in a corpus store came from outside the tree its origin claims.

    python scripts/corpus_contamination.py --dir data/corpus
    python scripts/corpus_contamination.py --db data/corpus/std_Nestor.db

`scripts/corpus/extract_*.py` stamp every row with an origin of the shape
``<name>@<rev>:<path>``, which asserts the row is a shape declared by that
repository at that revision. They take their file list from a **filesystem
walk**, so any directory sitting in the working tree is quoted under that
revision whether or not it is in the commit — build artefacts, virtualenvs,
vendored dependencies, caches.

IDEAS §6.102 is the measured case: 18,665 of one store's 19,804 rows came from
`.venv/lib/python3.11/site-packages`, filed as `Nestor@f1fea81:` although
`.venv` is gitignored and those files are in no commit at all. Every one of
twenty-five sibling repositories was clean, because Nestor is the only one whose
own setup instructions say to create `.venv` at the repo root.

This reports the damage; it does not repair it. The repair is `git ls-files` in
the extractors — the tree the origin string already claims to be quoting — and
a `git worktree` is a working stand-in until then.

**The pattern list is a floor, not a definition.** It catches the directories
that have bitten so far. A corpus store reported clean here is one in which no
*known* build-artefact path appears, which is a weaker statement than "every row
is in the commit" and is deliberately not written as the stronger one.
"""
from __future__ import annotations

import argparse
import pathlib
import sqlite3

BOLD, DIM, GREEN, AMBER, RED, OFF = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m")

#: Paths that are in a working tree and not in a commit. A floor, not a
#: definition — see the module docstring.
VENDORED = (
    ".venv/", "venv/", "site-packages/", "node_modules/", ".tox/",
    "dist-info/", ".egg-info/", "__pycache__/", "/build/", ".mypy_cache/",
    ".pytest_cache/", "target/debug/", "target/release/", "vendor/",
)


def contaminated(origin: str) -> str:
    """The first known build-artefact marker in an origin, or ``''``."""
    low = (origin or "").lower()
    for marker in VENDORED:
        if marker in low:
            return marker
    return ""


def audit(db: pathlib.Path) -> tuple[int, int, dict[str, int]]:
    """``(total, vendored, {marker: count})`` for one corpus store."""
    con = sqlite3.connect(str(db))
    try:
        origins = [row[0] for row in con.execute("SELECT origin FROM tm_pairs")]
    finally:
        con.close()
    counts: dict[str, int] = {}
    for origin in origins:
        marker = contaminated(origin)
        if marker:
            counts[marker] = counts.get(marker, 0) + 1
    return len(origins), sum(counts.values()), counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", default="", help="a directory of corpus stores")
    ap.add_argument("--db", action="append", default=[], help="a single store; repeatable")
    ap.add_argument("--fail-on-contamination", action="store_true",
                    help="exit 1 if any row is vendored (for a gate)")
    args = ap.parse_args()

    stores: list[pathlib.Path] = [pathlib.Path(p) for p in args.db]
    if args.dir:
        root = pathlib.Path(args.dir)
        if not root.is_dir():
            print(f"{RED}no directory at {root}{OFF}")
            print(f"   {DIM}'I could not look' — refusing rather than reporting "
                  f"a clean corpus.{OFF}")
            return 2
        stores.extend(sorted(root.glob("*.db")))
    if not stores:
        print(f"{RED}no store named — pass --dir or --db{OFF}")
        return 2

    print(f"\n{BOLD}corpus contamination{OFF}  "
          f"{DIM}rows whose origin names a path that is in a working tree "
          f"and not in a commit{OFF}")
    print(f"\n  {'store':<34}{'total':>8}{'vendored':>10}{'real':>8}")

    grand_total = grand_vendored = 0
    dirty: list[tuple[str, dict[str, int]]] = []
    unreadable: list[str] = []
    for db in stores:
        try:
            total, vendored, counts = audit(db)
        except sqlite3.Error as exc:
            unreadable.append(f"{db.name}: {exc}")
            continue
        grand_total += total
        grand_vendored += vendored
        flag = f"  {RED}<-- contaminated{OFF}" if vendored else ""
        print(f"  {db.name:<34}{total:>8}{vendored:>10}{total - vendored:>8}{flag}")
        if vendored:
            dirty.append((db.name, counts))

    print(f"  {'-' * 58}")
    print(f"  {'TOTAL':<34}{grand_total:>8}{grand_vendored:>10}"
          f"{grand_total - grand_vendored:>8}")

    for name, counts in dirty:
        print(f"\n  {AMBER}{name}{OFF}")
        for marker, count in sorted(counts.items(), key=lambda kv: -kv[1]):
            print(f"    {count:>7}  {marker}")

    if unreadable:
        print(f"\n  {RED}could not read{OFF} ({len(unreadable)})")
        for line in unreadable:
            print(f"    {line}")
        print(f"    {DIM}Not 'clean': nothing about these stores is known.{OFF}")

    if not grand_vendored and not unreadable:
        print(f"\n  {GREEN}no known build-artefact path in any origin{OFF}")
        print(f"    {DIM}A floor, not a proof — see the module docstring. This "
              f"says no PATTERN matched, not that every row is in its commit.{OFF}")

    if args.fail_on_contamination and grand_vendored:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
