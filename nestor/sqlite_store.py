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
import uuid
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
-- triple, so unlike tm_pairs.source_norm this one is indexed from the start.
CREATE INDEX IF NOT EXISTS idx_tm_rejections_query
    ON tm_rejections(query_norm, source_lang, target_lang);
"""


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
        if db_path == ":memory:":
            self._shared = self._connect()

    def _connect(self) -> sqlite3.Connection:
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @contextmanager
    def _db(self):
        conn = self._shared or self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            if self._shared is None:
                conn.close()

    # --- lifecycle -------------------------------------------------------

    def init_db(self) -> None:
        with self._db() as conn:
            conn.executescript(_SCHEMA)

    def memory_init(self) -> None:
        # tm_pairs is created by the same schema script; keep it idempotent.
        with self._db() as conn:
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

    def update_segment_status(self, segment_id: str, status: str) -> None:
        """Not required by the Protocol, but handy for hosts/tests driving
        a segment to 'verified' before graduating it."""
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
