"""Embedding-based matcher — optional ``nestor[semantic]`` extra (IDEAS §3.3).

``normalize`` stays a cheap lexical dedup key (:class:`~nestor.matcher.StringMatcher`);
``score`` compares raw surfaces with cosine similarity on embedding vectors.
Core ``nestor`` has zero runtime dependencies; :mod:`fastembed` is required at
construction time (``pip install nestor[semantic]``) and the model loads on the
first embed call.

A single :class:`SemanticMatcher` may be shared across threads (for example from
:mod:`nestor.ui`'s pool): embedding and cache updates are serialized with a lock.
"""
from __future__ import annotations

import os
import threading
from collections import OrderedDict
from typing import Optional

from .matcher import Matcher, StringMatcher

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
_CACHE_MAX = 512
INTEGRATION_TEST_ENV = "NESTOR_SEMANTIC_TEST"


def integration_tests_enabled() -> bool:
    """True when ``NESTOR_SEMANTIC_TEST=1`` (optional integration tests only)."""
    return os.environ.get(INTEGRATION_TEST_ENV, "").strip() == "1"


def _require_fastembed() -> None:
    try:
        import fastembed  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "SemanticMatcher requires the optional 'semantic' extra: "
            "pip install nestor[semantic]"
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
        A `fastembed` text model (default is a small English bi-encoder).
    dedup:
        Matcher used for ``normalize`` and for ``similarity`` when only norms
        are available. Defaults to :class:`StringMatcher`.
    cache_size:
        Number of embedded strings to retain in memory (LRU).
    """

    name = "semantic"

    def __init__(self, model_name: str = DEFAULT_MODEL,
                 dedup: Optional[Matcher] = None,
                 cache_size: int = _CACHE_MAX) -> None:
        self.model_name = model_name
        self._dedup = dedup or StringMatcher()
        self._cache_size = max(1, cache_size)
        self._cache: OrderedDict[str, tuple[float, ...]] = OrderedDict()
        self._model = None
        self._lock = threading.Lock()
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

    def _embed_unlocked(self, text: str) -> tuple[float, ...]:
        hit = self._cache.get(text)
        if hit is not None:
            self._cache.move_to_end(text)
            return hit
        model = self._load_model()
        vec = next(model.embed([text]))
        return self._remember(text, tuple(float(x) for x in vec))

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
        q = "" if query_text is None else str(query_text)
        q_norm = self.normalize(q)
        out = [0.0] * len(stored_texts)
        pending: list[tuple[int, str]] = []
        with self._lock:
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
            need: list[str] = []
            seen: set[str] = set()
            for text in (q, *(b for _, b in pending)):
                if text not in self._cache and text not in seen:
                    need.append(text)
                    seen.add(text)
            if need:
                model = self._load_model()
                for text, vec in zip(need, model.embed(need)):
                    self._remember(text, tuple(float(x) for x in vec))
            for i, b in pending:
                out[i] = _cosine(self._embed_unlocked(q), self._embed_unlocked(b))
        return out
