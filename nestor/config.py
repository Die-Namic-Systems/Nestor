"""nestor.config — one layered resolver, one precedence order: env > file > default.

Nestor reads knobs the way most young codebases do: ``os.environ.get(name,
default)`` scattered across a dozen modules, each inventing its own default and
its own idea of what an empty string means. That is fine until two of them
disagree about the same setting, and then nobody can say which one wins without
reading all twelve. This module is the single place that answer lives.

The order is fixed and total: an environment variable overrides a config-file
value, which overrides the code default. Nothing else is consulted, and the same
inputs always produce the same output — no clock, no network, no import-order
surprise. Callers ask for a *typed* value (:meth:`Resolver.get_int`,
:meth:`~Resolver.get_bool`, …); a value that cannot be cast is a raised
:class:`ConfigError`, never a quietly-substituted zero.

The one rule that earns this module its keep: **absence surfaces as unknown,
never as a result.** A config file that is *not there* is a legitimate empty
layer — the resolver drops to the default, because "no file" is a real, declared
state. A config file that is there but *malformed or unreadable* is not empty; it
is unknown, and unknown is a :class:`ConfigError`, because degrading a broken
file to "use the default" would hand back a wrong value while looking healthy.
Missing and broken are different facts and this module keeps them different.

Secrets, following the njord seam this was ported from, are env-only: this module
knows the *names* of secret env vars, never their values, and no secret is ever
read out of the config file. Use :func:`get_secret` for those.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping, Optional

__all__ = [
    "ConfigError",
    "Resolver",
    "VarSpec",
    "load",
    "load_file",
    "default_config_path",
    "get_secret",
    "get_bool_loose",
    "secret_names",
    "configurable_names",
    "REGISTRY",
    "ENV_PREFIX",
    "CONFIG_PATH_ENV",
    "DEFAULT_CONFIG_FILENAME",
]

#: Env-var prefix for auto-derived names: file key ``ledger`` -> ``NESTOR_LEDGER``.
ENV_PREFIX = "NESTOR_"

#: Env var naming the config file's location (itself an env override of the path).
CONFIG_PATH_ENV = "NESTOR_CONFIG"

#: Default config-file name, looked for in the current working directory.
DEFAULT_CONFIG_FILENAME = "nestor.config.json"

#: Strings accepted as booleans. Anything else is a ConfigError, not a silent False.
_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off", ""})


class ConfigError(RuntimeError):
    """Configuration is unusable: a malformed/unreadable file, or a value that
    cannot be cast to the requested type. Never raised for a *missing* file —
    that is a legitimate empty layer, not an error."""


def default_config_path() -> Path:
    """Where the config file lives: ``$NESTOR_CONFIG`` if set, else
    ``./nestor.config.json`` in the current working directory.

    This is only the *path*; the file need not exist. A non-existent path is a
    valid answer (no file layer), which is why this never raises.
    """
    override = os.environ.get(CONFIG_PATH_ENV)
    if override and override.strip():
        return Path(override).expanduser()
    return Path.cwd() / DEFAULT_CONFIG_FILENAME


def load_file(path: Optional[Path]) -> dict[str, Any]:
    """Read the file layer as a flat mapping. The heart of the missing/broken
    distinction:

    * ``path is None`` or the file **does not exist** -> ``{}`` (no file layer).
      Absence of a file is a declared state, not a failure.
    * the file exists but is **unreadable** (permissions, is-a-directory, decode
      error) -> :class:`ConfigError`. We cannot say whether it held an override,
      so we refuse to pretend it was empty.
    * the file exists but is **malformed** (not JSON, or JSON that is not a
      top-level object) -> :class:`ConfigError`. A broken file is unknown, and
      unknown never degrades to the default silently.
    """
    if path is None:
        return {}
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(
            f"config file {str(path)!r} exists but could not be read ({exc}); "
            f"refusing to fall back to defaults over an unreadable override."
        ) from exc
    except UnicodeDecodeError as exc:
        raise ConfigError(
            f"config file {str(path)!r} is not valid UTF-8 text ({exc})."
        ) from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"config file {str(path)!r} is not valid JSON: {exc}. A malformed "
            f"config is unknown, not empty — fix the file or remove it."
        ) from exc
    if not isinstance(data, dict):
        raise ConfigError(
            f"config file {str(path)!r} must hold a JSON object at the top "
            f"level, not {type(data).__name__}."
        )
    return data


def _env_name(key: str) -> str:
    """Auto-derive the env-var name for a file key: ``foo.bar`` -> ``NESTOR_FOO_BAR``."""
    return ENV_PREFIX + key.strip().upper().replace(".", "_").replace("-", "_")


@dataclass(frozen=True)
class Resolver:
    """A deterministic env > file > default resolver over one env mapping and one
    file layer.

    Construct with :func:`load` (which reads the environment and config file for
    you) or directly with an explicit ``env`` mapping and ``file_data`` — the
    explicit form takes no I/O and is what the tests pin precedence with.

    Every accessor takes the *file key*, a *default*, and an optional ``env``
    override for the environment-variable name (defaults to the auto-derived
    ``NESTOR_<KEY>``). Precedence per lookup:

        1. environment variable, if present and non-empty
        2. file value, if the key is present
        3. the supplied default
    """

    env: Mapping[str, str] = field(default_factory=dict)
    file_data: Mapping[str, Any] = field(default_factory=dict)

    # -- layer resolution ---------------------------------------------------
    def _raw(self, key: str, env_name: Optional[str]) -> tuple[str, Any]:
        """Return ``(source, value)`` for the winning layer, or
        ``("default", _MISSING)`` when neither env nor file supplies the key.
        ``source`` is one of ``"env"``, ``"file"``, ``"default"``."""
        name = env_name or _env_name(key)
        raw_env = self.env.get(name)
        if raw_env is not None and raw_env.strip() != "":
            return "env", raw_env
        if key in self.file_data:
            return "file", self.file_data[key]
        return "default", _MISSING

    def source_of(self, key: str, *, env: Optional[str] = None) -> str:
        """Which layer would answer ``key``: ``"env"``, ``"file"`` or ``"default"``.
        Handy for logging where a value came from without leaking the value."""
        return self._raw(key, env)[0]

    # -- typed accessors ----------------------------------------------------
    def get_str(self, key: str, default: str, *, env: Optional[str] = None) -> str:
        source, value = self._raw(key, env)
        if source == "default":
            return default
        if source == "env":
            return value
        if not isinstance(value, str):
            raise self._cast_error(key, source, value, "string")
        return value

    def get_int(self, key: str, default: int, *, env: Optional[str] = None) -> int:
        source, value = self._raw(key, env)
        if source == "default":
            return default
        try:
            if source == "env":
                return int(value.strip())
            if isinstance(value, bool):  # bool is an int subclass — reject it explicitly
                raise ValueError("boolean is not an integer")
            return int(value)
        except (ValueError, TypeError) as exc:
            raise self._cast_error(key, source, value, "integer") from exc

    def get_float(self, key: str, default: float, *, env: Optional[str] = None) -> float:
        source, value = self._raw(key, env)
        if source == "default":
            return default
        try:
            if source == "env":
                return float(value.strip())
            if isinstance(value, bool):
                raise ValueError("boolean is not a float")
            return float(value)
        except (ValueError, TypeError) as exc:
            raise self._cast_error(key, source, value, "float") from exc

    def get_bool(self, key: str, default: bool, *, env: Optional[str] = None) -> bool:
        source, value = self._raw(key, env)
        if source == "default":
            return default
        if source == "file" and isinstance(value, bool):
            return value
        token = str(value).strip().lower()
        if token in _TRUE:
            return True
        if token in _FALSE:
            return False
        raise self._cast_error(
            key, source, value,
            f"boolean (one of {sorted(_TRUE | (_FALSE - {''}))})",
        )

    def get_path(self, key: str, default: Any, *, env: Optional[str] = None) -> Path:
        """Resolve a filesystem path, ``~`` expanded. ``default`` may be a str or
        Path. Never touches disk — resolves the string only."""
        source, value = self._raw(key, env)
        if source == "default":
            return Path(default).expanduser()
        if not isinstance(value, str):
            raise self._cast_error(key, source, value, "path string")
        return Path(value).expanduser()

    @staticmethod
    def _cast_error(key: str, source: str, value: Any, want: str) -> ConfigError:
        where = f"env override {_env_name(key)!r}" if source == "env" else f"config-file key {key!r}"
        return ConfigError(
            f"{where} = {value!r} is not a valid {want}; refusing to substitute "
            f"a default over a value that was actually set."
        )


class _Missing:
    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debug aid only
        return "<missing>"


#: Sentinel for "no layer supplied this key" — distinct from a supplied ``None``.
_MISSING = _Missing()


def load(
    *,
    env: Optional[Mapping[str, str]] = None,
    path: Optional[Path] = None,
) -> Resolver:
    """Build a :class:`Resolver` from the live environment and the config file.

    ``env`` defaults to ``os.environ``; ``path`` defaults to
    :func:`default_config_path`. A missing file yields an empty file layer; a
    malformed or unreadable file raises :class:`ConfigError` (see
    :func:`load_file`).
    """
    resolved_env: Mapping[str, str] = os.environ if env is None else env
    resolved_path = default_config_path() if path is None else path
    return Resolver(env=dict(resolved_env), file_data=load_file(resolved_path))


def get_secret(env_name: str, *, env: Optional[Mapping[str, str]] = None) -> Optional[str]:
    """Single seam for secret retrieval, ported from njord: **env only**. Secrets
    are never read from the config file and never stored in this module — only
    the env-var *name* is passed in. An OS-keyring lookup can be added here later
    without touching call sites."""
    source = os.environ if env is None else env
    value = source.get(env_name)
    if value is not None and value.strip() == "":
        return None
    return value


def get_bool_loose(name: str, default: bool, true_tokens: frozenset[str],
                    *, env: Optional[Mapping[str, str]] = None) -> bool:
    """A second, **permissive** boolean reader, kept apart from
    :meth:`Resolver.get_bool` on purpose.

    A handful of call sites (``NESTOR_REQUIRE_SEAL_KEY``, ``NESTOR_FRANK_STRICT``,
    ``NESTOR_SEMANTIC_TEST``) predate this module and were each written as
    ``os.environ.get(NAME, "").strip().lower() in (...)`` — an unrecognized token
    silently reads as ``False``, not a raised error, and each site accepts its own
    slightly different set of truthy spellings (one omits ``"on"``; one accepts
    only the literal ``"1"``). :meth:`Resolver.get_bool` is strict by design — an
    unrecognized token is a :class:`ConfigError` — which is the right default for
    a *new* setting but would be a silent behavior change for these three: turning
    a typo that used to read as "off" into a hard refusal is not a refactor.

    This function is the adoption seam for that shape: env-only (these sites
    never had a file layer and gaining one is out of scope for a
    behavior-preserving migration), and it reproduces the exact
    unset/blank/unrecognized -> ``default`` fallthrough every one of them had.
    Route the *name* through :data:`REGISTRY` even when the parsing stays loose,
    so the enumeration remains complete.
    """
    source = os.environ if env is None else env
    raw = (source.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw in true_tokens


#: What a config knob *is* — not what it currently holds. One entry per
#: ``NESTOR_*`` name this codebase reads, so a reviewer (or a hook, such as the
#: self-grant pin in ``hooks/before_authority.py``) has one place to enumerate
#: them instead of grepping ``nestor/*.py`` for ``os.environ``.
@dataclass(frozen=True)
class VarSpec:
    """One row of the registry.

    ``kind`` names the typed accessor a well-behaved caller resolves it with
    (``get_str`` / ``get_int`` / ``get_float`` / ``get_bool`` / ``get_path``) —
    documentation, not an enforcement the dataclass carries out itself.

    ``default`` is the value a caller falls back to when neither env nor file
    supplies the key. It is ``None`` for two different reasons that this
    registry does not need to tell apart: a secret has no safe default to
    print, and a few paths (``NESTOR_HOME``, ``NESTOR_GLOSSARY``) compute
    their fallback at call time (the user's home directory; the process's
    working directory captured at import) rather than carrying a literal.

    ``secret`` marks the key-material subset — ``NESTOR_SEAL_KEY`` and
    ``NESTOR_CACHE_KEY`` today — that must be resolved with :func:`get_secret`
    and never surfaced from the config file. See :func:`secret_names`.

    ``configurable`` is ``False`` for the two ``NESTOR_IDB_*`` entries: they
    are literal identifiers inside the browser-side IndexedDB script in
    :mod:`nestor.ui_page` (a database name and an object-store name), not
    environment variables any Nestor process reads. They are listed here for
    completeness — so "every ``NESTOR_*`` name in the tree" has one answer —
    and so nobody mistakes them for a settable knob.
    """

    name: str
    kind: Literal["str", "int", "float", "bool", "path"]
    default: Any = None
    secret: bool = False
    configurable: bool = True
    doc: str = ""


#: The single enumerated list IDEAS §7.5 asks for. Every ``NESTOR_*`` name
#: this tree reads or reserves, keyed by its full env-var name. Confirm new
#: entries against ``git grep 'NESTOR_' nestor/`` before adding one — this is
#: meant to be exhaustive, not aspirational.
REGISTRY: dict[str, VarSpec] = {
    v.name: v for v in (
        VarSpec("NESTOR_HOME", "path", default=None, doc=(
            "Household root for embedding hosts (nestor.home_paths). Default "
            "is computed at call time (`~/.nestor`), not a static literal — "
            "see home_paths.home().")),
        VarSpec("NESTOR_LEDGER", "path", default="data/ledger.jsonl", doc=(
            "Hash-chained ledger location (nestor.cascade).")),
        VarSpec("NESTOR_LEDGER_VERIFY_INTERVAL_SEC", "float", default=0.0, doc=(
            "Seconds between full ledger chain walks; 0 = once per process, "
            "<0 = every append (nestor.cascade).")),
        VarSpec("NESTOR_KEYRING", "path", default="", doc=(
            "Per-verifier keyring file. Empty/unset = no keyring, single "
            "shared NESTOR_SEAL_KEY (nestor.keyring).")),
        VarSpec("NESTOR_SEAL_KEY", "str", default=None, secret=True, doc=(
            "Shared HMAC seal key. Key material — env-only, via get_secret() "
            "(nestor.signing).")),
        VarSpec("NESTOR_REQUIRE_SEAL_KEY", "bool", default=False, doc=(
            "Fail closed instead of degrading to unsigned when no seal key "
            "is configured (nestor.signing). Not itself a secret — a "
            "fail-closed flag.")),
        VarSpec("NESTOR_GLOSSARY", "path", default=None, doc=(
            "Term-lock glossary file. Default is the cwd-relative "
            "data/glossary.json captured once at import (nestor.glossary).")),
        VarSpec("NESTOR_CACHE_KEY", "str", default=None, secret=True, doc=(
            "Embedding-cache HMAC key, separate from NESTOR_SEAL_KEY. Key "
            "material — env-only, via get_secret() (nestor.signing).")),
        VarSpec("NESTOR_SEMANTIC_TEST", "bool", default=False, doc=(
            "Enables the optional Ollama/fastembed integration tests. Exact "
            "'1' only, not the usual truthy set (nestor.semantic_matcher).")),
        VarSpec("NESTOR_OLLAMA_EMBED_MODEL", "str", default="nomic-embed-text",
                doc="Ollama embedding model tag (nestor.ollama_embed)."),
        VarSpec("NESTOR_OLLAMA_EMBED_TIMEOUT", "float", default=60.0,
                doc="Ollama HTTP request timeout, seconds (nestor.ollama_embed)."),
        VarSpec("NESTOR_FRANK_APP_ID", "str", default="", doc=(
            "FRANK app seat to call as; falls further back to WILLOW_APP_ID "
            "then 'nestor' (nestor.frank.WillowForwarder).")),
        VarSpec("NESTOR_FRANK_PROJECT", "str", default="", doc=(
            "FRANK project name; falls back to 'nestor' "
            "(nestor.frank.WillowForwarder).")),
        VarSpec("NESTOR_FRANK_STRICT", "bool", default=False, doc=(
            "Propagate a down FRANK mirror as a raised error instead of "
            "swallowing it (nestor.frank).")),
        VarSpec("NESTOR_GATE_ROLLUP", "str", default="", doc=(
            "Charter JSON of Nestor seals -> Hanuman dispatches (nestor.ui).")),
        VarSpec("NESTOR_IDB_NAME", "str", default="nestor-keys",
                configurable=False, doc=(
                    "IndexedDB database name in the browser-side identity "
                    "script (nestor.ui_page). A JS literal, not an env var "
                    "any process reads.")),
        VarSpec("NESTOR_IDB_STORE", "str", default="identities",
                configurable=False, doc=(
                    "IndexedDB object-store name in the same script. Also a "
                    "JS literal, not an env var.")),
        VarSpec("NESTOR_CONFIG", "path", default=None, doc=(
            "Points at the config file this module's own file layer reads. "
            "Meta: it names *where*, not a value inside it.")),
    )
}


def secret_names() -> tuple[str, ...]:
    """The key-material subset — every :class:`VarSpec` with ``secret=True`` —
    sorted, so a caller (the self-grant pin in ``hooks/before_authority.py``
    among them) can import this list instead of grepping source for
    ``NESTOR_*KEY`` patterns."""
    return tuple(sorted(v.name for v in REGISTRY.values() if v.secret))


def configurable_names() -> tuple[str, ...]:
    """Every registered name that is an actual, settable environment
    variable — excludes the ``NESTOR_IDB_*`` JS literals."""
    return tuple(sorted(v.name for v in REGISTRY.values() if v.configurable))
