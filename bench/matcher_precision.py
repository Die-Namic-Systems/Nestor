#!/usr/bin/env python3
"""Precision and recall for the decision matcher — the rate the gate turns on.

    python bench/matcher_precision.py            # precision/recall at the knee
    python bench/matcher_precision.py --sweep    # the trade-off across a bar ladder

The house already measures most of this. ``bench_decision_n1.py`` reports rank@1,
recall, and a wrong-key *count* across a bar sweep; ``retrieval_quality.py`` the
verbatim floor and compression recall; ``nestor.calibrate`` the false-serve half.
What none of them names is **precision as a rate** — of the probes the matcher
*would serve* at a bar (its top candidate scores at/above it), the fraction whose
top is the right decision. That is the number the serve gate actually turns on:
the product's whole claim is that it does not serve a near-miss as verified, and
precision is how much that claim is worth at a given bar.

So this does not re-score anything — it imports ``bench_decision_n1``'s corpus
loader and scorer and adds the one derived metric, the same way
``retrieval_quality`` delegates collisions to ``calibrate`` rather than
re-scanning.

**What the numbers say** (StringMatcher, the committed N1 corpus): rank@1 is
21/24 — the correct decision is the top match for all but three probes, and those
three are the interrogative-stem confusables IDEAS 6.106 named. At the calibrated
knee (bar 0.45) precision is 1.0 and recall 0.75: everything served is right.
Below ~0.40 the three confusables start being served, and precision falls — which
is the mis-set-bar failure made visible, not a matcher that cannot rank.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))   # repo root, for nestor
sys.path.insert(0, str(HERE))          # bench dir, for bench_decision_n1

from bench_decision_n1 import _build_matcher, _load, _scores_matcher  # noqa: E402

CORPUS = HERE / "corpus_decision_n1"
#: The calibrated clean knee from ``bench_decision_n1 --sweep``, not the shipped
#: 0.92 — at 0.92 the matcher serves nothing on this corpus (recall 0).
BAR = 0.45
#: The bars the sweep walks, high to low.
LADDER = (0.92, 0.60, 0.45, 0.35, 0.30, 0.20)


def _rows(corpus, probes, matcher) -> list[tuple[int, int, float]]:
    """``(true_id, top_id, top_score)`` per probe — its top candidate and score.

    Ties broken by candidate id so the ordering is deterministic, matching
    ``bench_decision_n1``'s own tie-break shape."""
    ids = list(corpus)
    rows: list[tuple[int, int, float]] = []
    for k in ids:
        if k not in probes:
            continue
        scored = sorted(
            ((_scores_matcher(matcher, probes[k], corpus[c]["question"]), c) for c in ids),
            key=lambda t: (-t[0], t[1]))
        top_score, top_id = scored[0]
        rows.append((k, top_id, top_score))
    return rows


def load_rows(corpus_dir: pathlib.Path = CORPUS, matcher_name: str = "string"):
    corpus, probes = _load(corpus_dir)
    return _rows(corpus, probes, _build_matcher(matcher_name))


def measure(rows: list[tuple[int, int, float]], bar: float) -> dict:
    """Precision/recall of the serve-the-top policy at ``bar``.

    * **served** — probes whose top candidate scores ``>= bar`` (would serve).
    * **precision** — of those, the fraction whose top is the right decision;
      ``None`` when nothing is served (a rate over zero is not zero).
    * **recall** — of all probes, the fraction whose right decision is served.
    * **rank1** — bar-independent: the top match is the right decision.
    """
    n = len(rows)
    served = [r for r in rows if r[2] >= bar]
    correct = [r for r in served if r[1] == r[0]]
    precision = (len(correct) / len(served)) if served else None
    return {"n": n, "bar": bar, "served": len(served), "correct": len(correct),
            "wrong": len(served) - len(correct), "precision": precision,
            "recall": (len(correct) / n) if n else 0.0,
            "rank1": sum(1 for k, ti, _s in rows if ti == k)}


def _fmt(m: dict) -> str:
    p = "  n/a" if m["precision"] is None else f"{m['precision']:.3f}"
    return (f"  bar {m['bar']:>4}  served {m['served']:>2}/{m['n']}  "
            f"precision {p}  recall {m['recall']:.3f}  wrong {m['wrong']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--matcher", default="string", help="string|token|jaccard")
    ap.add_argument("--bar", type=float, default=BAR)
    ap.add_argument("--sweep", action="store_true", help="walk the bar ladder")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    rows = load_rows(matcher_name=args.matcher)
    if args.sweep:
        curve = [measure(rows, b) for b in LADDER]
        if args.json:
            print(json.dumps({"matcher": args.matcher, "sweep": curve}))
        else:
            print(f"matcher {args.matcher}: rank@1 {curve[0]['rank1']}/{curve[0]['n']} "
                  f"(bar-independent)")
            for m in curve:
                print(_fmt(m))
        return 0

    m = measure(rows, args.bar)
    print(json.dumps(m) if args.json
          else f"matcher {args.matcher}: rank@1 {m['rank1']}/{m['n']}\n{_fmt(m)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
