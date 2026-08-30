#!/usr/bin/env python3
"""Every session log in the box, through corpus-lens, into the corpus.

    python scripts/corpus/extract_sessions.py --out data/corpus/sessions.db

Sessions are the one large body of evidence this box produces continuously and
has never been able to query. They exist as JSONL under several Claude homes, in
the vault's exports, and in archives -- thousands of turns describing how the
work actually went, none of it reachable by the anti-rediscovery instrument that
the same work keeps needing.

**This extractor never reads a session.** It runs `corpuslens`, which owns the
wall -- *"relative time is process; the absolute anchor is person"* -- and
extracts only from the report corpuslens emits. The distinction is the whole
safety argument: the report has already had absolute dates, timezones and
filenames removed and passes corpuslens' own `scan_egress` backstop before it is
written. A pipeline that parsed the JSONL itself would have to re-implement that
wall, and a second implementation of a privacy boundary is a second place for it
to be wrong.

So the rule here is: if corpuslens refuses, this refuses. Exit 3 from the lens
means a quarantined value reached the rendered report and the report was
discarded -- that root is skipped loudly and never partially salvaged.

The pin is corpuslens' HEAD, not the session directory's. The sessions are an
export, not a checkout (`provenance.commit` returns ``unknown`` for one, by
design), and what actually determines a reading is the analyzer version that
produced it. Re-run with a different lens and the numbers legitimately change;
the origin should say so.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import provenance                                                  # noqa: E402

from nestor.sqlite_store import SqliteStore                        # noqa: E402

HOME = pathlib.Path.home()

#: Where sessions accumulate. Each entry is (label, path, adapter). Roots that
#: do not exist are skipped silently -- a box without Cursor is not a fault --
#: but a root that exists and yields nothing is reported, because "no sessions
#: here" and "I could not read them" are different answers.
ROOTS: list[tuple[str, pathlib.Path, str]] = [
    ("claude-code",          HOME / ".claude" / "projects",              "claude-code"),
    ("claude-code-clean",    HOME / ".claude-clean" / "projects",        "claude-code"),
    ("claude-code-science",  HOME / ".claude-science" / "projects",      "claude-code"),
    ("vault-exports",        HOME / "sean-data-vault" / "claude-code-sessions", "claude-code"),
    ("cursor",               HOME / ".cursor",                           "cursor"),
    ("cursor-config",        HOME / ".config" / "cursor",                "cursor"),
]

LENS = HOME / "github" / "willow-memory" / "corpus-lens"

#: ``## name`` followed by a fenced json block -- the shape ``render.markdown``
#: emits, one per analyzer.
SECTION = re.compile(r"^## (\w+)\n```json\n(.*?)\n```", re.MULTILINE | re.DOTALL)


def discover(extra: list[pathlib.Path]) -> list[tuple[str, pathlib.Path, str]]:
    """Roots that exist and hold at least one ``*.jsonl``."""
    found = []
    for label, path, adapter in ROOTS + [(p.name, p, "claude-code") for p in extra]:
        if not path.is_dir():
            continue
        n = sum(1 for f in path.rglob("*.jsonl") if f.is_file())
        if n:
            found.append((label, path, adapter))
        else:
            print(f"  {label}: exists, 0 *.jsonl -- skipped")
    return found


def lens(root: pathlib.Path, adapter: str, out: pathlib.Path) -> str | None:
    """Run corpuslens over one root. ``None`` on any refusal, never partial."""
    proc = subprocess.run(
        [sys.executable, "-m", "corpuslens", "run", str(root),
         "--adapter", adapter, "--out", str(out)],
        cwd=str(LENS), capture_output=True, text=True, timeout=1800)
    if proc.returncode == 3:
        print(f"    REFUSED: the lens's egress guard rejected this report -- "
              f"a quarantined value reached it. Not salvaged.\n"
              f"    {proc.stderr.strip()}")
        return None
    if proc.returncode != 0:
        print(f"    REFUSED: corpuslens exit {proc.returncode} -- "
              f"{proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else 'no message'}")
        return None
    return out.read_text(encoding="utf-8")


def rows(label: str, report: str, path: pathlib.Path):
    """``(source, target, reason, path, anchor)`` per analyzer metric.

    The analyzer's own ``denominator`` becomes the reason, because every reading
    here is only meaningful against what it counted -- a percentage with no
    denominator is the shape this corpus refuses elsewhere.
    """
    out, skipped = [], 0
    for name, body in SECTION.findall(report):
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            skipped += 1
            continue
        denom = str(data.get("denominator", "")).strip()
        for key, value in data.items():
            if key in ("denominator", "reference", "note", "reading", "buckets"):
                continue
            if isinstance(value, (dict, list)):
                continue
            out.append((f"{label} · {name} · {key}", str(value),
                        denom or f"{name}, denominator not declared", path, name))
        for extra in ("reading", "note"):
            if isinstance(data.get(extra), str) and data[extra].strip():
                out.append((f"{label} · {name} · {extra}", data[extra].strip(),
                            denom or name, path, name))
    return out, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="data/corpus/sessions.db")
    ap.add_argument("--reports", default=None,
                    help="where the lens reports land (default: beside --out)")
    ap.add_argument("--root", action="append", default=[], type=pathlib.Path,
                    help="an extra session directory; repeatable")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not (LENS / "corpuslens").is_dir():
        print(f"error: corpus-lens is not checked out at {LENS}", file=sys.stderr)
        return 2

    out = pathlib.Path(args.out).resolve()
    reports = pathlib.Path(args.reports).resolve() if args.reports else out.parent / "session-reports"
    reports.mkdir(parents=True, exist_ok=True)

    print("discovering session roots")
    roots = discover(args.root)
    if not roots:
        print("error: no session root holds a *.jsonl file", file=sys.stderr)
        return 1

    origin = provenance.Origin("sessions", reports, __file__)
    # The sessions are an export, not a checkout. What makes a reading
    # reproducible is the analyzer that produced it, so pin to corpus-lens.
    origin.commit = provenance.commit(LENS)

    plan_rows, refused, dropped = [], 0, 0
    for label, root, adapter in roots:
        n = sum(1 for f in root.rglob("*.jsonl") if f.is_file())
        print(f"\n  {label}  ({n} *.jsonl, adapter {adapter})")
        report = lens(root, adapter, reports / f"{label}.md")
        if report is None:
            refused += 1
            continue
        got, skipped = rows(label, report, reports / f"{label}.md")
        dropped += skipped
        print(f"    {len(got)} reading(s)" + (f", {skipped} unparsable block(s)" if skipped else ""))
        plan_rows.extend(got)

    print(f"\n{len(plan_rows)} reading(s) from {len(roots) - refused}/{len(roots)} root(s)"
          + (f"; {refused} refused" if refused else "")
          + (f"; {dropped} unparsable" if dropped else ""))
    if args.dry_run:
        print("dry run -- nothing written")
        return 0
    if not plan_rows:
        print("error: nothing to write -- refusing to create an empty store", file=sys.stderr)
        return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    store = SqliteStore(str(out))
    store.memory_init()
    try:
        import common                                              # noqa: E402
        common.load(store, [("measure", plan_rows, "measure", "reading")], origin)
    finally:
        store.close()
    print(f"\n  store:   {out}\n  reports: {reports}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
