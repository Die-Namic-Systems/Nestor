"""Reference store: schema invariants the Protocol assumes."""

from __future__ import annotations

import warnings

import pytest

from nestor import memory
from nestor.sqlite_store import SqliteStore


def _pair_row(pair_id: str, source: str, norm: str, target: str) -> tuple:
    return (pair_id, source, norm, "en", target, "es", "sealed", "rita",
            1.0, "", "2026-07-31T00:00:00+00:00", "")


def test_memory_init_indexes_source_norm_for_memory_find(tmp_path):
    """IDEAS §2.3 — memory_find on every add_pair must not table-scan."""
    db = tmp_path / "nestor.db"
    store = SqliteStore(str(db))
    store.memory_init()
    memory.add_pair("hello", "hola", "en", "es", status="sealed",
                    verifier="rita", store=store)

    with store._db() as conn:
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='tm_pairs'")}
        assert "idx_tm_pairs_key" in names

        norm = memory._norm("hello")
        plan = conn.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM tm_pairs "
            "WHERE source_norm=? AND source_lang=? AND target_lang=?",
            (norm, "en", "es"),
        ).fetchall()
    plan_text = " ".join(str(cell) for row in plan for cell in row).lower()
    assert "idx_tm_pairs" in plan_text


def test_a_duplicate_norm_database_still_indexes_lookups(tmp_path):
    """Without uniqueness, ingest must not fall back to a full scan either."""
    from nestor import sqlite_store as sm

    db = str(tmp_path / "dup.db")
    store = SqliteStore(db)
    norm = memory._norm("shared source")
    with store._db() as conn:
        conn.executescript(sm._SCHEMA)
        conn.executemany(
            "INSERT INTO tm_pairs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            [_pair_row("a", "shared source", norm, "one"),
             _pair_row("b", "shared source", norm, "two")],
        )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        SqliteStore(db).memory_init()
    assert any("more than one" in str(w.message) for w in caught)

    with SqliteStore(db)._db() as conn:
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='tm_pairs'")}
    assert "idx_tm_pairs_find" in names
    assert "idx_tm_pairs_key" not in names


def _sealed_pair(store, source="hello world", target="hola mundo") -> str:
    return memory.add_pair(source, target, "en", "es", status="sealed",
                           verifier="rita", store=store)["id"]


def test_tm_embeddings_roundtrip(tmp_path):
    from nestor.embedding_store import blob_to_vec, source_text_sha, vec_to_blob

    store = SqliteStore(str(tmp_path / "emb.db"))
    store.memory_init()
    pair_id = _sealed_pair(store)
    vec = (0.1, 0.2, 0.3, 0.4)
    sha = source_text_sha("hello world")
    store.embedding_save(pair_id, "test-model", sha, vec_to_blob(vec), "sig-x")
    loaded = store.embedding_load(pair_id, "test-model")
    assert loaded is not None
    assert loaded[0] == sha and loaded[2] == "sig-x"
    assert blob_to_vec(loaded[1]) == pytest.approx(vec)
    store.embedding_drop(pair_id)
    assert store.embedding_load(pair_id, "test-model") is None


def test_deleting_a_pair_takes_its_embeddings_with_it(tmp_path):
    """A vector for a row that no longer exists is unreachable by every path
    that reads one, and nothing else prunes the table."""
    from nestor.embedding_store import vec_to_blob

    store = SqliteStore(str(tmp_path / "fk.db"))
    store.memory_init()
    pair_id = _sealed_pair(store)
    store.embedding_save(pair_id, "test-model", "sha", vec_to_blob((0.5, 0.5)), "")

    with store._db() as conn:
        conn.execute("DELETE FROM tm_pairs WHERE id=?", (pair_id,))
        assert conn.execute("SELECT COUNT(*) FROM tm_embeddings").fetchone()[0] == 0


def test_a_pre_sig_embedding_table_is_rebuilt_not_left_to_raise(tmp_path):
    """`CREATE TABLE IF NOT EXISTS` is a no-op on a table that already exists, so
    a database written before `sig` would fail every read. It is a cache: throw
    it away and recompute rather than carry a shape that cannot be verified."""
    db = str(tmp_path / "old.db")
    store = SqliteStore(db)
    store.memory_init()
    with store._db() as conn:
        conn.execute("DROP TABLE tm_embeddings")
        conn.execute("CREATE TABLE tm_embeddings (pair_id TEXT NOT NULL, "
                     "model_name TEXT NOT NULL, source_sha TEXT NOT NULL, "
                     "embedding BLOB NOT NULL, PRIMARY KEY (pair_id, model_name))")
        conn.execute("INSERT INTO tm_embeddings VALUES ('gone','m','sha',X'00')")

    SqliteStore(db).memory_init()
    with SqliteStore(db)._db() as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(tm_embeddings)")}
        assert "sig" in cols
        assert conn.execute("SELECT COUNT(*) FROM tm_embeddings").fetchone()[0] == 0
