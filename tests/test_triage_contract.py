"""The triage loader and types — the contract the cluster/supersede/report
modules are built against. Pins the record shape and the offline defaults so a
change to either is a deliberate, visible edit, not a silent drift.
"""
from __future__ import annotations

from conftest import ARCHIVE_DECISIONS

from nestor.triage import DEFAULT_BAR, EDGE_KINDS, Decision, load_decisions


def test_load_expands_every_pair_with_a_stable_id():
    ds = load_decisions()
    assert ds, "no decisions loaded"
    # ids are "<file-number>#<index>", sorted, unique.
    assert ds == sorted(ds, key=lambda d: d.id)
    assert len({d.id for d in ds}) == len(ds)
    assert all("#" in d.id and d.question for d in ds)


def test_consolidated_onto_is_carried_through():
    """The store's existing supersession note must survive the load — it is the
    ground truth the refutation pass is measured against."""
    ds = load_decisions(ARCHIVE_DECISIONS)
    assert any(d.consolidated_onto for d in ds), "consolidated_onto never populated"


def test_the_bar_is_the_measured_triage_knee_not_the_seal_bar():
    """Triage keys off recall (the measured all-pairs knee), never the 0.92 seal
    bar — surfacing a maybe-duplicate is the point, sealing is not. The knee is
    0.55 here: the audit measured 0.45 flooding this corpus with skeleton
    false-positives, so the default was moved to where --calibrate stops moving."""
    assert DEFAULT_BAR == 0.55
    from nestor.memory import SEAL_THRESHOLD
    assert DEFAULT_BAR < SEAL_THRESHOLD


def test_edge_kinds_are_a_subset_of_the_decision_graphs_kinds():
    from nestor.decision import EDGE_KINDS as CANONICAL
    assert set(EDGE_KINDS) <= set(CANONICAL)


def test_decision_is_frozen():
    d = load_decisions()[0]
    assert isinstance(d, Decision)
    try:
        d.question = "x"          # type: ignore[misc]
        raise AssertionError("Decision must be immutable")
    except AttributeError:
        pass
