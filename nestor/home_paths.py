"""Nestor's own household root — ``$NESTOR_HOME`` / ``~/.nestor``.

Nestor keeps its household state under a root **it names**. A person who
installs Nestor and nothing else should not find another product's brand in
their home directory: that is the audience test in
``docs/roots-willow-and-homestead.md`` applied to Nestor itself, the same way
it already argues a household user should not be handed ``WILLOW_*``.

A host that embeds Nestor into another face pins the root explicitly —
``NESTOR_HOME=~/.homestead`` puts the keep tree exactly where the homestead
seat wants it, without Nestor hardcoding a root it does not own. The binding
is one line at startup, the same obligation as ``nestor_seam.bind()``.

**Not the Nestor product dev default.** This tree still uses ``./data/`` and
``docs/dogfood/`` for day-to-day work. The household layout is for faces that
embed Nestor (Homestead · Affairs, etc.).
"""
from __future__ import annotations

import os
from pathlib import Path

__all__ = ["HomeRelocationRefused", "home", "keep_dir", "ledger_path", "bind_ledger"]

_ROOT_ENV = "NESTOR_HOME"
_ROOT_NAME = ".nestor"

# The root Nestor used to borrow. Still read — but only to refuse, see `home`.
# Never resolved to, because resolving it is the silent relocation.
_LEGACY_ENV = "HOMESTEAD_HOME"


class HomeRelocationRefused(RuntimeError):
    """``$HOMESTEAD_HOME`` is set and ``$NESTOR_HOME`` is not — refuse to guess.

    Raised instead of quietly resolving to ``~/.nestor``, because that answer
    is wrong in the one case that matters: a host already keeping a
    hash-chained ``keep/ledger.jsonl`` under the homestead root. Resolving
    elsewhere would not move that chain, it would start a second one, and two
    partial chains each verify on their own while the history between them is
    gone. A refusal the operator reads is recoverable; a fork they find at
    audit time is not.
    """


def home() -> Path:
    """Household root — ``$NESTOR_HOME`` or ``<user-home>/.nestor``.

    Raises :class:`HomeRelocationRefused` when the legacy ``$HOMESTEAD_HOME``
    is set without ``$NESTOR_HOME``, rather than picking one of two roots the
    operator may have meant.
    """
    override = os.environ.get(_ROOT_ENV)
    if override:
        return Path(override)
    legacy = os.environ.get(_LEGACY_ENV)
    if legacy:
        raise HomeRelocationRefused(
            f"${_LEGACY_ENV} is set ({legacy}) but ${_ROOT_ENV} is not. Nestor's "
            f"root is now ~/{_ROOT_NAME}, so resolving this silently would leave "
            f"any existing {legacy}/keep/ledger.jsonl behind and start a second "
            f"chain. Set {_ROOT_ENV}={legacy} to keep the current location, or "
            f"{_ROOT_ENV}=~/{_ROOT_NAME} once the keep tree has been moved. "
            f"See docs/home-paths.md."
        )
    return Path.home() / _ROOT_NAME


def keep_dir() -> Path:
    """Nestor-adjacent household state (ledger, future seam store)."""
    return home() / "keep"


def ledger_path() -> Path:
    """Pinned hash-chained ledger (``nestor_seam`` contract)."""
    return keep_dir() / "ledger.jsonl"


def bind_ledger() -> Path:
    """Point :mod:`nestor.cascade` at :func:`ledger_path` and return that path."""
    from .cascade import set_ledger_path

    path = ledger_path()
    set_ledger_path(path)
    return path
