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
