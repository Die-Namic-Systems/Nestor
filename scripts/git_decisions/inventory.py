#!/usr/bin/env python3
"""Every repository on a box, with the decisions the operator actually made in it.

    python scripts/git_decisions/inventory.py --root ~/github
    python scripts/git_decisions/inventory.py --root ~/github --out data/git-decisions/manifest.json
    python scripts/git_decisions/inventory.py --root ~/github --email me@example.com

**Why this exists.** A merged pull request is a decision a human already made and
already followed to production: attributed, timestamped, immutable, and — because
git is itself a hash chain — anchored by something that was not trying to be
helpful about it. The transcripts of how it was argued are noisier and require
inferring what a "yes" was yes *to*; the merge does not. Git also pre-filtered the
corpus: what was abandoned never landed. This is agent-log §6.105 — the fleet's
own decision record is invisible to every corpus extractor — approached from the
side where the record already exists.

**Order is smallest first.** Each repository is a rung, and a rung has to be right
before anything is built on it (``docs/corpus-order.md`` makes the same argument
for the corpus-from-a-corpus exercise, in the other direction). The smallest
repository is the one whose output a person can read in full and say "yes, that is
what I decided" — so it is the one that proves the shape. Scaling from there means
every later run is judged against a shape already checked by eye, rather than
everything arriving at once and being trusted because reading it is impractical.

**Identity is the remote, not the directory.** A clone directory is whatever the
person cloning it typed; on this box ``willow`` holds ``Willow`` and ``dotgithub``
holds ``.github``. Keying on the directory silently mis-names repositories — the
defect this repo's own fleet survey carried until it was measured.

Read-only. Writes a manifest and prints a table; extracts nothing and seals
nothing. The covenant holds here as everywhere: propose, do not confirm.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

#: Merge subjects that are automation, not a judgment somebody made. A release
#: bot's merge is a decision the way a cron tick is: it happened, nobody chose it
#: in the moment. Counted separately rather than dropped, so the manifest shows
#: what it set aside instead of quietly shrinking.
ROBOT_MARKERS = ("dependabot", "release-please", "renovate", "[bot]",
                 "chore(master): release", "chore(deps)")


def git(root: pathlib.Path, *args: str) -> str:
    """One git call; empty string on any failure.

    A repository that cannot answer is reported as zero rather than crashing a
    survey of the thirty-five others.
    """
    try:
        done = subprocess.run(["git", "-C", str(root), *args],
                              capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout if done.returncode == 0 else ""


def repo_name(root: pathlib.Path) -> str:
    """What the repository is called — ``owner/name``, because the name alone is
    not unique.

    Five organisations on this box each have a ``.github`` repository. Keyed on
    the bare name they are one row that silently overwrites four others, which is
    the same identity mistake as keying on the directory, one level up: a name is
    not an identity until it is qualified by the thing that scopes it. The owner
    comes from the remote for the same reason the name does.
    """
    url = git(root, "remote", "get-url", "origin").strip()
    if not url:
        return root.name
    trimmed = url.rstrip("/").removesuffix(".git")
    tail = trimmed.rsplit(":", 1)[-1]                 # git@host:owner/name
    parts = [p for p in tail.split("/") if p]
    return "/".join(parts[-2:]) if len(parts) >= 2 else (parts[-1] if parts else root.name)


def find_checkouts(root: pathlib.Path, depth: int) -> list[pathlib.Path]:
    """Clones under ``root``, at most ``depth`` levels down.

    Org directories on this box hold the repositories one level in
    (``willow-memory/willow-gate``), and a checkout does not contain another, so
    the walk stops descending once it finds one.
    """
    found: list[pathlib.Path] = []

    def walk(d: pathlib.Path, level: int) -> None:
        if level > depth or not d.is_dir():
            return
        if (d / ".git").is_dir():
            found.append(d)
            return                      # a checkout is a leaf for this purpose
        try:
            children = sorted(d.iterdir())
        except OSError:
            return
        for child in children:
            if child.is_dir():
                walk(child, level + 1)

    walk(root, 0)
    return found


def emails_for(root: pathlib.Path, explicit: list[str]) -> list[str]:
    """Whose commits count as the operator's.

    An explicit ``--email`` wins. Otherwise the repository's own configured
    ``user.email`` is the best available answer, and a repo with none contributes
    nothing rather than guessing at an identity.
    """
    if explicit:
        return explicit
    configured = git(root, "config", "user.email").strip()
    return [configured] if configured else []


def survey(root: pathlib.Path, emails: list[str]) -> dict:
    """Count what this repository holds, split into judgments and automation."""
    who = [f"--author={e}" for e in emails]
    total = len(git(root, "log", "--all", "--format=%h").splitlines())
    mine = len(git(root, "log", "--all", *who,
                   "--format=%h").splitlines()) if who else 0

    merges, robots = 0, 0
    if who:
        for line in git(root, "log", "--all", "--merges", *who,
                        "--format=%s").splitlines():
            low = line.lower()
            if any(m in low for m in ROBOT_MARKERS):
                robots += 1
            else:
                merges += 1

    firsts = git(root, "log", "--all", *who, "--reverse", "--format=%ad",
                 "--date=short").splitlines() if who else []
    last = git(root, "log", "--all", *who, "-1", "--format=%ad",
               "--date=short").strip() if who else ""
    return {
        "name": repo_name(root),
        "path": str(root),
        "head": git(root, "rev-parse", "--short", "HEAD").strip(),
        "emails": emails,
        "commits_total": total,
        "commits_mine": mine,
        "merges_mine": merges,
        "merges_robot": robots,
        "first": firsts[0] if firsts else "",
        "last": last,
        # The rung's size: what a person would actually be asked to look at.
        "weight": mine + merges,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default="~/github",
                    help="directory holding the clones")
    ap.add_argument("--depth", type=int, default=2,
                    help="levels down to look for checkouts (default 2)")
    ap.add_argument("--email", nargs="*", default=[],
                    help="whose commits count; defaults to each repo's user.email")
    ap.add_argument("--out", default="",
                    help="write the ordered manifest here as JSON")
    ap.add_argument("--include-empty", action="store_true",
                    help="also list repositories the operator never committed to")
    args = ap.parse_args()

    root = pathlib.Path(args.root).expanduser()
    if not root.is_dir():
        print(f"no such directory: {root}", file=sys.stderr)
        return 2

    rows = [survey(c, emails_for(c, args.email))
            for c in find_checkouts(root, args.depth)]
    skipped = [r for r in rows if r["commits_mine"] == 0]
    if not args.include_empty:
        rows = [r for r in rows if r["commits_mine"] > 0]

    # Smallest first — see the module docstring. Name breaks ties so a re-run
    # produces the same order and a resumed run picks up where it left off.
    rows.sort(key=lambda r: (r["weight"], r["name"]))

    print(f"\n  {len(rows)} repositorie(s) with your commits, smallest first\n")
    head = (f"  {'#':>3}  {'repository':<36} {'yours':>6} {'merges':>7} "
            f"{'robot':>6} {'of total':>9}  {'first':<11} last")
    print(head)
    print("  " + "-" * (len(head) - 2))
    for i, r in enumerate(rows, 1):
        print(f"  {i:>3}  {r['name']:<36} {r['commits_mine']:>6} "
              f"{r['merges_mine']:>7} {r['merges_robot']:>6} "
              f"{r['commits_total']:>9}  {r['first']:<11} {r['last']}")

    print(f"\n  {'':>3}  {'TOTAL':<36} "
          f"{sum(r['commits_mine'] for r in rows):>6} "
          f"{sum(r['merges_mine'] for r in rows):>7} "
          f"{sum(r['merges_robot'] for r in rows):>6}")
    if skipped and not args.include_empty:
        print(f"\n  {len(skipped)} checkout(s) with none of your commits, not "
              f"listed — upstream clones and forks you only read.")
    print("  robot merges are counted and set aside, not dropped: a release "
          "bot's merge\n  is not a judgment somebody made.")

    if args.out:
        out = pathlib.Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"root": str(root), "order": "weight asc",
                                   "repos": rows}, indent=2), encoding="utf-8")
        print(f"\n  manifest: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
