"""Established-knowledge lane for Nestor.

Recognition only — never seals. Sits between the tier-1 sealed lookup and
the tier-2 engine draft (see decision 0205 for the seam in
:mod:`nestor.cascade`), so a query that hits a lexicon entry (``42`` →
"the answer to life, the universe, and everything") or a trusted-corpus
nugget (a Jeles Q&A pair with ``verification_kind`` ``human`` or ``machine``)
lands as a draft with citation warrants instead of falling to the engine
and cluttering the human seal queue.

Public surface — see the individual modules for details:

* :func:`recognize` / :func:`recognize_lexicon` — pure lookups, no
  store writes. Return an established-shaped hit dict or ``None``.
* :func:`ensure_established_draft` — the writer: given a lookup hit,
  land a draft pair with an evidence row and a citation warrant.
  Idempotent per source_norm; refuses to write when the pair has been
  previously rejected.
* :func:`install` / :func:`uninstall` — wire the recognizer through
  :func:`nestor.cascade.set_tier15_recognizer` (decision 0205's seam).
  Process-local; safe to call in a test's setup and undo in teardown.
* :func:`recognize_from_jeles` / :func:`seed_demo_nuggets` — the Jeles
  bridge. ``jeles`` is imported lazily so the core module tree does not
  hard-depend on it.
* :data:`DEFAULT_LEXICON` — the shipped small lexicon (``42``, ``404``,
  ``paris``, ``big blue``). Callers may substitute their own via
  ``lexicon=`` on every recognizer function.

Decisions: 0205 (the seam), 0206 (this subpackage).
"""
from __future__ import annotations

from .jeles_bridge import recognize_from_jeles, seed_demo_nuggets
from .recognize import (
    DEFAULT_LEXICON,
    ensure_established_draft,
    recognize,
    recognize_lexicon,
)
from .wire import install, installed, uninstall

__all__ = [
    "DEFAULT_LEXICON",
    "ensure_established_draft",
    "install",
    "installed",
    "recognize",
    "recognize_from_jeles",
    "recognize_lexicon",
    "seed_demo_nuggets",
    "uninstall",
]
