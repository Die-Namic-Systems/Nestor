"""Gates for :func:`nestor.evidence.aggregate_provenance` (decision 0207).

The function is a promotion of ``demo/the_dispatches_audit.weakest`` into the
shipped API. Independently, ``kitchen-pudding``'s ``Provenance.aggregate``
carries the same shape in a different domain. This module locks the shared
invariants so a future refactor of either side surfaces here first, and
adversarial guards refuse the inputs the pattern's whole point rules out.

The invariants pinned:

* ``min()`` over the ordering ``assumed < fitted < measured``, matching both
  prior arts;
* monotonicity — piling ``measured`` rows onto a ``fitted`` pool never lifts
  the pool (the whole point of ``min()``-not-mean);
* empty input refused (a "no ingredients" pool is not a provenance claim,
  kitchen-pudding's rule);
* unknown state refused (a typo would grow an unqueryable taxonomy, the same
  posture :data:`nestor.evidence.EVIDENCE_KINDS` takes at attach time);
* :data:`nestor.evidence.PROVENANCE_STATES` matches the demo's ``STATES``
  tuple verbatim — a rename on either side breaks this test rather than
  drifting silently.
"""
from __future__ import annotations

import pytest

from nestor.evidence import (
    PROVENANCE_RANK,
    PROVENANCE_STATES,
    aggregate_provenance,
)


def test_states_match_the_demo_spelling_and_order():
    """The demo's STATES tuple is the intended canonical spelling. If either
    side is edited to reorder, rename, or add a state, this test surfaces
    the drift before the caller does."""
    from demo import the_dispatches_audit as demo
    assert PROVENANCE_STATES == demo.STATES, (
        "PROVENANCE_STATES has drifted from demo.STATES — one of them was "
        f"edited without the other. shipped={PROVENANCE_STATES!r}, "
        f"demo={demo.STATES!r}"
    )
    # Ordering is load-bearing (weakest first) — a swap here would silently
    # invert every downstream min().
    assert PROVENANCE_STATES[0] == "assumed"
    assert PROVENANCE_STATES[-1] == "measured"


def test_ranks_are_ordered_weakest_to_strongest():
    assert PROVENANCE_RANK["assumed"] < PROVENANCE_RANK["fitted"]
    assert PROVENANCE_RANK["fitted"] < PROVENANCE_RANK["measured"]


def test_agrees_with_the_demo_on_every_reference_case():
    """Every case the demo's weakest() was locked on must return the same
    answer from the shipped function — a promotion must be behaviorally
    identical to what it promotes, or it isn't a promotion."""
    from demo import the_dispatches_audit as demo
    for states in (
        ["measured", "measured"],
        ["measured", "fitted"],
        ["measured", "fitted", "assumed"],
        ["fitted"] + ["measured"] * 9,
        ["assumed"],
    ):
        assert aggregate_provenance(states) == demo.weakest(states), states


def test_pooling_is_min_not_average():
    """Kitchen-pudding's aggregation invariant, mirrored: a recipe with one
    assumed ingredient in nine measured is an ASSUMED recipe. Averaging or
    majority-voting would call it measured. min() cannot."""
    pool = ["assumed"] + ["measured"] * 9
    assert aggregate_provenance(pool) == "assumed"


def test_monotonicity_measured_on_fitted_never_lifts():
    """Adding measured rows to a fitted pool never lifts it — the shape
    demo.weakest was originally proved on."""
    assert aggregate_provenance(["fitted"] + ["measured"] * 9) == "fitted"
    assert aggregate_provenance(["measured"] * 9 + ["fitted"]) == "fitted"


def test_single_state_returns_itself():
    for s in PROVENANCE_STATES:
        assert aggregate_provenance([s]) == s


def test_accepts_any_iterable_not_just_list():
    assert aggregate_provenance(iter(["measured", "fitted"])) == "fitted"
    assert aggregate_provenance(s for s in ["fitted", "assumed"]) == "assumed"
    assert aggregate_provenance({"measured", "assumed"}) == "assumed"


# ── adversarial refusals ──────────────────────────────────────────────────
def test_empty_pool_refused():
    with pytest.raises(ValueError, match="empty pool"):
        aggregate_provenance([])


def test_unknown_state_refused_and_names_the_legal_set():
    with pytest.raises(ValueError, match="unknown provenance state") as exc_info:
        aggregate_provenance(["measured", "bogus"])
    # The error must name the legal set so a caller doesn't have to grep for it
    msg = str(exc_info.value)
    for legal in PROVENANCE_STATES:
        assert legal in msg


def test_case_sensitivity_is_load_bearing():
    """States are lowercase strings by spec (matching demo.STATES). A
    caller passing 'MEASURED' would be silently accepted by a case-
    insensitive comparison, but the demo's STATES tuple and every
    kitchen-pudding call use lowercase. Enforce it at the boundary."""
    with pytest.raises(ValueError, match="unknown provenance state"):
        aggregate_provenance(["MEASURED"])


def test_kinds_and_provenance_are_orthogonal_axes():
    """PROVENANCE_STATES must not overlap EVIDENCE_KINDS — kind names what
    a reference points at; provenance names how the fact was arrived at.
    A collision would let a caller confuse one taxonomy for the other."""
    from nestor.evidence import EVIDENCE_KINDS
    assert set(PROVENANCE_STATES).isdisjoint(EVIDENCE_KINDS)
