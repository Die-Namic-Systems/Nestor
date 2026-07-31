"""The curator can see, audit, revoke and export what was verified.

Sealing used to be write-only: a pair could be verified but never browsed,
inspected, revoked or exported. These tests pin the surface that fixes that,
and in particular the two distinctions it exists to make — *unseal* is not
*reject*, and "says sealed" is not "would be served".
"""
from __future__ import annotations

import os

import json

import pytest

from nestor import cascade, memory, storage
from nestor.curator import Curator, CurationUnsupportedError
from nestor.sqlite_store import SqliteStore


@pytest.fixture()
def store(tmp_path, seal_key):
    os.environ['NESTOR_SEAL_KEY'] = 'test-key'
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    s = SqliteStore(":memory:")
    s.init_db()
    storage.set_store(s)
    return s


@pytest.fixture()
def filled(store):
    memory.add_pair("the annual invoice", "la factura anual", "en", "es",
                    status="sealed", verifier="rita", store=store)
    memory.add_pair("the monthly report", "el informe mensual", "en", "es",
                    status="sealed", verifier="sam", store=store)
    memory.add_pair("a draft phrase", "una frase", "en", "es",
                    status="draft", store=store)
    return store


# --- browsing --------------------------------------------------------------

def test_list_returns_pairs_with_signature_and_servability(filled):
    c = Curator(filled, "en", "es")
    rows = c.list()
    assert len(rows) == 3
    for r in rows:
        assert "signature_valid" in r and "servable" in r
    sealed = [r for r in rows if r["status"] == "sealed"]
    assert all(r["servable"] for r in sealed)


def test_list_filters(filled):
    c = Curator(filled, "en", "es")
    assert len(c.list(status="sealed")) == 2
    assert len(c.list(verifier="rita")) == 1
    assert len(c.list(contains="invoice")) == 1
    assert len(c.list(contains="FACTURA")) == 1        # case-insensitive, target side
    assert c.list(contains="nothing-matches-this") == []


def test_list_paginates(filled):
    c = Curator(filled, "en", "es")
    first = c.list(limit=2, offset=0)
    second = c.list(limit=2, offset=2)
    assert len(first) == 2 and len(second) == 1
    assert {r["id"] for r in first}.isdisjoint({r["id"] for r in second})


# --- inspecting ------------------------------------------------------------

def test_get_includes_rejections_against_the_pair(filled):
    c = Curator(filled, "en", "es")
    pair = c.list(contains="invoice")[0]
    memory.reject_match("the annual invoices", "en", "es", pair_id=pair["id"],
                        verifier="rita", reason="different year", store=filled)
    memory.reject_match("annual invoice thing", "en", "es", pair_id=pair["id"],
                        verifier="sam", reason="wrong doc", store=filled)

    detail = c.get(pair["id"])
    assert detail["rejection_count"] == 2
    assert {r["verifier"] for r in detail["rejections"]} == {"rita", "sam"}
    assert all(r["signature_valid"] for r in detail["rejections"])


def test_get_unknown_id_returns_none(filled):
    assert Curator(filled, "en", "es").get("no-such-pair") is None


def test_unverifiable_surfaces_a_forged_seal(store):
    """A row that says 'sealed' but was written without the seal key."""
    memory.add_pair("honest phrase", "frase honesta", "en", "es",
                    status="sealed", verifier="rita", store=store)
    store.memory_insert({
        "id": "forged-1", "source_text": "forged phrase",
        "source_norm": memory._norm("forged phrase"), "source_lang": "en",
        "target_text": "forjado", "target_lang": "es", "status": "sealed",
        "verifier": "mallory", "weight": 1.0, "origin": "", "created_at": "2026-01-01",
        "seal_sig": "",
    })
    c = Curator(store, "en", "es")
    bad = c.unverifiable()
    assert [p["id"] for p in bad] == ["forged-1"]
    assert bad[0]["status"] == "sealed" and bad[0]["servable"] is False
    # And Nestor genuinely refuses to serve it.
    assert memory.best_sealed("forged phrase", "en", "es", store=store) is None


# --- revoking --------------------------------------------------------------

def test_unseal_demotes_to_draft_and_stops_serving(filled):
    c = Curator(filled, "en", "es")
    pair = c.list(contains="invoice")[0]
    assert memory.best_sealed("the annual invoice", "en", "es", store=filled)

    out = c.unseal(pair["id"], verifier="rita", reason="terminology changed")
    assert out["status"] == "draft"
    assert out["seal_sig"] == "", "a draft must not keep a live seal signature"
    assert memory.best_sealed("the annual invoice", "en", "es", store=filled) is None


def test_unseal_is_reversible_but_reject_is_not(filled):
    """The distinction the surface exists to make."""
    c = Curator(filled, "en", "es")
    pair = c.list(contains="invoice")[0]

    c.unseal(pair["id"], verifier="rita", reason="unsure")
    # Re-sealing an unsealed pair restores service — it went back to the queue.
    memory.add_pair("the annual invoice", "la factura anual", "en", "es",
                    status="sealed", verifier="rita", store=filled)
    assert memory.best_sealed("the annual invoice", "en", "es", store=filled)

    # A rejected pair is retired, and re-sealing it REFUSES rather than
    # silently resurrecting it.
    memory.reject_pair(pair["id"], verifier="rita", reason="just wrong",
                       store=filled)
    with pytest.raises(memory.RejectedPairError):
        memory.add_pair("the annual invoice", "la factura anual", "en", "es",
                        status="sealed", verifier="rita", store=filled)
    assert memory.best_sealed("the annual invoice", "en", "es", store=filled) is None


def test_rejected_pair_is_not_resurrected_by_a_routine_reseal(filled):
    """The bug this surface found: without the guard, a curator's rejection was
    undone by the next graduate_segment over the same source text."""
    c = Curator(filled, "en", "es")
    pair = c.list(contains="report")[0]
    memory.reject_pair(pair["id"], verifier="rita", reason="wrong", store=filled)

    with pytest.raises(memory.RejectedPairError, match="will not be re-sealed"):
        memory.add_pair("the monthly report", "el informe mensual", "en", "es",
                        status="sealed", verifier="sam", store=filled)
    assert c.get(pair["id"])["status"] == "rejected"


def test_restore_is_the_explicit_way_back(filled):
    c = Curator(filled, "en", "es")
    pair = c.list(contains="report")[0]
    memory.reject_pair(pair["id"], verifier="rita", reason="wrong", store=filled)

    restored = c.restore(pair["id"], verifier="sam", reason="rita was mistaken")
    assert restored["status"] == "draft", "restore returns to review, not to sealed"
    assert memory.best_sealed("the monthly report", "en", "es", store=filled) is None

    # Now a deliberate re-seal is allowed.
    memory.add_pair("the monthly report", "el informe mensual", "en", "es",
                    status="sealed", verifier="sam", store=filled)
    assert memory.best_sealed("the monthly report", "en", "es", store=filled)


def test_override_rejection_is_available_but_explicit(filled):
    c = Curator(filled, "en", "es")
    pair = c.list(contains="report")[0]
    memory.reject_pair(pair["id"], verifier="rita", reason="wrong", store=filled)
    memory.add_pair("the monthly report", "el informe mensual", "en", "es",
                    status="sealed", verifier="sam", store=filled,
                    override_rejection=True)
    assert memory.best_sealed("the monthly report", "en", "es", store=filled)


def test_unseal_is_written_to_the_ledger(filled, tmp_path):
    c = Curator(filled, "en", "es")
    pair = c.list(contains="invoice")[0]
    c.unseal(pair["id"], verifier="rita", reason="stale")

    kinds = [json.loads(x)["kind"]
             for x in (tmp_path / "ledger.jsonl").read_text().strip().split("\n")]
    assert "unseal" in kinds, "withdrawing trust must be audited, not just granting it"

    from nestor.ledger import verify
    ok, detail = verify(str(tmp_path / "ledger.jsonl"))
    assert ok, detail


def test_unseal_unknown_id_returns_none(filled):
    assert Curator(filled, "en", "es").unseal("nope", verifier="rita") is None


# --- exporting -------------------------------------------------------------

def test_export_is_json_serializable_and_complete(filled):
    c = Curator(filled, "en", "es")
    pair = c.list(contains="invoice")[0]
    memory.reject_match("the annual invoices", "en", "es", pair_id=pair["id"],
                        verifier="rita", store=filled)

    dump = c.export()
    json.dumps(dump)                       # must round-trip
    assert dump["signing_enabled"] is True
    assert dump["counts"]["sealed"] == 2 and dump["counts"]["draft"] == 1
    exported = next(p for p in dump["pairs"] if p["id"] == pair["id"])
    assert exported["rejection_count"] == 1
    assert exported["seal_sig"], "signatures travel with the export"


def test_summary_counts_what_stats_omits(filled):
    s = Curator(filled, "en", "es").summary()
    assert s["sealed"] == 2 and s["draft"] == 1 and s["rejected"] == 0
    assert s["sealed_unverifiable"] == 0
    assert s["verifiers"] == ["rita", "sam"]


# --- capability handling ---------------------------------------------------

def test_store_without_curation_raises_clearly(tmp_path, seal_key):
    os.environ['NESTOR_SEAL_KEY'] = 'k'
    cascade.set_ledger_path(tmp_path / "l.jsonl")

    class _Legacy(SqliteStore):
        memory_list = None

    legacy = _Legacy(":memory:")
    legacy.init_db()
    assert not storage.supports_curation(legacy)
    with pytest.raises(CurationUnsupportedError, match="curation capability"):
        Curator(legacy)


def test_reference_store_supports_curation(store):
    assert storage.supports_curation(store)
