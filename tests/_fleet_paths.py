"""Where sibling fleet checkouts and charter cards live on this machine.

CI / cloud containers historically pinned ``/workspace/jeles`` and
``/workspace/rudi193-cmd/willow-2.0`` (archive directory name). After the
2026-08-10 org-folder layout those paths are empty. Constitution *case cards*
now live in the charter repo (``governance/compliance/cases/``); jeles stays a
sibling package checkout.
"""
from __future__ import annotations

import os
import pathlib
import warnings

_HOME = pathlib.Path.home()

# Archive trees keep the historical directory segment ``willow-2.0`` on disk;
# prose and env vars use "legacy monolith" instead.
_LEGACY_MONOLITH_ARCHIVE_SEGMENTS = (
    "/workspace/rudi193-cmd/willow-2.0",
    "/workspace/willow-2.0",
    _HOME / "github/willow-memory/willow-2.0",
    _HOME / "github/willow-2.0",
    _HOME / "github-archive-greenfield-2026-08-10/archive/legacy-flat-2026-08-10/willow-2.0",
)


def _first_existing(*candidates: str | pathlib.Path | None) -> pathlib.Path | None:
    for raw in candidates:
        if not raw:
            continue
        path = pathlib.Path(raw).expanduser()
        if path.is_dir():
            return path.resolve()
    return None


def _legacy_monolith_repo_env() -> str | None:
    primary = os.environ.get("WILLOW_LEGACY_MONOLITH_REPO")
    if primary:
        return primary
    legacy = os.environ.get("WILLOW_20_REPO")
    if legacy:
        warnings.warn(
            "WILLOW_20_REPO is deprecated; set WILLOW_LEGACY_MONOLITH_REPO instead.",
            DeprecationWarning,
            stacklevel=3,
        )
        return legacy
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
    legacy_cases = [
        pathlib.Path(p) / "constitution/cases"
        for p in _LEGACY_MONOLITH_ARCHIVE_SEGMENTS[:4]
    ]
    found = _first_existing(
        pathlib.Path(charter) / "governance/compliance/cases" if charter else None,
        _HOME / "github/willow-memory/willow/governance/compliance/cases",
        _HOME / "github/willow/governance/compliance/cases",
        *legacy_cases,
    )
    return found or (
        _HOME / "github/willow-memory/willow/governance/compliance/cases"
    )


def legacy_monolith_checkout() -> pathlib.Path:
    """Archived legacy fleet monolith tree, if present (migrations / corpus extract only)."""
    found = _first_existing(
        _legacy_monolith_repo_env(),
        *_LEGACY_MONOLITH_ARCHIVE_SEGMENTS,
    )
    return found or pathlib.Path(_LEGACY_MONOLITH_ARCHIVE_SEGMENTS[0])


def willow20_checkout() -> pathlib.Path:
    """Deprecated alias for :func:`legacy_monolith_checkout`."""
    warnings.warn(
        "willow20_checkout() is deprecated; use legacy_monolith_checkout() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return legacy_monolith_checkout()
