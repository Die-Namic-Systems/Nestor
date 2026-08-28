#!/usr/bin/env python3
"""Re-extract the corpus from the plan the corpus is already carrying.

    python scripts/corpus/refresh.py --dry-run            # what has drifted
    python scripts/corpus/refresh.py                      # re-extract and sync

Twenty-one extractors sit in this directory and nothing invokes any of them.
Each rung was run by hand (``docs/corpus-order.md``), which was right while the
corpus was being *built* one repository at a time and is wrong now that it is
being *kept*: measured 2026-08-28, the household corpus was pinned at commits
from 2026-08-21 and stood 227 commits behind ``nestor`` and 115 behind
``willow-mcp``, while ten frozen repositories were exactly current. **The corpus
decays fastest where the work is**, so the anti-rediscovery instrument is least
accurate precisely where rediscovery is most likely.

**The plan is derived, never authored.** A hand-written roster here would be a
second source of truth for something ``docs/corpus-order.md`` warns about in its
own first paragraph — *"an exception agreed in conversation and not written down
is one a later session will silently undo"* — and the exceptions are real:
``mealie`` and ``litellm`` are excluded by operator decision, ``sean-data-vault``
was taken under an allowlist, forks are read by ``extract_fork.py`` because the
unit is the delta. A roster invented here could quietly reverse any of them.

So every field comes out of the store instead, from the provenance §6.51 put in
the ``origin`` for exactly this kind of question:

    willow@cf1040a:CONSTITUTION.md#Identity Authority [decision/a1b2c3d]
    └─name  └─commit └─path        └─anchor            └─shape └─toolchain

* **which repositories** — ``corpus_claims.repository``, which ``corpus.sync``
  sets from the source database's filename. A repository nobody extracted has no
  rows, so an exclusion cannot be undone by this script: it has nothing to act on.
* **which extractor** — the toolchain digest, resolved against the content hash
  of every committed ``extract_*.py``. All 24 repositories resolved on the first
  run. This is only possible because the extractors are committed, which is the
  reason §6.53 gives for committing them.
* **which name** — the origin's own prefix, which is the ``--name`` the run used
  and is *not* always the repository (``safe-app-store-public`` was read as
  ``safe``; ``willow-grove`` as ``safe-app-willow-grove``).
* **which commit it last read** — the origin's, which is what makes drift
  measurable at all.

Only the checkout path is not in the store, and that is a property of this
machine rather than of the corpus, so it is the one thing passed in.

**Three refusals, all fail-closed.** Each exists because the quiet version is
worse than the loud one:

* an **unresolvable toolchain** means the extractor changed since the rows were
  written. Re-running it would produce rows that mean something different under
  a label that says they do not — the parser-versus-corpus confusion §6.52
  measured at sixty-three collisions. Refused, named, and skipped.
* a **missing checkout** is the ``require_checkout`` case (§6.101): an absent
  repository and a genuinely empty one print the same thing unless something
  refuses.
* a **dirty tree** is refused because ``provenance.commit()`` reports ``HEAD``
  whatever is in the working tree, so extracting from one writes rows pinned to
  a commit that does not contain them. ``docs/corpus-order.md`` names this exact
  failure for live repositories — *"a corpus of a particular afternoon,
  mislabelled as a corpus of the repository"* — and an uncommitted tree is that
  with no afternoon at all.

A refused repository keeps its existing ``data/corpus/<repository>.db`` and so
keeps its old rows and old pin through the sync: the corpus goes stale there
rather than losing the repository. What is *not* tolerated is a repository the
household knows about with no source database at all — syncing then would
silently drop it, because ``corpus.sync`` rebuilds the whole snapshot from
whatever ``data/corpus/`` holds.

**And one outcome that is not a refusal at all.** A repository recorded in
``tombstones.json`` reports as **RETIRED** with the shape it ended in and where
it went, is excluded from the refusal count, and is never looked for. Without
that, a retired repository refuses on every run forever: ``willow-grove`` was
archived 2026-08-27 and would have sat in the refusal list beside conditions an
operator can actually fix, until the list stopped being read — the same way an
advisory that fires every turn stops being read (0221).

The tombstone file is **the one authored thing in this driver**, and 0222 is the
reason it has to be. The plan is derived so it cannot reverse an operator
decision; a tombstone *is* an operator decision, and nothing can derive it — an
absent checkout is indistinguishable from an unmounted disk, a renamed
directory, or a clone that has not happened yet. So ``REFUSED`` keeps meaning
*I could not look* and ``RETIRED`` means *there is nothing to look at, and here
is where it went*: a recorded negative, not an absence. Its vocabulary is reused
verbatim from ``safe-app-store-public/docs/conventions/tombstones.md`` rather
than invented, and a record missing the forward its end-shape requires raises
rather than being skipped — a tombstone that silently did not apply would put
the repository back in the refusal list with nothing to say anyone had tried.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sqlite3
import subprocess
import sys
from dataclasses import dataclass

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import provenance

from nestor import corpus

#: ``name@commit:`` at the head, ``[shape/toolchain]`` at the tail.
_ORIGIN_RX = re.compile(
    r"^(?P<name>[^@\s]+)@(?P<commit>[0-9a-zA-Z]+):.*"
    r"\[(?P<shape>[a-z_]+)/(?P<toolchain>[0-9a-f]+)\]\s*$"
)


@dataclass(frozen=True)
class Row:
    """One repository's refresh plan, entirely read out of the household store."""
    repository: str          # corpus_claims.repository — the source db's stem
    name: str                # the --name the extraction used, from the origin
    commit: str              # the commit those rows were read at
    toolchain: str           # digest of the extractor that read them
    claims: int


def plan(household: pathlib.Path) -> list[Row]:
    """Every repository the household corpus holds, and how it was read.

    A repository whose origins disagree about name, commit or toolchain is a
    corpus assembled from two runs; the most common of each wins and the
    disagreement is reported by ``main`` rather than resolved silently here.
    """
    conn = sqlite3.connect(f"file:{household}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT repository, origin FROM corpus_claims"
        ).fetchall()
    finally:
        conn.close()
    tally: dict[str, dict[tuple[str, str, str], int]] = {}
    for repository, origin in rows:
        match = _ORIGIN_RX.match(str(origin or ""))
        if not match:
            continue
        key = (match["name"], match["commit"], match["toolchain"])
        tally.setdefault(str(repository), {}).setdefault(key, 0)
        tally[str(repository)][key] += 1
    out = []
    for repository, keys in sorted(tally.items()):
        (name, commit, toolchain), _ = max(keys.items(), key=lambda kv: kv[1])
        out.append(Row(repository, name, commit, toolchain,
                       claims=sum(keys.values())))
    return out


def extractors() -> dict[str, pathlib.Path]:
    """Toolchain digest -> the committed extractor that currently hashes to it.

    Computed, not tabulated: ``provenance.toolchain`` hashes the extractor and
    ``provenance.py`` together, so this map goes stale the moment either changes
    — which is the signal, not a defect. A digest that resolves to nothing means
    the toolchain moved since those rows were written.
    """
    here = pathlib.Path(__file__).resolve().parent
    return {provenance.toolchain(path): path
            for path in sorted(here.glob("extract_*.py"))}


def find_checkout(roots: list[pathlib.Path], row: Row) -> pathlib.Path | None:
    """The checkout for ``row``, searched by repository name then origin name.

    Both are tried because they diverge (``safe-app-store-public`` was read as
    ``safe``), and directory layout is a property of the machine, so this is a
    search rather than a mapping anyone has to maintain.
    """
    for root in roots:
        if not root.is_dir():
            continue
        for wanted in (row.repository, row.name):
            direct = root / wanted
            if (direct / ".git").exists():
                return direct
            for path in sorted(root.glob(f"*/{wanted}")):
                if (path / ".git").exists():
                    return path
    return None


#: The end-shapes a tombstone may declare, and the field each one must carry.
#: Reused verbatim from safe-app-store-public/docs/conventions/tombstones.md
#: rather than invented here, because a second vocabulary for the same idea is
#: the drift that convention exists to prevent. ``retired`` is the only shape
#: permitted to point nowhere, and it must say why "deliberately rather than by
#: omission".
_END_SHAPES = {
    "merged": "successor",
    "promoted": "successor",
    "rebuilt": "successor",
    "retired": "reason",
}

TOMBSTONES = pathlib.Path(__file__).resolve().parent / "tombstones.json"


def tombstones(path: pathlib.Path | None = None) -> dict[str, dict]:
    """Repositories recorded as retired, keyed by ``corpus_claims.repository``.

    **Authored, not derived** — and the one thing in this driver that is. The
    refresh *plan* is read out of the corpus precisely so it cannot reverse an
    operator decision (0222). A tombstone **is** an operator decision, and it is
    derivable from nothing: an absent checkout is indistinguishable from an
    unmounted disk, a renamed directory, or a clone that has not happened yet.
    So it must be written down, and this reads it rather than inferring it.

    The distinction it buys is the one the box keeps arriving at independently:
    **a recorded negative is not an absence.** ``REFUSED`` means *I could not
    look*; ``RETIRED`` means *there is nothing to look at, and here is where it
    went*. Without it a refusal list accumulates entries nobody can act on until
    nobody reads it — the same way an advisory that fires every turn stops being
    read (0221).

    A malformed record raises rather than being skipped: a tombstone that
    silently did not apply would put the repository back in the refusal list
    with no indication that anyone had tried to retire it.
    """
    path = path or TOMBSTONES
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1:
        raise ValueError(f"{path}: tombstones version must be 1")
    out = {}
    for repository, record in (data.get("tombstones") or {}).items():
        ended = record.get("ended")
        if ended not in _END_SHAPES:
            raise ValueError(
                f"{path}: {repository}: ended must be one of "
                f"{', '.join(sorted(_END_SHAPES))}, not {ended!r}")
        required = _END_SHAPES[ended]
        if not str(record.get(required) or "").strip():
            raise ValueError(
                f"{path}: {repository}: ended={ended!r} requires {required!r} — "
                f"a {ended} with nowhere to point is a deletion wearing an archive")
        out[repository] = record
    return out


def git_state(path: pathlib.Path, since: str) -> tuple[str, bool, int | None]:
    """``(head, dirty, commits_since)`` for a checkout. Never raises."""
    def run(*args: str) -> str:
        try:
            out = subprocess.run(["git", "-C", str(path), *args],
                                 capture_output=True, text=True,
                                 timeout=30, check=True)
            return out.stdout.strip()
        except (subprocess.SubprocessError, OSError):
            return ""
    head = run("rev-parse", "--short", "HEAD") or "unknown"
    dirty = bool(run("status", "--porcelain"))
    counted = run("rev-list", "--count", f"{since}..HEAD")
    return head, dirty, int(counted) if counted.isdigit() else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--household", default=str(pathlib.Path.home()
                                               / ".nestor/keep/nestor.db"),
                    help="the consolidated corpus to read the plan from and sync into")
    ap.add_argument("--repos-root", action="append", default=None,
                    metavar="DIR", help="where checkouts live; repeatable "
                                        "(default: ~/github)")
    ap.add_argument("--out", default="data/corpus",
                    help="source databases directory (gitignored)")
    ap.add_argument("--only", action="append", default=None, metavar="REPOSITORY",
                    help="limit to these repositories; repeatable")
    ap.add_argument("--dry-run", action="store_true",
                    help="report drift and refusals, extract nothing, sync nothing")
    args = ap.parse_args()

    household = pathlib.Path(args.household).expanduser().resolve()
    if not household.is_file():
        print(f"could not look — no household corpus at {household}")
        return 1
    roots = [pathlib.Path(r).expanduser().resolve()
             for r in (args.repos_root or [str(pathlib.Path.home() / "github")])]
    out_dir = pathlib.Path(args.out).expanduser().resolve()

    rows = plan(household)
    if args.only:
        wanted = set(args.only)
        rows = [row for row in rows if row.repository in wanted]
    if not rows:
        print(f"could not look — {household} holds no corpus claims to plan from")
        return 1

    known = extractors()
    retired = tombstones()
    ready: list[tuple[Row, pathlib.Path, pathlib.Path]] = []
    refused: list[tuple[Row, str]] = []
    laid_to_rest: list[tuple[Row, dict]] = []
    print(f"{'repository':<26} {'pinned':<9} {'head':<9} {'behind':>6}  {'extractor':<24} checkout / refusal")
    for row in rows:
        # A tombstoned repository is reported before anything else is tried.
        # Looking for a checkout that is recorded as gone, and then reporting
        # its absence as a failure, is how a refusal list fills with entries
        # nobody can act on.
        record = retired.get(row.repository)
        if record is not None:
            forward = record.get("successor") or record.get("reason") or ""
            print(f"  {row.repository:<24} {row.commit:<9} {'—':<9} {'—':>6}  "
                  f"{'RETIRED (' + str(record.get('ended')) + ')':<24} {forward}")
            laid_to_rest.append((row, record))
            continue
        extractor = known.get(row.toolchain)
        checkout = find_checkout(roots, row)
        if extractor is None:
            reason = (f"toolchain {row.toolchain} resolves to no committed "
                      f"extractor — it changed since these rows were written")
        elif checkout is None:
            reason = f"no checkout named {row.repository!r} or {row.name!r} under " \
                     f"{', '.join(str(r) for r in roots)}"
        else:
            head, dirty, behind = git_state(checkout, row.commit)
            if dirty:
                reason = (f"{checkout} has uncommitted changes — rows would be "
                          f"pinned to {head}, which does not contain them")
            else:
                behind_text = "?" if behind is None else str(behind)
                # The checkout path is printed, not just the extractor, because
                # a wider --repos-root can match an *archived* copy of a
                # retired repository (~/github-archive-*/willow resolved that
                # way on the first run) and re-extract it as though it were
                # live. Naming the directory makes that visible instead of
                # silent; no heuristic here can tell an archive from a checkout.
                try:
                    where = f"~/{checkout.relative_to(pathlib.Path.home())}"
                except ValueError:
                    where = str(checkout)
                print(f"  {row.repository:<24} {row.commit:<9} {head:<9} "
                      f"{behind_text:>6}  {extractor.name:<24} {where}")
                ready.append((row, extractor, checkout))
                continue
        print(f"  {row.repository:<24} {row.commit:<9} {'—':<9} {'—':>6}  REFUSED: {reason}")
        refused.append((row, reason))

    rest = f", {len(laid_to_rest)} retired" if laid_to_rest else ""
    print(f"\n{len(ready)} ready, {len(refused)} refused{rest}")
    if args.dry_run:
        print("dry run — nothing extracted, nothing synced")
        return 1 if refused else 0

    # A refused repository must still have a source database, or the sync would
    # rebuild the snapshot without it and the corpus would lose the repository
    # rather than merely let it go stale.
    out_dir.mkdir(parents=True, exist_ok=True)
    orphaned = [row.repository for row, _ in refused
                if not (out_dir / f"{row.repository}.db").is_file()]
    if orphaned:
        print(f"\nrefusing to sync — {len(orphaned)} refused repositor(y/ies) have no "
              f"existing source database, so syncing would drop them entirely: "
              f"{', '.join(orphaned)}")
        return 1

    failed = []
    for row, extractor, checkout in ready:
        target = out_dir / f"{row.repository}.db"
        print(f"\n=== {row.repository} ({extractor.name}) ===")
        result = subprocess.run(
            [sys.executable, str(extractor), "--repo", str(checkout),
             "--name", row.name, "--out", str(target)],
            check=False)
        if result.returncode != 0:
            print(f"  {extractor.name} exited {result.returncode} — "
                  f"{row.repository} keeps its previous rows")
            failed.append(row.repository)

    report = corpus.sync(out_dir, household)
    print(f"\nsynced {report.sources} source(s) -> {report.claims} claim(s); "
          f"snapshot {report.snapshot_sha256[:12]} "
          f"({'changed' if report.changed else 'unchanged'})")
    if failed:
        print(f"{len(failed)} extractor(s) failed: {', '.join(failed)}")
    return 1 if (refused or failed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
