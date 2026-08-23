import json

import pytest
from conftest import read_ledger

from nestor.reconcile import Reconciler


def test_in_tolerance_observation_not_flagged(store):
    # A contract ceiling of $1,000,000; observed spend within 5% is fine.
    r = Reconciler(store, domain="contract", pct_tol=0.05)
    r.seal_baseline("ceiling", "$1,000,000", verifier="auditor")

    res = r.check("ceiling", "$1,030,000")   # +3%
    assert res["baseline"] == 1_000_000.0
    assert res["observed"] == 1_030_000.0
    assert res["within_tolerance"] is True
    assert res["flagged"] is False
    assert res["variation"] == pytest.approx(30_000.0)
    assert res["variation_pct"] == pytest.approx(0.03)


def test_out_of_tolerance_observation_flagged_with_variation(store):
    r = Reconciler(store, domain="contract", pct_tol=0.05)
    r.seal_baseline("ceiling", 1_000_000)

    res = r.check("ceiling", 1_250_000)      # +25%, well outside 5%
    assert res["within_tolerance"] is False
    assert res["flagged"] is True
    assert res["variation"] == pytest.approx(250_000.0)
    assert res["variation_pct"] == pytest.approx(0.25)


def test_absolute_tolerance_band(store):
    r = Reconciler(store, domain="reading", abs_tol=2.0, pct_tol=0.0)
    r.seal_baseline("temp", 98.6)
    assert r.check("temp", 100.0)["flagged"] is False   # within +/- 2
    assert r.check("temp", 102.0)["flagged"] is True    # outside


def test_unknown_label_has_no_baseline(store):
    r = Reconciler(store, domain="contract")
    res = r.check("never-sealed", 500)
    assert res["baseline"] is None
    assert res["flagged"] is False
    assert res["within_tolerance"] is False


def test_reconcile_is_ledgered(store):
    r = Reconciler(store, domain="contract", pct_tol=0.05)
    r.seal_baseline("ceiling", 1_000_000)
    r.check("ceiling", 1_250_000)
    kinds = [e["kind"] for e in read_ledger()]
    assert "baseline_seal" in kinds
    assert "reconcile" in kinds
    flagged = next(e for e in read_ledger() if e["kind"] == "reconcile")
    assert flagged["flagged"] is True


# --- one baseline per label ------------------------------------------------
#
# The hole these pin: `add_pair`'s conflicting-seal guard keys on the normalized
# source, and under a NumericMatcher every figure is its own key — so a second
# baseline for a label was an insert, not an overwrite, and nothing raised.
# Both stayed sealed and `check` scored an observation against whichever it sat
# nearest, which is the one figure guaranteed to excuse it.

def test_a_second_verifiers_baseline_is_a_conflict_not_an_addition(store):
    r = Reconciler(store, domain="contract", pct_tol=0.05)
    r.seal_baseline("ceiling", "$1,000,000", verifier="auditor")

    with pytest.raises(Exception, match="does not replace the first"):
        r.seal_baseline("ceiling", "$1,250,000", verifier="someone-else")

    assert [b["target_text"] for b in r.sealed_baselines("ceiling")] == ["$1,000,000"]
    # And the deviation the second figure would have excused is still flagged.
    assert r.check("ceiling", "$1,240,000")["flagged"] is True


def test_a_self_correction_replaces_the_baseline_rather_than_joining_it(store):
    r = Reconciler(store, domain="contract", pct_tol=0.05)
    r.seal_baseline("ceiling", "$1,000,000", verifier="auditor")
    r.seal_baseline("ceiling", "$1,250,000", verifier="auditor")

    assert [b["target_text"] for b in r.sealed_baselines("ceiling")] == ["$1,250,000"]
    res = r.check("ceiling", "$1,240,000")
    assert res["baseline"] == 1_250_000.0 and res["ambiguous"] is False
    # The retired figure is not consultable, and the replacement is auditable.
    assert r.check("ceiling", "$1,000,000")["flagged"] is True
    replaced = [e for e in read_ledger() if e["kind"] == "baseline_replaced"]
    assert replaced and replaced[0]["replaced_baseline"] == "$1,000,000"
    assert replaced[0]["retired"] is True


def test_an_override_is_available_but_explicit(store):
    r = Reconciler(store, domain="contract", pct_tol=0.05)
    r.seal_baseline("ceiling", "$1,000,000", verifier="auditor")
    r.seal_baseline("ceiling", "$1,250,000", verifier="someone-else",
                    override_conflict=True)
    assert [b["target_text"] for b in r.sealed_baselines("ceiling")] == ["$1,250,000"]


def test_a_store_that_cannot_retire_says_so_and_check_reports_ambiguity(store, recwarn):
    """Degrading is allowed; degrading silently is not."""
    class _NoCuration(type(store)):
        memory_unseal = None

    s = _NoCuration(":memory:")
    s.init_db()
    r = Reconciler(s, domain="contract", pct_tol=0.05)
    r.seal_baseline("ceiling", "$5,000,000", verifier="auditor")
    with pytest.warns(RuntimeWarning, match="stay sealed"):
        r.seal_baseline("ceiling", "$1,000,000", verifier="auditor")

    # $4.9M sits inside 5% of the SUPERSEDED ceiling and 390% outside the
    # standing one. Scoring by similarity picked the first and passed it.
    res = r.check("ceiling", "$4,900,000")
    assert res["ambiguous"] is True and res["baseline_count"] == 2
    assert res["baseline"] == 1_000_000.0, "the newest baseline, not the nearest"
    assert res["flagged"] is True


# --- the figure that was actually compared (IDEAS 1.9) ----------------------
#
# `parse` searches for a number rather than requiring one, so a typo produces a
# real figure rather than a refusal. The failure direction is safe; the silence
# was not.

def test_a_partially_read_observation_says_so(store):
    r = Reconciler(store, domain="contract", pct_tol=0.05)
    r.seal_baseline("ceiling", "$1,000,000", verifier="auditor")

    res = r.check("ceiling", "$1,00o,000")      # one typo: a letter o for a zero
    assert res["observed"] == 100.0, "documented behavior: the first number found"
    assert res["observed_partial"] is True
    assert res["observed_text"] == "$1,00o,000"
    assert res["flagged"] is True               # the safe direction, unchanged


def test_a_date_is_a_partial_read_too(store):
    r = Reconciler(store, domain="ledger", pct_tol=0.05)
    r.seal_baseline("closing", 12, verifier="auditor")

    res = r.check("closing", "12/31/2024")
    # It compares as 12 and therefore passes, which is precisely the case the
    # flag exists for: a clean pass on a figure nobody meant to state.
    assert res["observed"] == 12.0 and res["flagged"] is False
    assert res["observed_partial"] is True


def test_a_currency_or_unit_suffix_is_not_a_partial_read(store):
    r = Reconciler(store, domain="contract", pct_tol=0.05)
    r.seal_baseline("ceiling", "$1,000,000 USD", verifier="auditor")

    res = r.check("ceiling", "$1,000,000 USD")
    assert res["observed"] == 1_000_000.0
    assert res["observed_partial"] is False, "USD is decoration, not a dropped digit"
    assert res["baseline_partial"] is False
    assert res["within_tolerance"] is True


def test_sealing_a_half_read_baseline_warns_and_is_reported(store):
    r = Reconciler(store, domain="contract", pct_tol=0.05)
    with pytest.warns(RuntimeWarning, match="was not part of the number"):
        out = r.seal_baseline("ceiling", "$1,00o,000", verifier="auditor")
    assert out["baseline"] == 100.0 and out["baseline_partial"] is True
    assert out["baseline_text"] == "$1,00o,000"

    # And every later check carries it, so the discrepancy is not only visible
    # at the moment of sealing — which is the moment nobody re-reads.
    res = r.check("ceiling", 100)
    assert res["baseline_partial"] is True
    assert res["baseline_text"] == "$1,00o,000"


def test_the_ledger_records_that_a_figure_was_half_read(store):
    r = Reconciler(store, domain="contract", pct_tol=0.05)
    r.seal_baseline("ceiling", "$1,000,000", verifier="auditor")
    r.check("ceiling", "$1,00o,000")

    entry = [e for e in read_ledger() if e["kind"] == "reconcile"][-1]
    assert entry["observed_partial"] is True
    assert entry["baseline_partial"] is False
    # The raw strings stay out of the trail: nestor.frank mirrors entries
    # verbatim into somebody else's ledger.
    assert "1,00o,000" not in json.dumps(entry)


# -- the two denominators, and the number that reconciles them ---------------
#
# `variation_pct` is baseline-relative; the verdict's proportional leg is a
# fraction of the larger magnitude. Against a rising observation those differ,
# so a passing check can print a percentage above `pct_tol`. That is not a bug
# in either number — it is a bug in reporting only one of them.

def test_a_passing_check_can_report_a_percentage_above_pct_tol(store):
    r = Reconciler(store, domain="q", pct_tol=0.05)
    r.seal_baseline("revenue", 3.9, verifier="auditor")

    res = r.check("revenue", 4.1)
    # Reads as over a 5% tolerance...
    assert res["variation_pct"] == pytest.approx(0.051282, rel=1e-4)
    assert res["variation_pct"] > 0.05
    # ...and passes, because the slack is measured against the larger value.
    assert res["within_tolerance"] is True
    # The slack itself is what makes that legible rather than contradictory.
    assert res["tolerance_abs"] == pytest.approx(0.205)
    assert res["variation"] <= res["tolerance_abs"]


def test_tolerance_abs_is_the_number_the_verdict_turns_on(store):
    # The invariant that lets a reader check a verdict with one comparison and
    # no knowledge of which denominator was used.
    r = Reconciler(store, domain="q", pct_tol=0.05, abs_tol=0.01)
    r.seal_baseline("revenue", 100.0, verifier="auditor")

    for observed in (100.0, 101.0, 104.9, 105.0, 105.2, 105.3, 110.0, 0.0, 250.0):
        res = r.check("revenue", observed)
        assert res["within_tolerance"] == (res["variation"] <= res["tolerance_abs"]), observed


def test_the_band_where_the_percentage_and_the_verdict_disagree_is_bounded(store):
    # Ceiling is pct/(1-pct): above it, no passing check can print a percentage
    # that high. Guards against the band silently widening.
    pct = 0.05
    r = Reconciler(store, domain="q", pct_tol=pct)
    r.seal_baseline("revenue", 100.0, verifier="auditor")

    ceiling = pct / (1 - pct)               # 0.052631...
    assert r.check("revenue", 105.2)["within_tolerance"] is True
    just_over = r.check("revenue", 105.5)
    assert just_over["within_tolerance"] is False
    assert just_over["variation_pct"] > ceiling


def test_no_comparison_means_no_tolerance_rather_than_a_tolerance_of_zero(store):
    # A tolerance of 0.0 would claim "zero slack was allowed" — a verdict about
    # a comparison that never happened. The absence has to stay an absence.
    r = Reconciler(store, domain="q", pct_tol=0.05)
    r.seal_baseline("revenue", 100.0, verifier="auditor")

    assert r.check("nothing-sealed-here", 5)["tolerance_abs"] is None
    unreadable = r.check("revenue", "abc")
    assert unreadable["observed"] is None
    assert unreadable["tolerance_abs"] is None
