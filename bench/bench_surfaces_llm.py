#!/usr/bin/env python3
"""Stage 2 — surfaces authored by a model that never saw the probe distribution.

IDEAS.md §3.4. Stage 1 (`bench_surfaces.py`) sealed surfaces straight from
`corpora.aliased`, so the generator had perfect knowledge of the probe families.
That is a ceiling, not a forecast. Here a model sees **only the canonical form**
and authors the alternates; everything else — meanings, probes, noise, seed,
thresholds — is held identical, so the difference between arms is the model.

Both arms are built in **one process against one probe list**, rather than
reconstructing stage 1's RNG sequence, because comparability that depends on
replaying a random stream is comparability waiting to break silently.

What this measures, and what it does not
----------------------------------------
`corpora.aliased` is synthetic, so a model given `jarvale robotics group 41` can
only **derive** alternates by manipulating the string. It cannot **know** them.
Four of the generator's five families are derivable; `legacy` is a rename
(`caldwell bros 41`) with no relationship to the canonical at all, so it is
unwinnable by construction — roughly a fifth of the probe distribution.

Real aliasing is mostly the knowledge case: `Amazon` → `AWS` / `AMZN` requires
knowing the world. A model has that and cannot have it here. So a stage-2 number
from this bench is a **lower bound** on real-world alias quality, and the
per-family breakdown below is the part worth reading — it separates "the model
could not derive this" from "the model derived it and it did not help."

Provenance of the authored surfaces
-----------------------------------
`bench/results/authored_surfaces.json`, with the authoring note recorded in it.
The first authoring pass was **discarded**: one agent read the stage-2 prediction
document, which was sitting in the output directory, and self-reported it. All
three were re-run against a tree with the prediction removed. The discard is
recorded rather than the contaminated run being quietly kept.

Usage
-----
    python bench/bench_surfaces_llm.py --probes 250
"""
from __future__ import annotations

import argparse
import json
import pathlib
import random
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from bench import corpora, harness  # noqa: E402
from bench.bench_accuracy import THRESHOLDS, best_match_fast  # noqa: E402
from bench.bench_surfaces import FLOOR, _seal_meaning  # noqa: E402
from nestor import memory  # noqa: E402
from nestor.matcher import StringMatcher  # noqa: E402

AUTHORED = pathlib.Path(__file__).parent / "results" / "authored_surfaces.json"
FAMILIES = ("full", "short", "acronym", "ticker", "legacy")


def score_arm(label: str, surface_sets: list[list[str]], k: int,
              probes: list[tuple[str, str, int]], absent: list[str],
              matcher) -> dict:
    """Seal `k` surfaces per meaning, score the shared probes."""
    store = harness.fresh_store()
    intended = 0
    for i, surfaces in enumerate(surface_sets):
        _seal_meaning(store, surfaces[:k], f"BENCH:{i}", matcher)
        intended += len(surfaces[:k])
    actual = memory.stats(store=store)["sealed"]
    rows = store.memory_candidates("en", "es")

    scored = [(*best_match_fast(p, rows, matcher, FLOOR), expect, fam)
              for p, expect, fam in probes]
    absent_scored = [best_match_fast(p, rows, matcher, FLOOR)
                     for p in absent]

    out = {"arm": label, "surfaces_per_meaning": k, "meanings": len(surface_sets),
           "rows_intended": intended, "rows_sealed": actual,
           "rows_lost_to_duplicate": intended - actual,
           "n_probes": len(scored), "n_absent": len(absent_scored),
           "by_threshold": [], "by_family": {}}

    for t in THRESHOLDS:
        hit = sum(1 for sim, tgt, _, expect, _ in scored if sim >= t and tgt == expect)
        fs = sum(1 for sim, _, _ in absent_scored if sim >= t)
        out["by_threshold"].append({
            "threshold": t,
            "recall": round(hit / max(1, len(scored)), 4),
            "false_seal_rate": round(fs / max(1, len(absent_scored)), 4),
        })

    # Per-family recall at the shipped default. This is the diagnostic that
    # separates "could not derive it" from "derived it and it did not help".
    for fi, fname in enumerate(FAMILIES):
        fam = [s for s in scored if s[4] == fi]
        if not fam:
            continue
        hit = sum(1 for sim, tgt, _, expect, _ in fam if sim >= 0.92 and tgt == expect)
        out["by_family"][fname] = {"n": len(fam), "recall@0.92": round(hit / len(fam), 4)}
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--probes", type=int, default=250)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--surfaces", default="3,5")
    args = ap.parse_args()

    if not AUTHORED.exists():
        sys.exit(f"missing {AUTHORED} — author surfaces first (see module docstring)")
    doc = json.loads(AUTHORED.read_text())
    authored = doc["surfaces"]

    harness.quiet_ledger(tempfile.mkdtemp())
    harness.seal_key("bench-key")
    matcher = StringMatcher()

    pool = corpora.aliased(1500, seed=args.seed)
    meanings = [m for m in pool if m[0] in authored]
    absent_meanings = pool[len(meanings):len(meanings) + args.probes]

    # ONE probe list, shared by every arm. Family drawn uniformly across the
    # generator's five families — the query distribution the model was never
    # shown — then roughened with the same aliased_query noise stage 1 used.
    rng = random.Random(args.seed)
    probes = []
    for i, m in enumerate(meanings):
        fam = rng.randrange(len(m))
        probes.append((corpora.aliased_query(m[fam], rng), f"BENCH:{i}", fam))
    absent = [corpora.aliased_query(m[rng.randrange(len(m))], rng)
              for m in absent_meanings]

    gen_sets = meanings
    llm_sets = [[m[0]] + list(authored[m[0]]) for m in meanings]

    print(f"meanings: {len(meanings)}   probes: {len(probes)}   absent: {len(absent)}")
    print(f"probe families are the generator's; the model saw only family 0 "
          f"({FAMILIES[0]})\n")

    results = []
    for k in [int(x) for x in args.surfaces.split(",")]:
        for label, sets in (("generator (stage 1)", gen_sets), ("model-authored (stage 2)", llm_sets)):
            r = score_arm(label, sets, k, probes, absent, matcher)
            results.append(r)
            at92 = next(x for x in r["by_threshold"] if x["threshold"] == 0.92)
            at96 = next(x for x in r["by_threshold"] if x["threshold"] == 0.96)
            print(f"K={k}  {label:26s} rows={r['rows_sealed']:5d} "
                  f"(dup-lost {r['rows_lost_to_duplicate']:3d})  "
                  f"recall@.92={at92['recall']:.3f} fs={at92['false_seal_rate']:.3f}  "
                  f"recall@.96={at96['recall']:.3f} fs={at96['false_seal_rate']:.3f}")
        print()

    print("per-family recall @0.92 (K=5) — the model never saw families 1-4:")
    for r in results:
        if r["surfaces_per_meaning"] != 5:
            continue
        fams = "  ".join(f"{k}={v['recall@0.92']:.2f}(n={v['n']})"
                         for k, v in r["by_family"].items())
        print(f"  {r['arm']:26s} {fams}")

    path = harness.record(
        "surfaces_llm",
        {"probes": args.probes, "seed": args.seed, "meanings": len(meanings),
         "surfaces": args.surfaces, "thresholds": THRESHOLDS,
         "authoring": doc.get("authored_by"), "prompt_note": doc.get("prompt_note")},
        results,
        notes=("Stage 2 of IDEAS.md 3.4. Both arms share one probe list; only the "
               "source of the sealed surfaces differs. The model saw ONLY the "
               "canonical form (family 0) and never the probe distribution. "
               "aliased is synthetic, so this measures DERIVATION not KNOWLEDGE: "
               "the 'legacy' family is a rename with no derivable relationship to "
               "the canonical and is unwinnable by construction, so stage 2 here "
               "is a LOWER bound on real-world alias quality. Read by_family."),
    )
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
