import hashlib

import pytest

from nestor import cascade, memory
from nestor.cascade import Passage, graduate_segment, translate_segment, translate_text
from nestor.engine import OfflineEngine

from conftest import read_ledger


def test_translate_segment_returns_passage_and_ledgers(store):
    # Empty memory + offline engine with nothing to match -> tier 0 pending,
    # but still a Passage and still a ledger entry.
    p = translate_segment("Hello there.", "en", "es",
                          engine=OfflineEngine(), store=store)
    assert isinstance(p, Passage)
    assert p.tier == 0 and p.state == "pending"

    entries = read_ledger()
    assert len(entries) == 1
    assert entries[0]["kind"] == "passage"
    assert entries[0]["source_lang"] == "en"


def test_translate_segment_tier1_from_sealed_memory(store):
    memory.add_pair("Good morning", "Buenos días", "en", "es",
                    status="sealed", verifier="tester", store=store)
    p = translate_segment("Good morning", "en", "es",
                          engine=OfflineEngine(), store=store)
    assert p.tier == 1
    assert p.state == "sealed"
    assert p.target == "Buenos días"
    assert p.engine == "memory"


def test_translate_segment_tier2_draft_and_queues_segment(store):
    # A *draft* pair in memory: not sealed (so no tier 1), but the offline
    # engine will serve it as a low-confidence draft (tier 2).
    memory.add_pair("The quick brown fox", "El zorro marrón rápido", "en", "es",
                    status="draft", store=store)
    doc = store.create_document("t", "en", "es")
    p = translate_segment("The quick brown fox", "en", "es",
                          engine=OfflineEngine(), document_id=doc["id"],
                          position=0, store=store)
    assert p.tier == 2
    assert p.state == "draft"
    assert p.segment_id  # queued into the review pipeline
    seg = store.get_segment(p.segment_id)
    assert seg["source_text"] == "The quick brown fox"


def test_translate_text_all_sealed_marks_verified(store):
    memory.add_pair("One.", "Uno.", "en", "es", status="sealed", store=store)
    memory.add_pair("Two.", "Dos.", "en", "es", status="sealed", store=store)
    memory.add_pair("Three.", "Tres.", "en", "es", status="sealed", store=store)
    doc, passages = translate_text("One. Two. Three.", target_lang="es",
                                   source_lang="en", engine_name="offline",
                                   store=store)
    assert all(p.tier == 1 for p in passages)
    assert store.get_document(doc["id"])["status"] == "verified"


def test_translate_text_pending_when_a_segment_needs_review(store):
    doc, passages = translate_text("A wholly unseen sentence here.",
                                   target_lang="es", source_lang="en",
                                   engine_name="offline", store=store)
    assert any(p.tier != 1 for p in passages)
    assert store.get_document(doc["id"])["status"] == "pending_review"


def test_ledger_is_hash_chained(store):
    translate_segment("first", "en", "es", engine=OfflineEngine(), store=store)
    translate_segment("second", "en", "es", engine=OfflineEngine(), store=store)

    path = cascade._ledger_path()
    raw_lines = [l for l in path.read_text().splitlines() if l.strip()]
    assert len(raw_lines) == 2

    entries = read_ledger()
    assert entries[0]["prev"] == "genesis"
    expected_prev = hashlib.sha256(raw_lines[0].encode()).hexdigest()
    assert entries[1]["prev"] == expected_prev


def test_graduate_segment_seals_pair_and_ledgers(store):
    doc = store.create_document("d", "en", "es")
    seg = store.create_segment(doc["id"], 0, "See you soon", "Hasta pronto", 0.6)

    pair = graduate_segment(seg["id"], verifier="alice", store=store)
    assert pair is not None
    assert pair["status"] == "sealed"
    assert pair["verifier"] == "alice"

    # It now serves as a tier-1 sealed hit.
    hit = memory.best_sealed("See you soon", "en", "es", store=store)
    assert hit is not None
    assert hit["pair"]["target_text"] == "Hasta pronto"

    seal_entries = [e for e in read_ledger() if e.get("kind") == "seal"]
    assert len(seal_entries) == 1
    assert seal_entries[0]["segment_id"] == seg["id"]


def test_graduate_segment_none_without_candidate(store):
    doc = store.create_document("d", "en", "es")
    seg = store.create_segment(doc["id"], 0, "no candidate", "", 0.0)
    assert graduate_segment(seg["id"], store=store) is None
