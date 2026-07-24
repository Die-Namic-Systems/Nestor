"""Nestor — meaning infrastructure. In medio, fides.

The fidelity layer: a three-tier cascade per segment.
  tier 1 · Nestor's ledger — translation-memory hit, served sealed
  tier 2 · Nova's draft   — glossary-constrained LLM interpretation, marked draft
  tier 3 · Nestor's seal  — human verification graduates segments into memory

Standalone package. Persistence is injected via :mod:`nestor.storage`
(``set_store`` / ``get_store``); a reference SQLite implementation lives in
:mod:`nestor.sqlite_store`.
"""
from __future__ import annotations

from . import (
    cascade,
    engine,
    entity,
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
    set_ledger_path,
    translate_segment,
    translate_text,
)
from .entity import EntityResolver
from .matcher import Matcher, NumericMatcher, StringMatcher
from .memory import get_matcher, set_bilingual_loader, set_matcher
from .reconcile import Reconciler
from .storage import Storage, get_store, set_store

__all__ = [
    "EntityResolver",
    "Matcher",
    "NumericMatcher",
    "Passage",
    "Reconciler",
    "Storage",
    "StringMatcher",
    "cascade",
    "engine",
    "entity",
    "get_matcher",
    "get_store",
    "glossary",
    "graduate_segment",
    "langid",
    "matcher",
    "memory",
    "reconcile",
    "segment",
    "set_bilingual_loader",
    "set_ledger_path",
    "set_matcher",
    "set_store",
    "storage",
    "translate_segment",
    "translate_text",
]
