"""Household paths aligned with the homestead seat (``homestead.keep.paths``).

The homestead repo owns the canonical resolver; this module mirrors its contract
so Nestor can pin ledger (and later store) paths under ``~/.homestead`` without
taking a dependency on homestead. Hosts call :func:`bind_ledger` once at startup
— same obligation as ``nestor_seam.bind()`` in the homestead design draft.

**Not the Nestor product dev default.** This tree still uses ``./data/`` and
``docs/dogfood/`` for day-to-day work. Household layout is for faces that embed
Nestor (Homestead · Affairs, etc.).
"""
from __future__ import annotations

import os
from pathlib import Path

__all__ = ["home", "keep_dir", "ledger_path", "bind_ledger"]

_ROOT_ENV = "HOMESTEAD_HOME"
_ROOT_NAME = ".homestead"


def home() -> Path:
    """Household root — ``$HOMESTEAD_HOME`` or ``<user-home>/.homestead``."""
    override = os.environ.get(_ROOT_ENV)
    if override:
        return Path(override)
    return Path.home() / _ROOT_NAME


def keep_dir() -> Path:
    """Nestor-adjacent household state (ledger, future seam store)."""
    return home() / "keep"


def ledger_path() -> Path:
    """Pinned hash-chained ledger (homestead / ``nestor_seam`` contract)."""
    return keep_dir() / "ledger.jsonl"


def bind_ledger() -> Path:
    """Point :mod:`nestor.cascade` at :func:`ledger_path` and return that path."""
    from .cascade import set_ledger_path

    path = ledger_path()
    set_ledger_path(path)
    return path
