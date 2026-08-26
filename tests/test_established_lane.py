"""``nestor.established`` — the established-knowledge lane.

Decision 0206: a subpackage that registers through the tier-1.5
recognizer seam (decision 0205) to surface lexicon and Jeles hits as
tier-2 drafts with citation warrants, so a human does not have to pair
what is already culturally or corpus-established.

Contract locked by this bench:

* Lexicon lookups are exact-norm and domain-scoped. `42` under
  `(number, meaning)` hits; `42` under `(headcount, value)` misses;
  `Room 42` misses because ``StringMatcher.normalize`` keys on
  ``room 42`` not ``42``.
* ``ensure_established_draft`` writes exactly one draft per source_norm,
  attaches evidence and a citation warrant, and NEVER seals.
* Repeat calls with the same key reuse the existing draft.
* A rejected pair suppresses re-drafting.
* An already-sealed pair short-circuits (no rewrite).
* ``install()`` registers the recognizer through
  :func:`nestor.cascade.set_tier15_recognizer` (no monkeypatch),
  ``uninstall()`` clears it, ``installed()`` reports the state.
* End-to-end: with the recognizer installed,
  ``cascade.translate_segment`` on ``"42"`` under ``(number, meaning)``
  returns a tier-2 draft with ``engine="established"`` — the sealed
  lane at tier 1 still wins if a real seal exists.
"""
from __future__ import annotations

import pathlib

import pytest

from nestor import cascade, established, memory
from nestor.sqlite_store import SqliteStore


@pytest.fixture
def store(tmp_path):
    cascade.set_ledger_path(str(tmp_path / "ledger.jsonl"))
    cascade._verified_ledgers.clear()
    cascade._checkpoints.clear()
    st = SqliteStore(str(tmp_path / "nestor.db"))
    st.init_db()
    st.memory_init()
    yield st
    # Never leak the recognizer into the next test.
    established.uninstall()
    cascade.set_tier15_recognizer(None)


# --- lexicon: pure lookups -------------------------------------------------

def test_lexicon_hit_returns_established_shape():
    """A lexicon hit returns a hit-dict with rung=established,
    provider=lexicon, and every field the writer needs."""
    hit = established.recognize_lexicon("42", "number", "meaning")
    assert hit is not None
    assert hit["rung"] == "established"
    assert hit["provider"] == "lexicon"
    assert hit["source_norm"] == "42"
    assert "answer" in hit["target_text"].lower() or "hitchhiker" in hit["target_text"].lower()
    assert hit["authority"] == "cultural:hitchhiker"
    assert hit["locator"].startswith("https://")
    assert hit["confidence"] == pytest.approx(1.0)


def test_lexicon_miss_returns_none():
    """A source not in the lexicon returns None with no side effects."""
    assert established.recognize_lexicon("hello world", "en", "es") is None
    assert established.recognize_lexicon("999", "number", "meaning") is None


@pytest.mark.parametrize("source_text,source_lang,target_lang,expect_hit", [
    ("42", "number", "meaning", True),
    ("42", "headcount", "value", False),   # wrong domain
    ("42", "en", "es", False),              # wrong domain
    ("Room 42", "number", "meaning", False),  # norm becomes 'room 42', not '42'
    ("404", "http", "desc", True),
    ("404", "en", "es", False),             # wrong domain
    ("Paris", "geo", "desc", True),         # case-fold succeeds
    ("PARIS", "geo", "desc", True),
    ("Big Blue", "entity", "entity", True),
])
def test_lexicon_is_exact_norm_and_domain_scoped(source_text, source_lang,
                                                  target_lang, expect_hit):
    hit = established.recognize_lexicon(source_text, source_lang, target_lang)
    assert (hit is not None) == expect_hit, (
        f"{source_text!r} under ({source_lang}, {target_lang}): "
        f"expected {'hit' if expect_hit else 'miss'}, got "
        f"{'hit' if hit else 'miss'}"
    )


def test_empty_norm_returns_none():
    """An input whose normalize output is empty (pure punctuation,
    whitespace) can't collide the lexicon on an empty key — same class
    of collision the memory layer refuses at ``add_pair``."""
    assert established.recognize_lexicon("...", "number", "meaning") is None
    assert established.recognize_lexicon("   ", "number", "meaning") is None


def test_custom_lexicon_replaces_the_default():
    """Callers can substitute their own lexicon. The default is not
    consulted when ``lexicon=`` is passed."""
    my_lex = {
        ("greeting", "language", "hi"): {
            "target_text": "a common English greeting",
            "authority": "test:custom",
            "locator": "https://example.test/hi",
            "check": "trivial",
            "confidence": 1.0,
        },
    }
    # My key hits.
    hit = established.recognize_lexicon("hi", "greeting", "language",
                                         lexicon=my_lex)
    assert hit is not None
    assert hit["target_text"].startswith("a common English greeting")
    # Default's key misses.
    assert established.recognize_lexicon("42", "number", "meaning",
                                          lexicon=my_lex) is None


# --- ensure_established_draft: the writer ---------------------------------

def test_ensure_established_draft_miss(store):
    """Recognition miss → action='miss', nothing written."""
    result = established.ensure_established_draft(
        "unknown phrase", "en", "es", store=store, use_jeles=False,
    )
    assert result == {"action": "miss", "recognized": False}
    # No pair landed.
    assert store.memory_list() == []


def test_ensure_established_draft_creates_draft_with_citation(store):
    """Recognition hit → draft pair + evidence + citation warrant."""
    result = established.ensure_established_draft(
        "42", "number", "meaning", store=store, use_jeles=False,
    )
    assert result["action"] == "created_draft"
    assert result["recognized"] is True
    assert result["status"] == "draft"
    assert result["rung"] == "established"
    assert result["provider"] == "lexicon"
    # Exactly one draft pair with no verifier and no signature.
    pairs = store.memory_list()
    assert len(pairs) == 1
    p = pairs[0]
    assert p["status"] == "draft"
    assert not p["verifier"]
    assert not p["seal_sig"]
    assert p["origin"] == "established-lexicon"
    # Evidence attached.
    assert result["evidence"]
    # Citation warrant attached.
    assert result["warrant"].get("kind") == "citation"
    assert result["warrant"].get("authority") == "cultural:hitchhiker"


def test_ensure_established_draft_is_idempotent(store):
    """Repeat calls reuse the existing draft rather than raising or
    duplicating."""
    r1 = established.ensure_established_draft(
        "42", "number", "meaning", store=store, use_jeles=False,
    )
    r2 = established.ensure_established_draft(
        "42", "number", "meaning", store=store, use_jeles=False,
    )
    assert r1["action"] == "created_draft"
    assert r2["action"] == "reused_draft"
    assert r2["pair_id"] == r1["pair_id"]
    assert len(store.memory_list()) == 1


def test_ensure_established_draft_never_seals(store):
    """The whole rationale for the rung system — a recognized fact is
    still a draft until a human seals it."""
    established.ensure_established_draft(
        "42", "number", "meaning", store=store, use_jeles=False,
    )
    pairs = store.memory_list()
    for p in pairs:
        assert p["status"] != "sealed", (
            f"pair {p['id']} sealed by the established lane; the lane "
            f"must never seal — decision 0206"
        )


def test_ensure_established_draft_respects_rejection(store):
    """A rejected pair for this norm suppresses re-drafting — a reviewer
    who said no should not have the established lane re-propose the
    same target."""
    # First create + then reject.
    r1 = established.ensure_established_draft(
        "42", "number", "meaning", store=store, use_jeles=False,
    )
    memory.reject_pair(r1["pair_id"], verifier="test-reviewer",
                        reason="not helpful", store=store)
    # Now a second call: suppressed.
    r2 = established.ensure_established_draft(
        "42", "number", "meaning", store=store, use_jeles=False,
    )
    assert r2["action"] == "suppressed_by_rejection"


def test_ensure_established_draft_already_sealed(store):
    """A pair sealed for this norm short-circuits — the established
    lane does not overwrite or add a second row."""
    memory.add_pair("42", "the answer",
                    "number", "meaning", status="sealed",
                    verifier="a-human", origin="test", store=store)
    result = established.ensure_established_draft(
        "42", "number", "meaning", store=store, use_jeles=False,
    )
    assert result["action"] == "already_sealed"
    assert result["status"] == "sealed"


# --- wire: install / uninstall / installed --------------------------------

def test_install_registers_through_cascade_seam(store):
    """After install(), the recognizer sits in cascade.set_tier15_recognizer's
    slot. Uninstall clears it. installed() reports the state."""
    assert established.installed() is False
    assert cascade.get_tier15_recognizer() is None

    established.install()
    assert established.installed() is True
    assert cascade.get_tier15_recognizer() is not None

    established.uninstall()
    assert established.installed() is False
    assert cascade.get_tier15_recognizer() is None


def test_uninstall_leaves_other_recognizers_alone(store):
    """If someone else installed their own recognizer between install()
    and uninstall(), our uninstall() must not silently clobber theirs."""

    def somebody_elses(text, source_lang, target_lang, *, store, matcher):
        return None

    established.install()
    cascade.set_tier15_recognizer(somebody_elses)
    established.uninstall()
    assert cascade.get_tier15_recognizer() is somebody_elses
    cascade.set_tier15_recognizer(None)


# --- cascade integration ---------------------------------------------------

def test_cascade_serves_lexicon_hit_as_established_draft(store):
    """The load-bearing shape: with install() called,
    cascade.translate_segment on '42' under (number, meaning) returns
    a tier-2 draft whose engine is 'established' and whose meta carries
    rung/provider/authority. The seal queue is not touched."""
    established.install()
    passage = cascade.translate_segment(
        "42", "number", "meaning", store=store,
    )
    assert passage.state == "draft"
    assert passage.engine == "established"
    assert passage.tier == 2
    assert "hitchhiker" in passage.target.lower()
    assert passage.meta.get("rung") == "established"
    assert passage.meta.get("provider") == "lexicon"
    assert passage.meta.get("authority") == "cultural:hitchhiker"
    assert passage.meta.get("seal_queue") is False
    # A pair landed with the citation warrant attached.
    pairs = store.memory_list()
    assert len(pairs) == 1
    assert pairs[0]["origin"] == "established-lexicon"


def test_cascade_sealed_lane_still_wins_over_recognizer(store):
    """If a sealed pair exists at tier 1, the recognizer must not even
    be called — the sealed lane is authoritative."""
    memory.add_pair("42", "the sealed answer",
                    "number", "meaning", status="sealed",
                    verifier="a-human", origin="test", store=store)
    established.install()
    passage = cascade.translate_segment(
        "42", "number", "meaning", store=store,
    )
    assert passage.tier == 1
    assert passage.state == "sealed"
    assert passage.target == "the sealed answer"
    assert passage.engine == "memory"


def test_cascade_unknown_falls_through_to_engine(store):
    """A source that neither the sealed lane nor the recognizer catches
    reaches the tier-2 engine (which for an unseeded OfflineEngine either
    drafts nothing or leaves it pending). The recognizer being installed
    must not short-circuit the engine on a miss."""
    established.install()
    passage = cascade.translate_segment(
        "some unknown phrase", "en", "es", store=store,
    )
    assert passage.engine != "established"
    # No established pair landed.
    pairs = store.memory_list()
    for p in pairs:
        assert p.get("origin") != "established-lexicon"


def test_cascade_rejection_suppresses_established_lane(store):
    """If a pair for this norm was rejected, the recognizer returns
    None (via ensure_established_draft's suppressed_by_rejection path)
    and the cascade falls through to the engine — a reviewer's no
    survives the recognizer."""
    # Create a draft + reject it.
    r = established.ensure_established_draft(
        "42", "number", "meaning", store=store, use_jeles=False,
    )
    memory.reject_pair(r["pair_id"], verifier="test-reviewer",
                        reason="not helpful here", store=store)
    established.install()
    passage = cascade.translate_segment(
        "42", "number", "meaning", store=store,
    )
    # Fell through to the engine (or pending), NOT served as an
    # established draft.
    assert passage.engine != "established"


# --- jeles bridge (skips without jeles installed) -------------------------

def test_jeles_bridge_importable():
    """The bridge imports jeles at import time. Test-skip when jeles is
    absent (the module docstring names jeles as an optional dep)."""
    pytest.importorskip("jeles")
    from nestor.established import jeles_bridge
    assert callable(jeles_bridge.recognize_from_jeles)
    assert callable(jeles_bridge.seed_demo_nuggets)


def test_jeles_recognizer_rejects_asserted_by_default(store, tmp_path,
                                                       monkeypatch):
    """A Jeles nugget with verification_kind='asserted' must not be
    served by default. Uses a stub jeles.corpus module so the test is
    hermetic — no real corpus writes, no cross-test contamination."""
    pytest.importorskip("jeles")
    import types

    stub = types.SimpleNamespace(
        ask_corpus=lambda q, include_asserted=False: {
            "found": True,
            "exact": True,
            "nugget": {
                "answer": "hunter2",
                "verification_kind": "asserted",
                "verified_by": "random-bot",
                "sources": [],
                "tags": [],
            },
        },
        MIN_ASK_SCORE=0.5,
    )
    monkeypatch.setattr("nestor.established.jeles_bridge.jeles_corpus", stub)

    hit = established.recognize_from_jeles(
        "any question", "en", "es", include_asserted=False,
    )
    assert hit is None, "asserted-kind nugget served without include_asserted=True"


def test_jeles_recognizer_serves_human_verified(store, tmp_path, monkeypatch):
    """A human-verified nugget lands as an established hit with the
    'human' rung and jeles authority."""
    pytest.importorskip("jeles")
    import types

    stub = types.SimpleNamespace(
        ask_corpus=lambda q, include_asserted=False: {
            "found": True,
            "exact": True,
            "nugget": {
                "answer": "42 (Douglas Adams)",
                "verification_kind": "human",
                "verified_by": "demo-curator",
                "sources": ["https://en.wikipedia.org/wiki/Hitchhiker"],
                "tags": ["domain:number->meaning"],
            },
        },
        MIN_ASK_SCORE=0.5,
    )
    monkeypatch.setattr("nestor.established.jeles_bridge.jeles_corpus", stub)

    hit = established.recognize_from_jeles(
        "What is the answer?", "number", "meaning", include_asserted=False,
    )
    assert hit is not None
    assert hit["rung"] == "established"
    assert hit["provider"] == "jeles"
    assert hit["verification_kind"] == "human"
    assert "demo-curator" in hit["authority"]


def test_jeles_machine_kind_maps_to_corroborated_rung(store, tmp_path,
                                                       monkeypatch):
    """A machine-verified nugget is corroborated, not established — names
    the rung the recognizer chooses so a reviewer sees which class of
    trust it came from."""
    pytest.importorskip("jeles")
    import types

    stub = types.SimpleNamespace(
        ask_corpus=lambda q, include_asserted=False: {
            "found": True,
            "exact": True,
            "nugget": {
                "answer": "some machine-derived answer",
                "verification_kind": "machine",
                "verified_by": "automated-check",
                "sources": ["https://example.test/source"],
                "tags": [],
            },
        },
        MIN_ASK_SCORE=0.5,
    )
    monkeypatch.setattr("nestor.established.jeles_bridge.jeles_corpus", stub)

    hit = established.recognize_from_jeles(
        "some question", "en", "es", include_asserted=False,
    )
    assert hit is not None
    assert hit["rung"] == "corroborated"


def test_jeles_domain_scoping_rejects_mismatched_tags(store, tmp_path,
                                                       monkeypatch):
    """A nugget tagged for one domain must not serve a query in a
    different domain."""
    pytest.importorskip("jeles")
    import types

    stub = types.SimpleNamespace(
        ask_corpus=lambda q, include_asserted=False: {
            "found": True,
            "exact": True,
            "nugget": {
                "answer": "Paris",
                "verification_kind": "human",
                "verified_by": "demo",
                "sources": ["https://example.test/paris"],
                "tags": ["domain:geo->desc"],
            },
        },
        MIN_ASK_SCORE=0.5,
    )
    monkeypatch.setattr("nestor.established.jeles_bridge.jeles_corpus", stub)

    # Wrong domain — must miss.
    assert established.recognize_from_jeles(
        "What is the capital?", "en", "es"
    ) is None
    # Right domain — hits.
    assert established.recognize_from_jeles(
        "What is the capital?", "geo", "desc"
    ) is not None


# --- ledger presence ------------------------------------------------------

def test_ledger_records_the_tier15_draft(store, tmp_path):
    """An established draft that comes out of cascade.translate_segment
    must be visible in the ledger with kind='passage' and
    engine='established'."""
    established.install()
    cascade.translate_segment("42", "number", "meaning", store=store)

    ledger_path = pathlib.Path(cascade._ledger_path())
    text = ledger_path.read_text()
    # At least one passage entry with our engine.
    import json
    seen = False
    for line in text.splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        if e.get("kind") == "passage" and e.get("engine") == "established":
            seen = True
            assert e.get("state") == "draft"
            assert e.get("source_lang") == "number"
            assert e.get("target_lang") == "meaning"
            break
    assert seen, "no established-lane passage entry landed in the ledger"
