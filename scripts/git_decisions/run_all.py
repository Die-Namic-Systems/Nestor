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
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manifest", default="data/git-decisions/manifest.json")
    ap.add_argument("--out-dir", default="data/git-decisions")
    ap.add_argument("--email", nargs="*", default=[])
    ap.add_argument("--stop-after", type=int, default=0,
                    help="run only the first N rungs (0 = all)")
    ap.add_argument("--resume", action="store_true",
                    help="skip rungs whose store already exists")
    args = ap.parse_args()

    manifest = pathlib.Path(args.manifest)
    if not manifest.is_file():
        print(f"no manifest at {manifest} — run inventory.py first", file=sys.stderr)
        return 2
    repos = json.loads(manifest.read_text(encoding="utf-8"))["repos"]
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
