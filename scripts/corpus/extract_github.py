#!/usr/bin/env python3
"""Pull requests and issues — where the decisions were actually argued.

    python scripts/corpus/extract_github.py --org willow-memory --out data/corpus/gh-willow-memory.db

Measured 2026-08-30: 1,342 pull requests and issues across seven orgs, none of
them in the corpus. It is the largest body of decision evidence the box owns and
the densest: a merged PR carries what changed, why, what review caught, and what
was rejected on the way.

What this takes, and what it deliberately leaves:

* **The title and the first paragraph of the body.** A PR body's opening
  paragraph is the author's own summary; the rest is diff commentary that ages
  badly and belongs to the commit, not to the corpus.
* **The outcome as its own row** — merged, closed unmerged, still open. "Closed
  without merging" is a decision, and a corpus that only records merges is the
  green-only CI trap: a recorded negative is not an absence.
* **Never review comments.** They are conversation, frequently about people, and
  the wall this corpus keeps is that it holds process, not persons.

Every row is a draft, like everything in this lane. A merged PR is not a sealed
claim — a human merged code, which is not the same act as verifying a statement.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import common                                                      # noqa: E402
import provenance                                                  # noqa: E402

from nestor.sqlite_store import SqliteStore                        # noqa: E402

FIELDS = "number,title,state,body,url,closedAt"


def gh(*args: str) -> list | None:
    try:
        p = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.SubprocessError):
        return None
    if p.returncode != 0:
        return None
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        return None


def first_para(body: str) -> str:
    for block in (body or "").replace("\r", "").split("\n\n"):
        t = " ".join(block.split())
        if t and not t.startswith(("#", "-", "*", "|", "```", "<!--", ">")):
            return t
    return ""


def rows_for(repo: str, root: pathlib.Path) -> tuple[list, int]:
    rows, seen = [], 0
    for kind, cmd in (("pr", ["pr", "list", "--json", FIELDS + ",mergedAt"]),
                      ("issue", ["issue", "list", "--json", FIELDS])):
        items = gh(*cmd, "--repo", repo, "--state", "all", "--limit", "400")
        if items is None:
            print(f"    REFUSED: gh could not list {kind}s for {repo}")
            continue
        for it in items:
            seen += 1
            title = " ".join(str(it.get("title", "")).split())
            if not title:
                continue
            num = it.get("number")
            ref = f"{repo}#{num}"
            summary = first_para(it.get("body") or "")
            if summary:
                rows.append((f"{ref} · {title}", summary[:1500],
                             f"{kind}, {it.get('url', '')}", root, str(num)))
            if kind == "pr":
                outcome = ("merged" if it.get("mergedAt")
                           else "closed without merging" if it.get("closedAt") else "open")
            else:
                outcome = "closed" if it.get("closedAt") else "open"
            rows.append((f"{ref} · outcome", outcome,
                         f"{kind} titled: {title}", root, f"{num}-outcome"))
    return rows, seen


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--org", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--anchor-repo", default=".",
                    help="a checkout used only to pin the origin's commit")
    args = ap.parse_args()

    repos = gh("repo", "list", args.org, "--limit", "200", "--json", "nameWithOwner")
    if repos is None:
        print(f"error: gh could not list repositories for {args.org}", file=sys.stderr)
        return 1
    root = pathlib.Path(args.anchor_repo).resolve()
    rows, seen = [], 0
    for r in repos:
        name = r["nameWithOwner"]
        got, n = rows_for(name, root)
        seen += n
        if got:
            print(f"    {name}: {len(got)} row(s) from {n} item(s)")
        rows.extend(got)
    print(f"  {args.org}: {len(rows)} row(s) from {seen} item(s)")
    if not rows:
        print("error: nothing to write — refusing to create an empty store", file=sys.stderr)
        return 1

    out = pathlib.Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    origin = provenance.Origin(f"gh-{args.org}", root, __file__)
    store = SqliteStore(str(out))
    store.memory_init()
    try:
        common.load(store, [("github", rows, "issue", "summary")], origin)
    finally:
        store.close()
    print(f"  store: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
