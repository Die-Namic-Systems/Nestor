#!/usr/bin/env python3
"""The top — run every repo feed, and be honest about the ones that found nothing.

    python scripts/feed_all.py --willow-2 /path/to/willow --jeles /path/to/jeles
    python scripts/feed_all.py                       # no paths: every feed skipped

``--willow-2`` names the *charter* checkout (cases under
``governance/compliance/cases/``); the flag keeps its historical name. Pass the
greenfield-archive willow-2.0 tree only for ``--willow-2-migrations``.

One entry point over the individual feeders in this directory. It adds exactly
one thing they cannot do alone: **a combined verdict that separates the three
ways a feed produces no rows.**

    fed          the corpus was read and had contents
    empty        the corpus was read and declares nothing
    unreadable   it could not be read — a path missing, a literal that is not one
    skipped      no checkout was supplied for it

A feeder reports its own case correctly. Run several together and the distinction
is what disappears first: four feeds, one summary line, *0 rows* — and nobody can
tell whether the corpora were empty or the paths were wrong. That is the failure
this file exists to prevent, and it is the same failure the package prevents for
answers: *nothing matched* and *I could not look* are different sentences.

**Why it exists at all.** Running the feeders against an empty repository is what
found the defect they both had — an unreadable registry and an empty one printed
the same words. The top is the place that mistake is cheapest to make again, so
it is the place the distinction is pinned.

**It runs the feeders as subprocesses**, on purpose. Each installs a
process-wide store, ledger path and matcher; importing them into one interpreter
would make the last one win, which is `demo/desks.py`'s whole subject. The exit
code is the contract: 0 fed or genuinely empty, 1 unreadable.
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent

BOLD, DIM, GREEN, AMBER, RED, OFF = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m")

#: (flag, feeder, what it feeds). Order is the order they were built.
FEEDS = (
    ("willow_2", "feed_willow_constitution.py",
     "charter constitution cards — clause → forbidden act"),
    ("jeles", "feed_jeles_sources.py",
     "jeles registry — source → subjects claimed"),
    ("willow_2_migrations", "feed_willow_migrations.py",
     "archived willow-2.0 migrations — change → stated intent"),
    ("willow_19", "feed_willow19_plans.py",
     "willow-1.9 plans — plan → what it committed to (archived)"),
)

FED, EMPTY, UNREADABLE, SKIPPED = "fed", "empty", "unreadable", "skipped"

#: What each feeder prints when it read a corpus that declares nothing. Mirrored
#: rather than imported — these are the words a reader sees, and importing a
#: constant would make the pin true by construction.
_EMPTY_MARKERS = ("declares 0 institutions", "holds 0 const_*.py",
                  "holds 0 .sql files", "hold 0 .md files")


def run_one(script: str, repo: str) -> tuple[str, str, int]:
    """``(state, output, returncode)`` for one feeder against one checkout."""
    done = subprocess.run([sys.executable, str(HERE / script), "--repo", repo],
                          capture_output=True, text=True, timeout=300)
    out = done.stdout + done.stderr
    if done.returncode != 0:
        return UNREADABLE, out, done.returncode
    if any(marker in out for marker in _EMPTY_MARKERS):
        return EMPTY, out, done.returncode
    return FED, out, done.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for flag, _, what in FEEDS:
        ap.add_argument(f"--{flag.replace('_', '-')}", default="", help=what)
    ap.add_argument("--quiet", action="store_true",
                    help="summary only; do not echo each feeder's output")
    args = ap.parse_args()

    print(f"\n{BOLD}feeding the box{OFF}")
    results: list[tuple[str, str, str]] = []
    for flag, script, what in FEEDS:
        repo = getattr(args, flag)
        if not repo:
            results.append((script, SKIPPED, "no checkout supplied"))
            continue
        state, out, _ = run_one(script, repo)
        results.append((script, state, repo))
        if not args.quiet:
            print(f"\n{DIM}{'─' * 68}{OFF}")
            print(out.rstrip())

    print(f"\n{DIM}{'─' * 68}{OFF}")
    print(f"{BOLD}verdict{OFF}")
    colour = {FED: GREEN, EMPTY: AMBER, UNREADABLE: RED, SKIPPED: DIM}
    for script, state, detail in results:
        print(f"   {colour[state]}{state:11}{OFF} {script:34} {DIM}{detail}{OFF}")

    counts = {s: sum(1 for _, st, _ in results if st == s)
              for s in (FED, EMPTY, UNREADABLE, SKIPPED)}
    print(f"\n   {counts[FED]} fed · {counts[EMPTY]} empty · "
          f"{counts[UNREADABLE]} unreadable · {counts[SKIPPED]} skipped")

    if counts[FED] == 0:
        print(f"\n   {AMBER}Nothing was fed.{OFF} Which is not the same as "
              f"nothing being there —")
        print(f"   {DIM}see the per-feed states above. A summary that said only "
              f"'0 rows' would have{OFF}")
        print(f"   {DIM}hidden which of the three reasons applied, and that is "
              f"the reason this file exists.{OFF}")
    if counts[UNREADABLE]:
        print(f"\n   {RED}{counts[UNREADABLE]} corpus/corpora could not be "
              f"read.{OFF} Nothing about them is known —")
        print(f"   {DIM}they are not empty, and they are not fed.{OFF}")

    print(f"\n   {DIM}Every row every feeder wrote is a draft. Nothing here "
          f"seals anything.{OFF}\n")
    return 1 if counts[UNREADABLE] else 0


if __name__ == "__main__":
    raise SystemExit(main())
