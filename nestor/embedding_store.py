"""Optional persistence for semantic embeddings on sealed rows (IDEAS §6.4).

Only :class:`~nestor.sqlite_store.SqliteStore` implements this today; matchers
probe with :func:`supports_embedding_store` rather than extending the core
``Storage`` Protocol.

Two different things can be wrong with a cached vector, and they need two
different checks:

* the row's surface text changed since the vector was computed — *staleness*,
  caught by :func:`source_text_sha`;
* somebody wrote a vector of their own choosing — *tampering*, which the sha
  cannot catch, because it is a digest of text sitting in the row next to it.
  Whoever can write the vector can write the matching sha.

The second one matters because under
:class:`~nestor.semantic_matcher.SemanticMatcher` these vectors are an input to
the serve decision. A seal signature binds ``(source_norm, target_text,
verifier)``; it says nothing about what the row *matches*, so a store-writer who
cannot forge a seal could still choose which queries a sealed row answers. That
is Nestor#2 one object over, and it is closed the same way: an HMAC keyed
outside the store (:func:`nestor.signing.sign_embedding`).

Failing that check is not a refusal. A cached vector is an optimization, so an
entry that does not verify is recomputed — the cost is latency, never an answer.
"""
from __future__ import annotations

import hashlib
import struct
import warnings
from typing import Optional, Protocol

from . import signing

_warned_unavailable = False


class EmbeddingCapableStorage(Protocol):
    """The three embedding-cache methods, as a ``cast`` target for a caller
    that already checked :func:`supports_embedding_store` — the same
    check-then-cast shape as :class:`nestor.storage.LineageStorage`, kept
    here rather than in ``storage.py`` because this capability was
    deliberately never folded into the core ``Storage`` Protocol (see the
    module docstring)."""

    def embedding_load(self, pair_id: str,
                       model_name: str) -> Optional[tuple[str, bytes, str]]: ...

    def embedding_save(self, pair_id: str, model_name: str, source_sha: str,
                       blob: bytes, sig: str = "") -> None: ...

    def embedding_drop(self, pair_id: str) -> None: ...


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


def cache_enabled() -> bool:
    """False when signing is on but no key exists to MAC cached vectors with.

    The store is untrusted in that deployment and the cache cannot be checked,
    so it is neither read nor written; embeddings are recomputed every time. Says
    so once, because "semantic matching got slower" is otherwise unattributable.
    """
    if signing.cache_trust() != "unavailable":
        return True
    global _warned_unavailable
    if not _warned_unavailable:
        _warned_unavailable = True
        warnings.warn(
            "seal signing is on but no deployment-wide key is available to sign "
            "cached embeddings with, so the embedding cache is disabled and "
            "vectors are recomputed on every match. Set NESTOR_CACHE_KEY (or "
            "NESTOR_SEAL_KEY) to enable it.", RuntimeWarning, stacklevel=3)
    return False


def load_embedding(store, pair_id: str, model_name: str,
                   text: str) -> Optional[tuple[float, ...]]:
    """A cached vector for ``pair_id``, or ``None`` to compute it.

    ``None`` covers every reason not to use one — absent, stale, or unverifiable
    — because they have the same remedy. A stale entry is dropped, since its
    text is gone and nothing will ever match it again; an entry that fails its
    MAC is left alone to be overwritten by the recomputed one, so a store the
    matcher cannot write is not also a store it spins on.
    """
    if not cache_enabled():
        return None
    hit = store.embedding_load(pair_id, model_name)
    if hit is None:
        return None
    sha, blob, sig = hit
    if sha != source_text_sha(text):
        store.embedding_drop(pair_id)
        return None
    if not signing.embedding_is_valid(pair_id, model_name, sha, blob, sig):
        return None
    return blob_to_vec(blob)


def save_embedding(store, pair_id: str, model_name: str, text: str,
                   vec: tuple[float, ...]) -> None:
    """Cache ``vec``, MAC'd so it can be trusted when it is read back."""
    if not cache_enabled():
        return
    sha = source_text_sha(text)
    blob = vec_to_blob(vec)
    store.embedding_save(pair_id, model_name, sha, blob,
                         signing.sign_embedding(pair_id, model_name, sha, blob))
