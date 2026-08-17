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


def test_an_over_long_locator_is_refused_with_nothing_written(store):
    pair = _sealed(store, "too long")
    with pytest.raises(ValueError, match="too long"):
        evidence.attach(pair["id"], "url", "x" * 5000, store=store)
    assert evidence.evidence_for(pair["id"], store=store) == []


def test_a_broken_ledger_refuses_the_attach_before_the_row_is_written(store, tmp_path):
    """The orphan-row guard: if the trail will not take the entry, refuse BEFORE
    the store write, so an evidence row can never outlive its ledger line — the
    rule every other write path holds. Found by the evidence-relation audit."""
    pair = _sealed(store, "broken ledger")           # a valid seal entry lands
    # Point the ledger at a directory: not a regular file, so the preflight
    # refuses to append (QUESTIONS.md §17), exactly as it would on a broken chain.
    bad = tmp_path / "ledger_is_a_dir"
    bad.mkdir()
    cascade.set_ledger_path(bad)
    with pytest.raises(Exception):
        evidence.attach(pair["id"], "document", "x.pdf", store=store)
    # nothing written — the row did not land ahead of a trail that refused it
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    assert evidence.evidence_for(pair["id"], store=store) == []


# -- audit follow-up: domain scope, content hash, bundle warning ------------

def test_the_report_can_scope_to_one_domain(store):
    """A multi-domain store's queue can be narrowed; unscoped, it lists all."""
    d = _sealed(store, "decision seal")                     # decision/decision
    t = memory.add_pair("hola", "hello", "es", "en", status="sealed",
                        verifier="rita", store=store)        # es/en
    allrows = {r["id"] for r in evidence.unevidenced_seals(store=store)}
    assert allrows == {d["id"], t["id"]}                    # both, unscoped
    dec = evidence.unevidenced_seals(store=store, source_lang="decision",
                                     target_lang="decision")
    assert [r["id"] for r in dec] == [d["id"]]
    tr = evidence.unevidenced_seals(store=store, source_lang="es", target_lang="en")
    assert [r["id"] for r in tr] == [t["id"]]


def test_attach_records_a_content_hash_in_the_ledger(store):
    """The attach_evidence entry carries a hash of the mutable content, so an
    out-of-band edit to a row's locator/reason is detectable against the chain."""
    import hashlib
    pair = _sealed(store, "hashed")
    ev = evidence.attach(pair["id"], "document", "MSA.pdf", reason="clause 4",
                         store=store)
    entry = [e for e in ledger.entries(kind="attach_evidence")
             if e.get("evidence_id") == ev["id"]][0]
    expected = hashlib.sha256(
        "\n".join(("document", "MSA.pdf", "clause 4")).encode()).hexdigest()
    assert entry["content_sha"] == expected


def test_evidence_survives_an_export_import_round_trip(store, tmp_path):
    """Carriage: a reference attached here is carried in the v3 bundle and lands
    on the pair after importing into a fresh instance (decision 0144)."""
    from nestor import portable
    pair = _sealed(store, "round trip")
    evidence.attach(pair["id"], "document", "MSA.pdf#cl.4", reason="the def",
                    attached_by="rita", store=store)
    bundle = portable.export_bundle(store=store)
    assert bundle["nestor_bundle"] == 3
    assert bundle["counts"]["evidence"] == 1
    ok, detail = portable.verify_bundle(bundle)
    assert ok, detail

    # a fresh instance with its own store + ledger
    cascade.set_ledger_path(tmp_path / "dest_ledger.jsonl")
    dest = SqliteStore(":memory:")
    dest.memory_init()
    portable.import_bundle(bundle, store=dest, dry_run=False, verifier="sam")
    landed = evidence.evidence_for(pair["id"], store=dest)
    assert len(landed) == 1
    assert landed[0]["locator"] == "MSA.pdf#cl.4"
    assert landed[0]["kind"] == "document"
    dest.close()


def test_the_digest_covers_evidence_so_an_edit_is_caught(store):
    """Tampering an evidence row after export breaks verify — evidence is inside
    the integrity digest for v3, not bolted on beside it."""
    from nestor import portable
    pair = _sealed(store, "tamper")
    evidence.attach(pair["id"], "url", "https://real", store=store)
    bundle = portable.export_bundle(store=store)
    assert portable.verify_bundle(bundle)[0]
    bundle["evidence"][0]["locator"] = "https://forged"
    ok, detail = portable.verify_bundle(bundle)
    assert not ok and "digest mismatch" in detail


def test_import_drops_evidence_naming_a_pair_the_bundle_does_not_carry(store, tmp_path):
    """A hand-edited bundle whose evidence names an uncarried pair: the reference
    is dropped, not left dangling. Export cannot produce this — only tampering."""
    from nestor import portable
    pair = _sealed(store, "carried")
    evidence.attach(pair["id"], "document", "x.pdf", store=store)
    bundle = portable.export_bundle(store=store)
    bundle["evidence"][0]["pair_id"] = "ghost-pair-id-not-in-bundle"
    bundle["digest"] = portable.digest(bundle["pairs"], bundle["rejections"],
                                       bundle["evidence"], version=3)
    cascade.set_ledger_path(tmp_path / "dest2_ledger.jsonl")
    dest = SqliteStore(":memory:")
    dest.memory_init()
    report = portable.import_bundle(bundle, store=dest, dry_run=False, verifier="sam")
    assert report["evidence"] == 0
    assert report["dangling_evidence"] == ["ghost-pair-id-not-in-bundle"]
    dest.close()


def test_a_store_advertising_evidence_but_lacking_memory_get_says_so_honestly(store):
    """supports_evidence checks three ops; attach also needs memory_get (a
    different capability). A store shaped that way must get an honest capability
    error, not a false 'no pair' about a pair that exists. Found by the audit."""
    pair = _sealed(store, "cap gap")

    class NoGet:
        """Delegates everything to a real store but hides memory_get."""
        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, name):
            if name == "memory_get":
                raise AttributeError(name)
            return getattr(self._inner, name)

    wrapped = NoGet(store)
    assert storage.supports_evidence(wrapped) is True     # it advertises support
    with pytest.raises(RuntimeError, match="memory_get"):
        evidence.attach(pair["id"], "document", "x.pdf", store=wrapped)
    # and the pair genuinely exists — the old code would have said "no pair"
    assert store.memory_get(pair["id"]) is not None
