"""Embedding-based matcher — ``fastembed`` extra or local Ollama (IDEAS §3.3 / §6.96).

``normalize`` stays a cheap lexical dedup key (:class:`~nestor.matcher.StringMatcher`);
``score`` compares raw surfaces with cosine similarity on embedding vectors.

Two backends:

* ``fastembed`` (default for the ``semantic`` name) — optional pip extra
  ``nestor-meaning[semantic]``; model loads on the first embed call.
* ``ollama`` (the ``ollama`` shipped name) — stdlib HTTP to a local daemon;
  default model ``nomic-embed-text``. No pip extra.

A single :class:`SemanticMatcher` may be shared across threads (for example from
:mod:`nestor.ui`'s pool): embedding and cache updates are serialized with a lock.
"""
from __future__ import annotations

import threading
from collections import OrderedDict

from . import config
from .embedding_store import load_embedding, save_embedding, supports_embedding_store
from .matcher import Matcher, StringMatcher

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
_CACHE_MAX = 512
INTEGRATION_TEST_ENV = "NESTOR_SEMANTIC_TEST"
BACKENDS = ("fastembed", "ollama")


def integration_tests_enabled() -> bool:
    """True when ``NESTOR_SEMANTIC_TEST=1`` (optional integration tests only).

    Exact ``"1"`` only, unlike the usual truthy token set — preserved via
    :func:`nestor.config.get_bool_loose`, which is also why this stays
    lowercased-but-not-widened: ``"true"``/``"on"`` were never accepted here.
    """
    return config.get_bool_loose(INTEGRATION_TEST_ENV, False, frozenset({"1"}))


def _require_fastembed() -> None:
    try:
        import fastembed  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "SemanticMatcher requires the optional 'semantic' extra: "
            "pip install nestor-meaning[semantic]"
        ) from exc


def _cosine(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0.0 or nb == 0.0:
        return 0.0
    # Text embeddings are same-hemisphere; clamp for a [0, 1] serve threshold.
    return max(0.0, min(1.0, dot / (na * nb)))


class SemanticMatcher:
    """Lexical dedup key + embedding similarity on raw text.

    Parameters
    ----------
    model_name:
        Embedding model id. Defaults to the fastembed bi-encoder, or
        ``nomic-embed-text`` when ``backend="ollama"``.
    backend:
        ``"fastembed"`` (pip extra) or ``"ollama"`` (local daemon, stdlib).
    dedup:
        Matcher used for ``normalize`` and for ``similarity`` when only norms
        are available. Defaults to :class:`StringMatcher`.
    cache_size:
        Number of embedded strings to retain in memory (LRU).
    persist:
        Whether newly computed vectors may be written to the store's embedding
        cache. ``False`` for a read-only surface: matching is a read, and a
        reader who passed ``--read-only`` did not agree to a write just because
        the matcher would like one. Reading the cache is unaffected.

    Notes
    -----
    The default ``SEAL_THRESHOLD`` was measured for character-ratio /
    fastembed space. Ollama ``nomic-embed-text`` bunches differently — measure
    with ``nestor calibrate --matcher ollama`` before trusting serves.
    """

    name = "semantic"

    def __init__(self, model_name: str | None = None,
                 dedup: Matcher | None = None,
                 cache_size: int = _CACHE_MAX,
                 persist: bool = True,
                 backend: str = "fastembed") -> None:
        if backend not in BACKENDS:
            raise ValueError(
                f"unknown embedding backend {backend!r} — "
                f"shipped backends are {', '.join(BACKENDS)}"
            )
        self.backend = backend
        self.persist = persist
        self._dedup = dedup or StringMatcher()
        self._cache_size = max(1, cache_size)
        self._cache: OrderedDict[str, tuple[float, ...]] = OrderedDict()
        self._model = None
        self._lock = threading.Lock()
        if backend == "ollama":
            from . import ollama_embed
            self.model_name = model_name or ollama_embed.DEFAULT_EMBED_MODEL
            self.name = "ollama"
            if not ollama_embed.available(self.model_name):
                raise RuntimeError(
                    f"ollama matcher needs Ollama reachable at {ollama_embed.host()} "
                    f"with model {self.model_name!r} installed "
                    f"(OLLAMA_HOST / NESTOR_OLLAMA_EMBED_MODEL)"
                )
        else:
            self.model_name = model_name or DEFAULT_MODEL
            self.name = "semantic"
            _require_fastembed()

    def _load_model(self):
        if self._model is not None:
            return self._model
        from fastembed import TextEmbedding
        self._model = TextEmbedding(model_name=self.model_name)
        return self._model

    def _remember(self, key: str, vec: tuple[float, ...]) -> tuple[float, ...]:
        self._cache[key] = vec
        self._cache.move_to_end(key)
        if len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)
        return vec

    def _embed_batch_unlocked(self, texts: list[str]) -> None:
        need: list[str] = []
        seen: set[str] = set()
        for text in texts:
            if text not in self._cache and text not in seen:
                need.append(text)
                seen.add(text)
        if not need:
            return
        if self.backend == "ollama":
            from . import ollama_embed
            for text, vec in zip(need, ollama_embed.embed_many(need, model=self.model_name)):
                self._remember(text, vec)
            return
        model = self._load_model()
        for text, vec in zip(need, model.embed(need)):
            self._remember(text, tuple(float(x) for x in vec))

    def _embed_unlocked(self, text: str) -> tuple[float, ...]:
        hit = self._cache.get(text)
        if hit is not None:
            self._cache.move_to_end(text)
            return hit
        self._embed_batch_unlocked([text])
        return self._cache[text]

    def _embed(self, text: str) -> tuple[float, ...]:
        with self._lock:
            return self._embed_unlocked(text)

    def normalize(self, value) -> str:
        return self._dedup.normalize(value)

    def similarity(self, a_norm: str, b_norm: str) -> float:
        return self._dedup.similarity(a_norm, b_norm)

    def score(self, raw_a, raw_b) -> float:
        a = "" if raw_a is None else str(raw_a)
        b = "" if raw_b is None else str(raw_b)
        if not a.strip() or not b.strip():
            return 0.0
        if self.normalize(a) == self.normalize(b):
            return 1.0
        if a == b:
            return 1.0
        with self._lock:
            return _cosine(self._embed_unlocked(a), self._embed_unlocked(b))

    def scores_against(self, query_text: str, stored_texts: list[str]) -> list[float]:
        """Score one query against many stored surfaces (batched embed when needed)."""
        with self._lock:
            return self._scores_against_unlocked(query_text, stored_texts)

    def scores_against_for_rows(self, query_text: str, rows: list[dict],
                                store=None) -> list[float]:
        """Like :meth:`scores_against`, with optional store-backed embedding cache."""
        texts = [r.get("source_text") or "" for r in rows]
        with self._lock:
            cached = self._hydrate_embeddings_from_store(rows, store)
            scores = self._scores_against_unlocked(query_text, texts)
            self._persist_embeddings_to_store(rows, texts, store, cached)
        return scores

    def _hydrate_embeddings_from_store(self, rows: list[dict], store) -> set[str]:
        """Fill the in-memory cache from the store; return the ids it came from.

        Those ids already hold a current, verified entry, so
        :meth:`_persist_embeddings_to_store` must not write them again — a cache
        whose steady state is one UPSERT per row per serve is not a cache.
        """
        if not store or not supports_embedding_store(store):
            return set()
        cached: set[str] = set()
        for row in rows:
            text = (row.get("source_text") or "").strip()
            if not text:
                continue
            vec = load_embedding(store, row["id"], self.model_name, text)
            if vec is None:
                continue
            cached.add(row["id"])
            # Only when absent: an in-memory vector is the model's own float64
            # output, and the stored one has been through float32.
            if text not in self._cache:
                self._remember(text, vec)
        return cached

    def _persist_embeddings_to_store(self, rows: list[dict], texts: list[str],
                                     store, cached: set[str]) -> None:
        if not store or not supports_embedding_store(store) or not self.persist:
            return
        for row, text in zip(rows, texts):
            raw = (text or "").strip()
            if not raw or row["id"] in cached:
                continue
            vec = self._cache.get(raw)
            if vec is None:
                continue
            save_embedding(store, row["id"], self.model_name, raw, vec)

    def _scores_against_unlocked(self, query_text: str,
                                 stored_texts: list[str]) -> list[float]:
        q = "" if query_text is None else str(query_text)
        q_norm = self.normalize(q)
        out = [0.0] * len(stored_texts)
        pending: list[tuple[int, str]] = []
        for i, raw in enumerate(stored_texts):
            b = "" if raw is None else str(raw)
            if not q.strip() or not b.strip():
                continue
            if self.normalize(b) == q_norm or q == b:
                out[i] = 1.0
                continue
            pending.append((i, b))
        if not pending:
            return out
        self._embed_batch_unlocked([q, *(b for _, b in pending)])
        for i, b in pending:
            out[i] = _cosine(self._embed_unlocked(q), self._embed_unlocked(b))
        return out
