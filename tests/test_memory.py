import pytest

from nestor import memory


def test_lookup_seal_roundtrip_via_storage(store):
    # Insert a draft, look it up, seal it, confirm the seal took.
    memory.add_pair("Thank you", "Gracias", "en", "es", status="draft", store=store)

    matches = memory.lookup("Thank you", "en", "es", store=store)
    assert matches
    assert matches[0]["similarity"] == 1.0
    assert matches[0]["pair"]["status"] == "draft"
    # A draft is not a tier-1 sealed hit yet.
    assert memory.best_sealed("Thank you", "en", "es", store=store) is None

    # Seal it (add_pair upgrades the existing row via Storage.memory_seal).
    sealed = memory.add_pair("Thank you", "Gracias", "en", "es",
                             status="sealed", verifier="bob", store=store)
    assert sealed["status"] == "sealed"

    hit = memory.best_sealed("Thank you", "en", "es", store=store)
    assert hit is not None
    assert hit["pair"]["verifier"] == "bob"


def test_add_pair_upsert_does_not_duplicate(store):
    memory.add_pair("Hi", "Hola", "en", "es", status="draft", store=store)
    memory.add_pair("Hi", "Hola", "en", "es", status="sealed", store=store)
    stats = memory.stats(store=store)
    assert stats["total"] == 1
    assert stats["sealed"] == 1
    assert stats["draft"] == 0


def test_fuzzy_match_below_seal_threshold_is_not_tier1(store):
    memory.add_pair("The weather is nice today", "Hace buen tiempo hoy",
                    "en", "es", status="sealed", store=store)
    # Similar but not near-identical -> a context-level match, not a tier-1 seal.
    hit = memory.best_sealed("The weather is quite bad today", "en", "es", store=store)
    assert hit is None


def test_seed_from_corpus_uses_injected_loader(store):
    def loader():
        return [
            {"front": "cat", "back": "gato", "lang_front": "en",
             "lang_back": "es", "lesson": "animals"},
        ]
    count = memory.seed_from_corpus(loader=loader, store=store)
    assert count == 2  # both directions
    assert memory.best_sealed("cat", "en", "es", store=store)["pair"]["target_text"] == "gato"
    assert memory.best_sealed("gato", "es", "en", store=store)["pair"]["target_text"] == "cat"


def test_seed_from_corpus_default_loader_is_empty(store):
    assert memory.seed_from_corpus(store=store) == 0
