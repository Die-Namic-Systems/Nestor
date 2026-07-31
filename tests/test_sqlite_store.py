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
