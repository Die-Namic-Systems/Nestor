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

import uuid
from datetime import datetime, timezone
from typing import Callable, Optional

from . import signing
from .matcher import Matcher, StringMatcher
from .storage import Storage, get_store

EXACT = 1.0
SEAL_THRESHOLD = 0.92   # fuzzy similarity at/above which a sealed pair serves as tier 1
CONTEXT_THRESHOLD = 0.55  # pairs above this feed the engine as context


# --------------------------------------------------------------------------
# Injected matcher (the domain seam)
# --------------------------------------------------------------------------
#
# The memory used to hardcode text normalization (``_norm``) and difflib
# scoring. Both are now supplied by an injected :class:`~nestor.matcher.Matcher`
# so the same seal/serve/ledger mechanic works for translations, entities and
# numbers. The default is :class:`StringMatcher`, which reproduces the original
# translation behavior exactly — so every public signature stays
# backward-compatible.

_matcher: Matcher = StringMatcher()


def set_matcher(m: Matcher) -> None:
    """Install the process-wide matcher used when no explicit ``matcher=`` is passed."""
    global _matcher
    _matcher = m


def get_matcher(m: Optional[Matcher] = None) -> Matcher:
    """Resolve the matcher to use — an explicit argument wins, else the global."""
    return m if m is not None else _matcher


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
    """Backward-compatible alias for the default StringMatcher normalization.

    The normalization algorithm now lives in :class:`nestor.matcher.StringMatcher`;
    this thin wrapper is kept so any host that imported ``memory._norm`` keeps
    working.
    """
    return StringMatcher().normalize(text)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def add_pair(source_text: str, target_text: str, source_lang: str, target_lang: str,
             status: str = "draft", verifier: str = "", weight: float = 1.0,
             origin: str = "", store: Optional[Storage] = None,
             matcher: Optional[Matcher] = None) -> dict:
    """Insert or upgrade a pair. A sealed insert replaces a draft for the same source.

    ``source_lang`` / ``target_lang`` are generic DOMAIN tags: for translation
    they are languages; for entity resolution or numeric reconciliation they
    carry the entity-type / label bucket. The ``matcher`` (default
    :class:`StringMatcher`) decides how ``source_text`` is normalized.
    """
    store = get_store(store)
    matcher = get_matcher(matcher)
    store.memory_init()
    norm = matcher.normalize(source_text)
    # Bind the seal to a key the store does not hold (Nestor#2). Signing is
    # opt-in: with no NESTOR_SEAL_KEY, sign_seal returns "" and nothing changes.
    seal_sig = signing.sign_seal(norm, target_text, verifier) if status == "sealed" else ""
    existing = store.memory_find(norm, source_lang, target_lang)
    if existing:
        if status == "sealed" and (
            existing["status"] != "sealed" or existing["target_text"] != target_text
        ):
            store.memory_seal(existing["id"], target_text, verifier, weight, seal_sig)
            existing = store.memory_find(norm, source_lang, target_lang)
        return existing
    pair = dict(id=str(uuid.uuid4()), source_text=source_text, source_norm=norm,
                source_lang=source_lang, target_text=target_text, target_lang=target_lang,
                status=status, verifier=verifier, weight=weight, origin=origin,
                created_at=_now(), seal_sig=seal_sig)
    store.memory_insert(pair)
    return pair


def lookup(source_text: str, source_lang: str, target_lang: str,
           limit: int = 5, store: Optional[Storage] = None,
           matcher: Optional[Matcher] = None,
           context_threshold: Optional[float] = None) -> list[dict]:
    """Ranked matches: [{pair, similarity}], best first. Sealed and draft both returned.

    Scoring is delegated to the injected ``matcher`` (default StringMatcher, so
    translation behavior is unchanged). ``context_threshold`` overrides the
    module-level :data:`CONTEXT_THRESHOLD` floor below which candidates are
    dropped — pass ``0.0`` to keep every candidate (used by the numeric
    reconciler so a far-off figure is still returned for variation reporting).
    """
    store = get_store(store)
    matcher = get_matcher(matcher)
    ctx = CONTEXT_THRESHOLD if context_threshold is None else context_threshold
    store.memory_init()
    norm = matcher.normalize(source_text)
    rows = store.memory_candidates(source_lang, target_lang)
    scored = []
    for row in rows:
        sim = matcher.similarity(norm, row["source_norm"])
        if sim >= ctx:
            scored.append({"pair": row, "similarity": round(sim, 3)})
    scored.sort(key=lambda m: (-m["similarity"], m["pair"]["status"] != "sealed"))
    return scored[:limit]


def best_sealed(source_text: str, source_lang: str, target_lang: str,
                store: Optional[Storage] = None,
                matcher: Optional[Matcher] = None,
                seal_threshold: Optional[float] = None,
                context_threshold: Optional[float] = None) -> Optional[dict]:
    """Tier-1 check: the best sealed match at/above the seal threshold, else None.

    ``seal_threshold`` overrides the module-level :data:`SEAL_THRESHOLD`.
    """
    seal = SEAL_THRESHOLD if seal_threshold is None else seal_threshold
    for m in lookup(source_text, source_lang, target_lang, store=store,
                    matcher=matcher, context_threshold=context_threshold):
        p = m["pair"]
        # A "sealed" row is served as tier-1 only if its signature is valid.
        # When signing is disabled (no key) seal_is_valid is always True, so
        # behavior is unchanged; when enabled, a forged seal is not served.
        if (p["status"] == "sealed" and m["similarity"] >= seal
                and signing.seal_is_valid(p["source_norm"], p["target_text"],
                                          p["verifier"], p.get("seal_sig", ""))):
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
