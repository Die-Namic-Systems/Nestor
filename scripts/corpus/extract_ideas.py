#!/usr/bin/env python3
"""The agent log, fed to the thing it is about.

    python scripts/corpus/extract_ideas.py --ref origin/master --ref HEAD \
        --out data/corpus/ideas.db

**Why by hand.** Rung 29 measured `IDEAS.md` at four rows from 3,891 lines: the
corpus cannot read its own findings, because they are prose and every shape it
knows requires a declared structure. This does deliberately what the extractor
was unable to do automatically, and `IDEAS.md` is the one document where that is
worth the effort — every line of it was written to be a claim.

**Four fields, lifted, not interpreted:**

    claim    the heading, with its number and status removed
    verdict  the status words the heading already carries
    reason   the italic provenance line every entry opens with
    origin   ref, commit, and the entry number

Pulling the *argument* out of an entry's body would mean deciding what the prose
meant, which is the line all thirty-five rungs refused to cross. The heading is
a claim the author wrote as a claim; the status is a verdict the author wrote as
a verdict. Nothing here is inferred.

**The key is the claim, never the number.** Two branches of this repository both
number entries 6.40 through 6.49, for ten different pairs of findings. A number
identifies a slot in a file, not a claim — §6.66's lesson, and the reason this
tool records the number in `origin` and lets the duplication show up as a
reported fact rather than a silently resolved one.

Every row lands as a **draft**. Several entries are corrections of earlier ones;
sealing a finding that was later withdrawn would put a known-false claim in the
memory permanently, which is precisely why the queue belongs to a human.
"""
from __future__ import annotations

import argparse
import collections
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import common                                                    # noqa: E402
import provenance                                                # noqa: E402

from nestor import memory                                        # noqa: E402
from nestor.sqlite_store import SqliteStore                      # noqa: E402

HEADING = re.compile(r"^### (\d+\.\d+) (.+)$", re.M)
STATUS = re.compile(r"\*\*([a-z][a-z ]*)\*\*")


def read_ref(ref: str, path: str = "IDEAS.md") -> tuple[str, str]:
    """``(text, short commit)`` for a file at a git ref."""
    def git(*args):
        return subprocess.run(["git", *args], capture_output=True, text=True,
                              timeout=120, check=True).stdout
    return git("show", f"{ref}:{path}"), git("rev-parse", "--short", ref).strip()


def entries(text: str) -> list[tuple[str, str, str, str]]:
    """``(number, claim, verdict, provenance)`` for each ### entry."""
    out = []
    marks = list(HEADING.finditer(text))
    for i, m in enumerate(marks):
        number, heading = m.group(1), m.group(2).strip()
        body = text[m.end():marks[i + 1].start() if i + 1 < len(marks) else len(text)]

        verdicts = STATUS.findall(heading)
        verdict = " / ".join(v.strip() for v in verdicts) or "unstated"
        # The claim is the heading with its trailing status clause removed.
        claim = re.split(r"\s+—\s+\*\*", heading)[0].strip().rstrip(",")

        # Every entry opens with an italic provenance line: what was run, when.
        prov = ""
        first = re.search(r"^\*(.+?)\*\s*$", body.strip(), re.S | re.M)
        if first:
            prov = " ".join(first.group(1).split())
        out.append((number, claim, verdict, prov[:600]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ref", action="append", required=True,
                    help="git ref to read IDEAS.md from; repeat for each branch")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out = pathlib.Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    rows: list[tuple] = []
    numbers: dict[str, set] = collections.defaultdict(set)
    root = pathlib.Path.cwd()
    for ref in args.ref:
        text, commit = read_ref(ref)
        for number, claim, verdict, prov in entries(text):
            numbers[number].add(claim)
            reason = f"§{number} @ {ref}" + (f" — {prov}" if prov else "")
            rows.append((claim, verdict, reason, root / "IDEAS.md",
                         f"{number}@{commit}"))

    origin = provenance.Origin("ideas", root, __file__)
    store = SqliteStore(str(out))
    store.memory_init()
    try:
        common.load(store, [("finding", rows, "claim", "verdict")], origin)
        stats = memory.stats(store=store)
        clashing = {n: c for n, c in numbers.items() if len(c) > 1}
        print(f"\n  {len(args.ref)} ref(s) read: {', '.join(args.ref)}")
        print(f"  entry numbers used twice for different claims: {len(clashing)}")
        for n in sorted(clashing, key=lambda s: [int(x) for x in s.split(".")]):
            print(f"    §{n}")
            for claim in sorted(clashing[n]):
                print(f"      {claim[:88]}")
        print(f"\n  sealed: {stats['sealed']}")
    finally:
        store.close()
    print(f"\n  store: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
