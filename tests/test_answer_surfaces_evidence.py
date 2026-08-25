"""#163 — cascade metadata and check output surface `evidence_count`.

The evidence subsystem was write-only through the cascade / check paths: a
pair with three institutional references produced a passage byte-identical to
one with zero. Decision 0142 explicitly kept evidence and seal state
orthogonal — evidence must not gate serving — but a curator or consumer
reading the cascade should not have to run `evidence for <pair>` to see that
the sealed answer they got rests on nothing.

These tests hold the visibility fix down. They do not assert any change to
what serves: the *same* pair serves with 0 evidence as with 3. Only the
metadata differs.

Split against the unfixed answer.py: without `_enrich_with_evidence_count`,
`ask()` returns a passage meta with no `evidence_count` key; without the
`_evidence_count` helper wired into `baselines[]`, `check()` returns a
baseline row with no `evidence_count` key. Both tests fail closed on the
missing key.
"""
from __future__ import annotations

import os

import pytest

from nestor import answer, cascade, evidence, memory, reconcile, storage
from nestor.sqlite_store import SqliteStore


@pytest.fixture()
def store(tmp_path, seal_key):
    os.environ["NESTOR_SEAL_KEY"] = "test-key"
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    s = SqliteStore(":memory:")
    s.init_db()
    s.memory_init()
    storage.set_store(s)
    return s


# --- ask / cascade ---------------------------------------------------------


def test_ask_surfaces_evidence_count_on_a_sealed_hit(store):
    pair = memory.add_pair(
        "speed of light", "299792458 m/s", "value", "value",
        status="sealed", verifier="rita", store=store)
    for locator in ("BIPM 2019", "NIST 2020", "CGPM 2018"):
        evidence.attach(pair["id"], kind="document", locator=locator,
                        reason="SI redefinition", attached_by="rita", store=store)

    res = answer.ask(store, "speed of light", "value", "value")
    meta = res["passage"]["meta"]

    assert meta["pair_id"] == pair["id"]
    assert meta["evidence_count"] == 3


def test_ask_reports_zero_evidence_count_on_a_sealed_hit_without_evidence(store):
    memory.add_pair("greeting", "hola", "value", "value",
                    status="sealed", verifier="rita", store=store)

    res = answer.ask(store, "greeting", "value", "value")
    meta = res["passage"]["meta"]

    assert meta["evidence_count"] == 0, (
        "an unevidenced sealed row must still report a count — 0 is a fact, "
        "the key being absent is what the issue is filed about")


def test_ask_omits_evidence_count_on_a_pending_passage(store):
    # nothing sealed, so the cascade returns pending with no pair_id
    res = answer.ask(store, "nobody has verified this", "value", "value")
    meta = res["passage"]["meta"]

    # No pair_id → no evidence_count. A pending passage carries no pair the
    # count could belong to; the field being absent is the honest answer.
    assert "pair_id" not in meta
    assert "evidence_count" not in meta


# --- check ------------------------------------------------------------------


def test_check_surfaces_evidence_count_at_top_and_per_baseline(store):
    rc = reconcile.Reconciler(store, domain="contract", pct_tol=0.05)
    rc.seal_baseline("ceiling", "$1,000,000", verifier="auditor")
    baseline = rc.sealed_baselines("ceiling")[0]
    for locator in ("signed contract v3", "counterparty acknowledgement"):
        evidence.attach(baseline["id"], kind="document", locator=locator,
                        reason="original", attached_by="auditor", store=store)

    result = answer.check(store, "ceiling", "$1,020,000",
                          domain="contract", pct_tol=0.05)

    assert result["baselines"][0]["evidence_count"] == 2
    assert result["evidence_count"] == 2


def test_check_reports_zero_when_the_baseline_has_no_evidence(store):
    rc = reconcile.Reconciler(store, domain="contract", pct_tol=0.05)
    rc.seal_baseline("floor", "$500,000", verifier="auditor")

    result = answer.check(store, "floor", "$500,000",
                          domain="contract", pct_tol=0.05)

    assert result["baselines"][0]["evidence_count"] == 0
    assert result["evidence_count"] == 0


# NOTE: the `len(baselines_raw) == 1` guard in `answer.check` protects
# against a >1-baseline state that the normal API refuses to create
# (`Reconciler.seal_baseline` raises `ConflictingSealError`, and
# `memory.add_pair` with `override_conflict=True` REPLACES the sealed row
# rather than adding a sibling). The guard is defensive — for hand-edited
# stores, corrupt imports, or future callers — and its else-branch is
# unreachable through the shipped write paths. The tests above pin the 0-
# and 1-baseline cases; the 2+ case would need direct SQL manipulation to
# construct, which is more machinery than the branch earns.


def test_check_reports_no_baseline_carries_no_top_evidence_count(store):
    """A check against a label with no sealed baseline yields `baselines=[]`
    and no ambiguity — but also no winner, so no top-level count."""
    result = answer.check(store, "unset-label", "$100",
                          domain="contract", pct_tol=0.05)
    assert result["baseline"] is None
    assert result["baselines"] == []
    assert "evidence_count" not in result


# --- the invariant the issue explicitly keeps ------------------------------


def test_evidence_visibility_does_not_change_serving(store):
    """The whole point of #163's design: evidence is *visible*, not
    *governing*. A pair with 3 references and a pair with 0 references
    must serve identically — same `state`, `verified`, `confidence`.
    """
    memory.add_pair("phrase without refs", "answer A", "value", "value",
                    status="sealed", verifier="rita", store=store)
    ev = memory.add_pair("phrase with refs", "answer B", "value", "value",
                         status="sealed", verifier="rita", store=store)
    for i in range(3):
        evidence.attach(ev["id"], kind="document", locator=f"ref-{i}",
                        reason="cited", attached_by="rita", store=store)

    a = answer.ask(store, "phrase without refs", "value", "value")
    b = answer.ask(store, "phrase with refs", "value", "value")

    assert a["passage"]["state"] == b["passage"]["state"] == "sealed"
    assert a["verified"] is True and b["verified"] is True
    assert a["passage"]["confidence"] == b["passage"]["confidence"]
    # Only the visibility field differs:
    assert a["passage"]["meta"]["evidence_count"] == 0
    assert b["passage"]["meta"]["evidence_count"] == 3
