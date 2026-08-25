#!/usr/bin/env python3
"""Feed cortex's workflow surface into Nestor — injected globals and CLI backends.

    python scripts/feed_cortex_workflow.py --readme /path/to/cortex/README.md
    python scripts/feed_cortex_workflow.py --repo /path/to/cortex
    python scripts/feed_cortex_workflow.py --repo … --keep DIR

Cortex is a model-agnostic workflow orchestrator for coding agents. Its README
declares two things a caller has to know to write a workflow: the injected
globals (``agent``, ``parallel``, ``pipeline``, ``phase``, ``log``, ``args``)
and the CLI backends the ``agent()`` call actually dispatches to (``claude``,
``codex``, ``cursor``). Both are pipe-delimited markdown tables under known
headings.

**Two shapes come out of one file.** The globals table lands as
``add_pair(name, behavior, "runtime_global", "behavior", status="draft")``;
the backends table as ``add_pair(name, cli, "backend", "cli", status="draft")``.
The row's ``reason`` carries the section heading it was parsed under so a
reader can go back to the README.

**Read by parsing, never by importing.** The README is markdown; the tables
are matched by regex over lines beginning with a pipe. No JavaScript runs to
get the rows, no attempt to load the workflow runtime itself.

**Absent, empty, and unreadable are three different sentences.** A missing
README is unreadable (exit 1); a README with the headings but no table rows
is empty (exit 0, loud); anything is fed (exit 0). Same distinction the other
feeders preserve.

**Why draft.** The tables restate the runtime's contract from the README —
one place, easily edited. Whether a specific row still matches what
``src/runtime.ts`` actually injects is a check nothing in this feeder makes;
that agreement is what sealing would ratify.
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
from recipes import patch_review                     # noqa: E402

ORIGIN = "cortex:readme"
MATCHER = patch_review.MATCHER

GLOBALS_DOMAIN, GLOBALS_TARGET = "runtime_global", "behavior"
BACKENDS_DOMAIN, BACKENDS_TARGET = "backend", "cli"

BOLD, DIM, GREEN, AMBER, RED, OFF = (
    "\033[1m", "\033[2m", "\033[32m", "\033[33m", "\033[31m", "\033[0m")


def resolve_readme(repo: str = "", readme: str = "") -> pathlib.Path | None:
    if readme:
        p = pathlib.Path(readme)
        return p if p.is_file() else None
    if not repo:
        return None
    p = pathlib.Path(repo) / "README.md"
    return p if p.is_file() else None


def _rows_after(text: str, heading_pat: str) -> list[list[str]]:
    """Rows of the first pipe-table under a heading. Skip the header + divider."""
    m = re.search(heading_pat, text, re.M | re.I)
    if not m:
        return []
    after = text[m.end():]
    lines = after.splitlines()
    table = []
    started = False
    for ln in lines:
        s = ln.strip()
        if s.startswith("|"):
            started = True
            cells = [c.strip() for c in s.strip("|").split("|")]
            table.append(cells)
            continue
        if started and not s:
            break
        if started and not s.startswith("|"):
            break
    if len(table) < 3:  # header, divider, at least one row
        return []
    return [row for row in table[2:] if row and any(row)]


def parse(path: pathlib.Path) -> tuple[list[tuple[str, str]], list[tuple[str, str]]] | None:
    """Return (globals_rows, backends_rows). Each row: (name, meaning)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    globals_rows = []
    for row in _rows_after(text, r"^###\s*Injected globals\s*$"):
        if len(row) >= 2 and row[0] and row[1]:
            name = row[0].strip("` ")
            name = re.sub(r"\(.*?\)", "", name).strip()
            behavior = row[1]
            globals_rows.append((name, behavior))
    backends_rows = []
    m = re.search(r"^##\s*Backends\s*$", text, re.M)
    if m:
        after = text[m.end():]
        fenced = re.search(r"```[a-zA-Z]*\s*\n(.*?)\n```", after, re.S)
        if fenced:
            for ln in fenced.group(1).splitlines():
                parts = ln.split()
                if len(parts) >= 2:
                    backends_rows.append((parts[0], parts[1]))
    return globals_rows, backends_rows


class CortexIngestMismatch(RuntimeError):
    """The store holds something other than what was parsed."""


def ingest(globals_rows, backends_rows, store) -> tuple[int, int]:
    for name, behavior in globals_rows:
        memory.add_pair(
            name, behavior, GLOBALS_DOMAIN, GLOBALS_TARGET,
            status="draft",
            origin=f"{ORIGIN}:injected-globals",
            reason="README §Writing a workflow → Injected globals table",
            store=store, matcher=MATCHER,
        )
    for name, cli in backends_rows:
        memory.add_pair(
            name, cli, BACKENDS_DOMAIN, BACKENDS_TARGET,
            status="draft",
            origin=f"{ORIGIN}:backends",
            reason="README §Backends — three-column verified backends list",
            store=store, matcher=MATCHER,
        )
    return len(globals_rows), len(backends_rows)


def verify_ingested(globals_rows, backends_rows, store) -> int:
    checks = []
    for name, behavior in globals_rows:
        checks.append((GLOBALS_DOMAIN, GLOBALS_TARGET, name, behavior))
    for name, cli in backends_rows:
        checks.append((BACKENDS_DOMAIN, BACKENDS_TARGET, name, cli))
    problems = []
    for dom, tgt, src, want in checks:
        want_sha = memory._sha(want)
        landed = {c["source_text"]: c["target_text"]
                  for c in store.memory_candidates(dom, tgt)
                  if str(c.get("origin", "")).startswith(ORIGIN)}
        if src not in landed:
            problems.append(f"{dom}:{src} never ingested")
            continue
        got_sha = memory._sha(landed[src])
        if got_sha != want_sha:
            problems.append(f"{dom}:{src} hash mismatch ({got_sha} != {want_sha})")
    if problems:
        raise CortexIngestMismatch(
            f"{len(problems)} ingested row(s) do not match the README:\n  "
            + "\n  ".join(problems))
    return len(checks)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--readme", default="", help="path to a cortex README.md")
    ap.add_argument("--repo", default="",
                    help="cortex checkout; resolves README.md at its root")
    ap.add_argument("--keep", default="", help="leave the store behind here")
    args = ap.parse_args()
    if not args.readme and not args.repo:
        ap.error("one of --readme or --repo is required")

    path = resolve_readme(repo=args.repo, readme=args.readme)
    if path is None:
        print(f"{RED}no cortex README.md found{OFF}")
        print(f"   {DIM}'I could not look' — refusing rather than reporting "
              f"zero rows.{OFF}")
        return 1

    parsed = parse(path)
    if parsed is None:
        print(f"{RED}README.md at {path} is not readable{OFF}")
        return 1
    globals_rows, backends_rows = parsed

    if not globals_rows and not backends_rows:
        print(f"\n{BOLD}cortex workflow surface → nestor{OFF}")
        print(f"   {AMBER}{path} holds 0 injected globals and 0 backends{OFF}")
        print(f"   {DIM}A true empty, not a failure — headings without tables.{OFF}\n")
        return 0

    work = pathlib.Path(args.keep) if args.keep else pathlib.Path(
        tempfile.mkdtemp(prefix="nestor-feed-"))
    work.mkdir(parents=True, exist_ok=True)
    cascade.set_ledger_path(str(work / "ledger.jsonl"))
    store = SqliteStore(str(work / "nestor.db"))
    store.init_db()
    store.memory_init()
    storage.set_store(store)

    print(f"\n{BOLD}cortex workflow surface → nestor{OFF}  "
          f"{DIM}read by parsing README.md{OFF}")
    print(f"   {DIM}readme: {path}{OFF}")

    g_written, b_written = ingest(globals_rows, backends_rows, store)
    print(f"   {g_written} injected global(s), {b_written} backend(s)")

    try:
        verified = verify_ingested(globals_rows, backends_rows, store)
    except CortexIngestMismatch as exc:
        print(f"\n{RED}ingest verification FAILED — refusing{OFF}")
        print(f"   {DIM}{exc}{OFF}\n")
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)
        raise
    print(f"   {GREEN}{verified} row(s) verified against the README{OFF}")
    print()
    if globals_rows:
        print(f"   {BOLD}injected globals{OFF}  {DIM}{GLOBALS_DOMAIN}→{GLOBALS_TARGET}{OFF}")
        for name, behavior in globals_rows:
            print(f"   {AMBER}~{OFF} {BOLD}{name:12}{OFF} {behavior[:96]}"
                  + ("…" if len(behavior) > 96 else ""))
    if backends_rows:
        print(f"\n   {BOLD}backends{OFF}  {DIM}{BACKENDS_DOMAIN}→{BACKENDS_TARGET}{OFF}")
        for name, cli in backends_rows:
            print(f"   {AMBER}~{OFF} {BOLD}{name:10}{OFF} → {cli}")

    sealed = sum(1 for dom, tgt in (
        (GLOBALS_DOMAIN, GLOBALS_TARGET), (BACKENDS_DOMAIN, BACKENDS_TARGET))
        for r in store.memory_candidates(dom, tgt) if r["status"] == "sealed")
    chain = (work / "ledger.jsonl")
    lines = [x for x in chain.read_text(encoding="utf-8").splitlines()
             if x.strip()] if chain.exists() else []
    print(f"\n{BOLD}what is in the store{OFF}")
    print(f"   {g_written + b_written} row(s), {AMBER}{sealed} sealed{OFF}, "
          f"{len(lines)} chain entrie(s)")
    print(f"   {DIM}Every row is a draft. Whether a global's behavior line still{OFF}")
    print(f"   {DIM}matches src/runtime.ts is a separate check — a person's job.{OFF}")

    if args.keep:
        print(f"\n   {DIM}kept: {work}{OFF}\n")
    else:
        shutil.rmtree(work, ignore_errors=True)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
