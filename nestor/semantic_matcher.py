"""Embedding-based matcher — optional ``nestor[semantic]`` extra (IDEAS §3.3).

``normalize`` stays a cheap lexical dedup key (:class:`~nestor.matcher.StringMatcher`);
``score`` compares raw surfaces with cosine similarity on embedding vectors.
Core ``nestor`` has zero runtime dependencies; :mod:`fastembed` is required at
construction time (``pip install nestor[semantic]``) and the model loads on the
first embed call.

Not thread-safe: the LRU cache and lazy model handle are shared mutable state.
Use one matcher per thread, or inject a fresh instance per request, if serving
from a pool (same guidance as :class:`~nestor.matcher.StringMatcher`'s bounds).
"""
from __future__ import annotations

import os
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

    def __init__(self, model_name: str = DEFAULT_MODEL,
                 dedup: Optional[Matcher] = None,
                 cache_size: int = _CACHE_MAX) -> None:
        self.model_name = model_name
        self._dedup = dedup or StringMatcher()
        self._cache_size = max(1, cache_size)
        self._cache: OrderedDict[str, tuple[float, ...]] = OrderedDict()
        self._model = None
        _require_fastembed()

    def _load_model(self):
        if self._model is not None:
            return self._model
        from fastembed import TextEmbedding
        self._model = TextEmbedding(model_name=self.model_name)
        return self._model

    def _embed(self, text: str) -> tuple[float, ...]:
        key = text
        hit = self._cache.get(key)
        if hit is not None:
            self._cache.move_to_end(key)
            return hit
        model = self._load_model()
        # fastembed returns a generator of vectors (numpy or list-like).
        vec = next(model.embed([text]))
        out = tuple(float(x) for x in vec)
        self._cache[key] = out
        if len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)
        return out

    def normalize(self, value) -> str:
        return self._dedup.normalize(value)

    def similarity(self, a_norm: str, b_norm: str) -> float:
        return self._dedup.similarity(a_norm, b_norm)

    def score(self, raw_a, raw_b) -> float:
        a = "" if raw_a is None else str(raw_a)
        b = "" if raw_b is None else str(raw_b)
        if not a.strip() or not b.strip():
            return 0.0
        if a == b:
            return 1.0
        return _cosine(self._embed(a), self._embed(b))
