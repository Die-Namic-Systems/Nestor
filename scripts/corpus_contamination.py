#!/usr/bin/env python3
"""Which rows in a corpus store name a path outside the tree its origin claims.

    python scripts/corpus_contamination.py --repo . --dir data/corpus
    python scripts/corpus_contamination.py --repo . --db data/corpus/std_Nestor.db

`scripts/corpus/extract_*.py` stamp every row with an origin of the shape
``<repo>@<rev>:<path>#<anchor> [<shape>/<toolchain>]`` (see
`scripts/corpus/provenance.py`), which asserts the row is a shape declared by
that repository at that revision. The extractors take their file list from a
**filesystem walk**, so any directory sitting in the working tree is quoted
under that revision whether or not it is in the commit — build artefacts,
virtualenvs, vendored dependencies, caches.

IDEAS §6.102 is the measured case: 18,665 of one store's 19,804 rows came from
`.venv/lib/python3.11/site-packages`, filed as `Nestor@f1fea81:` although
`.venv` is gitignored and those files are in no commit at all. Every one of
twenty-five sibling repositories was clean, because Nestor is the only one whose
own setup instructions say to create `.venv` at the repo root.

**The mechanism is ``git ls-files``, not a pattern list.** The tree an origin
already claims to be quoting is exactly the set ``git ls-files`` reports for the
repository at that revision. So the allowed scope is enumerated from git, and a
row whose path is not in that set is contamination — the file is in the working
tree and not in the commit the origin names. This is the direct port of the
scope-bijection check in safe-app-willow-grove
``tests/test_security_audit_scope.py`` (``_tracked_sources`` +
``test_every_tracked_source_file_appears_in_the_scope_table``), inverted: there
the sin is a tracked file absent from a claim, here it is a claimed path absent
from the tree.

**Absence is not cleanliness.** If ``git ls-files`` cannot enumerate the scope
(no git, not a checkout, a bad ``--repo``), this reports UNKNOWN and exits
non-zero — it never falls back to "no contamination". An empty allowed-scope
would make every row read as out-of-scope, or, read the other way, make a
corpus look clean because nothing could be compared; "I could not look" is a
distinct answer from "nothing is contaminated". A store this tool cannot open,
or rows whose origin carries no path, are surfaced as caveats for the same
reason.

The ``VENDORED`` markers below are kept only to *label why* a flagged path is
out of scope in the report. They are a floor, not the verdict — the verdict is
``git ls-files`` membership.
"""
from __future__ import annotations

import argparse
import pathlib
import sqlite3
import subprocess

BOLD, DIM, GREEN, AMBER, RED, OFF = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m")

#: Known build-artefact path markers. Used only to annotate a flagged path in
#: the report — the flag itself is decided by ``git ls-files`` membership.
VENDORED = (
    ".venv/", "venv/", "site-packages/", "node_modules/", ".tox/",
    "dist-info/", ".egg-info/", "__pycache__/", "/build/", ".mypy_cache/",
    ".pytest_cache/", "target/debug/", "target/release/", "vendor/",
)


class ScopeUnavailable(RuntimeError):
    """``git ls-files`` could not enumerate the allowed scope.

    Raised rather than swallowed into an empty set: an empty allowed-scope is
    not the same fact as a clean corpus, and conflating them is exactly the
    "reported an unreadable corpus in the words for a clean one" drift the
    corpus readers already fought (see tests/test_corpus_readers_fail_closed).
    """


def tracked_files(repo: str | pathlib.Path) -> set[str]:
    """The set of paths ``git ls-files`` reports for ``repo`` — the allowed scope.

    Ported from safe-app-willow-grove ``tests/test_security_audit_scope.py``
    (``_tracked_sources``), which enumerates the tree a claim must be a
    bijection with. Here the tree is the commit an origin string claims to quote.
    Raises :class:`ScopeUnavailable` when git cannot answer — never an empty set
    standing in for "clean".
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), "ls-files"],
            capture_output=True, text=True, timeout=60,
        )
    except OSError as exc:  # git not installed, repo path missing
        raise ScopeUnavailable(f"git unavailable for {repo}: {exc}") from exc
    if proc.returncode != 0:
        raise ScopeUnavailable(
            f"git ls-files failed in {repo}: "
            f"{proc.stderr.strip() or f'exit {proc.returncode}'}")
    return {line for line in proc.stdout.splitlines() if line}


def origin_path(origin: str) -> str:
    """The repo-relative path an origin claims, or ``''`` if it carries none.

    Origins are built by ``scripts/corpus/provenance.py`` as
    ``<repo>@<commit>:<path>#<anchor> [<shape>/<toolchain>]`` so the path is the
    field after the first ``:`` up to the ``#`` anchor or the `` [`` shape suffix.
    """
    if ":" not in (origin or ""):
        return ""
    after = origin.split(":", 1)[1]
    after = after.split("#", 1)[0]
    after = after.split(" [", 1)[0]
    return after.strip()


def marker_for(path: str) -> str:
    """A known build-artefact marker inside ``path``, or ``''`` — for the report."""
    low = path.lower()
    for marker in VENDORED:
        if marker in low:
            return marker
    return ""


def out_of_scope(origins, allowed: set[str]) -> tuple[dict[str, int], int]:
    """``({path: rows}, unshaped)`` — origin paths not in the allowed scope.

    The inverse of the template's ``missing = tracked - listed``. Unshaped
    origins (no path field) are counted separately: a row this tool cannot place
    in or out of scope is reported, never silently read as clean.
    """
    counts: dict[str, int] = {}
    unshaped = 0
    for origin in origins:
        path = origin_path(origin)
        if not path:
            unshaped += 1
            continue
        if path not in allowed:
            counts[path] = counts.get(path, 0) + 1
    return counts, unshaped


def audit(db: pathlib.Path, allowed: set[str]) -> tuple[int, dict[str, int], int]:
    """``(total_rows, {out-of-scope path: rows}, unshaped)`` for one store."""
    con = sqlite3.connect(str(db))
    try:
        origins = [row[0] for row in con.execute("SELECT origin FROM tm_pairs")]
    finally:
        con.close()
    counts, unshaped = out_of_scope(origins, allowed)
    return len(origins), counts, unshaped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".",
                    help="git worktree whose tracked files define the allowed scope")
    ap.add_argument("--dir", default="", help="a directory of corpus stores")
    ap.add_argument("--db", action="append", default=[],
                    help="a single store; repeatable")
    ap.add_argument("--fail-on-contamination", action="store_true",
                    help="exit 1 if any row names an out-of-scope path (for a gate)")
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

    try:
        allowed = tracked_files(args.repo)
    except ScopeUnavailable as exc:
        print(f"{RED}could not enumerate the allowed scope{OFF}")
        print(f"   {DIM}{exc}{OFF}")
        print(f"   {DIM}Reporting UNKNOWN, not a clean corpus — the scope the "
              f"origins claim could not be read.{OFF}")
        return 2

    print(f"\n{BOLD}corpus contamination{OFF}  "
          f"{DIM}rows whose origin names a path that is not in "
          f"`git ls-files {args.repo}`{OFF}")
    print(f"\n  {'store':<34}{'total':>8}{'out-scope':>10}{'in-scope':>9}")

    grand_total = grand_out = 0
    dirty: list[tuple[str, dict[str, int]]] = []
    caveats: list[str] = []
    unreadable: list[str] = []
    for db in stores:
        try:
            total, counts, unshaped = audit(db, allowed)
        except sqlite3.Error as exc:
            unreadable.append(f"{db.name}: {exc}")
            continue
        out_rows = sum(counts.values())
        grand_total += total
        grand_out += out_rows
        flag = f"  {RED}<-- contaminated{OFF}" if out_rows else ""
        print(f"  {db.name:<34}{total:>8}{out_rows:>10}{total - out_rows:>9}{flag}")
        if counts:
            dirty.append((db.name, counts))
        if unshaped:
            caveats.append(f"{db.name}: {unshaped} row(s) carry no path — "
                           f"cannot be placed in or out of scope")

    print(f"  {'-' * 59}")
    print(f"  {'TOTAL':<34}{grand_total:>8}{grand_out:>10}"
          f"{grand_total - grand_out:>9}")

    for name, counts in dirty:
        print(f"\n  {AMBER}{name}{OFF}")
        for path, count in sorted(counts.items(), key=lambda kv: -kv[1]):
            label = marker_for(path)
            note = f"  {DIM}({label}){OFF}" if label else ""
            print(f"    {count:>7}  {path}{note}")

    if caveats:
        print(f"\n  {AMBER}unplaceable{OFF} ({len(caveats)})")
        for line in caveats:
            print(f"    {line}")

    if unreadable:
        print(f"\n  {RED}could not read{OFF} ({len(unreadable)})")
        for line in unreadable:
            print(f"    {line}")
        print(f"    {DIM}Not 'clean': nothing about these stores is known.{OFF}")

    if not grand_out and not unreadable:
        print(f"\n  {GREEN}every origin names a git-tracked path{OFF}")
        print(f"    {DIM}Verified against `git ls-files {args.repo}` — every "
              f"placeable origin path is in the commit it claims.{OFF}")

    if args.fail_on_contamination and (grand_out or unreadable):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
