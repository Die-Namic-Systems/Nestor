"""Three one-liners deferred through three PRs — §6.25, §6.27, §6.29.

Each owns a different surface (the store's migration order, a path seam, the
package's exported vocabulary) and none interacts with the others, which is why
they were kept out of the commits that found them and why they arrive together
now.
"""

from __future__ import annotations

import sqlite3

import pytest

import nestor
from nestor import glossary, memory
from nestor.sqlite_store import SqliteStore

# --- §6.25: init_db on a pre-lineage database ------------------------------

def _pre_lineage_db(path: str) -> None:
    """The 12-column tm_pairs a pre-lineage build wrote. Mirrored, not imported."""
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE tm_pairs (
            id TEXT PRIMARY KEY, source_text TEXT NOT NULL,
            source_norm TEXT NOT NULL, source_lang TEXT NOT NULL,
            target_text TEXT NOT NULL, target_lang TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            verifier TEXT NOT NULL DEFAULT '',
            weight REAL NOT NULL DEFAULT 1.0,
            origin TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
            seal_sig TEXT NOT NULL DEFAULT '');
        INSERT INTO tm_pairs VALUES ('old-1', 'hello', 'hello', 'en',
            'hola', 'es', 'sealed', 'rita', 1.0, '', 'then', 'sig');
    """)
    conn.commit()
    conn.close()


def test_init_db_survives_a_pre_lineage_database(tmp_path):
    """§6.25. `_ensure_unique_key` builds indexes over `superseded_by`, which
    `_ensure_lineage_schema` adds — and `init_db` never called it, so this
    raised `no such column: superseded_by` on any database older than lineage."""
    db = str(tmp_path / "old.db")
    _pre_lineage_db(db)
    store = SqliteStore(db)
    store.init_db()
    assert store.memory_find("hello", "en", "es")["id"] == "old-1"


def test_the_migration_lives_where_the_indexes_need_it(tmp_path):
    """The structural half, and the reason this is not a call-order fix.

    §6.25 proposed reordering the calls inside `init_db`. That works and leaves
    the shape intact — a precondition honoured by convention at call sites, with
    a second path free to forget it, which is the defect `TODO.md`'s closing
    note names. `_ensure_unique_key` owns the migration now, so a caller cannot
    arrive without it. This drives the function directly, past both entry
    points."""
    db = str(tmp_path / "old.db")
    _pre_lineage_db(db)
    store = SqliteStore(db)
    with store._db() as conn:
        store._ensure_unique_key(conn)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(tm_pairs)")}
    assert {"reason", "superseded_by"} <= cols


# --- §6.27: the glossary path ----------------------------------------------

def test_the_glossary_survives_a_change_of_working_directory(tmp_path,
                                                             monkeypatch):
    """§6.27. The path was resolved against the process working directory on
    every call, so a service unit and the shell that entered the terms read
    different files and nothing said so."""
    glossary.set_glossary_path(tmp_path / "g.json")
    try:
        glossary.save({"en->ru": {"Nestor": "Nestor"}})
        monkeypatch.chdir(tmp_path.parent)
        assert glossary.load() == {"en->ru": {"Nestor": "Nestor"}}
    finally:
        glossary.set_glossary_path(None)


def test_the_glossary_path_is_always_absolute(monkeypatch):
    monkeypatch.setenv("NESTOR_GLOSSARY", "relative/glossary.json")
    assert glossary.glossary_path().is_absolute()
    monkeypatch.delenv("NESTOR_GLOSSARY")
    assert glossary.glossary_path().is_absolute()


def test_an_explicit_path_wins_over_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("NESTOR_GLOSSARY", str(tmp_path / "from-env.json"))
    glossary.set_glossary_path(tmp_path / "explicit.json")
    try:
        assert glossary.glossary_path() == (tmp_path / "explicit.json").resolve()
    finally:
        glossary.set_glossary_path(None)
    assert glossary.glossary_path() == (tmp_path / "from-env.json").resolve()


def test_the_default_does_not_move_when_the_process_does(monkeypatch, tmp_path):
    """Captured at import. A `chdir` mid-process must not silently relocate the
    locks a running server is reading."""
    before = glossary.glossary_path()
    monkeypatch.chdir(tmp_path)
    assert glossary.glossary_path() == before


# --- §6.29: the third refusal ----------------------------------------------

@pytest.mark.parametrize("name", ["ConflictingDraftError", "ConflictingSealError",
                                  "RejectedPairError"])
def test_every_refusal_is_on_the_public_surface(name):
    """§6.29. Two of the three were exported and the third was not — and the
    missing one is the refusal that exists to direct a caller to `revise_draft`,
    so the one error telling you what to do next was the one you could not catch
    from `nestor`."""
    assert name in nestor.__all__
    assert getattr(nestor, name) is getattr(memory, name)
