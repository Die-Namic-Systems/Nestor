"""Bounded embed-tick: warm tm_embeddings without a live model.

Same stub pattern as test_embedding_cache — CI has no fastembed/Ollama, and the
tick's job is the budget/receipt/cache write path, not the model.
"""
from __future__ import annotations

import hashlib
import os
import time

import pytest

from nestor import memory, semantic_matcher
from nestor.embed_tick import run_embed_tick
from nestor.semantic_matcher import SemanticMatcher

DIMS = 64
MODEL = "stub-embed-tick"


def _vec(text: str) -> tuple[float, ...]:
    i = int.from_bytes(hashlib.sha256(text.encode()).digest()[:4], "big") % DIMS
    return tuple(1.0 if j == i else 0.0 for j in range(DIMS))


class _StubModel:
    def __init__(self) -> None:
        self.embedded: list[str] = []
        self.delay_s = 0.0

    def embed(self, texts):
        if self.delay_s:
            time.sleep(self.delay_s)
        for t in texts:
            self.embedded.append(t)
            yield _vec(t)


@pytest.fixture
def matcher(monkeypatch):
    monkeypatch.setattr(semantic_matcher, "_require_fastembed", lambda: None)
    m = SemanticMatcher(model_name=MODEL)
    model = _StubModel()
    m._load_model = lambda: model  # type: ignore[method-assign]
    m.model = model
    return m


@pytest.fixture
def cache_key():
    os.environ["NESTOR_CACHE_KEY"] = "embed-tick-cache-key"


def _seal(store, matcher, source: str, target: str = "tgt") -> dict:
    return memory.add_pair(source, target, "en", "es", status="sealed",
                           verifier="rita", store=store, matcher=matcher)


def test_warm_embeddings_writes_missing_only(store, matcher, seal_key, cache_key):
    a = _seal(store, matcher, "alpha question")
    b = _seal(store, matcher, "beta question")
    rows = [store.memory_get(a["id"]), store.memory_get(b["id"])]

    n = matcher.warm_embeddings(rows, store)
    assert n == 2
    assert store.embedding_load(a["id"], MODEL) is not None
    assert store.embedding_load(b["id"], MODEL) is not None

    matcher._cache.clear()
    assert matcher.warm_embeddings(rows, store) == 0


def test_tick_ok_warms_and_receipt(store, matcher, seal_key, cache_key):
    for i in range(3):
        _seal(store, matcher, f"question number {i}")

    receipt = run_embed_tick(
        store, matcher_spec="semantic", matcher=matcher,
        budget_s=5.0, limit=10, batch_size=2,
    )
    assert receipt["status"] == "ok"
    assert receipt["embedded"] == 3
    assert receipt["candidates"] == 3
    assert receipt["remaining"] == 0
    assert receipt["stopped"] == "done"
    assert receipt["model"] == MODEL


def test_tick_empty_when_already_warm(store, matcher, seal_key, cache_key):
    pair = _seal(store, matcher, "already warm")
    row = store.memory_get(pair["id"])
    assert matcher.warm_embeddings([row], store) == 1

    receipt = run_embed_tick(
        store, matcher_spec="semantic", matcher=matcher, budget_s=5.0,
    )
    assert receipt["status"] == "empty"
    assert receipt["embedded"] == 0
    assert receipt["candidates"] == 0


def test_tick_unreachable_without_cache_key(store, matcher, seal_key, monkeypatch):
    monkeypatch.delenv("NESTOR_CACHE_KEY", raising=False)
    monkeypatch.delenv("NESTOR_SEAL_KEY", raising=False)
    # seal_key fixture may have set NESTOR_SEAL_KEY — force cache trust off.
    from nestor import signing
    monkeypatch.setattr(signing, "cache_trust", lambda: "unavailable")

    _seal(store, matcher, "cannot cache")
    receipt = run_embed_tick(
        store, matcher_spec="semantic", matcher=matcher, budget_s=5.0,
    )
    assert receipt["status"] == "unreachable"
    assert "cache" in receipt["reason"].lower() or "NESTOR_CACHE_KEY" in receipt["reason"]


def test_tick_stops_on_budget(store, matcher, seal_key, cache_key):
    for i in range(6):
        _seal(store, matcher, f"slow question {i}")
    matcher.model.delay_s = 0.08

    receipt = run_embed_tick(
        store, matcher_spec="semantic", matcher=matcher,
        budget_s=0.05, limit=6, batch_size=1,
    )
    assert receipt["status"] == "ok"
    assert receipt["stopped"] == "budget"
    assert receipt["embedded"] < 6
    assert receipt["remaining"] > 0


def test_tick_respects_limit(store, matcher, seal_key, cache_key):
    for i in range(5):
        _seal(store, matcher, f"capped question {i}")

    receipt = run_embed_tick(
        store, matcher_spec="semantic", matcher=matcher,
        budget_s=30.0, limit=2, batch_size=2,
    )
    assert receipt["status"] == "ok"
    assert receipt["candidates"] == 2
    assert receipt["embedded"] == 2
    assert receipt["stopped"] == "limit"
    assert receipt["more"] is True
