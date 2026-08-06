"""Reference store: schema invariants the Protocol assumes."""

from __future__ import annotations

import hashlib
import os
import pathlib
import shutil
import threading
import warnings

import pytest

from nestor import memory, sqlite_store
from nestor.sqlite_store import SqliteStore


def _pair_row(pair_id: str, source: str, norm: str, target: str) -> tuple:
    return (pair_id, source, norm, "en", target, "es", "sealed", "rita",
            1.0, "", "2026-07-31T00:00:00+00:00", "")


def test_file_backed_store_survives_concurrent_add_pair(tmp_path):
    """IDEAS §2.4 — nestor.ui serves from a thread pool on one SqliteStore."""
    store = SqliteStore(str(tmp_path / "threads.db"))
    store.memory_init()
    errors: list[BaseException] = []
    lock = threading.Lock()

    def worker(i: int) -> None:
        try:
            memory.add_pair(f"source {i}", f"target {i}", "en", "es",
                            status="sealed", verifier="rita", store=store)
        except BaseException as exc:
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(24)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert memory.stats(store=store)["sealed"] == 24


def test_file_backed_connection_is_reused_within_a_thread(tmp_path):
    store = SqliteStore(str(tmp_path / "reuse.db"))
    store.memory_init()
    with store._db() as first:
        id_first = id(first)
    with store._db() as second:
        assert id(second) == id_first


def test_the_idle_pool_is_capped_however_many_threads_arrive(tmp_path):
    """The reason this is a pool and not a connection per thread.

    ``nestor.ui`` runs HTTP/1.1 keep-alive on ``ThreadingHTTPServer``, so a
    thread exists per TCP connection: a reload, a reconnect, a monitoring probe.
    Binding a persistent connection to each of them leaves one descriptor per
    thread that ever touched the store, freed by the *cyclic* collector rather
    than promptly — and nothing about running out of descriptors makes Python
    collect. Measured before this cap: under ``ulimit -n 256`` the store failed
    after 340 requests with "unable to open database file", which also refuses
    seals, because the ledger needs to open a file too.
    """
    fd_dir = pathlib.Path("/proc/self/fd")
    if not fd_dir.is_dir():
        pytest.skip("counts open descriptors; needs /proc")

    db = tmp_path / "pooled.db"
    store = SqliteStore(str(db))
    store.memory_init()

    def open_handles() -> int:
        found = 0
        for entry in fd_dir.iterdir():
            try:
                if os.readlink(entry).startswith(str(db)):
                    found += 1
            except OSError:          # the fd closed while we walked
                continue
        return found

    def hammer(rounds: int) -> None:
        for _ in range(rounds):
            threads = [threading.Thread(target=memory.lookup,
                                        args=(f"q{i}", "en", "es"),
                                        kwargs={"store": store}) for i in range(30)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

    hammer(4)                        # fill the pool and create the WAL sidecars
    settled = open_handles()
    hammer(8)                        # 360 threads all told, none of them alive now
    grown = open_handles()
    # Bounded, not monotone: sidecar handles wobble by one or two between
    # interpreter versions, so allow a pool's worth of slack. What this has to
    # catch is growth that *scales with thread count* — the per-thread version
    # measured 156 -> 272 across exactly these two phases.
    assert grown <= settled + sqlite_store._POOL_MAX, (
        f"{grown} descriptors after 360 request threads against {settled} after 120 — "
        f"a connection that outlives its thread is a descriptor nothing closes")
    assert len(store._pool) <= sqlite_store._POOL_MAX


def test_a_closed_store_refuses_rather_than_answering_from_an_empty_one(tmp_path):
    """The failure mode matters more than the failure.

    ``close()`` used to leave ``_shared`` at ``None``, which sent the next call
    down the file path and opened a *fresh* ``:memory:`` database — so a closed
    store answered "0 sealed" instead of refusing. On a package whose product is
    "has a human checked this", a plausible wrong answer is worse than a crash.
    """
    mem = SqliteStore(":memory:")
    mem.memory_init()
    memory.add_pair("hello", "hola", "en", "es", status="sealed",
                    verifier="rita", store=mem)
    assert memory.stats(store=mem)["sealed"] == 1
    mem.close()
    with pytest.raises(sqlite_store.StoreClosedError):
        memory.stats(store=mem)

    disk = SqliteStore(str(tmp_path / "closed.db"))
    disk.memory_init()
    disk.close()
    disk.close()                      # idempotent: shutdown paths run twice
    with pytest.raises(sqlite_store.StoreClosedError):
        memory.stats(store=disk)


def test_close_checkpoints_wal_so_the_main_file_is_self_contained(tmp_path):
    """A plain cp of nestor.db while WAL is open is incomplete; close() fixes it."""
    db = tmp_path / "wal.db"
    store = SqliteStore(str(db))
    store.memory_init()
    memory.add_pair("hello", "hola", "en", "es", status="sealed",
                    verifier="rita", store=store)
    live_copy = tmp_path / "live-snapshot.db"
    shutil.copy(db, live_copy)
    assert memory.stats(store=SqliteStore(str(live_copy)))["sealed"] == 0
    store.close()
    closed_copy = tmp_path / "closed-snapshot.db"
    shutil.copy(db, closed_copy)
    assert memory.stats(store=SqliteStore(str(closed_copy)))["sealed"] == 1


def test_checkpoint_wal_flushes_without_closing(tmp_path):
    db = tmp_path / "wal.db"
    store = SqliteStore(str(db))
    store.memory_init()
    memory.add_pair("hello", "hola", "en", "es", status="sealed",
                    verifier="rita", store=store)
    store.checkpoint_wal()
    snapshot = tmp_path / "after-checkpoint.db"
    shutil.copy(db, snapshot)
    assert memory.stats(store=SqliteStore(str(snapshot)))["sealed"] == 1
    memory.add_pair("bye", "adios", "en", "es", store=store)
    assert memory.stats(store=store)["total"] == 2


def test_close_after_worker_threads_checkpoints_from_main(tmp_path):
    """UI shutdown runs close() on the main thread after pool workers sealed."""
    db = tmp_path / "pool.db"
    store = SqliteStore(str(db))
    store.memory_init()
    errors: list[BaseException] = []
    lock = threading.Lock()

    def worker(i: int) -> None:
        try:
            memory.add_pair(f"src {i}", f"tgt {i}", "en", "es",
                            status="sealed", verifier="rita", store=store)
        except BaseException as exc:
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    store.close()
    copy = tmp_path / "after-close.db"
    shutil.copy(db, copy)
    assert memory.stats(store=SqliteStore(str(copy)))["sealed"] == 6


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
        # Renamed when the index went partial (lineage N3): uniqueness over
        # live rows only, so superseded history can share the key.
        assert "idx_tm_pairs_key_live" in names

        norm = memory._norm("hello")
        # Mirrors memory_find's actual query: the live predicate is what
        # lets SQLite use the partial index at all.
        plan = conn.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM tm_pairs "
            "WHERE source_norm=? AND source_lang=? AND target_lang=? "
            "AND superseded_by=''",
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
            "INSERT INTO tm_pairs (id, source_text, source_norm, source_lang, "
            "target_text, target_lang, status, verifier, weight, origin, "
            "created_at, seal_sig) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
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


# --- IDEAS §6.8: the schema script is idempotent, which is not the same as free.


def _ddl_seen(store) -> list:
    """Statements the store's pooled connection is asked to run, from now on.

    One thread, a pool that hands back the connection it was just given, so the
    trace installed here is the trace on the connection the next call borrows.
    """
    seen: list = []
    with store._db() as conn:
        conn.set_trace_callback(seen.append)
    return seen


def test_memory_init_does_not_replay_the_schema_on_a_warm_connection(tmp_path):
    """§6.8. Twelve public functions in `nestor.memory` open with
    `store.memory_init()`, so the schema script and its three migration probes
    ran once per operation rather than once per connection."""
    store = SqliteStore(str(tmp_path / "n.db"))
    store.memory_init()

    seen = _ddl_seen(store)
    store.memory_init()
    with store._db() as conn:
        conn.set_trace_callback(None)

    ddl = [s for s in seen if any(k in s.upper() for k in ("CREATE ", "DROP ", "ALTER "))]
    assert not ddl, f"the schema was replayed on a connection that had it: {ddl[:3]}"


def test_a_second_store_on_one_file_still_builds_its_own_connection(tmp_path):
    """The flag is per connection, not per database. A second store has its own
    pool, so it must not inherit the first store's belief about a file."""
    db = str(tmp_path / "n.db")
    SqliteStore(db).memory_init()

    other = SqliteStore(db)
    seen = _ddl_seen(other)
    other.memory_init()
    with other._db() as conn:
        conn.set_trace_callback(None)

    assert any("CREATE" in s.upper() for s in seen), (
        "a fresh connection skipped the schema, which means the flag outlived "
        "the connection it describes")


def test_init_db_does_not_excuse_memory_init(tmp_path):
    """A **guard** — it passes before the §6.8 change as well as after, because
    before it there was no flag to set wrongly. It is here because the cheapest
    wrong version of this fix is to mark the connection ready inside `init_db`,
    which applies a strict subset: no `_ensure_lineage_schema`. A connection
    marked by the subset would make `memory_init` skip the ALTERs that bring a
    pre-lineage database up to date, and every `SELECT superseded_by` would
    raise on a database nobody could see was half-migrated."""
    store = SqliteStore(str(tmp_path / "n.db"))
    store.init_db()

    seen = _ddl_seen(store)
    store.memory_init()
    with store._db() as conn:
        conn.set_trace_callback(None)

    assert any("CREATE" in s.upper() for s in seen), (
        "memory_init did no schema work after init_db, so init_db claimed a "
        "completeness it does not deliver")


def test_a_class_attribute_cannot_answer_for_a_connection(tmp_path):
    """The reviewer's reproduction of PR #45, as a gate.

    `_Conn` carried `schema_ready = False` and `memory_init` read it with
    `getattr`. Setting `_Conn.schema_ready = True` therefore made every fresh
    connection claim to be initialized, and `memory_init` on an empty database
    returned having created nothing — the `id(conn)` defect in a different hat.

    Deleting the class default alone would not close this: a class attribute
    still shadows a missing instance one, so `getattr` would keep finding it.
    The read goes through `conn.__dict__`, which takes the class off the lookup
    path entirely.
    """
    # Restore exactly what was there, which is not the same as deleting. The
    # first draft of this test did `del` unconditionally and so *removed* the
    # class default it was written to detect — leaving the shape guard below
    # passing against the unfixed revision, for a reason that had nothing to do
    # with the code under test.
    missing = object()
    original = sqlite_store._Conn.__dict__.get("schema_ready", missing)
    try:
        sqlite_store._Conn.schema_ready = True
        store = SqliteStore(str(tmp_path / "poisoned.db"))
        store.memory_init()
        with store._db() as conn:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        if original is missing:
            del sqlite_store._Conn.schema_ready
        else:
            sqlite_store._Conn.schema_ready = original

    assert "tm_pairs" in tables, (
        "a class attribute answered for a connection, and memory_init returned "
        "on an empty database having created nothing")


def test_conn_declares_no_schema_ready_default():
    """A guard on the shape rather than the behaviour, because the default is
    an invitation even where it is no longer load-bearing: the next person to
    read this class should not find a flag that looks like it can be flipped."""
    assert "schema_ready" not in sqlite_store._Conn.__dict__


#: sha256[:16] of the sorted DDL `memory_init` actually leaves in sqlite_master.
#: Mirrored, not derived from _SCHEMA — deriving it would make the pin true by
#: construction, which is the vacuity `test_ledger_kinds.py` set the precedent
#: against. Stable across interpreters: identical under 3.10/sqlite 3.45.1 and
#: 3.11, because sqlite_master stores the DDL as written.
PINNED_SCHEMA_DIGEST = "f42f4ae579f0c8bd"


def test_a_schema_change_has_to_be_a_deliberate_release_decision(tmp_path):
    """The latch behind `docs/releasing.md`'s restart rule.

    Since IDEAS §6.8, `memory_init` skips its work on a connection that has
    already done it, so a long-lived process does not run a migration
    introduced after its pooled connections were opened. The rule that follows
    — *a release changing the schema must tell operators to restart* — lived
    only in prose, and prose does not fail a build.

    This does. It hashes the DDL `memory_init` leaves behind rather than the
    source that produced it, so comments and refactors move nothing and a real
    change to the database's shape moves it every time.

    Tripping this is not a bug. It means: say the restart line in the release
    notes, and update the digest in the same commit.
    """
    store = SqliteStore(str(tmp_path / "pin.db"))
    store.memory_init()
    with store._db() as conn:
        ddl = sorted(r[0] for r in conn.execute(
            "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL"))

    digest = hashlib.sha256("\n".join(ddl).encode("utf-8")).hexdigest()[:16]
    assert digest == PINNED_SCHEMA_DIGEST, (
        f"the effective schema changed ({PINNED_SCHEMA_DIGEST} -> {digest}).\n"
        f"Since §6.8 a warm connection skips migrations it did not have when it "
        f"was opened, so long-lived processes will NOT pick this up on a package "
        f"upgrade — only on restart. docs/releasing.md requires the release notes "
        f"to say so. Do that, then update PINNED_SCHEMA_DIGEST in this file, in "
        f"the same commit.")
