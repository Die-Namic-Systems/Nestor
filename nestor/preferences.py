"""Per-user, cross-session preferences — the §7.5 gap.

Not config (``nestor.config`` is per-deployment, correctness-affecting).
Not a decision (preferences are not sealed, don't constrain future work).
Not session context (preferences survive the session).
Not synced (the file lives under ``NESTOR_HOME`` on one machine).

See ``docs/drafts/user-preferences.md`` for the design rationale.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import home_paths

__all__ = [
    "KNOWN_KEYS",
    "clear",
    "get",
    "load",
    "path",
    "reset",
    "save",
    "set_pref",
]

_FILE = "preferences.json"
_SCHEMA_VERSION = 1

KNOWN_KEYS: dict[str, dict[str, Any]] = {
    "output.format":          {"type": "str",  "default": "text",
                               "choices": ("text", "json", "markdown")},
    "output.emoji":           {"type": "bool", "default": False},
    "serve.default_domain":   {"type": "str",  "default": "decision"},
    "serve.read_only":        {"type": "bool", "default": False},
    "ui.theme":               {"type": "str",  "default": "system",
                               "choices": ("system", "light", "dark")},
    "ui.page_size":           {"type": "int",  "default": 25},
    "cli.color":              {"type": "bool", "default": True},
    "cli.verbose":            {"type": "bool", "default": False},
}


def path(home: Path | None = None) -> Path:
    """Absolute path to the preferences file."""
    root = home if home is not None else home_paths.home()
    return root / _FILE


def load(home: Path | None = None) -> dict[str, Any]:
    """Load preferences. Returns the ``preferences`` dict (empty if file missing)."""
    p = path(home)
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise PreferencesError(f"cannot read {p}: {exc}") from exc
    if not isinstance(data, dict):
        raise PreferencesError(f"{p} is not a JSON object")
    return data.get("preferences", {})


def save(prefs: dict[str, Any], *, user: str = "",
         home: Path | None = None) -> Path:
    """Write preferences atomically (write-to-tmp, rename)."""
    p = path(home)
    envelope: dict[str, Any] = {
        "nestor_preferences": _SCHEMA_VERSION,
        "user": user,
        "preferences": prefs,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    existing = _load_envelope(home)
    if existing:
        envelope["user"] = envelope["user"] or existing.get("user", "")

    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    try:
        os.write(fd, (json.dumps(envelope, indent=2, ensure_ascii=False) + "\n").encode())
        os.close(fd)
        os.replace(tmp, str(p))
    except BaseException:
        os.close(fd) if not _fd_closed(fd) else None
        with _suppress():
            os.unlink(tmp)
        raise
    return p


def get(key: str, default: Any = None, home: Path | None = None) -> Any:
    """Read one preference by dotted key."""
    prefs = load(home)
    if key in prefs:
        return prefs[key]
    spec = KNOWN_KEYS.get(key)
    if spec is not None:
        return spec["default"]
    return default


def set_pref(key: str, value: Any, *, user: str = "",
             home: Path | None = None) -> None:
    """Set one preference. Validates against KNOWN_KEYS when the key is known."""
    value = _coerce(key, value)
    prefs = load(home)
    prefs[key] = value
    save(prefs, user=user, home=home)


def clear(key: str, home: Path | None = None) -> bool:
    """Remove one preference (revert to default). Returns True if it existed."""
    prefs = load(home)
    if key not in prefs:
        return False
    del prefs[key]
    save(prefs, home=home)
    return True


def reset(home: Path | None = None) -> bool:
    """Delete the preferences file entirely. Returns True if it existed."""
    p = path(home)
    if not p.is_file():
        return False
    p.unlink()
    return True


class PreferencesError(Exception):
    """A preferences file that cannot be read or is structurally wrong."""


def _load_envelope(home: Path | None = None) -> dict[str, Any]:
    """Load the full envelope (not just ``preferences``)."""
    p = path(home)
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _coerce(key: str, value: Any) -> Any:
    """Validate and coerce a value for a known key."""
    spec = KNOWN_KEYS.get(key)
    if spec is None:
        return value
    kind = spec["type"]
    if kind == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            low = value.lower()
            if low in ("true", "1", "yes", "on"):
                return True
            if low in ("false", "0", "no", "off"):
                return False
        raise PreferencesError(f"{key}: expected bool, got {value!r}")
    if kind == "int":
        try:
            return int(value)
        except (ValueError, TypeError) as exc:
            raise PreferencesError(f"{key}: expected int, got {value!r}") from exc
    if kind == "str":
        value = str(value)
        choices = spec.get("choices")
        if choices and value not in choices:
            raise PreferencesError(
                f"{key}: must be one of {', '.join(choices)}, got {value!r}")
        return value
    return value


def _fd_closed(fd: int) -> bool:
    try:
        os.fstat(fd)
        return False
    except OSError:
        return True


def _suppress():
    import contextlib
    return contextlib.suppress(OSError)
