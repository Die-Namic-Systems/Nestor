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
import sys
from typing import Any, Callable, Optional, Protocol, runtime_checkable

#: FRANK groups entries by project; every Nestor entry lands under this one.
DEFAULT_PROJECT = "nestor"

#: Local ledger ``kind`` → FRANK ``event_type``. Namespaced so the shared
#: chain stays readable next to every other project's events.
EVENT_PREFIX = "nestor."


@runtime_checkable
class Forwarder(Protocol):
    def __call__(self, event_type: str, content: dict) -> None: ...


class FrankUnavailable(RuntimeError):
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
    return os.environ.get("NESTOR_FRANK_STRICT", "").strip().lower() in ("1", "true", "yes")


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
    ``WILLOW_APP_ID``       the app seat to call as (default: ``nestor``)
    ``NESTOR_FRANK_PROJECT`` FRANK project name (default: ``nestor``)
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
        self._app_id = app_id or os.environ.get("WILLOW_APP_ID", "").strip() or DEFAULT_PROJECT
        self._project = project or os.environ.get("NESTOR_FRANK_PROJECT", "").strip() or DEFAULT_PROJECT
        self._timeout = timeout
        self._env = env
        self._proc: Optional[subprocess.Popen] = None
        self._next_id = 0

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
        self._next_id += 1
        self._send({"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params})
        while True:
            frame = self._read()
            if frame.get("id") == self._next_id:
                if "error" in frame:
                    raise FrankUnavailable(f"{method}: {frame['error']}")
                return frame.get("result") or {}

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
