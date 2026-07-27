"""Overwriting a seal must leave a trace.

Reads alongside ``test_conflicting_seal.py``: that guard REFUSES a
cross-verifier overwrite, so the replacements recorded here are the ones that
still happen — a verifier correcting their own earlier seal, or someone
deliberately passing ``override_conflict=True``. Both destroy a previous
decision and both need a trace; the override case is the one a curator should
actually look at.

The memory keeps exactly one row per normalized source, so re-sealing an
already-sealed source destroys the previous human decision with nothing left in
the store to show for it. Before this, ``add_pair`` wrote nothing to the ledger
at all — seals made directly through it were entirely unaudited, and an
overwrite was neither raised nor recorded.
"""
from __future__ import annotations

import json

import pytest

from nestor import cascade, ledger, memory, storage
from nestor.curator import Curator
from nestor.sqlite_store import SqliteStore


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("NESTOR_SEAL_KEY", "test-key")
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    s = SqliteStore(":memory:")
    s.init_db()
    storage.set_store(s)
    return s


def _kinds(tmp_path) -> list[str]:
    p = tmp_path / "ledger.jsonl"
    if not p.exists():
        return []
    return [json.loads(x)["kind"] for x in p.read_text().strip().split("\n") if x]


# --- the trace -------------------------------------------------------------

def test_replacing_a_seal_is_recorded(store, tmp_path):
    memory.add_pair("routing decisions", "pg_bridge shape", "d", "d",
                    status="sealed", verifier="rita", store=store)
    memory.add_pair("routing decisions", "schema.sql shape", "d", "d",
                    status="sealed", verifier="sam", store=store,
                    override_conflict=True)

    assert "seal_replaced" in _kinds(tmp_path)
    rec = ledger.entries(kind="seal_replaced", path=str(tmp_path / "ledger.jsonl"))[-1]
    assert rec["replaced_verifier"] == "rita"
    assert rec["verifier"] == "sam"
    assert rec["same_verifier"] is False
    # The previous target survives ONLY here — the store kept one row.
    assert rec["replaced_target_sha"] != rec["target_sha"]


def test_the_ledger_chain_survives_a_replacement(store, tmp_path):
    memory.add_pair("alpha", "one", "d", "d", status="sealed", verifier="rita",
                    store=store)
    memory.add_pair("alpha", "two", "d", "d", status="sealed", verifier="sam",
                    store=store, override_conflict=True)
    ok, detail = ledger.verify(str(tmp_path / "ledger.jsonl"))
    assert ok, detail


def test_self_correction_is_recorded_but_marked(store, tmp_path):
    """Same verifier revising their own seal is not a conflict — but it is still
    a replacement, and the trail should be able to tell them apart."""
    memory.add_pair("beta", "one", "d", "d", status="sealed", verifier="rita",
                    store=store)
    memory.add_pair("beta", "two", "d", "d", status="sealed", verifier="rita",
                    store=store)
    rec = ledger.entries(kind="seal_replaced", path=str(tmp_path / "ledger.jsonl"))[-1]
    assert rec["same_verifier"] is True


def test_targets_are_digested_not_copied(store, tmp_path):
    """Ledger entries are mirrored verbatim into shared provenance by
    nestor.frank, so target text must not ride along."""
    secret = "confidential clause text that must not leave the building"
    memory.add_pair("gamma", secret, "d", "d", status="sealed", verifier="rita",
                    store=store)
    memory.add_pair("gamma", "replacement", "d", "d", status="sealed",
                    verifier="sam", store=store, override_conflict=True)
    raw = (tmp_path / "ledger.jsonl").read_text()
    assert secret not in raw
    assert "replacement" not in raw


def test_an_unoverridden_conflict_raises_and_records_nothing(store, tmp_path):
    """The guard runs BEFORE the overwrite, so a refused conflict must leave the
    seal AND the ledger untouched — no half-applied state."""
    memory.add_pair("lambda", "one", "d", "d", status="sealed", verifier="rita",
                    store=store)
    with pytest.raises(memory.ConflictingSealError):
        memory.add_pair("lambda", "two", "d", "d", status="sealed",
                        verifier="sam", store=store)
    assert "seal_replaced" not in _kinds(tmp_path)
    still = memory.best_sealed("lambda", "d", "d", store=store)
    assert still["pair"]["target_text"] == "one", "the refused write must not land"


# --- what is NOT a replacement --------------------------------------------

def test_sealing_a_fresh_source_records_nothing(store, tmp_path):
    memory.add_pair("delta", "one", "d", "d", status="sealed", verifier="rita",
                    store=store)
    assert "seal_replaced" not in _kinds(tmp_path)


def test_re_sealing_the_same_target_records_nothing(store, tmp_path):
    """Idempotent re-seals are noise, not decisions."""
    for _ in range(3):
        memory.add_pair("epsilon", "same", "d", "d", status="sealed",
                        verifier="rita", store=store)
    assert "seal_replaced" not in _kinds(tmp_path)


def test_promoting_a_draft_is_not_a_replacement(store, tmp_path):
    """A draft becoming sealed is the normal cascade path — no prior human
    decision is being destroyed, so it is not a conflict."""
    memory.add_pair("zeta", "machine guess", "d", "d", status="draft", store=store)
    memory.add_pair("zeta", "verified text", "d", "d", status="sealed",
                    verifier="rita", store=store)
    assert "seal_replaced" not in _kinds(tmp_path)


# --- the curator surface ---------------------------------------------------

def test_curator_surfaces_conflicts_and_hides_self_corrections(store):
    memory.add_pair("eta", "one", "d", "d", status="sealed", verifier="rita",
                    store=store)
    memory.add_pair("eta", "two", "d", "d", status="sealed", verifier="sam",
                    store=store, override_conflict=True)   # overridden conflict
    memory.add_pair("theta", "one", "d", "d", status="sealed", verifier="rita",
                    store=store)
    memory.add_pair("theta", "two", "d", "d", status="sealed", verifier="rita",
                    store=store)          # self-correction

    c = Curator(store, "d", "d")
    conflicts = c.replaced_seals()
    assert len(conflicts) == 1
    assert conflicts[0]["replaced_verifier"] == "rita"
    assert conflicts[0]["verifier"] == "sam"
    assert len(c.replaced_seals(conflicts_only=False)) == 2


# --- audit must never break a write ---------------------------------------

def test_an_unwritable_ledger_does_not_lose_the_seal(store, tmp_path, monkeypatch):
    """The pair is already committed by the time the entry is written, so
    raising here would leave the caller with a completed write and an
    exception. Bulk seeding paths must not abort on an unwritable trail."""
    memory.add_pair("iota", "one", "d", "d", status="sealed", verifier="rita",
                    store=store)

    def boom(entry):
        raise OSError("ledger unavailable")

    monkeypatch.setattr(memory, "_log_rejection", boom)
    pair = memory.add_pair("iota", "two", "d", "d", status="sealed",
                           verifier="sam", store=store, override_conflict=True)
    assert pair["target_text"] == "two", "the seal must still have landed"


# --- the ledger reader -----------------------------------------------------

def test_entries_filters_by_kind(store, tmp_path):
    memory.add_pair("kappa", "one", "d", "d", status="sealed", verifier="rita",
                    store=store)
    memory.add_pair("kappa", "two", "d", "d", status="sealed", verifier="sam",
                    store=store, override_conflict=True)
    p = str(tmp_path / "ledger.jsonl")
    assert all(e["kind"] == "seal_replaced"
               for e in ledger.entries(kind="seal_replaced", path=p))
    assert len(ledger.entries(path=p)) >= len(ledger.entries(kind="seal_replaced", path=p))


def test_entries_on_a_missing_ledger_is_empty(tmp_path):
    assert ledger.entries(path=str(tmp_path / "nope.jsonl")) == []
