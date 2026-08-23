"""Precision/recall of the decision matcher, gated.

`bench/matcher_precision.py` adds the one metric the other benches leave implicit
— precision as a rate — and these tests turn it into a floor. They also assert
the harness *sees* the failure mode IDEAS 6.106 named: below the calibrated bar,
interrogative-stem confusables get served and precision drops. A precision gate
that couldn't fall when the matcher serves a wrong decision would gate nothing.
"""
from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "bench"))

import matcher_precision as mp


def test_precision_is_perfect_at_the_calibrated_knee():
    """At bar 0.45 everything the matcher serves is the right decision."""
    m = mp.measure(mp.load_rows(), 0.45)
    assert m["precision"] == 1.0, m
    assert m["served"] > 0
    assert m["recall"] >= 0.70, m


def test_the_matcher_ranks_the_right_decision_first_for_most():
    """rank@1 is bar-independent — the failure IDEAS 6.106 corrected is a bar
    problem, not a matcher that cannot rank."""
    m = mp.measure(mp.load_rows(), mp.BAR)
    assert m["rank1"] >= 20, m  # measured 21/24


def test_a_bar_below_the_knee_serves_confusables_and_drops_precision():
    """The failure made visible: the interrogative-stem confusables get served as
    the wrong decision below the knee, so precision falls under 1.0. If this ever
    stops holding, the gate has gone blind to the case it exists for."""
    lo = mp.measure(mp.load_rows(), 0.30)
    assert lo["wrong"] >= 1, lo
    assert lo["precision"] is not None and lo["precision"] < 1.0, lo


def test_precision_is_none_when_nothing_is_served():
    """A rate over zero served is not zero — the shipped 0.92 bar serves nothing
    on this corpus, and that reads as 'unavailable', never as 'perfect'."""
    hi = mp.measure(mp.load_rows(), 1.01)
    assert hi["served"] == 0 and hi["precision"] is None


def test_it_reuses_the_n1_scoring_not_a_reimplementation():
    """Like retrieval_quality delegating to calibrate: the score comes from
    bench_decision_n1, not a second copy written here."""
    import bench_decision_n1
    assert mp._scores_matcher is bench_decision_n1._scores_matcher


def test_the_sweep_cli_runs_clean(capsys):
    assert mp.main(["--sweep"]) == 0
    assert "rank@1" in capsys.readouterr().out
