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

CREATE TABLE IF NOT EXISTS tm_embeddings (
    pair_id     TEXT NOT NULL,
    model_name  TEXT NOT NULL,
    source_sha  TEXT NOT NULL,
    embedding   BLOB NOT NULL,
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


class SqliteStore:
    """A minimal SQLite-backed store. Satisfies ``nestor.storage.Storage``."""

    def __init__(self, db_path: str = "data/nestor.db") -> None:
        self.db_path = db_path
        # A ":memory:" database only survives for the life of one connection,
        # so hold a persistent connection open in that case.
        self._shared: Optional[sqlite3.Connection] = None
        # Guards the shared connection only. A file-backed store opens a
        # connection per operation, so threads never share one and SQLite's own
        # file locking applies; the in-memory store has exactly one connection
        # and would otherwise raise "SQLite objects created in a thread can only
        # be used in that same thread" under any threaded host — including
        # nestor.ui, which serves requests from a thread pool.
        self._lock = threading.RLock()
        if db_path == ":memory:":
            self._shared = self._connect()

    def _connect(self) -> sqlite3.Connection:
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread is relaxed only for the shared connection, and only
        # because self._lock serializes every use of it.
        conn = sqlite3.connect(self.db_path,
                               check_same_thread=(self.db_path != ":memory:"))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @contextmanager
    def _db(self):
        if self._shared is not None:
            with self._lock:
                try:
                    yield self._shared
                    self._shared.commit()
                except Exception:
                    self._shared.rollback()
                    raise
            return
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # --- lifecycle -------------------------------------------------------

    def init_db(self) -> None:
        with self._db() as conn:
            conn.executescript(_SCHEMA)
            self._ensure_unique_key(conn)

    def memory_init(self) -> None:
        # tm_pairs is created by the same schema script; keep it idempotent.
        with self._db() as conn:
            conn.executescript(_SCHEMA)
            self._ensure_unique_key(conn)

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
                       model_name: str) -> Optional[tuple[str, tuple[float, ...]]]:
        with self._db() as conn:
            row = conn.execute(
                "SELECT source_sha, embedding FROM tm_embeddings "
                "WHERE pair_id=? AND model_name=?",
                (pair_id, model_name),
            ).fetchone()
        if not row:
            return None
        from .embedding_store import blob_to_vec
        return row[0], blob_to_vec(row[1])

    def embedding_save(self, pair_id: str, model_name: str, source_sha: str,
                       vec: tuple[float, ...]) -> None:
        from .embedding_store import vec_to_blob
        with self._db() as conn:
            conn.execute(
                "INSERT INTO tm_embeddings(pair_id, model_name, source_sha, embedding) "
                "VALUES (?,?,?,?) ON CONFLICT(pair_id, model_name) DO UPDATE SET "
                "source_sha=excluded.source_sha, embedding=excluded.embedding",
                (pair_id, model_name, source_sha, vec_to_blob(vec)),
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
