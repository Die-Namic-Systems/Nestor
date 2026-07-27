"""Does the MARGIN separate a true match from a false seal?

`bench_accuracy` shows that raising `SEAL_THRESHOLD` cannot fix false seals
without eventually costing recall, because the worst collisions score 0.97+ —
above any cutoff that still serves real matches. The failures all look like this:

    asked : the joint term triggers any joint breach under section 5386
    served: the joint term triggers any joint breach under section 756

The hypothesis (IDEAS.md §1.1): the absolute top score is a weak signal, but the
**gap between the best and second-best candidate** is a strong one. A genuine
re-typing of a sealed phrase should beat its runner-up decisively; a phrase that
merely *resembles the corpus* sits in a crowd of near-equals, so its margin
collapses.

If that holds, the serve rule becomes::

    serve tier 1  iff  top >= SEAL_THRESHOLD  and  (top - second) >= MARGIN

and it costs nothing extra — the scan already visits every row.

This bench sweeps threshold × margin and reports false-seal rate against recall
for every combination, so the hypothesis can be accepted or killed on numbers.
"""
from __future__ import annotations

import argparse
import difflib
import random
import sys
import tempfile

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from bench import corpora, harness  # noqa: E402
from nestor import memory  # noqa: E402
from nestor.matcher import StringMatcher  # noqa: E402

THRESHOLDS = [0.90, 0.92, 0.94, 0.96]
MARGINS = [0.0, 0.005, 0.01, 0.02, 0.03, 0.05, 0.10]


def top_two(norm: str, rows: list[dict], floor: float = 0.0):
    """``(top_sim, top_target, second_sim)`` — best and best-with-a-different-target.

    The runner-up must point at a *different* target: two aliases of the same
    answer agreeing is not ambiguity, it is corroboration, and counting them as
    a collapsed margin would punish exactly the corpora Nestor is built for.

    Pruning: a candidate that cannot beat the current *second* place can change
    neither slot, so its real ratio is never computed. ``floor`` seeds second
    place, which censors margins wider than ``top - floor`` — reported, and
    conservative in the direction that makes the hypothesis look WORSE, never
    better.
    """
    sm = difflib.SequenceMatcher(None)
    sm.set_seq1(norm)
    top_sim, top_tgt = 0.0, ""
    snd_sim = floor
    for r in rows:
        cand = r["source_norm"]
        sim = 1.0 if cand == norm else None
        if sim is None:
            sm.set_seq2(cand)
            if sm.real_quick_ratio() <= snd_sim or sm.quick_ratio() <= snd_sim:
                continue
            sim = sm.ratio()
        tgt = r["target_text"]
        if sim > top_sim:
            if tgt != top_tgt:
                snd_sim = max(snd_sim, top_sim)
            top_sim, top_tgt = sim, tgt
        elif tgt != top_tgt and sim > snd_sim:
            snd_sim = sim
    return round(top_sim, 4), top_tgt, round(snd_sim, 4)


def run_one(corpus: str, size: int, n_probes: int, seed: int, floor: float) -> dict:
    m = StringMatcher()
    gen = corpora.CORPORA[corpus]
    pool = list(dict.fromkeys(gen(size + n_probes * 2, seed=seed)))
    random.Random(seed + 5).shuffle(pool)
    sealed, absent = pool[:size], pool[size:size + n_probes]
    absent = [a for a in absent if a not in set(sealed)]

    store = harness.fresh_store(":memory:")
    harness.seal_all(store, sealed, matcher=m)
    rows = store.memory_candidates("en", "es")

    rng = random.Random(seed + 2)
    idx = rng.sample(range(len(sealed)), min(n_probes, len(sealed)))
    retyped = [(corpora.perturb(sealed[i], rng), f"BENCH:{i}") for i in idx]

    # (top, margin) for probes that SHOULD NOT be served ...
    bad = [(t, t - s) for t, _, s in (top_two(m.normalize(p), rows, floor)
                                      for p in absent)]
    # ... and (top, margin, correct?) for probes that SHOULD be.
    good = []
    for p, want in retyped:
        t, tgt, s = top_two(m.normalize(p), rows, floor)
        good.append((t, t - s, tgt == want))

    grid = []
    for th in THRESHOLDS:
        for mg in MARGINS:
            fs = sum(1 for t, d in bad if t >= th and d >= mg)
            rc = sum(1 for t, d, ok in good if t >= th and d >= mg and ok)
            grid.append({"threshold": th, "margin": mg,
                         "false_seal_rate": round(fs / max(1, len(bad)), 4),
                         "recall": round(rc / max(1, len(good)), 4)})

    def pcts(vals):
        if not vals:
            return {}
        v = sorted(vals)
        at = lambda q: round(v[min(len(v) - 1, int(q * len(v)))], 4)  # noqa: E731
        return {"p10": at(.10), "p50": at(.50), "p90": at(.90), "max": round(v[-1], 4)}

    # The separation the hypothesis lives or dies on: margins of would-be false
    # seals vs margins of genuine matches, among probes that clear 0.92.
    fs_margins = [d for t, d in bad if t >= 0.92]
    tm_margins = [d for t, d, ok in good if t >= 0.92 and ok]
    return {
        "corpus": corpus, "size": size, "floor": floor,
        "n_absent": len(bad), "n_retyped": len(good),
        "grid": grid,
        "false_seal_margin_pcts": pcts(fs_margins),
        "true_match_margin_pcts": pcts(tm_margins),
        "n_false_seals_at_0.92": len(fs_margins),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, nargs="*", default=[2000, 8000, 24000])
    ap.add_argument("--prose-sizes", type=int, nargs="*", default=[2000, 4000])
    ap.add_argument("--probes", type=int, default=250)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--floor", type=float, default=0.80)
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    harness.seal_key()
    with tempfile.TemporaryDirectory() as td:
        harness.quiet_ledger(td)
        plan = ([("boilerplate", s) for s in args.sizes]
                + [("prose", s) for s in args.prose_sizes])
        run_id = harness.new_run_id()
        params = {"sizes": args.sizes, "prose_sizes": args.prose_sizes,
                  "probes": args.probes, "seed": args.seed, "floor": args.floor,
                  "thresholds": THRESHOLDS, "margins": MARGINS,
                  "shipped_seal_threshold": memory.SEAL_THRESHOLD}
        notes = ("Tests IDEAS.md §1.1. margin = top - best-scoring-candidate-with-a-"
                 "different-target. A rule serves iff top >= threshold AND margin >= "
                 "margin. false_seal_rate over held-out probes, recall over retyped "
                 "sealed probes routed to the correct pair.")

        done = {}
        if args.resume:
            for prior in harness.load_runs("margin"):
                p = prior.get("params", {})
                if (p.get("probes"), p.get("seed"), p.get("floor")) != (
                        args.probes, args.seed, args.floor):
                    continue
                for m in prior.get("measurements", []):
                    done[(m["corpus"], m["size"])] = m

        results = []
        for i, (name, size) in enumerate(plan):
            if (name, size) in done:
                results.append(done[(name, size)])
                print(f"  {name:12s} {size:>6,} ... (reused)", flush=True)
            else:
                print(f"  {name:12s} {size:>6,} ...", flush=True, end="")
                r = run_one(name, size, args.probes, args.seed, args.floor)
                results.append(r)
                print(f" false-seal margins {r['false_seal_margin_pcts']}  "
                      f"true-match margins {r['true_match_margin_pcts']}", flush=True)
            path = harness.record("margin", {**params, "plan_rows": len(plan)},
                                  results, notes=notes, run_id=run_id,
                                  complete=(i == len(plan) - 1))
        print(f"\n  -> {path}")


if __name__ == "__main__":
    main()
