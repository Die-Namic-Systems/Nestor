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

from .errors import NestorError

__all__ = ["HomeRelocationRefused", "PinRefused", "home", "keep_dir",
           "ledger_path", "bind_ledger", "db_path"]

_ROOT_ENV = "NESTOR_HOME"
_ROOT_NAME = ".nestor"
_DB_ENV = "NESTOR_DB"

# The root Nestor used to borrow. Still read — but only to refuse, see `home`.
# Never resolved to, because resolving it is the silent relocation.
_LEGACY_ENV = "HOMESTEAD_HOME"


class HomeRelocationRefused(NestorError):
    """``$HOMESTEAD_HOME`` is set and ``$NESTOR_HOME`` is not — refuse to guess.

    Raised instead of quietly resolving to ``~/.nestor``, because that answer
    is wrong in the one case that matters: a host already keeping a
    hash-chained ``keep/ledger.jsonl`` under the homestead root. Resolving
    elsewhere would not move that chain, it would start a second one, and two
    partial chains each verify on their own while the history between them is
    gone. A refusal the operator reads is recoverable; a fork they find at
    audit time is not.
    """


class PinRefused(NestorError):
    """``$NESTOR_DB`` is set but unusable — refuse rather than fall back.

    Same argument as :class:`HomeRelocationRefused`, one level down. A pin that
    names a directory, or a file whose parent does not exist, is an operator
    mistake: a typo in a service file, a stale path after a layout move.
    Reverting to the cwd-relative default would write a second corpus somewhere
    nobody is looking and report success.
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


def db_path() -> Path | None:
    """The pinned corpus, or ``None`` when nothing is pinned.

    Precedence: ``$NESTOR_DB`` (an explicit file), then ``$NESTOR_HOME``'s keep
    tree, then ``None`` — and *None* means the caller keeps its own default.
    This never invents a location.

    **Why it exists.** The willow fleet had been exporting ``NESTOR_DB`` in its
    env for weeks while no code in this package had ever heard of the variable.
    The result is the failure this package exists to refuse: ``nestor stats``
    run from a directory with no ``data/`` reported *"0 pairs, no ledger yet"*
    while the pinned store held eleven sealed rows and a valid chain. An empty
    corpus and a wrong location printed the same words.

    **And it refuses rather than falling back** — see :class:`PinRefused`.
    """
    pin = os.environ.get(_DB_ENV)
    if pin:
        p = Path(pin).expanduser()
        if p.is_dir():
            raise PinRefused(
                f"${_DB_ENV} names a directory ({p}); it must name the SQLite "
                f"file itself. A store written to a directory path is a store "
                f"nobody will find.")
        if not p.parent.exists():
            raise PinRefused(
                f"${_DB_ENV} is set to {p}, whose parent directory does not "
                f"exist. Refusing to fall back to the cwd-relative default: "
                f"that would write a second corpus somewhere nobody is looking "
                f"and report success. Create the directory, or fix the pin.")
        return p
    if os.environ.get(_ROOT_ENV):
        return keep_dir() / "nestor.db"
    return None


def cli_db_default() -> str:
    """The ``--db`` default for every surface: cli, serve, ui.

    One function because there were three copies of the literal
    ``"data/nestor.db"`` — in :mod:`nestor.cli`, :mod:`nestor.serve` and
    :mod:`nestor.ui` — and ``cli.main`` delegates ``serve``/``ui`` to their own
    parsers BEFORE the main one runs. Pinning only the first left the other two
    resolving from cwd, and ``serve`` is the surface an MCP client launches:
    every project would have served a different, usually empty corpus while its
    config looked correct.

    A rule written out three times is a rule enforced nowhere.
    """
    pinned = db_path()
    return str(pinned) if pinned else "data/nestor.db"


def ledger_for(db: str | Path) -> Path:
    """The chain that belongs to ``db``.

    ``$NESTOR_LEDGER`` wins. Otherwise two spellings are in use and both are
    checked before either is invented: ``<db>.ledger.jsonl`` (what the fleet
    actually has on disk — ``nestor.db.ledger.jsonl``) and
    ``<db-without-suffix>.ledger.jsonl`` (what ``db checkpoint`` writes, via
    ``os.path.splitext``). Whichever EXISTS is returned; if neither does, the
    first is the one that would be created.

    Pinning the corpus without pinning its chain is the same defect one level
    over: ``stats`` reported *"ledger: no ledger yet"* against a store whose
    chain was intact and eleven entries long, because the db moved and the
    ledger default did not follow it.
    """
    env = os.environ.get("NESTOR_LEDGER")
    if env:
        return Path(env).expanduser()
    p = Path(db)
    suffixed = p.with_name(p.name + ".ledger.jsonl")
    stripped = p.with_suffix("").with_name(p.with_suffix("").name + ".ledger.jsonl")
    for candidate in (suffixed, stripped):
        if candidate.is_file():
            return candidate
    return suffixed
