"""Optional persistence for semantic embeddings on sealed rows (IDEAS §6.4).

Only :class:`~nestor.sqlite_store.SqliteStore` implements this today; matchers
probe with :func:`supports_embedding_store` rather than extending the core
``Storage`` Protocol.
"""
from __future__ import annotations

import hashlib
import struct


def supports_embedding_store(store) -> bool:
    return all(callable(getattr(store, name, None)) for name in (
        "embedding_load", "embedding_save", "embedding_drop",
    ))


def source_text_sha(text: str) -> str:
    """Digest of the surface text an embedding was computed from."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def vec_to_blob(vec: tuple[float, ...]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def blob_to_vec(blob: bytes) -> tuple[float, ...]:
    n = len(blob) // 4
    return struct.unpack(f"{n}f", blob)
