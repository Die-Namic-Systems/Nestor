import pytest

from nestor import memory, storage
from nestor.cascade import translate_segment
from nestor.segment import _split_segments


# --- _split_segments: must match the host's original behavior ---------------

def test_split_segments_paragraphs_when_three_or_more():
    text = "Para one.\n\nPara two.\n\nPara three."
    assert _split_segments(text) == ["Para one.", "Para two.", "Para three."]


def test_split_segments_falls_back_to_sentences_when_few_paragraphs():
    text = "First sentence. Second sentence! Third one?"
    assert _split_segments(text) == ["First sentence.", "Second sentence!", "Third one?"]


def test_split_segments_strips_and_drops_empty():
    text = "  Only one paragraph here.  "
    assert _split_segments(text) == ["Only one paragraph here."]


# --- store-not-set raises a clear error -------------------------------------

def test_get_store_raises_clear_error_when_unset():
    # isolate_globals fixture guarantees _store is None here.
    with pytest.raises(RuntimeError) as exc:
        storage.get_store()
    assert "storage is not configured" in str(exc.value)
    assert "set_store" in str(exc.value)


def test_public_entry_raises_without_store():
    with pytest.raises(RuntimeError):
        translate_segment("hello", "en", "es")


def test_explicit_store_beats_missing_global(store):
    # No global set, but explicit store= works.
    p = translate_segment("hello", "en", "es", store=store)
    assert p is not None


def test_set_store_makes_global_available(store):
    storage.set_store(store)
    # No store= passed -> resolves the global.
    memory.add_pair("Yes", "Sí", "en", "es", status="sealed")
    assert memory.best_sealed("Yes", "en", "es") is not None


def test_reference_store_satisfies_protocol(store):
    # runtime_checkable Protocol structural check.
    assert isinstance(store, storage.Storage)
