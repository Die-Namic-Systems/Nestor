"""A reviewer's "no" must stick.

Before rejection existed a reviewer could seal a match but not refuse one, so a
wrong candidate came back identically forever. These tests pin the two distinct
refusals — a bad *pair* and a bad *match* — and the property that separates
them: rejecting a false seal must not destroy the (correct) pair it collided
with.
"""
from __future__ import annotations

import os

import pytest

from nestor import cascade, memory, signing, storage
from nestor.sqlite_store import SqliteStore


@pytest.fixture()
def store(tmp_path, seal_key):
    os.environ['NESTOR_SEAL_KEY'] = 'test-key'
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    s = SqliteStore(":memory:")
    s.init_db()
    storage.set_store(s)
    return s


# --- match rejection: right pair, wrong query ------------------------------

def test_rejecting_a_match_suppresses_it_for_that_query_only(store):
    memory.add_pair("the annual audit report", "el informe anual", "en", "es",
                    status="sealed", verifier="rita")

    probe = "the annual audit reports"          # fuzzy-matches the sealed pair
    hit = memory.best_sealed(probe, "en", "es", store=store)
    assert hit is not None, "precondition: the probe must match before rejection"
    pair_id = hit["pair"]["id"]

    memory.reject_match(probe, "en", "es", pair_id=pair_id, verifier="rita",
                        reason="different document", store=store)

    assert memory.best_sealed(probe, "en", "es", store=store) is None
    # The pair is untouched for its OWN source — this is the whole point.
    still = memory.best_sealed("the annual audit report", "en", "es", store=store)
    assert still is not None and still["pair"]["id"] == pair_id
    assert still["pair"]["status"] == "sealed"


def test_rejection_also_hides_the_pair_from_engine_context(store):
    """Filtering lives in lookup(), so every serve path inherits it — a rejected
    pair must not reach the engine's system prompt as reference material."""
    memory.add_pair("the annual audit report", "el informe anual", "en", "es",
                    status="sealed", verifier="rita")
    probe = "the annual audit reports"
    assert memory.lookup(probe, "en", "es", store=store)

    memory.reject_match(probe, "en", "es",
                        pair_id=memory.lookup(probe, "en", "es", store=store)[0]["pair"]["id"],
                        verifier="rita", store=store)
    assert memory.lookup(probe, "en", "es", store=store) == []


def test_rejecting_by_target_text_suppresses_a_draft_with_no_pair(store):
    memory.add_pair("buenos dias", "good morning", "es", "en",
                    status="sealed", verifier="rita")
    memory.reject_match("buenos dias", "es", "en", target_text="good morning",
                        verifier="rita", reason="wrong register", store=store)
    assert memory.best_sealed("buenos dias", "es", "en", store=store) is None


def test_reject_match_needs_something_to_suppress(store):
    with pytest.raises(ValueError):
        memory.reject_match("anything", "en", "es", verifier="rita", store=store)


# --- pair rejection: the mapping itself is wrong ---------------------------

def test_rejecting_a_pair_retires_it_everywhere(store):
    pair = memory.add_pair("good evening", "buenos dias", "en", "es",
                           status="sealed", verifier="rita")
    assert memory.best_sealed("good evening", "en", "es", store=store)

    memory.reject_pair(pair["id"], verifier="rita", reason="wrong time of day",
                       store=store)

    assert memory.best_sealed("good evening", "en", "es", store=store) is None
    assert memory.lookup("good evening", "en", "es", store=store) == []


# --- the reviewer path -----------------------------------------------------

def test_reject_segment_stops_the_candidate_coming_back(store):
    memory.add_pair("hola", "hello", "es", "en", status="draft")
    doc, passages = cascade.translate_text("Hola.", target_lang="en",
                                           source_lang="es", store=store)
    seg_id = passages[0].segment_id
    assert seg_id, "precondition: the draft must have been queued for review"
    candidate = passages[0].target

    rejection = cascade.reject_segment(seg_id, verifier="rita",
                                       reason="not a greeting here", store=store)
    assert rejection is not None
    assert store.get_segment(seg_id)["status"] == "rejected"

    # The same candidate must not be offered for that source text again.
    again = cascade.translate_segment("Hola.", "es", "en", store=store)
    assert again.target != candidate or again.state != "sealed"


def test_reject_segment_returns_none_for_unknown_segment(store):
    assert cascade.reject_segment("no-such-id", verifier="rita", store=store) is None


# --- ledger + signature ----------------------------------------------------

def test_rejections_are_written_to_the_ledger(store, tmp_path):
    memory.add_pair("alpha beta", "alfa beta", "en", "es", status="sealed",
                    verifier="rita")
    memory.reject_match("alpha beta", "en", "es", target_text="alfa beta",
                        verifier="rita", reason="bad", store=store)
    lines = (tmp_path / "ledger.jsonl").read_text().strip().split("\n")
    kinds = [__import__("json").loads(x)["kind"] for x in lines]
    assert "reject_match" in kinds, "a human's 'no' belongs in the audit trail"

    from nestor.ledger import verify
    ok, detail = verify(str(tmp_path / "ledger.jsonl"))
    assert ok, detail


def test_rejection_signature_round_trips(store):
    memory.add_pair("gamma", "gama", "en", "es", status="sealed", verifier="rita")
    r = memory.reject_match("gamma", "en", "es", target_text="gama",
                            verifier="rita", store=store)
    assert r["reject_sig"], "signing is enabled in this fixture"
    assert signing.rejection_is_valid(r["query_norm"], r["pair_id"],
                                      r["target_text"], r["verifier"],
                                      r["reject_sig"])
    assert not signing.rejection_is_valid(r["query_norm"], r["pair_id"],
                                          r["target_text"], "someone-else",
                                          r["reject_sig"])


def test_a_rejection_signature_is_not_a_seal_signature(store):
    """Domain separation: the two protocols must not accept each other's
    signatures, or one could be replayed as the other."""
    seal = signing.sign_seal("norm", "target", "rita")
    assert not signing.rejection_is_valid("norm", "", "target", "rita", seal)


def test_unverifiable_rejections_are_still_honored(store):
    """Suppression fails safe; serving does not. A rejection whose signature
    does not verify still withholds the answer (degrading to human review),
    but is reported as invalid for audit."""
    memory.add_pair("delta", "delta-es", "en", "es", status="sealed",
                    verifier="rita")
    store.memory_add_rejection({
        "id": "forged-1", "query_norm": memory._norm("delta"),
        "source_lang": "en", "target_lang": "es", "pair_id": "",
        "target_text": "delta-es", "verifier": "mallory",
        "reason": "forged", "created_at": "2026-01-01T00:00:00Z",
        "reject_sig": "not-a-real-signature",
    })
    assert memory.best_sealed("delta", "en", "es", store=store) is None

    report = memory.rejection_signature_report(memory._norm("delta"), "en", "es",
                                               store=store)
    assert report and report[0]["signature_valid"] is False


# --- capability handling ---------------------------------------------------

class _LegacyStore(SqliteStore):
    """A host store predating the rejection capability."""
    memory_reject_pair = None
    memory_add_rejection = None
    memory_rejections = None


def test_a_store_without_rejection_still_works(tmp_path, seal_key):
    os.environ['NESTOR_SEAL_KEY'] = 'test-key'
    cascade.set_ledger_path(tmp_path / "l.jsonl")
    legacy = _LegacyStore(":memory:")
    legacy.init_db()
    assert not storage.supports_rejection(legacy)
    memory.add_pair("epsilon", "epsilon-es", "en", "es", status="sealed",
                    verifier="rita", store=legacy)
    assert memory.best_sealed("epsilon", "en", "es", store=legacy)


def test_rejection_refuses_rather_than_silently_dropping(tmp_path, seal_key):
    os.environ['NESTOR_SEAL_KEY'] = 'test-key'
    cascade.set_ledger_path(tmp_path / "l.jsonl")
    legacy = _LegacyStore(":memory:")
    legacy.init_db()
    with pytest.raises(RuntimeError, match="rejection capability"):
        memory.reject_match("epsilon", "en", "es", target_text="x",
                            verifier="rita", store=legacy)


def test_partial_rejection_support_counts_as_none(tmp_path):
    class _Partial(SqliteStore):
        memory_rejections = None          # can write, cannot read back
    assert not storage.supports_rejection(_Partial(":memory:"))
