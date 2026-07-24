"""The storage seam — Nestor's dependency inversion boundary.

Nestor owns translation logic (the cascade, fuzzy matching, the ledger) but
owns no persistence. Every database touch goes through the ``Storage``
Protocol below, and a concrete implementation is *injected* by the host.

Two ways to supply a store:

  * Globally, once at startup::

        from nestor import storage
        storage.set_store(MyStore())

    After that every public entry point (``translate_text``,
    ``translate_segment``, ``graduate_segment``, and the ``memory`` lookups)
    finds it via ``get_store()``.

  * Per call, explicitly: pass ``store=...`` to any public entry function.
    An explicit argument always wins over the global.

The reference implementation is :mod:`nestor.sqlite_store`.
"""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class Storage(Protocol):
    """The exact set of persistence operations Nestor requires.

    Derived from real usage in ``cascade.py`` (documents + segments) and
    ``memory.py`` (the translation-memory table). Row dicts are plain
    ``dict[str, Any]``; the keys named in each contract below are the only
    ones Nestor reads.
    """

    # --- lifecycle -------------------------------------------------------

    def init_db(self) -> None:
        """Ensure the document/segment schema exists. Idempotent.

        Called once at the start of ``translate_text``.
        """

    # --- documents -------------------------------------------------------

    def create_document(self, title: str, source_lang: str,
                        target_lang: str) -> dict:
        """Create a document row and return it.

        The returned dict MUST contain ``"id"`` (a stable unique string).
        ``source_lang`` / ``target_lang`` are stored so ``get_document`` can
        return them later (``graduate_segment`` reads them).
        """

    def get_document(self, document_id: str) -> Optional[dict]:
        """Return the document row, or ``None`` if absent.

        When present, the dict MUST expose ``"source_lang"`` and
        ``"target_lang"`` (read by ``graduate_segment``).
        """

    def update_document_status(self, document_id: str, status: str) -> None:
        """Set a document's ``status`` column. No-op if the id is unknown."""

    # --- segments --------------------------------------------------------

    def create_segment(self, document_id: str, position: int,
                       source_text: str, candidate: str,
                       jeles_score: float) -> dict:
        """Create a segment row queued for tier-3 review and return it.

        The returned dict MUST contain ``"id"``. The new segment's state is
        the store's own "pending" default — Nestor does not set it here.
        """

    def get_segment(self, segment_id: str) -> Optional[dict]:
        """Return the segment row, or ``None`` if absent.

        When present the dict MUST expose ``"candidate"``, ``"source_text"``
        and ``"document_id"`` (all read by ``graduate_segment``). A store that
        graduates segments should also update/read a ``"status"`` field, but
        Nestor's graduate path only requires the three keys above.
        """

    # --- translation memory (tier 1) ------------------------------------
    #
    # memory.py previously ran these as raw ``db.get_db()`` SQL. They are
    # refactored here into named operations. Nestor keeps the *algorithm*
    # (text normalization + difflib fuzzy scoring); the store keeps only the
    # persistence primitives.

    def memory_init(self) -> None:
        """Ensure the translation-memory table exists. Idempotent.

        (Was ``init_tm``: ``db.init_db()`` + ``executescript(_TM_SCHEMA)``.)
        """

    def memory_find(self, source_norm: str, source_lang: str,
                   target_lang: str) -> Optional[dict]:
        """Exact-key lookup by *normalized* source, for upsert.

        Returns the single pair whose ``source_norm`` + language pair match,
        or ``None``. The returned dict MUST expose ``id``, ``status``,
        ``target_text`` (read by ``add_pair`` to decide insert vs. seal).
        (Was the ``SELECT ... WHERE source_norm=? AND source_lang=? AND
        target_lang=?`` at the top of ``add_pair``.)
        """

    def memory_insert(self, pair: dict) -> None:
        """Insert one new translation-memory pair.

        ``pair`` carries every column Nestor writes: ``id``, ``source_text``,
        ``source_norm``, ``source_lang``, ``target_text``, ``target_lang``,
        ``status``, ``verifier``, ``weight``, ``origin``, ``created_at``.
        (Was the ``INSERT INTO tm_pairs`` in ``add_pair``.)
        """

    def memory_seal(self, pair_id: str, target_text: str, verifier: str,
                   weight: float) -> None:
        """Upgrade an existing pair to sealed status.

        Sets ``target_text``, ``status='sealed'``, ``verifier`` and ``weight``
        on the row with ``pair_id``. (Was the conditional ``UPDATE tm_pairs
        SET target_text=?, status='sealed', ...`` in ``add_pair``.)
        """

    def memory_candidates(self, source_lang: str,
                         target_lang: str) -> list[dict]:
        """Return ALL pairs for a language direction, for fuzzy scoring.

        Nestor's ``lookup`` ranks these with difflib in Python — the store
        does no matching, it just returns the candidate set. Each dict MUST
        expose at least ``source_norm``, ``status``, ``target_text``, ``id``.
        (Was the ``SELECT * WHERE source_lang=? AND target_lang=?`` in
        ``lookup``.)
        """

    def memory_stats(self) -> dict:
        """Return ``{"total", "sealed", "draft", "lang_pairs"}``.

        ``lang_pairs`` is a list of ``(source_lang, target_lang, count)``
        tuples, busiest first. (Was the COUNT/GROUP BY block in ``stats``.)
        """


# --------------------------------------------------------------------------
# Global injection point
# --------------------------------------------------------------------------

_store: "Optional[Storage]" = None


def set_store(store: "Storage") -> None:
    """Install the process-wide store used when no explicit ``store=`` is passed."""
    global _store
    _store = store


def get_store(store: "Optional[Storage]" = None) -> "Storage":
    """Resolve the store to use.

    An explicit ``store`` argument wins. Otherwise the global store set via
    :func:`set_store` is returned. Raises ``RuntimeError`` with a clear
    message if neither is available — Nestor never falls back to a hidden
    default database.
    """
    if store is not None:
        return store
    if _store is None:
        raise RuntimeError(
            "Nestor storage is not configured. Call nestor.storage.set_store(...) "
            "with a Storage implementation (e.g. nestor.sqlite_store.SqliteStore()) "
            "before using the cascade, or pass store=... explicitly."
        )
    return _store
