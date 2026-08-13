#!/usr/bin/env python3
"""Triage the local seal queue — group it, find its supersessions, print it.

    python scripts/decision_triage.py                 # read-only triage
    python scripts/decision_triage.py --bar 0.55      # a stricter bar
    python scripts/decision_triage.py --calibrate     # sweep the bar, see the knee
    python scripts/decision_triage.py --propose       # also propose edges (never seals)

The problem, in the operator's words: there are 200+ draft decisions to seal
locally, and starting oldest-first fails because many are already resolved,
superseded, or duplicated. This runs `nestor.triage.triage()` over the committed
`docs/dogfood/decisions/` corpus and prints the human-facing report — themed
groups, proposed supersede/contradict/refine edges, and the resolved-vs-open
split that tells a person which rows are still theirs to seal.

Read-only by default. `--propose` is opt-in and writes exactly one kind of row —
a *proposed* edge — into an ephemeral in-memory store; it never seals, never sets
a verifier. The whole tool proposes and confirms nothing (the covenant: you may
propose, you may not confirm). `scripts/` is not linted by CI; kept ruff-clean
anyway.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

# Running from scripts/ puts scripts/ on sys.path, not the repo root; put the
# repo root first so `import nestor...` resolves (dogfood_next_piece.py does the
# same for the same reason).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from nestor.answer import load_matcher                             # noqa: E402
from nestor.triage import DEFAULT_BAR, load_decisions, triage      # noqa: E402
from nestor.triage.report import emit_edges, render                # noqa: E402

#: The matchers triage can group with. ``string`` is the offline default the
#: 0.55 knee was measured for; ``semantic`` / ``ollama`` see paraphrase (the
#: #101 fix) but need model weights the build box could not reach — run them on a
#: host that has them, and re-``--calibrate``, because their cosine bar is on a
#: different scale (unrelated text scores 0.7-0.8, so 0.55 is far too low).
TRIAGE_MATCHERS = ("string", "semantic", "ollama")

#: The bars a `--calibrate` sweep reports at: either side of the measured triage
#: knee (0.55) so a human can see the group/edge counts move, and the 0.92 seal
#: bar at the top to show how little recall it leaves.
CALIBRATION_BARS = (0.35, 0.45, 0.55, 0.92)


def _calibrate(bars, matcher=None) -> None:
    """Run triage at several bars and tabulate how the counts change, so a human
    can pick the knee rather than trust a default. No store, no writes."""
    decisions = load_decisions()
    print(f"calibration over {len(decisions)} decisions "
          f"(pick the bar where the counts stop moving):\n")
    print(f"  {'bar':>5}  {'groups':>7}  {'edges':>7}")
    print(f"  {'-' * 5}  {'-' * 7}  {'-' * 7}")
    for bar in bars:
        report = triage(decisions=decisions, matcher=matcher, bar=bar)
        print(f"  {bar:>5.2f}  {len(report.clusters):>7}  {len(report.edges):>7}")


def _propose(report, decisions) -> None:
    """Opt-in: propose the report's edges into a throwaway in-memory store.

    Builds a `DecisionMemory` over an in-memory SQLite store, registers each
    decision as a **draft** pair under its triage id (so the edge endpoints
    resolve), then calls `emit_edges` — which proposes and only proposes. Asserts
    nothing was sealed before it returns. The store is discarded on exit; this is
    a demonstration of the sink, not a durable write.
    """
    from nestor import memory as _memory
    from nestor.decision import DecisionMemory
    from nestor.sqlite_store import SqliteStore

    store = SqliteStore(":memory:")
    store.init_db()
    store.memory_init()
    try:
        for d in decisions:
            # Each decision becomes one draft row keyed by its triage id, so the
            # edge endpoints resolve. The source is prefixed with the id because
            # the store enforces uniqueness on (source_norm, lang, lang) and many
            # decisions ask the same question — without the prefix the same-
            # question rows (exactly the ones an edge connects) would collide and
            # one endpoint would be missing. This store is a throwaway sink to
            # demonstrate propose-not-seal, not a faithful copy of the corpus.
            _memory.add_pair(
                source_text=f"{d.id}: {d.question}", target_text=d.commitment,
                source_lang="decision", target_lang="decision",
                status="draft", reason=d.why, origin=f"triage:{d.file}",
                pair_id=d.id, store=store)
        dm = DecisionMemory(store)
        rows = emit_edges(report, dm)

        sealed_pairs = store.memory_stats()["sealed"]
        sealed_edges = sum(1 for r in rows if r.get("edge_sig"))
        assert sealed_pairs == 0 and sealed_edges == 0, (
            "decision_triage proposed a sealed row — it must only propose "
            "(the covenant: you may propose, you may not confirm).")
        print(f"\nproposed {len(rows)} edge(s) into an ephemeral store; "
              f"{sealed_pairs} pairs and {sealed_edges} edges sealed (a human "
              f"seals at `nestor ui`).")
    finally:
        store.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bar", type=float, default=DEFAULT_BAR,
                    help=f"similarity bar for grouping/supersession "
                         f"(default {DEFAULT_BAR}, the measured triage knee for "
                         f"--matcher string; see --calibrate)")
    ap.add_argument("--matcher", choices=TRIAGE_MATCHERS, default="string",
                    help="how to score question similarity. 'string' is the "
                         "offline default; 'semantic'/'ollama' see paraphrase "
                         "(the #101 fix) but need model weights — run them on a "
                         "host that has them and re-calibrate (their bar scale "
                         "differs)")
    ap.add_argument("--propose", action="store_true",
                    help="also propose the report's edges into an ephemeral "
                         "store (opt-in; proposes only, never seals)")
    ap.add_argument("--calibrate", action="store_true",
                    help="sweep several bars and print how the group/edge counts "
                         "change, to find the knee")
    args = ap.parse_args(argv)

    # persist=False: a triage run must not write its embedding cache to the store.
    try:
        matcher = load_matcher(args.matcher, persist=False)
    except ValueError as exc:                 # e.g. Ollama unreachable, no fastembed
        print(f"matcher {args.matcher!r} unavailable: {exc}", file=sys.stderr)
        return 2
    if args.matcher != "string":
        print(f"# matcher={args.matcher}: the {DEFAULT_BAR} default is the string "
              f"knee; run --calibrate to find this matcher's bar.", file=sys.stderr)

    if args.calibrate:
        _calibrate(CALIBRATION_BARS, matcher)
        return 0

    decisions = load_decisions()
    report = triage(decisions=decisions, matcher=matcher, bar=args.bar)
    print(render(report, decisions))

    if args.propose:
        _propose(report, decisions)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
