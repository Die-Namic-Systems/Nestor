#!/usr/bin/env python3
"""Walk the manifest smallest-first and extract every repository's decisions.

    python scripts/git_decisions/run_all.py --manifest data/git-decisions/manifest.json
    python scripts/git_decisions/run_all.py --manifest … --stop-after 3
    python scripts/git_decisions/run_all.py --manifest … --resume

**Smallest first, and that is the whole point.** The manifest is ordered by how
much a person would be asked to look at. The first rung is three decisions — a
number you can read in full and say "yes, that is what I decided". If the shape
is wrong you find out there, having read everything, rather than at rung
twenty-two with 537 rows and no practical way to check. Every later rung is
judged against a shape already confirmed by eye.

``--stop-after N`` is the honest way to use that: run the first few, read them,
and only then let the rest go. ``--resume`` skips rungs whose store already
exists, so a run stopped to think can be continued without redoing work.

Each rung writes its own store. One store per repository keeps a rung's rows
separable — a bad extraction is deleted by removing one file, not by unpicking
rows from a merged database — and matches how ``data/corpus/`` already works.

Nothing here seals. Every row every rung writes is a draft.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent

#: A row leaves this status when a human decides it, so the count of rows still
#: carrying it IS the count still awaiting review.
_UNREVIEWED = "draft"


def review_state(store: pathlib.Path) -> dict:
    """What a store says about its own review, read from the rows themselves.

    **Nothing here is remembered.** A row is a draft until a human seals or
    rejects it, so the drafts remaining are exactly the rows still to look at
    — the review's place is already in the data. A separate cursor file would
    add a second account of the same fact, and a second account is a thing
    that can disagree with the first (decision 0163: do not store what the
    rows already say). It would also go stale the moment somebody reviewed a
    row in `nestor ui` without telling this script.

    Returns counts plus ``started``/``done``, or ``missing`` when no store has
    been extracted for that rung yet. An unreadable file is reported as an
    error rather than counted as zero, because zero is what "finished" looks
    like and a corrupt store must not read as a completed one.
    """
    if not store.exists():
        return {"missing": True, "total": 0, "unreviewed": 0, "decided": 0}
    try:
        con = sqlite3.connect(f"file:{store}?mode=ro", uri=True)
        rows = dict(con.execute(
            "SELECT status, COUNT(*) FROM tm_pairs GROUP BY status").fetchall())
        con.close()
    except sqlite3.DatabaseError as exc:
        return {"error": str(exc), "total": 0, "unreviewed": 0, "decided": 0}
    total = sum(rows.values())
    unreviewed = rows.get(_UNREVIEWED, 0)
    return {
        "total": total,
        "unreviewed": unreviewed,
        "decided": total - unreviewed,
        "by_status": rows,
        "started": total > unreviewed,
        "done": total > 0 and unreviewed == 0,
    }


def next_rung(ledger: list[tuple]) -> tuple | None:
    """Which rung to pick up next, and it is not simply the smallest.

    A rung somebody has already started outranks any untouched one, however
    small: a half-read store is a held context, and the cost of dropping it is
    paid again on return. Among equals, fewest rows still to review — the
    smallest-first doctrine of the extraction, applied to the reading.

    Empty and finished rungs are not candidates. Returns ``None`` when nothing
    is left, which is the honest answer for "what next" and is not the same as
    an error.
    """
    live = [row for row in ledger
            if row[1].get("unreviewed", 0) > 0 and not row[1].get("error")]
    if not live:
        return None
    return min(live, key=lambda row: (not row[1]["started"], row[1]["unreviewed"]))


def cmd_status(repos: list[dict], out_dir: pathlib.Path) -> int:
    """Print the review ledger: every rung, what is decided, what is left."""
    ledger = []
    for r in repos:
        store = out_dir / (r["name"].replace("/", "__") + ".db")
        ledger.append((r["name"], review_state(store)))

    rows = tot = und = dec = 0
    print(f"\n  review ledger — {len(ledger)} rung(s)\n")
    print(f"  {'REPOSITORY':<38} {'ROWS':>5} {'DECIDED':>8} {'LEFT':>5}  PROGRESS")
    for name, st in sorted(ledger, key=lambda x: -x[1].get("total", 0)):
        if st.get("error"):
            print(f"  {name:<38} {'':>5} {'':>8} {'':>5}  UNREADABLE — {st['error']}")
            continue
        if not st["total"]:
            continue
        rows += 1
        tot += st["total"]; und += st["unreviewed"]; dec += st["decided"]
        filled = round(20 * st["decided"] / st["total"])
        bar = "#" * filled + "." * (20 - filled)
        mark = "  done" if st["done"] else ""
        print(f"  {name:<38} {st['total']:>5} {st['decided']:>8} "
              f"{st['unreviewed']:>5}  {bar}{mark}")

    empty = len(ledger) - rows
    print(f"\n  {tot} row(s) across {rows} store(s) · {dec} decided · {und} left"
          + (f" · {empty} rung(s) hold nothing" if empty else ""))

    nxt = next_rung(ledger)
    if nxt is None:
        print("\n  Nothing is waiting. Every extracted row has been decided.\n")
        return 0
    name, st = nxt
    why = ("already started — finishing it costs less than re-reading it"
           if st["started"] else "the smallest untouched rung")
    print(f"\n  Next: {name} — {st['unreviewed']} row(s) left, {why}.")
    # Deliberately NOT --read-only: this line is for the person who seals, and
    # a read-only server refuses the seal at the API. An agent opening a store
    # to look at it still passes --read-only; that is a different errand with a
    # different flag, and printing the agent's flag here would hand the human a
    # UI whose only button does nothing.
    print(f"        nestor --db {out_dir}/{name.replace('/', '__')}.db ui\n")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manifest", default="data/git-decisions/manifest.json")
    ap.add_argument("--out-dir", default="data/git-decisions")
    ap.add_argument("--email", nargs="*", default=[])
    ap.add_argument("--stop-after", type=int, default=0,
                    help="run only the first N rungs (0 = all)")
    ap.add_argument("--resume", action="store_true",
                    help="skip rungs whose store already exists")
    ap.add_argument("--status", action="store_true",
                    help="print the review ledger and what to pick up next; "
                         "extracts nothing")
    args = ap.parse_args()

    manifest = pathlib.Path(args.manifest)
    if not manifest.is_file():
        print(f"no manifest at {manifest} — run inventory.py first", file=sys.stderr)
        return 2
    repos = json.loads(manifest.read_text(encoding="utf-8"))["repos"]
    # Before --stop-after trims anything: the ledger reports on every rung the
    # manifest knows, since "what is left to review" must not depend on a flag
    # that limits what a *run* would extract.
    if args.status:
        return cmd_status(repos, pathlib.Path(args.out_dir))
    if args.stop_after:
        repos = repos[:args.stop_after]

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n  {len(repos)} rung(s), smallest first\n")
    done = skipped = failed = 0
    totals = 0
    for i, r in enumerate(repos, 1):
        # `owner/name` is the identity; `owner__name.db` is its filename, since a
        # slash in a path would make `owner` a directory and split one rung's
        # store across two places.
        store = out_dir / (r["name"].replace("/", "__") + ".db")
        label = f"{i:>3}/{len(repos)}  {r['name']:<34}"
        if args.resume and store.exists():
            print(f"{label} skipped — store exists")
            skipped += 1
            continue
        argv = [sys.executable, str(HERE / "extract.py"),
                "--repo", r["path"], "--name", r["name"], "--out", str(store)]
        if args.email:
            argv += ["--email", *args.email]
        elif r.get("emails"):
            argv += ["--email", *r["emails"]]
        got = subprocess.run(argv, capture_output=True, text=True)
        if got.returncode != 0:
            print(f"{label} FAILED — {got.stderr.strip().splitlines()[-1:] or ['?']}")
            failed += 1
            continue
        # The extractor prints its own accounting; keep the first line, which
        # carries the count, and let the rest stay in the per-rung run.
        first = next((ln for ln in got.stdout.splitlines() if ln.strip()), "")
        n = "".join(c for c in first.split("decision")[0].split()[-1:] if c.isdigit())
        totals += int(n or 0)
        print(f"{label} {n or '0':>4} decision(s)")
        done += 1

    print(f"\n  {done} extracted · {skipped} skipped · {failed} failed"
          f"  —  {totals} decision(s), all drafts")
    print(f"  stores: {out_dir}/")
    if args.stop_after and args.stop_after < 99:
        print(f"\n  Read these before going further. Re-run with --resume and a "
              f"larger\n  --stop-after (or none) once the shape looks right.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
