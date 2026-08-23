"""Nestor — meaning infrastructure. In medio, fides.

The fidelity layer: a three-tier cascade per segment.
  tier 1 · Nestor's ledger — translation-memory hit, served sealed
  tier 2 · Nova's draft   — glossary-constrained LLM interpretation, marked draft
  tier 3 · Nestor's seal  — human verification graduates segments into memory

A reviewer's "no" is recorded too: ``reject_segment`` (and ``memory.reject_match``
/ ``memory.reject_pair``) suppress a wrong candidate so it is never offered for
that input again, and land in the same ledger as a seal.

Translation is one *recipe*. The same seal/serve/ledger mechanic resolves
entities (:class:`~nestor.entity.EntityResolver`) and reconciles figures
(:class:`~nestor.reconcile.Reconciler`) behind the :mod:`nestor.matcher` seam.

Surfaces, each a thin transport over :mod:`nestor.answer` so they cannot disagree
about what is verified — imported on demand rather than here, since a library
import should not pull in an HTTP server:

  * :mod:`nestor.ui`     — the browser (``nestor ui``)
  * :mod:`nestor.cli`    — the terminal (``nestor``)
  * :mod:`nestor.serve`  — a model, over MCP (``nestor serve``); it cannot seal

Standalone package. Persistence is injected via :mod:`nestor.storage`
(``set_store`` / ``get_store``); a reference SQLite implementation lives in
:mod:`nestor.sqlite_store`. :mod:`nestor.portable` moves a memory between
instances without laundering trust.
"""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _dist_version

#: The installed distribution's version, or ``"0+unknown"``.
#:
#: Read from installed metadata rather than written here, because
#: ``pyproject.toml`` already declares it and a second copy in this file would
#: be the defect ``test_engine.py::test_the_rule_is_written_once`` exists to
#: catch: two literals, no check, and a pending disagreement between them.
#:
#: ``"0+unknown"`` is a legal PEP 440 local version: it parses, it sorts below
#: every real release, and it cannot be mistaken for one — so a host that logs
#: it gets a string saying *nobody installed this* rather than a plausible lie.
#:
#: **What this reports is the distribution, not this file.** Measured, because
#: the obvious reading is wrong twice over:
#:
#: * A clone with **no install and no ``nestor.egg-info/``** reports
#:   ``0+unknown``. That is the state ``CLAUDE.md`` opens by warning about.
#: * A clone that has *ever* been installed into keeps ``nestor.egg-info/`` in
#:   the repo root, and ``importlib.metadata`` finds that as a distribution —
#:   so the same tree reports the declared version with nothing installed in
#:   the venv.
#: * A source tree on ``PYTHONPATH`` **in front of** an installed nestor runs
#:   this file and reports the *installed* version, because metadata is
#:   resolved by name across ``sys.path`` and does not care which copy of the
#:   module won the import. Shadow an installed release with a working tree and
#:   ``__version__`` names the release while the tree's code runs.
#:
#: No version literal appears in this comment, and that is not fussiness:
#: ``tests/test_version.py::test_the_version_is_written_once`` fired on an
#: earlier draft of this paragraph, which used the current version as an
#: example. A number in prose goes stale on the first bump exactly like a
#: number in code.
#:
#: The last one is a property of ``importlib.metadata``, not something worth
#: defeating here — the alternative is a literal in this file, which is the
#: defect the paragraph above refuses. It is written down so nobody debugs it
#: twice.
try:
    __version__ = _dist_version("nestor-meaning")
except PackageNotFoundError:  # running from a source tree, uninstalled
    __version__ = "0+unknown"

from . import (
    answer,
    cascade,
    curator,
    engine,
    entity,
    frank,
    glossary,
    langid,
    matcher,
    memory,
    persona,
    portable,
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
from .errors import NestorError
from .frank import set_forwarder as set_frank_forwarder
from .matcher import Matcher, NumericMatcher, StringMatcher
from .memory import (
    ConflictingDraftError,
    ConflictingSealError,
    RejectedPairError,
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
    "ConflictingDraftError",
    "ConflictingSealError",
    "Curator",
    "EntityResolver",
    "Matcher",
    "NestorError",
    "NumericMatcher",
    "Passage",
    "Reconciler",
    "RejectedPairError",
    "Storage",
    "StringMatcher",
    "__version__",
    "answer",
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
    "persona",
    "portable",
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
