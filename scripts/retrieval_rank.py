#!/usr/bin/env python3
"""Where does the *correct* row rank for a probe — not just whether it served.

    python scripts/retrieval_rank.py --db data/nestor.db --from decision --to decision \
        --probe "Can a language model stand in for the embedder?" \
        --expect "stand up a language model as a stand-in"

Served / pending counts cannot tell two very different failures apart, and
IDEAS §6.94 measured the counts without the rank:

* **below the bar at rank 1** — retrieval works, the threshold is refusing a
  match it is not sure of, and calibrating the bar down would serve the right
  answer;
* **below the bar at rank 110** — retrieval does not reach the row at all, and
  calibrating the bar down would serve a *wrong* answer, which is the outcome
  the bar exists to prevent.

Both print as `pending`. That is the whole reason this exists: §6.106 was
measured with it and corrected a claim made from the counts alone, in this
repository, ninety minutes earlier.

``--expect`` is a substring of the source text of the row that *should* win. It
is matched case-insensitively against `source_text`, and a probe whose expected
row is not in the store is reported as **unfindable** rather than as rank 0 —
"the answer is not here" and "the answer is here and ranked last" are different
facts, and the second is the only one that says anything about the matcher.

Scoring goes through :func:`nestor.matcher.match_similarity`, so ``--matcher``
selects the same shipped names the CLI accepts and a `score()`-based matcher is
used the way `memory.lookup` would use it.
"""
from __future__ import annotations

import argparse
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from nestor.answer import build_matcher, load_matcher               # noqa: E402
from nestor.matcher import match_similarity, uses_raw_score         # noqa: E402

BOLD, DIM, GREEN, AMBER, RED, OFF = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m")


def rows_for(db: str, source_lang: str, target_lang: str) -> list[tuple[str, str]]:
    con = sqlite3.connect(db)
    try:
        return con.execute(
            "SELECT source_text, source_norm FROM tm_pairs "
            "WHERE source_lang=? AND target_lang=?",
            (source_lang, target_lang)).fetchall()
    finally:
        con.close()


def ranked(probe: str, rows, matcher) -> list[tuple[float, str]]:
    """Every row scored against the probe, best first."""
    raw = uses_raw_score(matcher)
    norm = matcher.normalize(probe)
    scored = [(match_similarity(matcher, probe, norm, text, stored_norm or matcher.normalize(text),
                                _raw_score=raw), text)
              for text, stored_norm in rows]
    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    return scored


def find(scored: list[tuple[float, str]], needle: str) -> tuple[int, float] | None:
    low = needle.lower()
    for position, (score, text) in enumerate(scored, start=1):
        if low in text.lower():
            return position, score
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default="data/nestor.db")
    ap.add_argument("--source-lang", "--from", dest="source_lang", default="decision")
    ap.add_argument("--target-lang", "--to", dest="target_lang", default="decision")
    ap.add_argument("--matcher", default="string")
    ap.add_argument("--threshold", type=float, default=0.92)
    ap.add_argument("--show", type=int, default=3, help="losers to print above the correct row")
    ap.add_argument("--probe", action="append", required=True)
    ap.add_argument("--expect", action="append", required=True,
                    help="substring of the row that should win; pair-wise with --probe")
    args = ap.parse_args()

    if len(args.probe) != len(args.expect):
        print(f"{RED}--probe and --expect must be given the same number of times "
              f"({len(args.probe)} vs {len(args.expect)}){OFF}")
        return 2

    if not pathlib.Path(args.db).exists():
        print(f"{RED}no store at {args.db}{OFF}")
        print(f"   {DIM}'I could not look' — refusing rather than reporting a "
              f"corpus in which nothing ranks.{OFF}")
        return 1

    matcher = load_matcher(args.matcher) if ":" in args.matcher \
        else build_matcher(args.matcher, persist=False)
    rows = rows_for(args.db, args.source_lang, args.target_lang)
    if not rows:
        print(f"{AMBER}0 row(s) in {args.source_lang}→{args.target_lang}{OFF}")
        print(f"   {DIM}Read, and empty. Said differently from 'could not look' "
              f"on purpose.{OFF}")
        return 0

    print(f"\n{BOLD}retrieval rank{OFF}  {DIM}{len(rows)} row(s) in "
          f"{args.source_lang}→{args.target_lang}, matcher {type(matcher).__name__}, "
          f"bar {args.threshold}{OFF}")

    unfindable = 0
    for probe, expect in zip(args.probe, args.expect):
        scored = ranked(probe, rows, matcher)
        hit = find(scored, expect)
        print(f"\n  {BOLD}{probe[:96]}{OFF}")
        if hit is None:
            unfindable += 1
            print(f"    {RED}unfindable{OFF} — no row contains {expect!r}")
            print(f"    {DIM}Not rank last: the expected row is not in this store "
                  f"at all, which says nothing about the matcher.{OFF}")
            continue
        position, score = hit
        served = score >= args.threshold
        colour = GREEN if position == 1 else (AMBER if position <= args.show else RED)
        print(f"    correct row at {colour}rank {position}/{len(scored)}{OFF} "
              f"score {score:.3f}   top {scored[0][0]:.3f}   "
              f"{'served' if served else 'pending'}")
        if position > 1:
            for score_i, text in scored[:args.show]:
                print(f"      {DIM}beaten by {score_i:.3f}  {text[:78]}{OFF}")
        if position == 1 and not served:
            print(f"      {DIM}rank 1 below the bar: the threshold is the only thing "
                  f"between this question and its answer{OFF}")
        elif position > 1 and not served:
            print(f"      {DIM}not rank 1 and below the bar: lowering the bar would "
                  f"serve one of the rows above instead{OFF}")

    if unfindable:
        print(f"\n{AMBER}{unfindable} probe(s) had no expected row in this store{OFF}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
