"""Gates for the evidence relation (docs/evidence-edge.md, decision 0142).

Every test exercises surface new in this change, so all fail against ``HEAD~1``
for the trivial reason that ``nestor.evidence`` and the ``decision_evidence``
table did not exist. The ones that earn their place are the adversarial guards,
each attempting a forbidden or nonsensical act and asserting refusal with
nothing written, and the orthogonality checks that prove evidence is a separate
axis from the seal:

* an evidenced *draft* is never in the sealed-without-evidence queue, and a
  *sealed* row with no evidence always is — the two axes come apart;
* attaching evidence changes no seal state and is append-only (never rewritten);
* an unknown kind, an empty locator, and a ghost pair are each refused with the
  store left untouched;
* the report is read-only — running it changes nothing and never blocks a seal.
"""
from __future__ import annotations

import pytest

from nestor import cascade, evidence, ledger, memory, storage
from nestor.sqlite_store import SqliteStore


@pytest.fixture()
def store(tmp_path, monkeypatch):
    # No seal key: add_pair trusts a stored 'sealed' status, so a test can build
    # sealed rows without signing (the same posture test_rejection_signals uses).
    monkeypatch.delenv("NESTOR_SEAL_KEY", raising=False)
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    s = SqliteStore(":memory:")
    s.memory_init()
    storage.set_store(s)
    yield s
    s.close()
    storage.set_store(None)


def _sealed(store, q, c="yes", verifier="rita"):
    return memory.add_pair(q, c, "decision", "decision", status="sealed",
                           verifier=verifier, store=store)


def _draft(store, q, c="maybe"):
    return memory.add_pair(q, c, "decision", "decision", status="draft",
                           store=store)


# -- the capability is present on the shipped store --------------------------

def test_the_sqlite_store_supports_evidence(store):
    assert storage.supports_evidence(store) is True


# -- attach records a reference, and it reads back ---------------------------

def test_attach_then_read_back(store):
    pair = _sealed(store, "arrears defined")
    ev = evidence.attach(pair["id"], "document", "MSA-2024.pdf#cl.4",
                         reason="the definition", attached_by="rita", store=store)
    got = evidence.evidence_for(pair["id"], store=store)
    assert len(got) == 1
    assert got[0]["id"] == ev["id"]
    assert got[0]["kind"] == "document"
    assert got[0]["locator"] == "MSA-2024.pdf#cl.4"
    assert got[0]["attached_by"] == "rita"
    # attaches_to defaults to the pair's status at attach time
    assert got[0]["attaches_to"] == "sealed"


def test_attach_writes_the_ledger(store):
    pair = _sealed(store, "cure period")
    ev = evidence.attach(pair["id"], "url", "https://example/reg", store=store)
    entries = ledger.entries(kind="attach_evidence")
    mine = [e for e in entries if e.get("evidence_id") == ev["id"]]
    assert len(mine) == 1
    assert mine[0]["pair_id"] == pair["id"]
    assert mine[0]["evidence_kind"] == "url"


# -- the two axes come apart -------------------------------------------------

def test_a_sealed_pair_with_no_evidence_is_in_the_queue(store):
    pair = _sealed(store, "governing law")
    rows = evidence.unevidenced_seals(store=store)
    assert [r["id"] for r in rows] == [pair["id"]]


def test_a_sealed_pair_with_evidence_is_not_in_the_queue(store):
    pair = _sealed(store, "notice by email")
    evidence.attach(pair["id"], "human_statement", "counsel confirmed",
                    store=store)
    assert evidence.unevidenced_seals(store=store) == []


def test_an_evidenced_draft_is_never_in_the_queue(store):
    """The load-bearing orthogonality: a draft can be perfectly evidenced and it
    is still not a sealed row, so it is not what the queue is about."""
    draft = _draft(store, "force majeure")
    evidence.attach(draft["id"], "document", "brief.pdf", store=store)
    assert evidence.unevidenced_seals(store=store) == []


def test_a_superseded_seal_is_not_in_the_queue(store):
    """A superseded seal is history, not a live claim, so it is not queued even
    with no evidence — the report is about what is served now."""
    pair = _sealed(store, "old rule")
    store.memory_mark_superseded(pair["id"], "some-successor-id")
    assert evidence.unevidenced_seals(store=store) == []


# -- append-only, and no effect on seal state --------------------------------

def test_evidence_is_append_only_two_attaches_keep_both(store):
    pair = _sealed(store, "two sources")
    evidence.attach(pair["id"], "document", "a.pdf", store=store)
    evidence.attach(pair["id"], "url", "https://b", store=store)
    got = evidence.evidence_for(pair["id"], store=store)
    assert len(got) == 2
    assert {e["locator"] for e in got} == {"a.pdf", "https://b"}


def test_attaching_evidence_does_not_change_the_seal(store):
    pair = _sealed(store, "still sealed", verifier="sam")
    evidence.attach(pair["id"], "document", "x.pdf", store=store)
    after = store.memory_get(pair["id"])
    assert after["status"] == "sealed"
    assert after["verifier"] == "sam"


def test_attaching_evidence_does_not_seal_a_draft(store):
    draft = _draft(store, "still a draft")
    evidence.attach(draft["id"], "url", "https://x", store=store)
    assert store.memory_get(draft["id"])["status"] == "draft"


def test_the_report_is_read_only(store):
    pair = _sealed(store, "read only")
    before = store.memory_get(pair["id"])
    evidence.unevidenced_seals(store=store)
    evidence.unevidenced_seals(store=store)
    assert store.memory_get(pair["id"]) == before


# -- adversarial: each forbidden act refused with nothing written ------------

def test_an_unknown_kind_is_refused_and_nothing_is_written(store):
    pair = _sealed(store, "bad kind")
    with pytest.raises(ValueError, match="unknown evidence kind"):
        evidence.attach(pair["id"], "screenshot", "shot.png", store=store)
    assert evidence.evidence_for(pair["id"], store=store) == []
    # and the pair is still in the queue, because nothing attached
    assert [r["id"] for r in evidence.unevidenced_seals(store=store)] == [pair["id"]]


def test_an_empty_locator_is_refused(store):
    pair = _sealed(store, "no locator")
    with pytest.raises(ValueError, match="needs a locator"):
        evidence.attach(pair["id"], "document", "   ", store=store)
    assert evidence.evidence_for(pair["id"], store=store) == []


def test_a_reference_to_a_pair_that_does_not_exist_is_refused(store):
    ghost = "00000000-0000-0000-0000-000000000000"
    with pytest.raises(ValueError, match="no pair"):
        evidence.attach(ghost, "document", "x.pdf", store=store)
    assert evidence.evidence_for(ghost, store=store) == []
