"""``nestor.seed`` — the demo store that makes a cold ``nestor ui`` land live.

IDEAS §6.107: an empty first screen loses the visitor, so ``--demo`` seeds a
small, honest store across all three recipes. These pin what "honest" means:
sealed rows serve, the draft does not, all three domains are present, and
re-seeding is a no-op rather than a pile of duplicates.
"""
from __future__ import annotations

from nestor import cascade, memory, seed
from nestor.sqlite_store import SqliteStore


def _fresh_store(tmp_path, ledger="ledger.jsonl"):
    cascade.set_ledger_path(str(tmp_path / ledger))
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
    assert counts["sealed"] == 4 and counts["draft"] == 1
    assert counts["aliases"] == 2 and counts["baselines"] == 2
    assert counts["queued"] >= 1


def test_seed_leaves_a_review_queue(tmp_path):
    store = _fresh_store(tmp_path)
    seed.seed_store(store)
    # The Queue tab reads pending segments; a cold demo must not open it empty.
    pending = store.list_segments(status="pending")
    assert len(pending) >= 1


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


def test_is_empty_is_false_for_a_queue_only_store(tmp_path):
    # A store with real, unsealed review work (a document the cascade left) but
    # zero sealed/draft pairs must NOT read as empty — otherwise `--demo` seeds
    # demo rows and a demo signing key over someone's in-progress review.
    store = _fresh_store(tmp_path, "q.jsonl")
    cascade.translate_text("A sentence nobody has sealed yet.", "es",
                           source_lang="en", engine_name="offline", store=store)
    assert memory.stats(store=store)["total"] == 0   # no pairs...
    assert not seed.is_empty(store)                   # ...but not empty


def test_forged_row_is_not_exported(tmp_path, monkeypatch):
    from nestor import portable
    monkeypatch.setenv("NESTOR_SEAL_KEY", "demo-seal-key-for-tests")
    store = _fresh_store(tmp_path, "exp.jsonl")
    seed.seed_store(store, include_forged=True)
    bundle = portable.export_bundle(store=store)
    sources = {p["source_text"] for p in bundle["pairs"]}
    assert seed._FORGED_SOURCE not in sources   # the forged row does not travel
    assert "Good night." in sources             # genuine rows still export


def test_forged_row_needs_signing_and_is_refused(tmp_path, monkeypatch):
    # Signing OFF: the forged row is a no-op — with seal_is_valid trusting stored
    # status, it would read as servable, which is the opposite of the lesson.
    off = _fresh_store(tmp_path, "off.jsonl")
    assert seed.seed_store(off, include_forged=True)["forged"] == 0

    # Signing ON: the forged row is written, scores a perfect match, and is
    # refused — while a genuine seal signed under the same key still serves.
    monkeypatch.setenv("NESTOR_SEAL_KEY", "demo-seal-key-for-tests")
    on = _fresh_store(tmp_path, "on.jsonl")
    assert seed.seed_store(on, include_forged=True)["forged"] == 1
    assert memory.best_sealed("Good night.", "en", "es", store=on) is not None
    assert memory.best_sealed(seed._FORGED_SOURCE, "en", "es", store=on) is None


def test_cmd_demo_redirects_any_spelling_of_the_default(tmp_path, monkeypatch):
    # `--db ./data/nestor.db` (or any path that resolves to the default) must be
    # redirected to the demo store, never seed the real default.
    from nestor import cascade, cli
    monkeypatch.chdir(tmp_path)
    cascade._verified_ledgers.clear()
    cascade._checkpoints.clear()
    assert cli.main(["--db", "./data/nestor.db", "--json", "demo"]) == 0
    assert (tmp_path / "data" / "nestor-demo.db").exists()   # redirected here
    assert not (tmp_path / "data" / "nestor.db").exists()    # real default untouched


def test_cmd_demo_refuses_a_nonempty_store(tmp_path, monkeypatch, capsys):
    # A second `nestor demo` must refuse rather than pile up a duplicate queue.
    from nestor import cascade, cli
    from nestor.sqlite_store import SqliteStore
    monkeypatch.chdir(tmp_path)
    cascade._verified_ledgers.clear()
    cascade._checkpoints.clear()
    db = str(tmp_path / "demo.db")
    assert cli.main(["--db", db, "--json", "demo"]) == 0
    capsys.readouterr()
    assert cli.main(["--db", db, "--json", "demo"]) == 0
    assert '"seeded": false' in capsys.readouterr().out
    s = SqliteStore(db)
    s.init_db()
    s.memory_init()
    assert len(s.list_documents()) == 1              # not doubled
    assert len(s.list_segments(status="pending")) == 3


def test_seed_is_rerunnable(tmp_path):
    store = _fresh_store(tmp_path)
    seed.seed_store(store)
    before = memory.stats(store=store)["total"]
    seed.seed_store(store)  # same verifier, same sources — corrections, not duplicates
    assert memory.stats(store=store)["total"] == before
