"""FRANK forwarding — the shared-provenance half of the ledger.

``cascade._ledger_append`` writes Nestor's own hash-chained ``ledger.jsonl``
and that stays the source of truth. This module is the seam that *also* mirrors
each entry into FRANK, willow-mcp's append-only governance ledger, so the audit
trail lives in shared provenance infrastructure rather than one local file.

Injected, exactly like storage and the matcher — Nestor keeps no upward
dependency on any host:

    from nestor import frank

    frank.set_forwarder(frank.willow_forwarder())   # opt in
    frank.set_forwarder(None)                       # local ledger only (default)

A forwarder is any callable ``(event_type: str, content: dict) -> None``. With
none installed, nothing is forwarded and behavior is byte-for-byte what it was.

The bundled :class:`WillowForwarder` speaks MCP over stdio — the same protocol
any MCP client uses — so the write goes through willow-mcp's ``frank_append``
tool and its manifest ACL. It never touches the governance database directly;
a raw DB write would bypass the gate that makes the ledger trustworthy.

Forwarding is best-effort by contract: :meth:`cascade._ledger_append` catches
:class:`FrankUnavailable` and keeps going, because a translation must not fail
because a governance mirror is down. Set ``NESTOR_FRANK_STRICT=1`` to surface
those failures instead of swallowing them.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import sys
from typing import Any, Optional, Protocol, runtime_checkable

from . import config
from .errors import NestorError

#: FRANK groups entries by project; every Nestor entry lands under this one.
DEFAULT_PROJECT = "nestor"

#: Local ledger ``kind`` → FRANK ``event_type``. Namespaced so the shared
#: chain stays readable next to every other project's events.
EVENT_PREFIX = "nestor."


@runtime_checkable
class Forwarder(Protocol):
    def __call__(self, event_type: str, content: dict) -> None: ...


class FrankUnavailable(NestorError):
    """The FRANK mirror could not be written. Never fatal to a translation."""


_FORWARDER: Optional[Forwarder] = None


def set_forwarder(fn: Optional[Forwarder]) -> None:
    """Install (or clear, with ``None``) the process-wide FRANK forwarder."""
    global _FORWARDER
    if fn is not None and not callable(fn):
        raise TypeError("forwarder must be callable (event_type, content) -> None")
    _FORWARDER = fn


def get_forwarder() -> Optional[Forwarder]:
    return _FORWARDER


def strict() -> bool:
    # Loose parsing preserved exactly: an unrecognized token reads as False,
    # never a raised ConfigError (config.get_bool_loose), and this site's own
    # truthy set has always omitted "on" — unlike NESTOR_REQUIRE_SEAL_KEY's.
    return config.get_bool_loose("NESTOR_FRANK_STRICT", False,
                                 frozenset({"1", "true", "yes"}))


def event_type_for(entry: dict) -> str:
    """``{"kind": "seal", ...}`` → ``nestor.seal``. Unkinded entries → ``nestor.entry``."""
    kind = str(entry.get("kind") or "entry").strip() or "entry"
    return f"{EVENT_PREFIX}{kind}"


def forward(entry: dict, *, line_hash: str = "") -> None:
    """Mirror one local ledger entry into FRANK, if a forwarder is installed.

    ``line_hash`` is the sha256 of the ledger line as written, which cross-links
    the two chains: a FRANK entry can be matched back to the exact local line,
    and a rewritten local ledger no longer matches its mirror.
    """
    fwd = _FORWARDER
    if fwd is None:
        return
    content = dict(entry)
    if line_hash:
        content["local_hash"] = line_hash
    fwd(event_type_for(entry), content)


class WillowForwarder:
    """Forward to willow-mcp's ``frank_append`` over an MCP stdio session.

    The server subprocess is spawned lazily on the first entry and kept for the
    life of the forwarder — a translation run appends many entries, and one
    handshake per entry would dominate its cost. Call :meth:`close` when done
    (or use it as a context manager); the child is also terminated at exit.

    Defaults come from the environment the willow-mcp project wiring already
    sets, so an installed seat needs no arguments:

    ``WILLOW_MCP_COMMAND``  server argv as a JSON list
                            (default: ``[sys.executable, "-m", "willow_mcp"]``)
    ``NESTOR_FRANK_APP_ID`` the app seat to call as (default: ``nestor``)
    ``WILLOW_APP_ID``       fallback for the above, and a trap — see below
    ``NESTOR_FRANK_PROJECT`` FRANK project name (default: ``nestor``)

    .. note::

       ``WILLOW_APP_ID`` is read second, not first, and that ordering is load
       bearing. It is a *client-scoped* variable: a fleet shell exports one
       value for whatever seat that shell is driving, and anything in the
       process inherits it. Read first, it silently re-seats this forwarder —
       a shell set up for the orchestrator made Nestor's ledger mirror call as
       ``willow``, which willow-mcp refuses outright (``frank_append`` for
       ``willow`` demands a human-orchestrator host), so a correctly seated
       Nestor stopped forwarding the moment the fleet env was sourced.
       ``NESTOR_FRANK_APP_ID`` is Nestor's own line, and it wins.
    """

    def __init__(
        self,
        command: Optional[list[str]] = None,
        *,
        app_id: str = "",
        project: str = "",
        timeout: float = 30.0,
        env: Optional[dict[str, str]] = None,
    ) -> None:
        self._command = command or _default_command()
        # WILLOW_APP_ID is not a NESTOR_* var and stays a plain env read — see
        # the class docstring for why NESTOR_FRANK_APP_ID must be read first.
        self._app_id = (
            app_id
            or config.load().get_str("frank_app_id", "").strip()
            or os.environ.get("WILLOW_APP_ID", "").strip()
            or DEFAULT_PROJECT
        )
        self._project = (project or config.load().get_str("frank_project", "").strip()
                         or DEFAULT_PROJECT)
        self._timeout = timeout
        self._env = env
        self._proc: Optional[subprocess.Popen] = None
        self._next_id = 0
        # One request in flight at a time. The forwarder owns a single stdio
        # pipe, and nestor.ui appends to the ledger from a thread pool, so two
        # threads could otherwise interleave writes on it and read each other's
        # replies.
        self._lock = threading.RLock()

    # ── MCP plumbing ──────────────────────────────────────────────────────────

    def _send(self, message: dict) -> None:
        proc = self._proc
        assert proc is not None and proc.stdin is not None
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()

    def _read(self) -> dict:
        proc = self._proc
        assert proc is not None and proc.stdout is not None
        while True:
            line = proc.stdout.readline()
            if not line:
                raise FrankUnavailable("willow-mcp closed the connection")
            line = line.strip()
            if not line:
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue  # server logging on stdout — not our frame

    def _request(self, method: str, params: dict) -> dict:
        with self._lock:
            self._next_id += 1
            want = self._next_id
            self._send({"jsonrpc": "2.0", "id": want, "method": method, "params": params})
            deadline = time.monotonic() + self._timeout
            while True:
                frame = self._read_before(deadline)
                if frame.get("id") == want:
                    if "error" in frame:
                        raise FrankUnavailable(f"{method}: {frame['error']}")
                    return frame.get("result") or {}

    def _read_before(self, deadline: float) -> dict:
        """Read one frame, or give up. ``timeout`` was accepted and never used.

        The constructor has taken a ``timeout`` since this module was written and
        applied it to nothing: the read below is a blocking ``readline`` on a
        subprocess pipe, so a governance mirror that accepted the connection and
        then stopped answering hung the caller forever. Every seal, every serve
        and every rejection goes through ``cascade.ledger_append`` and, when a
        forwarder is installed, through here — so "the mirror is wedged" became
        "Nestor is wedged", which is the precise opposite of this module's
        contract that a mirror being down must never fail a translation.

        On timeout the subprocess is killed rather than left running. A stream
        with an unanswered request on it cannot be resynchronized — the next
        reply would be read as the answer to the next question — so the honest
        move is to drop the connection and let ``_connect`` start a clean one.
        The raise lands in ``forward``'s best-effort handler, which warns unless
        ``NESTOR_FRANK_STRICT`` says to propagate.
        """
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            self._abandon()
            raise FrankUnavailable(f"no reply within {self._timeout}s")
        box: dict = {}

        def read() -> None:
            try:
                box["frame"] = self._read()
            except Exception as exc:                # noqa: BLE001 — reported below
                box["error"] = exc

        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        reader.join(remaining)
        if reader.is_alive():
            # Killing the process makes the blocked readline return, so the
            # thread ends rather than leaking for the life of the program.
            self._abandon()
            raise FrankUnavailable(f"no reply within {self._timeout}s")
        if "error" in box:
            raise box["error"]
        return box.get("frame") or {}

    def _abandon(self) -> None:
        """Drop a subprocess that stopped answering, without waiting on it."""
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            proc.kill()
        except OSError:                             # pragma: no cover — already gone
            pass

    def _connect(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        try:
            self._proc = subprocess.Popen(
                self._command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                env=self._env,
            )
        except OSError as exc:
            raise FrankUnavailable(f"could not start willow-mcp {self._command!r}: {exc}") from exc
        self._next_id = 0
        self._request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "nestor", "version": _version()},
            },
        )
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    # ── the forwarder contract ────────────────────────────────────────────────

    def __call__(self, event_type: str, content: dict) -> None:
        self._connect()
        result = self._request(
            "tools/call",
            {
                "name": "frank_append",
                "arguments": {
                    "app_id": self._app_id,
                    "project": self._project,
                    "event_type": event_type,
                    "content": content,
                },
            },
        )
        payload = _tool_payload(result)
        # frank_append reports refusals in-band (gate denial, postgres down)
        # rather than as a JSON-RPC error, so an "error" key is still a failure.
        if isinstance(payload, dict) and payload.get("error"):
            raise FrankUnavailable(f"frank_append: {payload['error']}")

    def close(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        for stream in (proc.stdin, proc.stdout):
            try:
                if stream is not None:
                    stream.close()
            except OSError:
                pass
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    def __enter__(self) -> "WillowForwarder":
        self._connect()
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


def willow_forwarder(**kwargs: Any) -> WillowForwarder:
    """Convenience constructor — ``frank.set_forwarder(frank.willow_forwarder())``."""
    return WillowForwarder(**kwargs)


def _default_command() -> list[str]:
    raw = os.environ.get("WILLOW_MCP_COMMAND", "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return raw.split()
        if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
            return parsed
        raise ValueError("WILLOW_MCP_COMMAND must be a JSON list of strings")
    return [sys.executable, "-m", "willow_mcp"]


def _tool_payload(result: dict) -> Any:
    """MCP tool results carry their JSON body as concatenated text content."""
    text = "".join(
        block.get("text", "")
        for block in (result.get("content") or [])
        if isinstance(block, dict) and block.get("type") == "text"
    )
    if not text:
        return result.get("structuredContent")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("nestor")
    except PackageNotFoundError:
        return "0"


__all__ = [
    "DEFAULT_PROJECT",
    "EVENT_PREFIX",
    "Forwarder",
    "FrankUnavailable",
    "WillowForwarder",
    "event_type_for",
    "forward",
    "get_forwarder",
    "set_forwarder",
    "strict",
    "willow_forwarder",
]
