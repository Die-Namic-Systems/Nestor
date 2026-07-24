import pytest

from nestor.reconcile import Reconciler

from conftest import read_ledger


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
    flagged = [e for e in read_ledger() if e["kind"] == "reconcile"][0]
    assert flagged["flagged"] is True
