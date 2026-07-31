"""Reference SQLite implementation of the :class:`nestor.storage.Storage` Protocol.

Self-contained: it owns exactly the tables Nestor needs — ``documents``,
``segments`` and the translation-memory ``tm_pairs`` — so Nestor runs
end-to-end standalone. Minimal on purpose; a real host would back the same
Protocol with its own richer schema.

Usage::

    from nestor import storage
    from nestor.sqlite_store import SqliteStore

    storage.set_store(SqliteStore("data/nestor.db"))   # or ":memory:"
"""
from __future__ import annotations

import sqlite3
import threading
import uuid
import warnings
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    source_lang TEXT NOT NULL DEFAULT 'en',
    target_lang TEXT NOT NULL DEFAULT 'es',
    status      TEXT NOT NULL DEFAULT 'pending_review',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS segments (
    id          TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id),
    position    INTEGER NOT NULL,
    source_text TEXT NOT NULL,
    candidate   TEXT DEFAULT '',
    jeles_score REAL DEFAULT 0.0,
    status      TEXT NOT NULL DEFAULT 'pending',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tm_pairs (
    id          TEXT PRIMARY KEY,
    source_text TEXT NOT NULL,
    source_norm TEXT NOT NULL,
    source_lang TEXT NOT NULL,
    target_text TEXT NOT NULL,
    target_lang TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'draft',
    verifier    TEXT NOT NULL DEFAULT '',
    weight      REAL NOT NULL DEFAULT 1.0,
    origin      TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    seal_sig    TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tm_rejections (
    id          TEXT PRIMARY KEY,
    query_norm  TEXT NOT NULL,
    source_lang TEXT NOT NULL,
    target_lang TEXT NOT NULL,
    pair_id     TEXT NOT NULL DEFAULT '',
    target_text TEXT NOT NULL DEFAULT '',
    verifier    TEXT NOT NULL DEFAULT '',
    reason      TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    reject_sig  TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_segments_document ON segments(document_id);
CREATE INDEX IF NOT EXISTS idx_tm_langs ON tm_pairs(source_lang, target_lang, status);
-- Rejections are read on the hot path (every lookup), keyed by exactly this
-- triple. tm_pairs.source_norm is indexed via idx_tm_pairs_key (see below).
CREATE INDEX IF NOT EXISTS idx_tm_rejections_query
    ON tm_rejections(query_norm, source_lang, target_lang);

-- Cached embeddings for the semantic matcher. `source_sha` catches staleness
-- (the row's surface text changed); `sig` catches tampering, which the sha
-- cannot -- it is a digest of text sitting in the next table over, so whoever
-- writes the vector writes the sha. Under SemanticMatcher these vectors are an
-- input to the serve decision, so an unverifiable one is recomputed rather than
-- used. ON DELETE CASCADE because a deleted pair's vectors are unreachable.
CREATE TABLE IF NOT EXISTS tm_embeddings (
    pair_id     TEXT NOT NULL REFERENCES tm_pairs(id) ON DELETE CASCADE,
    model_name  TEXT NOT NULL,
    source_sha  TEXT NOT NULL,
    embedding   BLOB NOT NULL,
    sig         TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (pair_id, model_name)
);
"""


# Kept out of _SCHEMA and created separately: a database written before this
# existed may already hold duplicates, and a CREATE that raises inside the
# idempotent schema script would brick every later memory_init() on it.
_UNIQUE_KEY = ("CREATE UNIQUE INDEX IF NOT EXISTS idx_tm_pairs_key "
               "ON tm_pairs(source_norm, source_lang, target_lang)")
# When the unique index cannot be built (duplicate norms already present),
# lookups on every add_pair still need an index (IDEAS §2.3).
_LOOKUP_KEY = ("CREATE INDEX IF NOT EXISTS idx_tm_pairs_find "
               "ON tm_pairs(source_norm, source_lang, target_lang)")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid() -> str:
    return str(uuid.uuid4())


class StoreClosedError(RuntimeError):
    """The store was closed and something tried to use it anyway.

    Deliberately not a silent reopen. A closed ``":memory:"`` store has nothing
    left to reopen *to*, so answering from a fresh empty database would report
    "no verified answers" — which is a sentence this package must never say by
    accident. Loud beats plausible.
    """


# Idle connections kept for reuse on a file-backed store. Opening one costs
# real time (~20x on a single-row read), so a long-lived server should not do it
# per API call; keeping one per *thread* costs a descriptor for every thread
# that ever touched the store, and those are freed by the cyclic collector
# rather than promptly — which runs a UI out of file descriptors long before
# anything runs a garbage collection. A small idle pool gets the reuse with a
# ceiling: anything borrowed beyond it is closed on return, not accumulated.
_POOL_MAX = 8


class SqliteStore:
    """A minimal SQLite-backed store. Satisfies ``nestor.storage.Storage``."""

    def __init__(self, db_path: str = "data/nestor.db") -> None:
        self.db_path = db_path
        # A ":memory:" database only survives for the life of one connection,
        # so hold a persistent connection open in that case.
        self._shared: Optional[sqlite3.Connection] = None
        # In-memory: one shared connection, serialized with _lock (IDEAS §2.4).
        # File-backed: a bounded pool of idle connections (see _POOL_MAX).
        self._pool: list[sqlite3.Connection] = []
        self._pool_lock = threading.Lock()
        self._closed = False
        self._lock = threading.RLock()
        if db_path == ":memory:":
            self._shared = self._connect()

    def _connect(self) -> sqlite3.Connection:
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread is relaxed because no connection is ever used by two
        # threads at once: the shared one is serialized by self._lock, and a
        # pooled one is out of the pool for as long as a caller holds it.
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        if self.db_path != ":memory:":
            conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _acquire(self) -> sqlite3.Connection:
        with self._pool_lock:
            if self._closed:
                raise StoreClosedError(f"{self.db_path}: this store has been closed")
            if self._pool:
                return self._pool.pop()
        return self._connect()

    def _release(self, conn: sqlite3.Connection) -> None:
        """Park a connection for reuse, or close it if the pool is full."""
        with self._pool_lock:
            if not self._closed and len(self._pool) < _POOL_MAX:
                self._pool.append(conn)
                return
        conn.close()

    def close(self) -> None:
        """Checkpoint WAL into the main file and retire the store (IDEAS §2.4).

        While a process holds file-backed connections open, committed rows may
        live only in ``nestor.db-wal``, so a plain copy of ``nestor.db`` is
        incomplete; ``nestor.ui`` calls this on shutdown. A checkpoint from any
        one connection flushes the whole WAL, so this does not need to reach the
        connections other threads are holding — they are closed when returned.

        The store is not reusable afterwards: see :class:`StoreClosedError`.
        """
        with self._pool_lock:
            if self._closed:
                return
            self._closed = True
            idle = list(self._pool)
            self._pool.clear()
        if self.db_path == ":memory:":
            with self._lock:
                if self._shared is not None:
                    self._shared.close()
                    self._shared = None
            return
        self._wal_checkpoint_truncate(idle)

    def checkpoint_wal(self) -> None:
        """Flush WAL into the main file without closing the store (IDEAS §6.7)."""
        if self.db_path == ":memory:":
            return
        with self._pool_lock:
            if self._closed:
                raise StoreClosedError(f"{self.db_path}: this store has been closed")
            idle = list(self._pool)
            self._pool.clear()
        self._wal_checkpoint_truncate(idle)

    def backup_into(self, dest: str) -> None:
        """Write a consistent copy of the database to ``dest`` (``VACUUM INTO``)."""
        if self.db_path == ":memory:":
            raise ValueError("cannot backup an in-memory database to a file")
        self.checkpoint_wal()
        with self._lock:
            if self._closed:
                raise StoreClosedError(f"{self.db_path}: this store has been closed")
            conn = self._connect()
            try:
                conn.execute("VACUUM INTO ?", (dest,))
            finally:
                self._release(conn)

    def _wal_checkpoint_truncate(self, idle: list[sqlite3.Connection]) -> None:
        conn = idle.pop() if idle else self._connect()
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            conn.close()
            for spare in idle:
                spare.close()

    @contextmanager
    def _db(self):
        """Yield a connection; one level of use only — do not nest."""
        if self._closed:
            raise StoreClosedError(f"{self.db_path}: this store has been closed")
        if self._shared is not None:
            with self._lock:
                try:
                    yield self._shared
                    self._shared.commit()
                except Exception:
                    self._shared.rollback()
                    raise
            return
        conn = self._acquire()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._release(conn)

    # --- lifecycle -------------------------------------------------------

    def init_db(self) -> None:
        with self._db() as conn:
            conn.executescript(_SCHEMA)
            self._ensure_unique_key(conn)
            self._ensure_embedding_schema(conn)

    def memory_init(self) -> None:
        # tm_pairs is created by the same schema script; keep it idempotent.
        with self._db() as conn:
            conn.executescript(_SCHEMA)
            self._ensure_unique_key(conn)
            self._ensure_embedding_schema(conn)

    def _ensure_unique_key(self, conn: sqlite3.Connection) -> None:
        """One row per (normalized source, domain) — enforced by the database.

        Nestor's guards read a pair, decide, then write it, and nothing made that
        sequence atomic: two threads sealing the same phrase at once each found
        nothing and each inserted, leaving two sealed rows for one source with no
        ConflictingSealError and no way to say which one serves. The UI is a
        threaded server, so this is reachable by two reviewers pressing Seal at
        the same moment. A unique index turns the invariant from a convention
        every caller must honor into something the store cannot violate;
        ``memory.add_pair`` catches the collision and re-reads.

        A pre-existing database may already contain duplicates, in which case the
        index cannot be created. That degrades to the old behavior and says so,
        rather than failing every subsequent call.
        """
        try:
            conn.execute(_UNIQUE_KEY)
        except sqlite3.IntegrityError:
            dupes = conn.execute(
                "SELECT COUNT(*) FROM (SELECT source_norm, source_lang, target_lang "
                "FROM tm_pairs GROUP BY 1,2,3 HAVING COUNT(*) > 1)").fetchone()[0]
            warnings.warn(
                f"{self.db_path}: {dupes} normalized source(s) have more than one "
                f"row, so the uniqueness index could not be created and concurrent "
                f"seals can still race. Curator.list() shows the duplicates; "
                f"resolve them and re-open the store.", RuntimeWarning, stacklevel=3)
            conn.execute(_LOOKUP_KEY)

    def _ensure_embedding_schema(self, conn: sqlite3.Connection) -> None:
        """Bring a ``tm_embeddings`` written before ``sig`` existed up to date.

        ``CREATE TABLE IF NOT EXISTS`` is a no-op on an existing table, so a
        database opened by an earlier build keeps the unsigned shape and every
        ``SELECT sig`` on it raises. This drops and rebuilds it instead of
        ALTERing, because it is a *cache*: the cost of throwing it away is one
        recomputation, and rebuilding is the only way to also pick up the
        foreign key, which ALTER TABLE cannot add.
        """
        cols = {r[1] for r in conn.execute("PRAGMA table_info(tm_embeddings)")}
        if not cols or "sig" in cols:
            return
        conn.execute("DROP TABLE tm_embeddings")
        conn.executescript(_SCHEMA)

    # --- documents -------------------------------------------------------

    def create_document(self, title: str, source_lang: str,
                        target_lang: str) -> dict:
        doc = dict(id=_uid(), title=title, source_lang=source_lang,
                   target_lang=target_lang, status="pending_review",
                   created_at=_now())
        with self._db() as conn:
            conn.execute(
                "INSERT INTO documents VALUES "
                "(:id,:title,:source_lang,:target_lang,:status,:created_at)",
                doc,
            )
        return doc

    def get_document(self, document_id: str) -> Optional[dict]:
        with self._db() as conn:
            r = conn.execute("SELECT * FROM documents WHERE id=?",
                             (document_id,)).fetchone()
            return dict(r) if r else None

    def update_document_status(self, document_id: str, status: str) -> None:
        with self._db() as conn:
            conn.execute("UPDATE documents SET status=? WHERE id=?",
                         (status, document_id))

    def list_documents(self, status: str = "", limit: int = 50,
                       offset: int = 0) -> list[dict]:
        sql = "SELECT * FROM documents"
        params: list = []
        if status:
            sql += " WHERE status=?"
            params.append(status)
        sql += " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?"
        params += [max(0, int(limit)), max(0, int(offset))]
        with self._db() as conn:
            return [dict(r) for r in conn.execute(sql, params)]

    # --- segments --------------------------------------------------------

    def create_segment(self, document_id: str, position: int,
                       source_text: str, candidate: str,
                       jeles_score: float) -> dict:
        seg = dict(id=_uid(), document_id=document_id, position=position,
                   source_text=source_text, candidate=candidate,
                   jeles_score=jeles_score, status="pending", created_at=_now())
        with self._db() as conn:
            conn.execute(
                "INSERT INTO segments VALUES "
                "(:id,:document_id,:position,:source_text,:candidate,"
                ":jeles_score,:status,:created_at)",
                seg,
            )
        return seg

    def get_segment(self, segment_id: str) -> Optional[dict]:
        with self._db() as conn:
            r = conn.execute("SELECT * FROM segments WHERE id=?",
                             (segment_id,)).fetchone()
            return dict(r) if r else None

    def list_segments(self, document_id: str = "", status: str = "",
                      limit: int = 200, offset: int = 0) -> list[dict]:
        # Ordered by position, not by time: a reviewer reads a document in the
        # order it was written, and `created_at` ties within one cascade run.
        where, params = [], []
        for col, val in (("document_id", document_id), ("status", status)):
            if val:
                where.append(f"{col}=?")
                params.append(val)
        sql = "SELECT * FROM segments"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY created_at, document_id, position LIMIT ? OFFSET ?"
        params += [max(0, int(limit)), max(0, int(offset))]
        with self._db() as conn:
            return [dict(r) for r in conn.execute(sql, params)]

    def update_segment_status(self, segment_id: str, status: str) -> None:
        """Record a reviewer's decision on a queued segment.

        Part of the optional queue capability (``supports_queue``): Nestor
        writes 'verified' on graduation and 'rejected' on refusal, so a decided
        segment leaves the queue instead of being offered again.
        """
        with self._db() as conn:
            conn.execute("UPDATE segments SET status=? WHERE id=?",
                         (status, segment_id))

    # --- translation memory ---------------------------------------------

    def memory_find(self, source_norm: str, source_lang: str,
                   target_lang: str) -> Optional[dict]:
        with self._db() as conn:
            r = conn.execute(
                "SELECT * FROM tm_pairs WHERE source_norm=? AND source_lang=? "
                "AND target_lang=?",
                (source_norm, source_lang, target_lang),
            ).fetchone()
            return dict(r) if r else None

    def memory_insert(self, pair: dict) -> None:
        with self._db() as conn:
            conn.execute(
                "INSERT INTO tm_pairs VALUES (:id,:source_text,:source_norm,"
                ":source_lang,:target_text,:target_lang,:status,:verifier,"
                ":weight,:origin,:created_at,:seal_sig)",
                {"seal_sig": "", **pair},
            )

    def memory_seal(self, pair_id: str, target_text: str, verifier: str,
                   weight: float, seal_sig: str = "") -> None:
        with self._db() as conn:
            conn.execute(
                "UPDATE tm_pairs SET target_text=?, status='sealed', "
                "verifier=?, weight=?, seal_sig=? WHERE id=?",
                (target_text, verifier, weight, seal_sig, pair_id),
            )

    def memory_candidates(self, source_lang: str,
                         target_lang: str) -> list[dict]:
        with self._db() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM tm_pairs WHERE source_lang=? AND target_lang=?",
                (source_lang, target_lang),
            )]

    # --- semantic embeddings (optional; IDEAS §6.4) -----------------------

    def embedding_load(self, pair_id: str,
                       model_name: str) -> Optional[tuple[str, bytes, str]]:
        """``(source_sha, packed_vector, sig)`` — the packed bytes, not floats.

        The MAC is taken over exactly these bytes, so unpacking here and
        repacking to check it would make the check a test of ``struct``'s
        round-trip rather than of the stored value. The caller unpacks after it
        has decided to trust them.
        """
        with self._db() as conn:
            row = conn.execute(
                "SELECT source_sha, embedding, sig FROM tm_embeddings "
                "WHERE pair_id=? AND model_name=?",
                (pair_id, model_name),
            ).fetchone()
        if not row:
            return None
        return row[0], bytes(row[1]), row[2]

    def embedding_save(self, pair_id: str, model_name: str, source_sha: str,
                       blob: bytes, sig: str = "") -> None:
        with self._db() as conn:
            conn.execute(
                "INSERT INTO tm_embeddings(pair_id, model_name, source_sha, embedding, sig) "
                "VALUES (?,?,?,?,?) ON CONFLICT(pair_id, model_name) DO UPDATE SET "
                "source_sha=excluded.source_sha, embedding=excluded.embedding, "
                "sig=excluded.sig",
                (pair_id, model_name, source_sha, blob, sig),
            )

    def embedding_drop(self, pair_id: str) -> None:
        with self._db() as conn:
            conn.execute("DELETE FROM tm_embeddings WHERE pair_id=?", (pair_id,))

    # --- rejection -------------------------------------------------------

    def memory_reject_pair(self, pair_id: str, verifier: str,
                          reason: str) -> None:
        with self._db() as conn:
            conn.execute(
                "UPDATE tm_pairs SET status='rejected', verifier=?, origin=? "
                "WHERE id=?",
                (verifier, f"rejected:{reason}"[:200], pair_id),
            )

    def memory_add_rejection(self, rejection: dict) -> None:
        with self._db() as conn:
            conn.execute(
                "INSERT INTO tm_rejections VALUES (:id,:query_norm,:source_lang,"
                ":target_lang,:pair_id,:target_text,:verifier,:reason,"
                ":created_at,:reject_sig)",
                {"pair_id": "", "target_text": "", "verifier": "", "reason": "",
                 "reject_sig": "", **rejection},
            )

    def memory_rejections(self, query_norm: str, source_lang: str,
                          target_lang: str) -> list[dict]:
        with self._db() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM tm_rejections WHERE query_norm=? AND "
                "source_lang=? AND target_lang=?",
                (query_norm, source_lang, target_lang),
            )]

    # --- curation --------------------------------------------------------

    def memory_list(self, source_lang: str = "", target_lang: str = "",
                    status: str = "", verifier: str = "", contains: str = "",
                    limit: int = 50, offset: int = 0) -> list[dict]:
        where, params = [], []
        for col, val in (("source_lang", source_lang), ("target_lang", target_lang),
                         ("status", status), ("verifier", verifier)):
            if val:
                where.append(f"{col}=?")
                params.append(val)
        if contains:
            where.append("(LOWER(source_text) LIKE ? OR LOWER(target_text) LIKE ?)")
            like = f"%{contains.lower()}%"
            params += [like, like]
        sql = "SELECT * FROM tm_pairs"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?"
        params += [max(0, int(limit)), max(0, int(offset))]
        with self._db() as conn:
            return [dict(r) for r in conn.execute(sql, params)]

    def memory_get(self, pair_id: str) -> Optional[dict]:
        with self._db() as conn:
            r = conn.execute("SELECT * FROM tm_pairs WHERE id=?",
                             (pair_id,)).fetchone()
            return dict(r) if r else None

    def memory_unseal(self, pair_id: str, verifier: str, reason: str) -> None:
        # seal_sig is cleared, not kept: a 'draft' row still carrying a valid
        # signature is a seal waiting to be reactivated by anything that flips
        # the status column back.
        with self._db() as conn:
            conn.execute(
                "UPDATE tm_pairs SET status='draft', seal_sig='', origin=? "
                "WHERE id=?",
                (f"unsealed:{verifier}:{reason}"[:200], pair_id),
            )

    def memory_rejections_for_pair(self, pair_id: str) -> list[dict]:
        with self._db() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM tm_rejections WHERE pair_id=? ORDER BY created_at",
                (pair_id,))]

    def memory_stats(self) -> dict:
        with self._db() as conn:
            total = conn.execute("SELECT COUNT(*) FROM tm_pairs").fetchone()[0]
            sealed = conn.execute(
                "SELECT COUNT(*) FROM tm_pairs WHERE status='sealed'"
            ).fetchone()[0]
            langs = [tuple(r) for r in conn.execute(
                "SELECT source_lang, target_lang, COUNT(*) FROM tm_pairs "
                "GROUP BY source_lang, target_lang ORDER BY 3 DESC")]
        return {"total": total, "sealed": sealed, "draft": total - sealed,
                "lang_pairs": langs}
