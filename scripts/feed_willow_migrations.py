#!/usr/bin/env python3
"""Feed archived willow-2.0 migrations in — a schema change, and what it said it was for.

    python scripts/feed_willow_migrations.py --repo /path/to/archived/willow-2.0

**Historical tooling only.** ``willow-2.0`` is tier F (not cloned for live work).
On this machine the tree still exists under the greenfield archive, e.g.::

    ~/github-archive-greenfield-2026-08-10/archive/legacy-flat-2026-08-10/willow-2.0

or set ``WILLOW_20_REPO``. Origin label stays ``willow-2.0:migrations`` so rows
do not pretend to come from the living charter.

Third repo feed. Every file in ``migrations/`` opens with a ``--`` comment block
stating what the change is for, then the DDL. The pair is **migration → its
stated intent**, and the seal is a person confirming the DDL does what the
comment claims.

That gap is not hypothetical in this corpus. A migration comment is written
before the change lands and is never revisited; the DDL below it is what
actually ran. Nothing in any repository compares the two, and no test can — one
side is prose.

Read by parsing text, never by executing SQL. Everything lands as a draft.
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

DOMAIN, TARGET, ORIGIN = "migration", "intent", "willow-2.0:migrations"
BOLD, DIM, GREEN, AMBER, RED, OFF = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m")

_DDL = re.compile(r"\b(CREATE|ALTER|DROP)\s+(TABLE|INDEX|VIEW|TYPE)\s+"
                  r"(?:IF\s+(?:NOT\s+)?EXISTS\s+)?([A-Za-z0-9_.\"]+)", re.I)


def extract(path: pathlib.Path) -> dict | None:
    """``{name, intent, touches}``, or ``None`` if it could not be read.

    ``None`` and an empty intent are different: unreadable versus a migration
    that states nothing. Same distinction the other feeders had to be taught.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    lead: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if lead:
                break
            continue
        if stripped.startswith("--"):
            lead.append(stripped.lstrip("-").strip())
        else:
            break
    touches = sorted({m.group(3).strip('"') for m in _DDL.finditer(text)})
    return {"name": path.name,
            "intent": " ".join(" ".join(lead).split()),
            "touches": touches}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--keep", default="")
    args = ap.parse_args()

    d = pathlib.Path(args.repo) / "migrations"
    if not d.is_dir():
        print(f"{RED}no migrations/ under {args.repo}{OFF}")
        print(f"   {DIM}'I could not look' — refusing rather than reporting zero.{OFF}")
        return 1
    files = sorted(d.glob("*.sql"))
    if not files:
        print(f"\n{BOLD}willow-2.0 migrations → nestor{OFF}")
        print(f"   {AMBER}migrations/ exists and holds 0 .sql files{OFF}")
        print(f"   {DIM}A true empty, not a failure.{OFF}\n")
        return 0

    work = pathlib.Path(args.keep) if args.keep else pathlib.Path(
        tempfile.mkdtemp(prefix="nestor-feed-mig-"))
    work.mkdir(parents=True, exist_ok=True)
    cascade.set_ledger_path(str(work / "ledger.jsonl"))
    store = SqliteStore(str(work / "nestor.db"))
    store.init_db()
    store.memory_init()
    storage.set_store(store)

    rows = [r for r in (extract(p) for p in files) if r]
    print(f"\n{BOLD}willow-2.0 migrations → nestor{OFF}  {DIM}{DOMAIN}→{TARGET}{OFF}")
    print(f"   {len(files)} file(s), {len(rows)} read")

    silent = [r for r in rows if not r["intent"]]
    for r in rows:
        memory.add_pair(r["name"], r["intent"] or "(states no intent)",
                        DOMAIN, TARGET, status="draft",
                        origin=f"{ORIGIN}:{r['name']}", store=store,
                        reason=(f"Touches: {', '.join(r['touches']) or 'nothing parsed'}. "
                                f"Whether the DDL does what the comment says is prose "
                                f"against SQL — a person's job."))
    print()
    for r in rows:
        mark = AMBER if r["intent"] else RED
        print(f"   {mark}~{OFF} {BOLD}{r['name']:34}{OFF} "
              f"{DIM}{', '.join(r['touches'])[:44] or 'no DDL parsed'}{OFF}")
        print(f"        {(r['intent'] or '(states no intent)')[:96]}")

    if silent:
        print(f"\n   {RED}{len(silent)} migration(s) state no intent{OFF}: "
              f"{', '.join(r['name'] for r in silent)}")
    nodll = [r for r in rows if not r["touches"]]
    if nodll:
        print(f"   {AMBER}{len(nodll)} with no CREATE/ALTER/DROP parsed{OFF}: "
              f"{', '.join(r['name'] for r in nodll)}")

    print(f"\n   {len(rows)} row(s), {AMBER}0 sealed{OFF}. "
          f"{DIM}Every one a draft.{OFF}")
    if args.keep:
        print(f"   {DIM}kept: {work}{OFF}\n")
    else:
        shutil.rmtree(work, ignore_errors=True)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
