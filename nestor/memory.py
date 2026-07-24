"""Nestor's ledger — the translation memory. Tier 1 of the cascade.

Verified pairs live in whatever store is injected. A pair is "sealed"
(human-verified or curated-corpus) or "draft" (machine, awaiting seal).
Tier-1 serving uses sealed pairs only; drafts may be offered as context to
the engine but never served as verified.

Storage inversion
-----------------
This module owns the *algorithm* — source-text normalization and difflib
fuzzy scoring — and delegates every persistence operation to an injected
``Storage`` (see :mod:`nestor.storage`). Each public function takes an
optional ``store=`` argument; when omitted the process-wide store from
``set_store`` is used.

The corpus-seeding path used to import ``_load_bilingual_pairs`` from the
host. That is now an injected, optional callable — set one with
:func:`set_bilingual_loader`, or pass ``loader=`` to :func:`seed_from_corpus`.
The default loader returns ``[]`` (nothing to seed).
"""
from __future__ import annotations

import difflib
import re
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional

from .storage import Storage, get_store

EXACT = 1.0
SEAL_THRESHOLD = 0.92   # fuzzy similarity at/above which a sealed pair serves as tier 1
CONTEXT_THRESHOLD = 0.55  # pairs above this feed the engine as context


# --------------------------------------------------------------------------
# Injected bilingual-pair loader (was a host import of learn._load_bilingual_pairs)
# --------------------------------------------------------------------------

def _default_bilingual_loader() -> list[dict]:
    return []


_bilingual_loader: Callable[[], list[dict]] = _default_bilingual_loader


def set_bilingual_loader(fn: Callable[[], list[dict]]) -> None:
    """Install the callable that yields bilingual seed pairs.

    ``fn()`` must return a list of dicts, each with the keys
    ``front``, ``back``, ``lang_front``, ``lang_back`` and ``lesson`` —
    the shape produced by the host's ``learn._load_bilingual_pairs``.
    """
    global _bilingual_loader
    _bilingual_loader = fn


# --------------------------------------------------------------------------
# Translation-memory operations
# --------------------------------------------------------------------------

def init_tm(store: Optional[Storage] = None) -> None:
    store = get_store(store)
    store.memory_init()


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", text.lower())).strip()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_pair(source_text: str, target_text: str, source_lang: str, target_lang: str,
             status: str = "draft", verifier: str = "", weight: float = 1.0,
             origin: str = "", store: Optional[Storage] = None) -> dict:
    """Insert or upgrade a pair. A sealed insert replaces a draft for the same source."""
    store = get_store(store)
    store.memory_init()
    norm = _norm(source_text)
    existing = store.memory_find(norm, source_lang, target_lang)
    if existing:
        if status == "sealed" and (
            existing["status"] != "sealed" or existing["target_text"] != target_text
        ):
            store.memory_seal(existing["id"], target_text, verifier, weight)
            existing = store.memory_find(norm, source_lang, target_lang)
        return existing
    pair = dict(id=str(uuid.uuid4()), source_text=source_text, source_norm=norm,
                source_lang=source_lang, target_text=target_text, target_lang=target_lang,
                status=status, verifier=verifier, weight=weight, origin=origin,
                created_at=_now())
    store.memory_insert(pair)
    return pair


def lookup(source_text: str, source_lang: str, target_lang: str,
           limit: int = 5, store: Optional[Storage] = None) -> list[dict]:
    """Ranked matches: [{pair, similarity}], best first. Sealed and draft both returned."""
    store = get_store(store)
    store.memory_init()
    norm = _norm(source_text)
    rows = store.memory_candidates(source_lang, target_lang)
    scored = []
    for row in rows:
        if row["source_norm"] == norm:
            sim = EXACT
        else:
            sim = difflib.SequenceMatcher(None, norm, row["source_norm"]).ratio()
        if sim >= CONTEXT_THRESHOLD:
            scored.append({"pair": row, "similarity": round(sim, 3)})
    scored.sort(key=lambda m: (-m["similarity"], m["pair"]["status"] != "sealed"))
    return scored[:limit]


def best_sealed(source_text: str, source_lang: str, target_lang: str,
                store: Optional[Storage] = None) -> Optional[dict]:
    """Tier-1 check: the best sealed match at/above SEAL_THRESHOLD, else None."""
    for m in lookup(source_text, source_lang, target_lang, store=store):
        if m["pair"]["status"] == "sealed" and m["similarity"] >= SEAL_THRESHOLD:
            return m
    return None


def seed_from_corpus(loader: Optional[Callable[[], list[dict]]] = None,
                     store: Optional[Storage] = None) -> int:
    """Seed sealed pairs from bilingual lessons supplied by an injected loader.

    ``loader`` (or the one set via :func:`set_bilingual_loader`) returns the
    curated bilingual pairs; both directions of each pair are sealed into the
    memory. Returns the number of pairs written.
    """
    store = get_store(store)
    loader = loader or _bilingual_loader
    count = 0
    for item in loader():
        if item.get("front") and item.get("back"):
            add_pair(item["front"], item["back"], item["lang_front"], item["lang_back"],
                     status="sealed", verifier="corpus", origin=item.get("lesson", ""),
                     store=store)
            add_pair(item["back"], item["front"], item["lang_back"], item["lang_front"],
                     status="sealed", verifier="corpus", origin=item.get("lesson", ""),
                     store=store)
            count += 2
    return count


def stats(store: Optional[Storage] = None) -> dict:
    store = get_store(store)
    store.memory_init()
    return store.memory_stats()
