"""Where sibling fleet checkouts and charter cards live on this machine.

CI / cloud containers historically pinned ``/workspace/jeles`` and
``/workspace/rudi193-cmd/willow-2.0``. After the 2026-08-10 org-folder layout
those paths are empty. Constitution *case cards* now live in the charter repo
(``governance/compliance/cases/``); jeles stays a sibling package checkout.
"""
from __future__ import annotations

import os
import pathlib

_HOME = pathlib.Path.home()


def _first_existing(*candidates: str | pathlib.Path | None) -> pathlib.Path | None:
    for raw in candidates:
        if not raw:
            continue
        path = pathlib.Path(raw).expanduser()
        if path.is_dir():
            return path.resolve()
    return None


def jeles_checkout() -> pathlib.Path:
    """Root of the Jeles git checkout (the directory that contains ``jeles/``)."""
    found = _first_existing(
        os.environ.get("JELES_REPO"),
        "/workspace/jeles",
        _HOME / "github/hornbook-knowledge/Jeles",
        _HOME / "github/Jeles",
        _HOME / "github/jeles",
    )
    return found or pathlib.Path("/workspace/jeles")


def constitution_cases() -> pathlib.Path:
    """Directory of declarative ``const_*.py`` Trace-ID cards (charter)."""
    env = os.environ.get("WILLOW_CONSTITUTION_CASES")
    if env:
        found = _first_existing(env)
        if found is not None:
            return found
    charter = os.environ.get("WILLOW_CHARTER_REPO")
    found = _first_existing(
        pathlib.Path(charter) / "governance/compliance/cases" if charter else None,
        _HOME / "github/willow-memory/willow/governance/compliance/cases",
        _HOME / "github/willow/governance/compliance/cases",
        # Legacy willow-2.0 layout (CI mount or greenfield archive clone):
        "/workspace/rudi193-cmd/willow-2.0/constitution/cases",
        "/workspace/willow-2.0/constitution/cases",
        _HOME / "github/willow-memory/willow-2.0/constitution/cases",
    )
    return found or (
        _HOME / "github/willow-memory/willow/governance/compliance/cases"
    )


def willow20_checkout() -> pathlib.Path:
    """Archived willow-2.0 tree, if present (migrations / corpus extract only)."""
    found = _first_existing(
        os.environ.get("WILLOW_20_REPO"),
        "/workspace/rudi193-cmd/willow-2.0",
        "/workspace/willow-2.0",
        _HOME / "github/willow-memory/willow-2.0",
        _HOME / "github/willow-2.0",
        # Greenfield archive of the pre-move flat tree:
        _HOME / "github-archive-greenfield-2026-08-10/archive/legacy-flat-2026-08-10/willow-2.0",
    )
    return found or pathlib.Path("/workspace/rudi193-cmd/willow-2.0")
