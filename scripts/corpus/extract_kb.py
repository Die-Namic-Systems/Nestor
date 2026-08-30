#!/usr/bin/env python3
"""The knowledge base — only what the box itself marks open.

    python scripts/corpus/extract_kb.py --db willow_20 --name kb --out data/corpus/kb.db

`willow_20.knowledge` holds 21,914 rows. **10,975 are marked `sensitivity =
'sensitive'` and this extractor never reads them.** The filter is not a judgement
made here: the column exists because the box already made the call, row by row,
and the only correct behaviour is to obey a marking rather than re-derive one.

A row with a NULL sensitivity is treated as sensitive. Absent is not open — the
same rule the corpus applies to a missing checkout, which is refused rather than
assumed retired.

`tier` travels as the reason, because a `frontier` claim and a `canonical` one
carry different weight and a reader who cannot see which is which is being told
less than the store knows. `superseded` and `contested` rows are kept
deliberately: a superseded claim is evidence of what was believed and when, and
dropping it would make the corpus tidier and less honest.

Everything lands as draft. A KB row is willow's working knowledge, not a
verified answer, and moving it into a lane whose whole posture is
"attributed, authority-free" must not launder it into one.
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import provenance                                                  # noqa: E402
import common                                                      # noqa: E402

from nestor.sqlite_store import SqliteStore                        # noqa: E402

SEP = "\x1f"
QUERY = f"""
SELECT id, COALESCE(title,''), COALESCE(summary, substring(content::text from 1 for 800), ''),
       COALESCE(tier::text,'untiered'), COALESCE(category,''), COALESCE(domain,'')
FROM knowledge
WHERE sensitivity = 'open'
  AND COALESCE(title,'') <> '' AND COALESCE(summary, content::text, '') <> ''
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default="willow_20")
    ap.add_argument("--name", default="kb")
    ap.add_argument("--out", required=True)
    ap.add_argument("--anchor-repo", default=".")
    args = ap.parse_args()

    sql = " ".join(QUERY.split())
    try:
        p = subprocess.run(["psql", "-d", args.db, "-tA", "-F", SEP, "-c", sql],
                           capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"error: psql failed: {e}", file=sys.stderr)
        return 1
    if p.returncode != 0:
        print(f"error: psql exit {p.returncode}: {p.stderr.strip().splitlines()[-1] if p.stderr.strip() else ''}",
              file=sys.stderr)
        return 1

    root = pathlib.Path(args.anchor_repo).resolve()
    rows, dropped = [], 0
    for line in p.stdout.splitlines():
        parts = line.split(SEP)
        if len(parts) < 6:
            dropped += 1
            continue
        rid, title, body, tier, category, domain = parts[:6]
        title = " ".join(title.split())
        body = " ".join(body.split())
        if not (title and body):
            dropped += 1
            continue
        where = " · ".join(x for x in (category, domain) if x) or "uncategorised"
        rows.append((title[:400], body[:1500], f"tier {tier}; {where}", root, rid))

    print(f"  {len(rows)} open row(s)" + (f", {dropped} dropped" if dropped else "")
          + "  (sensitive rows never read)")
    if not rows:
        print("error: no open rows — refusing to write an empty store", file=sys.stderr)
        return 1

    out = pathlib.Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    origin = provenance.Origin(args.name, root, __file__)
    store = SqliteStore(str(out))
    store.memory_init()
    try:
        common.load(store, [("kb", rows, "title", "knowledge")], origin)
    finally:
        store.close()
    print(f"  store: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
