"""Nestor — meaning infrastructure. In medio, fides.

The fidelity layer: a three-tier cascade per segment.
  tier 1 · Nestor's ledger — translation-memory hit, served sealed
  tier 2 · Nova's draft   — glossary-constrained LLM interpretation, marked draft
  tier 3 · Nestor's seal  — human verification graduates segments into memory

A reviewer's "no" is recorded too: ``reject_segment`` (and ``memory.reject_match``
/ ``memory.reject_pair``) suppress a wrong candidate so it is never offered for
that input again, and land in the same ledger as a seal.

Standalone package. Persistence is injected via :mod:`nestor.storage`
(``set_store`` / ``get_store``); a reference SQLite implementation lives in
:mod:`nestor.sqlite_store`.
"""
from __future__ import annotations

from . import (
    cascade,
    curator,
    engine,
    entity,
    frank,
    glossary,
    langid,
    matcher,
    memory,
    reconcile,
    segment,
    storage,
)
from .cascade import (
    Passage,
    graduate_segment,
    reject_segment,
    set_ledger_path,
    translate_segment,
    translate_text,
)
from .curator import Curator
from .entity import EntityResolver
from .frank import set_forwarder as set_frank_forwarder
from .matcher import Matcher, NumericMatcher, StringMatcher
from .memory import (
    get_matcher,
    reject_match,
    reject_pair,
    set_bilingual_loader,
    set_matcher,
)
from .reconcile import Reconciler
from .storage import (
    Storage,
    get_store,
    set_store,
    supports_curation,
    supports_rejection,
)

__all__ = [
    "Curator",
    "EntityResolver",
    "Matcher",
    "NumericMatcher",
    "Passage",
    "Reconciler",
    "Storage",
    "StringMatcher",
    "cascade",
    "curator",
    "engine",
    "entity",
    "frank",
    "get_matcher",
    "get_store",
    "glossary",
    "graduate_segment",
    "langid",
    "matcher",
    "memory",
    "reconcile",
    "reject_match",
    "reject_pair",
    "reject_segment",
    "segment",
    "set_bilingual_loader",
    "set_frank_forwarder",
    "set_ledger_path",
    "set_matcher",
    "set_store",
    "storage",
    "supports_curation",
    "supports_rejection",
    "translate_segment",
    "translate_text",
]
