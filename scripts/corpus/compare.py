#!/usr/bin/env python3
"""What the stores cannot see about each other.

    python scripts/corpus/compare.py                     # every store in data/corpus
    python scripts/corpus/compare.py --dir data/corpus --examples 8

**Why this exists.** `ConflictingDraftError` fires *within* a store. The corpus
is one store per repository, so every disagreement *between* repositories is
invisible to the machinery — and disagreement between repositories is the entire
reason for reading a chronology in order. §6.64 found Gerald described two ways
three months apart and only because a script was written by hand to look. This
is that script, made repeatable.

**The classification is the substance, not the count.** A key in two
repositories is one of three different things, and collapsing them would repeat
§6.52's mistake at corpus scale:

``restated``
    Same key, same answer, two repositories. Not a problem — but the cheapest
    kind of drift to *create*, because nothing disagrees yet and nothing ever
    warns. §6.57 measured the same effect inside one repository.

``drift``
    Same key, **same kind of claim**, different answers. This is a real
    disagreement and the thing a verification memory exists to surface.

``two kinds``
    Same key, **different kinds of claim**. Not an error: a name doing two jobs.
    §6.22 recorded that a pair has no field for this, and rung 13 produced the
    live case — an operational role and a fictional character sharing a name,
    both descriptions correct. Reported separately because calling it drift
    would be wrong, and dropping it would hide the only instance the corpus has.

**Reads exported bundles, seals nothing, writes nothing.** The stores are inputs.
A comparison that mutated them would make the next comparison unrepeatable.
"""
from __future__ import annotations

import argparse
import collections
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from nestor import memory                                        # noqa: E402
from nestor import portable                                      # noqa: E402
from nestor.sqlite_store import SqliteStore                      # noqa: E402


def normalize(text: str) -> str:
    """The product's own normalizer, so keys match the way the store matches."""
    return memory.get_matcher().normalize(text)


def read(path: pathlib.Path) -> list[dict]:
    store = SqliteStore(str(path))
    try:
        store.memory_init()
        rows = portable.export_bundle(store)["pairs"]
    finally:
        store.close()
    for row in rows:
        row["repo"] = path.stem
    return rows


def classify(group: list[dict]) -> set:
    """The labels a key earns. A key can earn more than one.

    The first version returned a single label and so hid a real disagreement:
    `Ratification` drifts *within* `term->term` and also appears as
    `decision->authority`, and reporting only "two kinds" buried the drift under
    the rarer finding. Drift is judged per kind of claim; "two kinds" is judged
    across them. They are independent questions about the same key.
    """
    out = set()
    by_kind: dict[tuple, list] = collections.defaultdict(list)
    for row in group:
        by_kind[(row["source_lang"], row["target_lang"])].append(row)
    if len(by_kind) > 1:
        out.add("two kinds")
    for rows in by_kind.values():
        if len({r["repo"] for r in rows}) < 2:
            continue
        out.add("drift" if len({normalize(r["target_text"]) for r in rows}) > 1
                else "restated")
    return out or {"restated"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", default="data/corpus")
    ap.add_argument("--examples", type=int, default=5)
    args = ap.parse_args()

    stores = sorted(pathlib.Path(args.dir).glob("*.db"))
    if not stores:
        print(f"no stores in {args.dir}")
        return 1

    rows: list[dict] = []
    print(f"{len(stores)} store(s):")
    for path in stores:
        got = read(path)
        rows.extend(got)
        print(f"  {path.stem:28} {len(got):5} row(s)")
    print(f"\n{len(rows)} row(s) total\n")

    by_key: dict[str, list[dict]] = collections.defaultdict(list)
    for row in rows:
        by_key[normalize(row["source_text"])].append(row)

    shared = {k: g for k, g in by_key.items()
              if len({r["repo"] for r in g}) > 1}
    buckets: dict[str, list] = collections.defaultdict(list)
    for key, group in shared.items():
        for label in classify(group):
            buckets[label].append((key, group))

    print(f"keys present in more than one repository: {len(shared)}")
    print("  (a key can earn more than one label, so these need not sum)")
    for name in ("drift", "two kinds", "restated"):
        print(f"  {name:12} {len(buckets[name]):5}")

    for name in ("drift", "two kinds", "restated"):
        picked = sorted(buckets[name], key=lambda kv: -len({r["repo"] for r in kv[1]}))
        if not picked:
            continue
        print(f"\n--- {name} " + "-" * 56)
        for key, group in picked[:args.examples]:
            source = group[0]["source_text"]
            print(f"\n  {source[:78]}")
            seen = set()
            for row in group:
                mark = (row["repo"], normalize(row["target_text"]))
                if mark in seen:
                    continue
                seen.add(mark)
                kind = f"{row['source_lang']}->{row['target_lang']}"
                print(f"    {row['repo']:26} [{kind}]")
                print(f"      {' '.join(row['target_text'].split())[:96]}")
    sealed = sum(1 for r in rows if r["status"] == "sealed")
    print(f"\nsealed rows across the whole corpus: {sealed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
