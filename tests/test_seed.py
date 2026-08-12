"""``nestor.seed`` — the demo store that makes a cold ``nestor ui`` land live.

IDEAS §6.107: an empty first screen loses the visitor, so ``--demo`` seeds a
small, honest store across all three recipes. These pin what "honest" means:
sealed rows serve, the draft does not, all three domains are present, and
re-seeding is a no-op rather than a pile of duplicates.
"""
from __future__ import annotations

from nestor import cascade, memory, seed
from nestor.sqlite_store import SqliteStore


def _fresh_store(tmp_path):
    cascade.set_ledger_path(str(tmp_path / "ledger.jsonl"))
    cascade._verified_ledgers.clear()
    cascade._checkpoints.clear()
    store = SqliteStore(":memory:")
    store.init_db()
    store.memory_init()
    return store


def test_is_empty_then_seeded(tmp_path):
    store = _fresh_store(tmp_path)
    assert seed.is_empty(store)
    counts = seed.seed_store(store)
    assert not seed.is_empty(store)
    assert counts == {"sealed": 4, "draft": 1, "aliases": 2, "baselines": 2}


def test_seed_covers_all_three_recipes(tmp_path):
    store = _fresh_store(tmp_path)
    seed.seed_store(store)
    stats = memory.stats(store=store)
    pairs = {(sl, tl) for sl, tl, _ in stats["lang_pairs"]}
    targets = {tl for _, tl, _ in stats["lang_pairs"]}
    assert ("en", "es") in pairs          # translation
    assert ("entity", "entity") in pairs  # entity aliases
    assert "value" in targets             # numeric baselines, keyed <label> → value


def test_a_sealed_row_serves_and_the_draft_does_not(tmp_path):
    store = _fresh_store(tmp_path)
    seed.seed_store(store)
    assert memory.best_sealed("Good night.", "en", "es", store=store) is not None
    assert memory.best_sealed("Ship it.", "en", "es", store=store) is None


def test_seed_is_rerunnable(tmp_path):
    store = _fresh_store(tmp_path)
    seed.seed_store(store)
    before = memory.stats(store=store)["total"]
    seed.seed_store(store)  # same verifier, same sources — corrections, not duplicates
    assert memory.stats(store=store)["total"] == before
