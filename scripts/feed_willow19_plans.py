#!/usr/bin/env python3
"""Feed willow-1.9's plans in — a plan, and what it committed to.

    python scripts/feed_willow19_plans.py --repo /path/to/willow-1.9

Fourth and last of the repo feeds, and the one whose corpus is **frozen**.
willow-1.9 is archived. Its `docs/superpowers/plans/` and `specs/` are dated
documents stating what was going to be built, and nothing after the archive date
can change whether it was.

The pair is **plan → what it committed to**, and the seal is the only question
worth asking of an archived plan: *did this happen?* No test can answer it. The
repository cannot answer it — it stopped. Only somebody who was there can, which
is the narrowest and clearest case for a human signature in the whole box.

Everything lands as a draft, and here that is not a formality: a plan is written
in the future tense and reads as settled precisely because it was confident.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import shutil
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
os.environ.setdefault("NESTOR_SEAL_KEY", "feed-fixture-key-not-a-secret")

from nestor import cascade, memory, storage          # noqa: E402
from nestor.sqlite_store import SqliteStore          # noqa: E402

DOMAIN, TARGET, ORIGIN = "plan", "committed", "willow-1.9:plans"
BOLD, DIM, GREEN, AMBER, RED, OFF = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m")

_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def extract(path: pathlib.Path) -> dict | None:
    """``{name, date, title, commits}`` — or ``None`` if unreadable."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    title = ""
    body: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not title and s.startswith("# "):
            title = s[2:].strip()
            continue
        if title:
            if s.startswith("#"):
                break
            if s and not s.startswith(("|", "---", "```", ">")):
                body.append(s)
            elif body:
                break
    date = _DATE.search(path.name)
    return {"name": path.name,
            "date": date.group(1) if date else "",
            "title": title,
            "commits": " ".join(" ".join(body).split())[:400]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--keep", default="")
    args = ap.parse_args()

    root = pathlib.Path(args.repo) / "docs" / "superpowers"
    dirs = [root / "plans", root / "specs"]
    present = [d for d in dirs if d.is_dir()]
    if not present:
        print(f"{RED}no docs/superpowers/plans|specs under {args.repo}{OFF}")
        print(f"   {DIM}'I could not look' — refusing rather than reporting zero.{OFF}")
        return 1
    files = sorted(p for d in present for p in d.glob("*.md"))
    if not files:
        print(f"\n{BOLD}willow-1.9 plans → nestor{OFF}")
        print(f"   {AMBER}the plan directories exist and hold 0 .md files{OFF}")
        print(f"   {DIM}A true empty, not a failure.{OFF}\n")
        return 0

    work = pathlib.Path(args.keep) if args.keep else pathlib.Path(
        tempfile.mkdtemp(prefix="nestor-feed-plans-"))
    work.mkdir(parents=True, exist_ok=True)
    cascade.set_ledger_path(str(work / "ledger.jsonl"))
    store = SqliteStore(str(work / "nestor.db"))
    store.init_db()
    store.memory_init()
    storage.set_store(store)

    rows = [r for r in (extract(p) for p in files) if r]
    print(f"\n{BOLD}willow-1.9 plans → nestor{OFF}  {DIM}{DOMAIN}→{TARGET}, "
          f"archived corpus{OFF}")
    print(f"   {len(files)} document(s), {len(rows)} read")

    untitled = [r for r in rows if not r["title"]]
    silent = [r for r in rows if not r["commits"]]
    for r in rows:
        memory.add_pair(r["title"] or r["name"],
                        r["commits"] or "(states nothing under its heading)",
                        DOMAIN, TARGET, status="draft",
                        origin=f"{ORIGIN}:{r['name']}", store=store,
                        reason=(f"Dated {r['date'] or 'undated'}. willow-1.9 is "
                                f"archived, so whether this happened is not "
                                f"answerable from the repository — only by "
                                f"somebody who was there."))
    dates = sorted({r["date"] for r in rows if r["date"]})
    print(f"   {DIM}dated {dates[0]} … {dates[-1]}{OFF}" if dates else "")
    print()
    for r in rows[:12]:
        print(f"   {AMBER}~{OFF} {DIM}{r['date'] or '          '}{OFF} "
              f"{(r['title'] or r['name'])[:66]}")
    if len(rows) > 12:
        print(f"   {DIM}… and {len(rows) - 12} more{OFF}")

    if untitled:
        print(f"\n   {AMBER}{len(untitled)} document(s) with no '# ' heading{OFF}")
    if silent:
        print(f"   {AMBER}{len(silent)} state nothing under their heading{OFF}")
    print(f"\n   {len(rows)} row(s), {AMBER}0 sealed{OFF}. {DIM}Every one a draft, "
          f"and the corpus cannot answer its own question.{OFF}")
    if args.keep:
        print(f"   {DIM}kept: {work}{OFF}\n")
    else:
        shutil.rmtree(work, ignore_errors=True)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
