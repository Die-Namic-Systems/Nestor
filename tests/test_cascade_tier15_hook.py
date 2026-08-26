"""``cascade.set_tier15_recognizer`` — the tier-1.5 recognizer seam.

Decision 0205: an optional callable that cascade.translate_segment calls
between the tier-1 sealed lookup and the tier-2 engine call, so an
established-knowledge lane (a lexicon, a trusted corpus like Jeles) can
surface a draft here instead of every consumer monkeypatching
translate_segment.

Contract (locked here):

* No recognizer installed → translate_segment behaves exactly as it did
  before decision 0205.
* Recognizer returns ``None`` → cascade falls through to the tier-2 engine.
* Recognizer returns a draft ``Passage`` → cascade returns it as-is and
  appends the ordinary passage entry to the ledger.
* Recognizer returns a ``Passage`` with ``state == "sealed"`` → ``RuntimeError``.
  The sealed lane stays under the covenant's control at tier 1.
* Recognizer returns a non-``Passage`` value → ``TypeError``.
* ``set_tier15_recognizer(None)`` unregisters — no leakage across tests.
"""
from __future__ import annotations

import pathlib

import pytest

from nestor import cascade, memory
from nestor.cascade import Passage, set_tier15_recognizer
from nestor.sqlite_store import SqliteStore


@pytest.fixture
def store(tmp_path):
    cascade.set_ledger_path(str(tmp_path / "ledger.jsonl"))
    cascade._verified_ledgers.clear()
    cascade._checkpoints.clear()
    st = SqliteStore(":memory:")
    st.init_db()
    st.memory_init()
    yield st
    # Never leak a recognizer into the next test.
    set_tier15_recognizer(None)


# --- no recognizer path is unchanged --------------------------------------

def test_no_recognizer_behaves_as_before(store):
    """With no recognizer installed, translate_segment falls straight through
    to the engine and lands as draft or pending — the pre-0205 shape."""
    assert cascade.get_tier15_recognizer() is None
    passage = cascade.translate_segment(
        "a phrase nobody has sealed", "en", "es", store=store,
    )
    # With no engine draft (OfflineEngine returns nothing for unseeded),
    # the shape is either tier=2 draft or tier=0 pending — both are
    # legitimate no-recognizer outputs.
    assert passage.tier in (0, 2)
    assert passage.state in ("pending", "draft")


def test_sealed_row_still_wins_over_recognizer(store):
    """A sealed hit at tier 1 must never even call the recognizer — the
    sealed lane is authoritative."""
    memory.add_pair("hello", "hola", "en", "es",
                    status="sealed", verifier="test-verifier",
                    origin="test", store=store)
    calls: list[str] = []

    def recognizer(text, source_lang, target_lang, *, store, matcher):
        calls.append(text)
        return Passage(source=text, target="from-recognizer",
                       tier=2, state="draft", engine="test-recognizer",
                       confidence=0.99)

    set_tier15_recognizer(recognizer)
    try:
        passage = cascade.translate_segment("hello", "en", "es", store=store)
    finally:
        set_tier15_recognizer(None)
    assert passage.tier == 1
    assert passage.state == "sealed"
    assert passage.target == "hola"
    assert calls == [], (
        "recognizer was called for a sealed hit; the sealed lane must be "
        "answered by tier 1 without consulting the recognizer at all")


# --- recognizer return handling -------------------------------------------

def test_recognizer_returning_none_falls_through(store):
    """A recognizer that declines (returns None) must not short-circuit
    the tier-2 engine — the engine still gets its shot."""
    def recognizer(text, source_lang, target_lang, *, store, matcher):
        return None

    set_tier15_recognizer(recognizer)
    passage = cascade.translate_segment(
        "another unseen phrase", "en", "es", store=store,
    )
    assert passage.tier in (0, 2)
    assert passage.engine != "test-recognizer"


def test_recognizer_draft_is_served_as_is(store):
    """A recognizer that returns a draft Passage: cascade returns it
    verbatim, without asking the engine."""
    def recognizer(text, source_lang, target_lang, *, store, matcher):
        return Passage(
            source=text,
            target="from-recognizer",
            tier=2,
            state="draft",
            engine="established-lexicon",
            confidence=0.95,
            meta={"rung": "established", "provider": "lexicon"},
        )

    set_tier15_recognizer(recognizer)
    passage = cascade.translate_segment(
        "42", "number", "meaning", store=store,
    )
    assert passage.state == "draft"
    assert passage.engine == "established-lexicon"
    assert passage.target == "from-recognizer"
    assert passage.confidence == pytest.approx(0.95)


def test_recognizer_receives_the_cascade_context(store):
    """The recognizer must be called with the same (text, source_lang,
    target_lang, store, matcher) the cascade is using — that is the entire
    reason it is a callback rather than a monkeypatch."""
    seen: dict = {}

    def recognizer(text, source_lang, target_lang, *, store, matcher):
        seen.update(text=text, source_lang=source_lang,
                    target_lang=target_lang, store=store, matcher=matcher)

    set_tier15_recognizer(recognizer)
    cascade.translate_segment("hello world", "en", "es", store=store)
    assert seen["text"] == "hello world"
    assert seen["source_lang"] == "en"
    assert seen["target_lang"] == "es"
    assert seen["store"] is store
    # matcher may be None if the cascade caller didn't pass one, which is
    # the shape the recognizer needs to be ready for.
    assert "matcher" in seen


# --- refusal contract ------------------------------------------------------

def test_recognizer_returning_sealed_passage_refused(store):
    """A recognizer that returned a sealed passage would smuggle a seal
    past the ledger's evidence rules. RuntimeError, before the ledger sees
    anything."""
    def recognizer(text, source_lang, target_lang, *, store, matcher):
        return Passage(source=text, target="sneaky-seal",
                       tier=1, state="sealed", engine="pretend-memory",
                       confidence=1.0)

    set_tier15_recognizer(recognizer)
    with pytest.raises(RuntimeError, match=r"state='sealed'.*decision 0205"):
        cascade.translate_segment("42", "number", "meaning", store=store)


def test_recognizer_returning_non_passage_refused(store):
    """The seam's return type is Passage-or-None; anything else is a
    programming error caught at the boundary, not silently coerced."""
    def recognizer(text, source_lang, target_lang, *, store, matcher):
        return {"target": "hola", "tier": 2, "state": "draft"}  # not a Passage

    set_tier15_recognizer(recognizer)
    with pytest.raises(TypeError, match=r"must return Passage or None"):
        cascade.translate_segment("hello", "en", "es", store=store)


# --- register / unregister -------------------------------------------------

def test_set_none_unregisters(store):
    """Passing None to set_tier15_recognizer clears the recognizer — the
    cascade goes back to its pre-0205 shape."""
    def recognizer(text, source_lang, target_lang, *, store, matcher):
        return Passage(source=text, target="from-recognizer",
                       tier=2, state="draft", engine="test",
                       confidence=1.0)

    set_tier15_recognizer(recognizer)
    assert cascade.get_tier15_recognizer() is recognizer
    set_tier15_recognizer(None)
    assert cascade.get_tier15_recognizer() is None

    passage = cascade.translate_segment("hello", "en", "es", store=store)
    assert passage.engine != "test"


def test_second_install_replaces_first(store):
    """Calling set_tier15_recognizer twice replaces the first — a warning
    is not raised (decision 0205 Q2 names list-of-recognizers as the wider
    design if two lanes ever need to co-exist)."""
    calls: list[str] = []

    def first(text, source_lang, target_lang, *, store, matcher):
        calls.append("first")

    def second(text, source_lang, target_lang, *, store, matcher):
        calls.append("second")

    set_tier15_recognizer(first)
    set_tier15_recognizer(second)
    cascade.translate_segment("hello", "en", "es", store=store)
    assert calls == ["second"]


# --- ledger integration ---------------------------------------------------

def test_ledger_receives_tier15_passage_entry(store, tmp_path):
    """The ledger append happens uniformly at the bottom of
    translate_segment, so a tier-1.5 draft gets logged with the ordinary
    passage-entry shape — engine, tier, state, confidence, source_lang,
    target_lang all recorded."""
    def recognizer(text, source_lang, target_lang, *, store, matcher):
        return Passage(source=text, target="the-target",
                       tier=2, state="draft", engine="my-recognizer",
                       confidence=0.87)

    set_tier15_recognizer(recognizer)
    cascade.translate_segment("42", "number", "meaning", store=store)

    ledger_path = pathlib.Path(cascade._ledger_path())
    entries = [line for line in ledger_path.read_text().splitlines() if line.strip()]
    assert entries, "no ledger entry landed for the tier-1.5 draft"
    import json
    last = json.loads(entries[-1])
    assert last["kind"] == "passage"
    assert last["engine"] == "my-recognizer"
    assert last["state"] == "draft"
    assert last["confidence"] == pytest.approx(0.87)
    assert last["source_lang"] == "number"
    assert last["target_lang"] == "meaning"
