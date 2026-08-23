"""Idempotent scaffolder for the Nestor household home (``$NESTOR_HOME`` / ``~/.nestor``).

Re-land of willow-mcp's ``src/willow_mcp/home_init.py`` (``ensure_home_layout``) —
the "create the tree if absent, write a default file only when missing, never
clobber an operator's own content" pattern — narrowed to Nestor's household
layout. Path resolution is **not** duplicated: this module builds *on*
:mod:`nestor.home_paths` for **where** the home lives, and adds only the
idempotent **create**.

The household tree it guarantees (see ``docs/home-paths.md``)::

    <home>/
      keep/        # hash-chained ledger lives here (cascade owns the file)
      record/      # canonical household record
      logs/        # sealed log (I-22)
      drafts/
      layout.json  # written once; a version marker, never overwritten

The ledger file itself (``keep/ledger.jsonl``) is **not** pre-created here:
:mod:`nestor.cascade` owns its genesis and treats a missing file as a fresh
chain, so seeding an empty one would step on that contract. This scaffolder
makes the *directories* exist; cascade appends the *file*.

Deterministic and stdlib-only. Safe to call repeatedly.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from . import home_paths

__all__ = ["SUBDIRS", "ensure_home_layout", "layout_manifest_path", "required_dirs"]

_LAYOUT_VERSION = "nestor_household_v1"

# Directory tree under the household root, in a fixed order so the reported
# ``dirs_created`` is deterministic. ``keep`` first because it is the
# load-bearing one (the ledger's parent); the rest mirror the household seat.
SUBDIRS: tuple[str, ...] = ("keep", "record", "logs", "drafts")

_DEFAULT_MANIFEST: dict[str, Any] = {
    "format": _LAYOUT_VERSION,
    "dirs": list(SUBDIRS),
}


def _resolve_home(home: Path | None) -> Path:
    """Resolve the household root, reusing :mod:`home_paths` for the *where*.

    When ``home`` is given it is pinned via ``$NESTOR_HOME`` so every
    ``home_paths`` helper (``keep_dir``, ``ledger_path``) agrees with it —
    the same trick willow-mcp uses with ``$WILLOW_HOME``. When ``home`` is None
    the resolver's own default (``$NESTOR_HOME`` or ``~/.nestor``) wins.
    """
    if home is not None:
        os.environ[home_paths._ROOT_ENV] = str(home)
    return home_paths.home()


def required_dirs(home: Path | None = None) -> list[Path]:
    """Absolute paths of the household directories, in scaffold order.

    ``keep`` is taken from :func:`home_paths.keep_dir` so the ledger's
    parent stays authoritative; the siblings hang off the same resolved root.
    """
    root = _resolve_home(home)
    keep = home_paths.keep_dir()
    return [keep] + [root / name for name in SUBDIRS if name != "keep"]


def layout_manifest_path(home: Path | None = None) -> Path:
    """The written-once household layout marker (``<home>/layout.json``)."""
    return _resolve_home(home) / "layout.json"


def _write_json_if_missing(path: Path, data: dict[str, Any]) -> bool:
    """Write ``data`` as JSON only when ``path`` is absent. Never clobbers.

    Returns True when the file was created, False when it already existed (its
    content is left exactly as the operator left it).
    """
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return True


def ensure_home_layout(home: Path | None = None) -> dict[str, Any]:
    """Create the household tree under the resolved home. Idempotent.

    Missing directories are created; existing ones are left untouched. The
    ``layout.json`` marker is written only when absent. Nothing that already
    exists is overwritten, so a second call is a clean no-op and an operator's
    own files inside the tree are always preserved.
    """
    root = _resolve_home(home)

    created_dirs: list[str] = []
    for d in required_dirs():
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            created_dirs.append(str(d.relative_to(root)))

    files_created: list[str] = []
    manifest = layout_manifest_path()
    if _write_json_if_missing(manifest, _DEFAULT_MANIFEST):
        files_created.append(str(manifest.relative_to(root)))

    return {
        "home": str(root),
        "layout_version": _LAYOUT_VERSION,
        "dirs_created": created_dirs,
        "files_created": files_created,
    }


def main() -> None:
    print(json.dumps(ensure_home_layout(), indent=2))


if __name__ == "__main__":
    main()
