"""Schema versioning: an older on-disk database is upgraded deterministically,
and one from a newer build is refused rather than silently mis-read.

The decision store (``nestor/sqlite_store.py``) records its schema GENERATION in
the file header via ``PRAGMA user_version``. Two mechanisms hang off it and both
are gated here:

* **Forward migration.** A database written by an older build opens against the
  current one, is carried up to :data:`SCHEMA_VERSION` — through the idempotent
  self-heal ladder for a pre-versioning file, and through the ordered
  ``_FORWARD_MIGRATIONS`` ladder for a real generation gap — and keeps every row
  it held. This is the one path a real deployment runs that the rest of the
  suite never does: every other test builds its schema and its rows in the same
  breath, so a migration has only ever met an empty database.
* **The refusal.** A file whose ``user_version`` is *ahead* of this build must
  make the store REFUSE to open, loudly. A newer generation may carry a table,
  a column, or a constraint meaning this code cannot see; reading it blind is
  how a store starts answering "no verified answers" from a schema it
  half-understands, and rewriting it (``_ensure_embedding_schema`` drops and
  rebuilds a cache table) is how it loses a newer row. A guard that cannot fail
  is not a gate, so the refusal is asserted by attempting the forbidden open and
  requiring the raise — then shown to be specifically the version by opening the
  *same file* at a legal generation and watching it succeed.

Ported from the two fleet examples that already ship this shape:
safe-app-store/apps/marching-arts (the ordered, append-only migration ladder and
its migratability suite) and UTETY's ``utety/core/store.py`` (the
newer-``user_version`` refusal). This module simulates an older or newer writer
by stamping ``user_version`` directly on the file, and drives the forward ladder
over a two-generation world with injected steps — the store has had exactly one
generation so far, so the ladder is proven wired rather than merely declared.
"""
from __future__ import annotations

import sqlite3

import pytest

from nestor import memory, sqlite_store
from nestor.sqlite_store import SqliteStore, StoreSchemaTooNewError


def _version_on_disk(path: str) -> int:
    """The header ``user_version`` as an independent reader sees it."""
    conn = sqlite3.connect(path)
    try:
        return conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()


def _stamp_version_on_disk(path: str, version: int) -> None:
    """Simulate a writer that left the file at ``version``.

    Checkpoints so the change lands in the main file rather than a WAL another
    connection might or might not read, which is the kind of flakiness a
    migration test must not have.
    """
    conn = sqlite3.connect(path)
    try:
        conn.execute(f"PRAGMA user_version = {int(version)}")
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def _seal_hello(store: SqliteStore) -> None:
    """One sealed pair, the row whose survival across a migration is the point."""
    memory.add_pair("hello", "hola", "en", "es", status="sealed",
                    verifier="rita", store=store)


# ── a fresh database is stamped with the current generation ───────────────────


def test_a_fresh_database_lands_at_the_current_generation(tmp_path):
    """The floor everything else stands on: initializing a new store leaves the
    header at :data:`SCHEMA_VERSION`, so the next open knows what wrote it."""
    path = str(tmp_path / "fresh.db")
    store = SqliteStore(path)
    store.memory_init()
    with store._db() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == \
            sqlite_store.SCHEMA_VERSION
    store.close()
    assert _version_on_disk(path) == sqlite_store.SCHEMA_VERSION


def test_an_in_memory_database_is_versioned_too(tmp_path):
    """The ``:memory:`` path shares ``_apply_schema``; a shared connection must
    be stamped like a file so the refusal below is not a file-only guarantee."""
    store = SqliteStore(":memory:")
    store.memory_init()
    with store._db() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == \
            sqlite_store.SCHEMA_VERSION


# ── an older database migrates up, and its data survives ──────────────────────


def test_an_older_database_is_migrated_up_and_its_data_survives(tmp_path):
    """A pre-versioning file (``user_version`` 0) opened by this build is carried
    to the current generation by the idempotent self-heal, and the sealed row it
    already held is still there and still findable afterwards.

    The forbidden alternative this refuses is the one a real deployment would
    hit: an older on-disk database that either raises on first read or is
    silently mis-stamped, with the season's verified pairs the cost.
    """
    path = str(tmp_path / "last-season.db")
    store = SqliteStore(path)
    _seal_hello(store)
    assert memory.stats(store=store)["sealed"] == 1
    store.close()

    # rewind to a pre-versioning writer: rows present, generation unrecorded
    _stamp_version_on_disk(path, 0)
    assert _version_on_disk(path) == 0

    upgraded = SqliteStore(path)
    upgraded.memory_init()
    with upgraded._db() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == \
            sqlite_store.SCHEMA_VERSION
    # the row survived the upgrade, and still resolves through the live path
    assert memory.stats(store=upgraded)["sealed"] == 1
    found = upgraded.memory_find(memory._norm("hello"), "en", "es")
    assert found is not None and found["target_text"] == "hola"
    upgraded.close()
    assert _version_on_disk(path) == sqlite_store.SCHEMA_VERSION


def test_migrating_an_older_database_is_idempotent(tmp_path):
    """Opening a migrated file a second time changes nothing — no re-stamp storm,
    no double-run. Idempotence from the outside, the way marching-arts checks it."""
    path = str(tmp_path / "twice.db")
    store = SqliteStore(path)
    _seal_hello(store)
    store.close()
    _stamp_version_on_disk(path, 0)

    first = SqliteStore(path)
    first.memory_init()
    first.close()
    assert _version_on_disk(path) == sqlite_store.SCHEMA_VERSION

    second = SqliteStore(path)
    second.memory_init()
    assert memory.stats(store=second)["sealed"] == 1
    second.close()
    assert _version_on_disk(path) == sqlite_store.SCHEMA_VERSION


# ── a newer database is refused, not silently opened ──────────────────────────


def test_a_newer_database_is_refused_by_memory_init(tmp_path):
    """The core fail-loud gate. A file one generation ahead of this build makes
    ``memory_init`` raise :class:`StoreSchemaTooNewError` — it does not open."""
    path = str(tmp_path / "from-the-future.db")
    store = SqliteStore(path)
    _seal_hello(store)
    store.close()

    _stamp_version_on_disk(path, sqlite_store.SCHEMA_VERSION + 1)

    newer = SqliteStore(path)
    with pytest.raises(StoreSchemaTooNewError):
        newer.memory_init()


def test_a_newer_database_is_refused_by_init_db_too(tmp_path):
    """The other entry point shares the guard, because both route through
    ``_apply_schema``. A refusal on one path and a silent open on the other would
    be exactly the second-door defect the store's own comments warn about."""
    path = str(tmp_path / "future-init.db")
    SqliteStore(path).init_db()
    _stamp_version_on_disk(path, sqlite_store.SCHEMA_VERSION + 5)

    with pytest.raises(StoreSchemaTooNewError):
        SqliteStore(path).init_db()


def test_a_refused_store_does_not_answer_from_the_schema_it_half_understands(tmp_path):
    """The refusal reaches the public read path, not just the initializer. A
    caller that goes through ``memory.stats`` (which opens the store) must hear
    the raise rather than get a plausible number back from a schema this build
    cannot vouch for."""
    path = str(tmp_path / "no-quiet-read.db")
    store = SqliteStore(path)
    _seal_hello(store)
    store.close()

    _stamp_version_on_disk(path, sqlite_store.SCHEMA_VERSION + 1)
    with pytest.raises(StoreSchemaTooNewError):
        memory.stats(store=SqliteStore(path))


def test_the_refusal_is_the_version_and_nothing_else(tmp_path):
    """Proves the guard *can* fail, and fails for the stated reason.

    The same file that was refused a generation ahead opens cleanly once its
    header is stamped back to a legal generation, and the data is intact. If the
    raise came from a corrupt file rather than the version, this would not
    recover — so this is what separates a real gate from a test that passes
    because the file happened to be broken.
    """
    path = str(tmp_path / "recoverable.db")
    store = SqliteStore(path)
    _seal_hello(store)
    store.close()

    _stamp_version_on_disk(path, sqlite_store.SCHEMA_VERSION + 1)
    with pytest.raises(StoreSchemaTooNewError):
        SqliteStore(path).memory_init()

    # the file is fine; only the recorded generation was ahead
    _stamp_version_on_disk(path, sqlite_store.SCHEMA_VERSION)
    ok = SqliteStore(path)
    ok.memory_init()
    assert memory.stats(store=ok)["sealed"] == 1


# ── the ordered forward ladder actually migrates, in order, once each ─────────


def test_the_forward_ladder_applies_exactly_the_steps_above_the_stored_generation(
        tmp_path, monkeypatch):
    """The ``_FORWARD_MIGRATIONS`` mechanism, driven over a two-generation world.

    The store has had one generation, so the real ladder is empty; a real,
    injected step is what proves the loop is wired rather than declared. Under a
    build that knows two further generations, a generation-N file runs both new
    steps in order and stops; a file already at N+1 runs only the step above it;
    a file at head runs none. The sealed row from the older build survives every
    hop. Same contract as marching-arts' migratability suite, minus its domain.
    """
    path = str(tmp_path / "ladder.db")
    base = sqlite_store.SCHEMA_VERSION

    # a genuine generation-N database, written by today's build
    store = SqliteStore(path)
    _seal_hello(store)
    store.close()
    assert _version_on_disk(path) == base

    ran: list[str] = []

    def step_a(conn):
        conn.execute("CREATE TABLE IF NOT EXISTS ladder_probe_a (n INTEGER)")
        ran.append("a")

    def step_b(conn):
        conn.execute("CREATE TABLE IF NOT EXISTS ladder_probe_b (n INTEGER)")
        ran.append("b")

    monkeypatch.setattr(sqlite_store, "SCHEMA_VERSION", base + 2)
    monkeypatch.setattr(SqliteStore, "_FORWARD_MIGRATIONS",
                        [(base + 1, step_a), (base + 2, step_b)])

    # N → both steps, in order, and the pair is carried through
    up = SqliteStore(path)
    up.memory_init()
    assert ran == ["a", "b"]
    assert memory.stats(store=up)["sealed"] == 1
    up.close()
    assert _version_on_disk(path) == base + 2

    # head → nothing re-runs (run-once)
    ran.clear()
    again = SqliteStore(path)
    again.memory_init()
    assert ran == []
    again.close()

    # a file left one generation short → only the step above it
    _stamp_version_on_disk(path, base + 1)
    ran.clear()
    partial = SqliteStore(path)
    partial.memory_init()
    assert ran == ["b"]
    partial.close()
    assert _version_on_disk(path) == base + 2


def test_a_newer_database_is_refused_even_with_forward_steps_registered(
        tmp_path, monkeypatch):
    """The refusal is the version ceiling, above the top registered step — not a
    gap between steps. A file two generations past the highest known step is
    refused, so a forward ladder can never be talked into reading a future
    file."""
    path = str(tmp_path / "future-ladder.db")
    base = sqlite_store.SCHEMA_VERSION
    SqliteStore(path).init_db()

    monkeypatch.setattr(sqlite_store, "SCHEMA_VERSION", base + 1)
    monkeypatch.setattr(SqliteStore, "_FORWARD_MIGRATIONS",
                        [(base + 1, lambda conn: None)])
    _stamp_version_on_disk(path, base + 9)

    with pytest.raises(StoreSchemaTooNewError):
        SqliteStore(path).memory_init()


# ── the first real migration: visibility on tm_pairs (v1 → v2) ──────────────


def test_the_first_real_migration_adds_visibility_to_a_v1_store(tmp_path):
    """The machinery is no longer proven only by test injection — ``_migrate_v2``
    is a real step on the real ladder. A version-1 store (no ``visibility``
    column) opens, migrates to v2, and every row defaults to ``'internal'``.

    This is the acceptance criterion §91 names: a fixture store pinned at
    version N-1, asserted to open, migrate, and keep its data.
    """
    path = str(tmp_path / "v1-store.db")

    # Build a v1 store: full current schema minus the visibility column.
    # Stamp user_version=1 so the forward ladder sees it as generation 1.
    conn = sqlite3.connect(path)
    # Create tm_pairs WITHOUT visibility (the v1 shape).
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tm_pairs (
            id            TEXT PRIMARY KEY,
            source_text   TEXT NOT NULL,
            source_norm   TEXT NOT NULL,
            source_lang   TEXT NOT NULL,
            target_text   TEXT NOT NULL,
            target_lang   TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'draft',
            verifier      TEXT NOT NULL DEFAULT '',
            weight        REAL NOT NULL DEFAULT 1.0,
            origin        TEXT NOT NULL DEFAULT '',
            created_at    TEXT NOT NULL,
            seal_sig      TEXT NOT NULL DEFAULT '',
            reason        TEXT NOT NULL DEFAULT '',
            superseded_by TEXT NOT NULL DEFAULT ''
        );
    """)
    conn.execute(
        "INSERT INTO tm_pairs (id, source_text, source_norm, source_lang, "
        "target_text, target_lang, status, verifier, weight, origin, "
        "created_at, seal_sig, reason, superseded_by) VALUES "
        "(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("test-id", "hello", "hello", "en", "hola", "es", "sealed",
         "rita", 1.0, "", "2025-01-01T00:00:00Z", "", "", ""))
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()

    # Open with the current code: should migrate v1 → v2.
    store = SqliteStore(path)
    store.memory_init()

    # The version is now 2.
    assert _version_on_disk(path) == 2

    # The visibility column exists and defaults to 'internal'.
    with store._db() as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(tm_pairs)")}
        assert "visibility" in cols
        row = c.execute("SELECT visibility FROM tm_pairs WHERE id='test-id'"
                        ).fetchone()
        assert row[0] == "internal"

    # The sealed pair survived.
    pair = store.memory_get("test-id")
    assert pair is not None
    assert pair["target_text"] == "hola"
    assert pair["status"] == "sealed"
    store.close()


# ── the non-idempotent guard: a step that is not safe to replay goes red ────


def test_a_non_idempotent_migration_step_is_caught_by_replay(
        tmp_path, monkeypatch):
    """Acceptance criterion §91: *a migration deliberately made non-idempotent
    goes red — the mutation-guard discipline applied to the ladder itself.*

    A step that uses ``CREATE TABLE`` (not ``IF NOT EXISTS``) succeeds once
    and raises on replay. The test runs the step twice on the same store —
    once at its target version, then after stamping back to a version below
    it — and the second run is expected to fail. This is the shape every
    migration author should test against, and the fact that it catches the
    fault is the proof the framework needs.
    """
    path = str(tmp_path / "non-idem.db")
    base = sqlite_store.SCHEMA_VERSION

    store = SqliteStore(path)
    store.memory_init()
    store.close()

    def bad_step(conn):
        # Deliberately NOT idempotent: no IF NOT EXISTS.
        conn.execute("CREATE TABLE bad_probe (n INTEGER)")

    monkeypatch.setattr(sqlite_store, "SCHEMA_VERSION", base + 1)
    monkeypatch.setattr(SqliteStore, "_FORWARD_MIGRATIONS",
                        [(base + 1, bad_step)])

    # First run: stamp is at base, step targets base+1 — succeeds.
    first = SqliteStore(path)
    first.memory_init()
    first.close()
    assert _version_on_disk(path) == base + 1

    # Rewind the stamp so the step would replay.
    _stamp_version_on_disk(path, base)

    # Second run: the table already exists, so the non-idempotent step raises.
    second = SqliteStore(path)
    with pytest.raises(sqlite3.OperationalError, match="already exists"):
        second.memory_init()


# ── the real ladder's shape is locked, so a future edit cannot renumber it ────


def test_the_real_forward_ladder_is_ordered_and_within_the_current_generation():
    """A structural lock on ``_FORWARD_MIGRATIONS``, in the spirit of
    marching-arts' ``no_migration_is_renumbered`` test.

    Targets must be strictly increasing (append, never insert-ahead), each a
    positive generation no greater than :data:`SCHEMA_VERSION` (a step above the
    current version can never run and is a sign the constant was not bumped with
    it), and each step callable. Vacuously satisfied while the ladder is empty,
    and precisely the guard that catches the first bad entry once it is not.
    """
    ladder = SqliteStore._FORWARD_MIGRATIONS
    targets = [t for t, _ in ladder]
    assert targets == sorted(set(targets)), "targets must be unique and increasing"
    for target, step in ladder:
        assert 1 <= target <= sqlite_store.SCHEMA_VERSION, (
            f"migration target {target} is outside 1..{sqlite_store.SCHEMA_VERSION}")
        assert callable(step)
