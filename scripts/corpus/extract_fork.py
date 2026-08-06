#!/usr/bin/env python3
"""The delta a fork carries — one extractor for all 44 of them.

    python scripts/corpus/extract_fork.py --repo /workspace/rudi193-cmd/hermes-agent \
        --name hermes-agent --out data/corpus/hermes-agent.db

**A fork's tree is its upstream author's work.** Extracting it would fill this
corpus with somebody else's structure under this operator's chronology —
provenance-correct and subject-wrong. The contribution is the commits added on
top, so that is the unit:

1. Select commits by author email. Their **count is a measurement**: a fork with
   none is a bookmark, not a contribution, and the corpus should say which
   rather than quietly extracting 2,000 upstream files either way.
2. Take each commit's subject and body as a pair. A commit message is a
   declaration written beside the change — the same argument that admits a
   docstring, with the advantage that nobody writes one for show.
3. Run the standard shapes over **only the files those commits touched**.

Requires history: a `--depth 1` clone cannot answer any of this.

Trailers (`Co-authored-by`, `Signed-off-by`, `Claude-Session`) are stripped from
bodies. They are attribution metadata rather than the author's account of the
change, and leaving them in would file the same three lines under every row.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import common                                                    # noqa: E402
import provenance                                                # noqa: E402

from nestor.sqlite_store import SqliteStore                      # noqa: E402

SEP = "\x1e"
TRAILER = re.compile(r"^(Co-authored-by|Signed-off-by|Claude-Session|"
                     r"Co-Authored-By|Reviewed-by|Refs):", re.I)


def _git(root: pathlib.Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(root), *args],
                         capture_output=True, text=True, timeout=120, check=True)
    return out.stdout


def strip_trailers(body: str) -> str:
    kept = [ln for ln in body.splitlines()
            if ln.strip() and not TRAILER.match(ln.strip()) and ln.strip() != "---------"]
    return " ".join(" ".join(kept).split())


def created_by(root: pathlib.Path, files: set, email: str) -> tuple[set, set]:
    """Split touched files into ``(created here, merely modified)``.

    §6.49's gap. ``touched`` is not ``authored``: a file the operator edited was
    written by whoever added it, and its docstrings are that person's habit. Run
    over a fork's delta without this split, docstring coverage reported 77% —
    upstream's number, about to be filed under this operator's name.

    The creator is the author of the commit that added the path
    (``--diff-filter=A``, oldest such commit, since a path can be added, deleted
    and re-added).
    """
    created, modified = set(), set()
    for path in sorted(files):
        rel = path.relative_to(root)
        try:
            adds = _git(root, "log", "--diff-filter=A", "--format=%ae",
                        "--", str(rel)).split()
        except subprocess.SubprocessError:
            adds = []
        (created if adds and adds[-1] == email else modified).add(path)
    return created, modified


def delta(root: pathlib.Path, email: str) -> tuple[list[tuple], set, int]:
    """``(commit rows, files touched, commit count)`` for one author."""
    raw = _git(root, "log", f"--author={email}", f"--format=%h{SEP}%ad{SEP}%s{SEP}%b\x1d",
               "--date=short")
    rows: list[tuple] = []
    count = 0
    for record in raw.split("\x1d"):
        record = record.strip("\n")
        if not record.strip():
            continue
        parts = record.split(SEP)
        if len(parts) < 4:
            continue
        sha, date, subject, body = parts[0], parts[1], parts[2], parts[3]
        count += 1
        text = strip_trailers(body)
        if len(text) < 12:
            # A subject with no body is a change with no stated reason. Not an
            # error and not a pair — counted, not invented.
            continue
        rows.append((subject.strip(), text[:900], f"commit {sha}, {date}",
                     root / "README.md", sha))

    names = _git(root, "log", f"--author={email}", "--name-only", "--format=")
    touched = {(root / n).resolve() for n in names.splitlines() if n.strip()}
    return rows, {p for p in touched if p.exists()}, count


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--name", required=True, help="corpus name for origins")
    ap.add_argument("--out", required=True)
    ap.add_argument("--email", default="rudi193@gmail.com")
    args = ap.parse_args()

    root = pathlib.Path(args.repo).resolve()
    out = pathlib.Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    commits, touched, count = delta(root, args.email)
    created, modified = created_by(root, touched, args.email)
    total_commits = len(_git(root, "log", "--format=%h").splitlines())

    origin = provenance.Origin(args.name, root, __file__)
    plan, declined, symbols, defined = common.standard(root, only=touched)
    plan = [("commit", commits, "change", "rationale"), *plan]

    store = SqliteStore(str(out))
    store.memory_init()
    try:
        common.load(store, plan, origin, declined)
        print(f"\n  delta: {count} of {total_commits} commit(s) by {args.email}, "
              f"touching {len(touched)} file(s)")
        print(f"  commits with a stated reason: {len(commits)}/{count}")
        if defined:
            print(f"  docstrings over all touched files: {len(symbols)}/{defined}"
                  f"   <- blended, not the operator's")
            for label, group in (("created here", created), ("modified only", modified)):
                rows, total = common.docstrings(root, only=group)
                if total:
                    print(f"    {label:14} {len(rows):4}/{total:<4} "
                          f"({len(rows) / total:.0%})  over {len(group)} file(s)")
    finally:
        store.close()
    print(f"\n  store: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
