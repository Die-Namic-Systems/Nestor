"""Does a fuller sealed memory stay CORRECT?

Nestor serves a tier-1 hit verbatim, marked ``sealed``, with no review queue.
So the question that matters as the memory grows is not latency, it is:

* **false seal** — a phrase that is NOT in the memory is nonetheless served as
  a verified match. Silent wrong answer.
* **recall** — a phrase that IS in the memory, retyped by a human (case,
  punctuation, spacing, one typo), is still served. A miss is cheap: it just
  falls to tier 2 and gets reviewed.

Those two trade off against ``SEAL_THRESHOLD``, so this bench sweeps the
threshold instead of asserting one value, and does it on two corpora:
``boilerplate`` (homogeneous, worst case) and ``prose`` (diverse, real English).

Method
------
For every probe we compute the single best-scoring sealed row with the same
matcher ``memory.best_sealed`` uses, then evaluate every threshold against that
one scan. ``--verify`` checks a sample of those argmax results against the real
``memory.best_sealed`` call so the shortcut is proven faithful, not assumed.
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

THRESHOLDS = [0.80, 0.85, 0.90, 0.92, 0.94, 0.96, 0.98, 1.00]


def best_match(norm: str, rows: list[dict], matcher) -> tuple[float, str, str]:
    """(best similarity, that row's target, that row's source) — what
    ``best_sealed`` would serve. The source comes back too: without it a false
    seal can't be judged, because a probe that near-duplicates a sealed phrase
    is a different finding from one that doesn't resemble it at all."""
    best_sim, best_target, best_source = 0.0, "", ""
    for r in rows:
        sim = matcher.similarity(norm, r["source_norm"])
        if sim > best_sim:
            best_sim, best_target, best_source = sim, r["target_text"], r["source_text"]
    return round(best_sim, 3), best_target, best_source


def best_match_fast(norm: str, rows: list[dict], matcher) -> tuple[float, str, str]:
    """Identical result to :func:`best_match`, computed with far less work.

    ``difflib`` exposes two upper bounds on ``ratio()``: ``real_quick_ratio()``
    (length-based) and ``quick_ratio()`` (multiset-based), with
    ``ratio() <= quick_ratio() <= real_quick_ratio()``. A candidate whose upper
    bound cannot beat the best score so far cannot be the argmax, so its real
    ratio never needs computing — the answer is unchanged, only the cost.

    Argument order and ``autojunk`` are kept EXACTLY as ``StringMatcher`` has
    them — ``SequenceMatcher(None, probe_norm, row_norm)`` with autojunk left on.
    ``ratio()`` is not symmetric and autojunk changes results on sequences of
    200+ elements, so swapping either one silently measures a different function.
    That is why the probe is pinned as sequence *a* and the row varies as *b*,
    even though pinning the row as *b* instead would let difflib cache its b2j
    index: fidelity first, speed second.

    Only valid for :class:`StringMatcher`, whose ``similarity`` is exactly
    ``difflib`` ratio with a ``1.0`` short-circuit on equal normals; callers
    must fall back to :func:`best_match` for any other matcher. ``--equiv``
    checks the two agree, and ``--verify`` checks the winner against the real
    ``memory.best_sealed`` path.
    """
    sm = difflib.SequenceMatcher(None)
    sm.set_seq1(norm)
    best_sim, best_target, best_source = 0.0, "", ""
    for r in rows:
        cand = r["source_norm"]
        if cand == norm:                      # StringMatcher's equal-normals path
            return 1.0, r["target_text"], r["source_text"]
        sm.set_seq2(cand)
        # Upper bounds, cheapest first. Neither can be < the true ratio, so a
        # candidate failing to beat the incumbent cannot be the argmax.
        if sm.real_quick_ratio() <= best_sim or sm.quick_ratio() <= best_sim:
            continue
        sim = sm.ratio()
        if sim > best_sim:
            best_sim, best_target, best_source = sim, r["target_text"], r["source_text"]
    return round(best_sim, 3), best_target, best_source


def run_one(corpus_name: str, size: int, n_probes: int, matcher, seed: int,
            verify: int = 0, equiv_check: int = 0) -> dict:
    gen = corpora.CORPORA[corpus_name]
    # Draw ONE pool and shuffle-split it. The held-out probes must be
    # statistically exchangeable with the sealed ones: an earlier version of
    # this bench generated them from a disjoint id range, which made their
    # section numbers longer and let difflib separate them on length alone —
    # false seals collapsed to 0% for a reason that had nothing to do with
    # Nestor. Split a single pool and that artifact is gone.
    pool = list(dict.fromkeys(gen(size + n_probes * 2, seed=seed)))
    random.Random(seed + 5).shuffle(pool)
    sealed, absent = pool[:size], pool[size:size + n_probes]
    sealed_set = set(sealed)
    absent = [a for a in absent if a not in sealed_set]

    store = harness.fresh_store(":memory:")
    harness.seal_all(store, sealed, matcher=matcher)
    rows = store.memory_candidates("en", "es")

    rng = random.Random(seed + 2)
    idx = rng.sample(range(len(sealed)), min(n_probes, len(sealed)))
    retyped = [(corpora.perturb(sealed[i], rng), f"BENCH:{i}") for i in idx]

    scan = best_match_fast if isinstance(matcher, StringMatcher) else best_match

    # Prove the fast path is not quietly changing the answer, on this corpus,
    # before using it for every probe.
    equiv = None
    if equiv_check and scan is best_match_fast:
        disagreed = []
        for p in absent[:equiv_check]:
            n = matcher.normalize(p)
            slow, fast = best_match(n, rows, matcher), best_match_fast(n, rows, matcher)
            if slow != fast:
                disagreed.append({"probe": p, "slow": slow, "fast": fast})
        equiv = {"checked": min(equiv_check, len(absent)),
                 "disagreements": len(disagreed), "examples": disagreed[:3]}

    absent_scores = [scan(matcher.normalize(p), rows, matcher) for p in absent]
    retyped_scores = [(scan(matcher.normalize(p), rows, matcher), want)
                      for p, want in retyped]

    # Prove the argmax shortcut matches the real serve path at the shipped default.
    verified = None
    if verify:
        agree = 0
        for p, (sim, tgt, _) in list(zip(absent, absent_scores))[:verify]:
            hit = memory.best_sealed(p, "en", "es", store=store, matcher=matcher)
            served = hit["pair"]["target_text"] if hit else ""
            expect = tgt if sim >= memory.SEAL_THRESHOLD else ""
            agree += (served == expect)
        verified = {"checked": verify, "agreed_with_best_sealed": agree}

    sweep = []
    for t in THRESHOLDS:
        false_seals = sum(1 for sim, _, _ in absent_scores if sim >= t)
        served = [(got, want) for (sim, got, _), want in retyped_scores if sim >= t]
        correct = sum(1 for got, want in served if got == want)
        misrouted = len(served) - correct
        sweep.append({
            "threshold": t,
            "false_seal_rate": round(false_seals / max(1, len(absent_scores)), 4),
            "false_seals": false_seals,
            "recall": round(correct / max(1, len(retyped_scores)), 4),
            "misrouted": misrouted,
            "misroute_rate": round(misrouted / max(1, len(retyped_scores)), 4),
        })

    # Keep the worst offenders WITH the sealed phrase they collided with, so a
    # reader can judge each one instead of trusting the rate.
    ranked = sorted(range(len(absent_scores)), key=lambda i: -absent_scores[i][0])
    examples = [{
        "similarity": absent_scores[i][0],
        "asked": absent[i],
        "would_serve_source": absent_scores[i][2],
        "would_serve_target": absent_scores[i][1],
    } for i in ranked[:5]]

    return {
        "corpus": corpus_name, "size": size,
        "n_absent_probes": len(absent_scores), "n_retyped_probes": len(retyped_scores),
        "sweep": sweep,
        "worst_false_seals": examples,
        "absent_score_percentiles": _pcts([s for s, _, _ in absent_scores]),
        "retyped_score_percentiles": _pcts([s for (s, _, _), _ in retyped_scores]),
        "fidelity_check": verified,
        "fast_path_equivalence": equiv,
    }


def _pcts(vals: list[float]) -> dict:
    if not vals:
        return {}
    v = sorted(vals)
    at = lambda q: v[min(len(v) - 1, int(q * len(v)))]  # noqa: E731
    return {"p50": at(0.50), "p90": at(0.90), "p99": at(0.99), "max": v[-1]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, nargs="*", default=[500, 2000, 8000, 24000])
    ap.add_argument("--prose-sizes", type=int, nargs="*", default=[500, 2000, 4000])
    ap.add_argument("--probes", type=int, default=150)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--verify", type=int, default=25)
    ap.add_argument("--equiv", type=int, default=25,
                    help="probes to score BOTH ways, proving the fast path agrees")
    args = ap.parse_args()

    harness.seal_key()
    with tempfile.TemporaryDirectory() as td:
        harness.quiet_ledger(td)
        matcher = StringMatcher()
        results = []
        plan = ([("boilerplate", s) for s in args.sizes]
                + [("prose", s) for s in args.prose_sizes])
        run_id = harness.new_run_id()
        params = {"sizes": args.sizes, "prose_sizes": args.prose_sizes,
                  "probes": args.probes, "seed": args.seed,
                  "matcher": "StringMatcher", "thresholds": THRESHOLDS,
                  "shipped_seal_threshold": memory.SEAL_THRESHOLD,
                  "prose_pool": corpora.available_prose(),
                  "scan": "best_match_fast (difflib upper-bound pruning)"}
        notes = ("false_seal_rate = share of held-out (absent) probes served as a "
                 "verified tier-1 hit. recall = share of retyped sealed probes "
                 "served, routed to the correct pair. misrouted = served but "
                 "pointing at the wrong pair.")

        for i, (name, size) in enumerate(plan):
            print(f"  {name:12s} {size:>6,} pairs ...", flush=True, end="")
            r = run_one(name, size, args.probes, matcher, args.seed,
                        verify=args.verify, equiv_check=args.equiv)
            results.append(r)
            at92 = next(x for x in r["sweep"] if x["threshold"] == 0.92)
            print(f" false-seal {at92['false_seal_rate']:.1%}  "
                  f"recall {at92['recall']:.1%}  (@0.92)", flush=True)
            # Checkpoint after every row. A long bench that dies partway — the
            # first attempt at this one was killed by its own timeout — must
            # leave its completed rows on disk rather than take them with it.
            path = harness.record("accuracy", {**params, "plan_rows": len(plan)},
                                  results, notes=notes, run_id=run_id,
                                  complete=(i == len(plan) - 1))
        print(f"\n  -> {path}")


if __name__ == "__main__":
    main()
