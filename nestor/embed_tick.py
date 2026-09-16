"""Bounded warm of ``tm_embeddings`` for the semantic / ollama matcher.

Serve-time matching embeds every uncached sealed ``source_text`` on the first
``ask`` / triage that needs it. That work is sync and grows with the corpus;
``nestor embed-tick`` moves it onto a wall-clock budget so a timer or steward
tick can keep the cache warm without hogging Kart / Ollama for a long stretch.

Receipt status is the three-state contract:

* ``ok`` — at least one vector written, or candidates remain and the budget
  stopped the tick (progress is still a populated outcome).
* ``empty`` — nothing to warm (no sealed surfaces missing a current cache
  entry for this model).
* ``unreachable`` — embedder or cache signing is not usable; nothing written.
"""
from __future__ import annotations

import time
from typing import Any

from . import answer
from .embedding_store import cache_enabled, load_embedding, supports_embedding_store

DEFAULT_BUDGET_S = 5.0
DEFAULT_LIMIT = 64
DEFAULT_BATCH = 8
_SCAN_PAGE = 100

_BACKEND_ALIASES = {
    "ollama": "ollama",
    "semantic": "semantic",
    "fastembed": "semantic",
}


def _backend_name(matcher_spec: str) -> str:
    key = (matcher_spec or "ollama").strip().lower()
    if key not in _BACKEND_ALIASES:
        raise ValueError(
            f"embed-tick matcher must be 'ollama' or 'semantic' "
            f"(got {matcher_spec!r})"
        )
    return _BACKEND_ALIASES[key]


def _collect_candidates(store, *, source_lang: str, target_lang: str,
                        status: str, model_name: str, limit: int) -> list[dict]:
    """Sealed (or filtered) live rows whose cache entry is missing or stale."""
    out: list[dict] = []
    offset = 0
    while len(out) < limit:
        page = store.memory_list(
            source_lang=source_lang, target_lang=target_lang, status=status,
            limit=_SCAN_PAGE, offset=offset,
        )
        if not page:
            break
        for row in page:
            text = (row.get("source_text") or "").strip()
            if not text:
                continue
            if load_embedding(store, row["id"], model_name, text) is None:
                out.append(row)
                if len(out) >= limit:
                    break
        offset += len(page)
        if len(page) < _SCAN_PAGE:
            break
    return out


def run_embed_tick(
    store,
    *,
    matcher_spec: str = "ollama",
    source_lang: str = "",
    target_lang: str = "",
    status: str = "sealed",
    budget_s: float = DEFAULT_BUDGET_S,
    limit: int = DEFAULT_LIMIT,
    batch_size: int = DEFAULT_BATCH,
    matcher=None,
) -> dict[str, Any]:
    """Warm up to ``limit`` missing embeddings within ``budget_s``.

    ``matcher`` is optional — tests inject a stubbed :class:`SemanticMatcher`.
    When omitted, the shipped matcher for ``matcher_spec`` is built with
    ``persist=True``.
    """
    started = time.monotonic()
    budget_s = max(0.0, float(budget_s))
    limit = max(0, int(limit))
    batch_size = max(1, int(batch_size))
    backend = _backend_name(matcher_spec)

    base: dict[str, Any] = {
        "status": "unreachable",
        "backend": backend,
        "model": None,
        "embedded": 0,
        "candidates": 0,
        "remaining": 0,
        "stopped": "unreachable",
        "more": False,
        "budget_s": budget_s,
        "elapsed_s": 0.0,
        "reason": "",
    }

    if not supports_embedding_store(store):
        base["reason"] = "store does not support tm_embeddings"
        base["elapsed_s"] = round(time.monotonic() - started, 3)
        return base

    if not cache_enabled():
        base["reason"] = (
            "embedding cache disabled — set NESTOR_CACHE_KEY "
            "(or NESTOR_SEAL_KEY) so vectors can be MAC'd"
        )
        base["elapsed_s"] = round(time.monotonic() - started, 3)
        return base

    if matcher is None:
        try:
            matcher = answer.build_matcher(backend, persist=True)
        except (ValueError, RuntimeError, ImportError) as exc:
            base["reason"] = str(exc)
            base["elapsed_s"] = round(time.monotonic() - started, 3)
            return base

    model_name = getattr(matcher, "model_name", None) or backend
    base["model"] = model_name

    if limit == 0 or budget_s == 0.0:
        # Probe emptiness without embedding: a zero budget still reports state.
        candidates = _collect_candidates(
            store, source_lang=source_lang, target_lang=target_lang,
            status=status, model_name=model_name, limit=1,
        )
        base["status"] = "empty" if not candidates else "ok"
        base["candidates"] = len(candidates)
        base["remaining"] = len(candidates)
        base["stopped"] = "budget" if candidates else "done"
        base["more"] = bool(candidates)
        base["elapsed_s"] = round(time.monotonic() - started, 3)
        return base

    candidates = _collect_candidates(
        store, source_lang=source_lang, target_lang=target_lang,
        status=status, model_name=model_name, limit=limit,
    )
    base["candidates"] = len(candidates)
    if not candidates:
        base["status"] = "empty"
        base["stopped"] = "done"
        base["more"] = False
        base["elapsed_s"] = round(time.monotonic() - started, 3)
        return base

    deadline = started + budget_s
    embedded = 0
    stopped = "done"
    # Collection stopped at ``limit`` — more cold rows may sit past this page.
    hit_limit = len(candidates) >= limit
    warm = getattr(matcher, "warm_embeddings", None)
    for i in range(0, len(candidates), batch_size):
        if time.monotonic() >= deadline:
            stopped = "budget"
            break
        batch = candidates[i:i + batch_size]
        if warm is not None:
            embedded += int(warm(batch, store))
        else:
            # Defensive: a custom matcher without warm_embeddings.
            matcher.scores_against_for_rows("\u0000", batch, store)
            embedded += len(batch)
    else:
        # Finished all candidate batches without breaking on budget.
        if time.monotonic() >= deadline and embedded < len(candidates):
            stopped = "budget"

    remaining = max(0, len(candidates) - embedded)
    if stopped == "done" and (remaining or hit_limit):
        # Cap filled this tick; keep running until status=empty.
        stopped = "limit"

    base.update({
        "status": "ok",
        "embedded": embedded,
        "remaining": remaining,
        "stopped": stopped,
        "more": bool(hit_limit or remaining),
        "elapsed_s": round(time.monotonic() - started, 3),
        "reason": "",
    })
    return base
