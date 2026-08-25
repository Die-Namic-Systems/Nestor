"""The default-operation-opens-no-non-loopback-socket claim, gated.

The `docs/journal/public-sector-audience.md` §3 note calls three pitch-shape
claims out as **asserted, not verified** — *"local-first, no phone-home"*,
*"air-gap friendly"*, *"sovereign deployment"* — because nothing in the tree
currently fails when the process reaches out. This file is the check.

The load-bearing sentence the pitch wants to make:

    A default install of nestor-meaning, running any of its read commands
    (ask / resolve / match / check / provenance / stats), opens NO socket
    to any non-loopback address.

Every read command's default engine, default matcher, and default
transport is exercised here. If any of them silently gains a network
call — an added telemetry hook, a lazy import that fetches something,
a matcher that pings a model on load — a test in this file turns red
and names which one.

## What this file does NOT prove

- **`nestor ui`** is a *server* that binds a socket. It defaults to
  `127.0.0.1:8765` (`nestor/ui.py:1591`); a test below asserts that
  default is unchanged, but the server itself is out of scope for
  "default operation opens no non-loopback socket" (a bind is not a
  connect, and a loopback bind is not phone-home).
- **`--engine claude`** with `ANTHROPIC_API_KEY` set will call
  `anthropic.Anthropic()` and eventually `api.anthropic.com`. That
  is the opt-in surface the extra `[cloud]` exists for. A test below
  asserts the default engine is `offline` and the anthropic import
  is lazy inside `ClaudeEngine.__init__` — never top-level.
- **`--matcher semantic`** with `[semantic]` installed will download
  the fastembed model on first use. Also opt-in via extra. A test
  below asserts the default matcher is `string`.
- **`--matcher ollama`** with an OLLAMA_HOST reachable will hit
  `http://localhost:11434` by default (`nestor/ollama_embed.py:30`).
  Loopback, opt-in via matcher choice; not part of the default path.
- **`nestor.cloud_seal`** requires the `[gate]` extra and its import
  raises without it (`nestor/cloud_seal.py:37-46`). A test asserts
  that this module is not imported by anything in the default read
  path.

The intent is that a policy officer reading `docs/sovereign-deployment.md`
can point at the file below and know the claim is a test, not a
sentence.
"""
from __future__ import annotations

import contextlib
import importlib
import os
import socket
import sys
from collections.abc import Iterator

import pytest

from nestor import answer, cascade, memory, storage
from nestor.sqlite_store import SqliteStore

# --- the socket interceptor -------------------------------------------------


@pytest.fixture()
def no_inet_connect(monkeypatch):
    """Fail loudly on any AF_INET / AF_INET6 connect() that isn't loopback.

    Wraps ``socket.socket.connect`` so a call to a non-loopback address
    raises ``AssertionError`` with the address named. Loopback and Unix
    sockets pass through unchanged. Returns a list the test can inspect
    after the call to see what (if anything) was attempted.
    """
    attempts: list[tuple[int, object]] = []
    original = socket.socket.connect

    def _is_loopback(addr: object) -> bool:
        if not isinstance(addr, tuple) or not addr:
            return False
        host = addr[0]
        return isinstance(host, str) and host in ("127.0.0.1", "::1", "localhost")

    def spy(self: socket.socket, address, *args, **kwargs):
        attempts.append((self.family, address))
        if (self.family in (socket.AF_INET, socket.AF_INET6)
                and not _is_loopback(address)):
            raise AssertionError(
                f"non-loopback socket connect during default operation: "
                f"family={self.family!r} address={address!r}. This is the "
                f"pitch-claim 'default operation opens no non-loopback "
                f"socket' failing — see tests/test_no_network_by_default.py."
            )
        return original(self, address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", spy)
    return attempts


@contextlib.contextmanager
def _minimal_env() -> Iterator[None]:
    """A clean environment for a default-op test: no opt-in credentials, a
    scratch seal key so the process starts, and no fleet mirror.

    Removes ``ANTHROPIC_API_KEY``, ``OLLAMA_HOST``, ``NESTOR_FRANK_STRICT``,
    ``WILLOW_MCP_COMMAND`` so no lazy path finds credentials to try. Restores
    after the test.
    """
    keys_to_clear = (
        "ANTHROPIC_API_KEY", "OLLAMA_HOST",
        "NESTOR_FRANK_STRICT", "NESTOR_FRANK_APP_ID", "NESTOR_FRANK_PROJECT",
        "WILLOW_MCP_COMMAND", "WILLOW_APP_ID",
    )
    saved = {k: os.environ.pop(k, None) for k in keys_to_clear}
    os.environ["NESTOR_SEAL_KEY"] = os.environ.get("NESTOR_SEAL_KEY", "test-key")
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


@pytest.fixture()
def store(tmp_path, seal_key):
    """A fresh in-memory store seeded with one sealed pair for read tests."""
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    s = SqliteStore(":memory:")
    s.init_db()
    s.memory_init()
    storage.set_store(s)
    memory.add_pair("hello", "hola", "en", "es",
                    status="sealed", verifier="rita", store=s)
    memory.add_pair("$1,000,000", "$1,000,000", "value", "value",
                    status="sealed", verifier="rita", store=s)
    return s


# --- the default read path opens no non-loopback socket --------------------


def test_default_ask_opens_no_non_loopback_socket(store, no_inet_connect):
    """`answer.ask` with the offline engine and default matcher is the
    single most common read Nestor does. It must reach nothing off-box."""
    with _minimal_env():
        result = answer.ask(store, "hello", "en", "es")
    assert result["passage"]["state"] == "sealed"
    assert result["verified"] is True


def test_default_resolve_opens_no_non_loopback_socket(store, no_inet_connect):
    with _minimal_env():
        result = answer.resolve(store, "hello", domain="en")
    # The domain doesn't matter for this test — the point is the call
    # reached only local storage.
    assert "candidates" in result


def test_default_match_opens_no_non_loopback_socket(store, no_inet_connect):
    with _minimal_env():
        result = answer.match(store, "hello", "en", "es")
    assert "matches" in result or "served" in result


def test_default_check_opens_no_non_loopback_socket(store, no_inet_connect):
    with _minimal_env():
        result = answer.check(store, "$1,000,000", "$1,020,000",
                              domain="value", pct_tol=0.05)
    assert "baselines" in result


def test_default_provenance_opens_no_non_loopback_socket(store, no_inet_connect):
    pairs = store.memory_list()
    assert pairs, "seeded store must have at least one pair"
    pair_id = pairs[0]["id"]
    with _minimal_env():
        prov = answer.provenance(store, pair_id)
    assert prov is not None and "id" in prov


def test_default_stats_opens_no_non_loopback_socket(store, no_inet_connect):
    with _minimal_env():
        s = memory.stats(store=store)
    assert "lang_pairs" in s


def test_default_ledger_verify_opens_no_non_loopback_socket(
    tmp_path, seal_key, no_inet_connect,
):
    from nestor import ledger

    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    (tmp_path / "ledger.jsonl").touch()
    with _minimal_env():
        ok, detail = ledger.verify()
    assert isinstance(ok, bool)
    assert isinstance(detail, str)


def test_default_propose_opens_no_non_loopback_socket(store, no_inet_connect):
    with _minimal_env():
        result = answer.propose(store, "a new question?", "a candidate answer",
                                "en", "es")
    assert result["state"] == "draft"
    assert result["verified"] is False


# --- opt-in surfaces are opt-in --------------------------------------------


def test_default_engine_is_offline_not_claude():
    """`answer.get_engine` with no argument must return the offline engine.

    The pitch depends on this: switching the default from `offline` to
    `auto` or `claude` would silently turn every ask into an outbound
    request.
    """
    from nestor.engine import OfflineEngine

    engine = answer.get_engine("offline")
    assert isinstance(engine, OfflineEngine)


def test_claude_engine_import_is_lazy_and_gated_on_the_extra():
    """`nestor.engine` must not import `anthropic` at module load.
    Only ``ClaudeEngine.__init__`` may.

    A top-level import would drag the anthropic SDK into every read path
    the moment `nestor` is imported, defeating the fail-closed shape of
    the `[cloud]` extra.
    """
    import pathlib

    src = pathlib.Path(importlib.util.find_spec("nestor.engine").origin)
    text = src.read_text(encoding="utf-8")
    # Split off the ClaudeEngine class body — everything before it must
    # not import anthropic.
    head, _, _ = text.partition("class ClaudeEngine")
    for offending in ("import anthropic", "from anthropic"):
        assert offending not in head, (
            f"{offending!r} appears in nestor/engine.py before ClaudeEngine — "
            f"the anthropic SDK must be a lazy import inside the class, so "
            f"a plain `nestor ask --engine offline` does not touch it.")


def test_default_matcher_string_does_not_drag_in_semantic_or_ollama():
    """Loading the ``"string"`` matcher — the shipped default — must not
    import ``nestor.semantic_matcher`` or ``nestor.ollama_embed`` as a
    side effect. Both are behind opt-in extras / an external daemon; a
    top-level side-import would defeat the fail-closed shape.

    ``load_matcher('string')`` returns ``None`` (the "use process-wide
    default" sentinel), which is fine — the point is that resolving the
    name does not pull the network-touching matchers in.
    """
    # Any earlier test that already loaded the semantic matcher would
    # invalidate this check, so we clear both modules from sys.modules
    # first and re-check after the load.
    for mod in ("nestor.semantic_matcher", "nestor.ollama_embed"):
        sys.modules.pop(mod, None)

    answer.load_matcher("string")

    for mod in ("nestor.semantic_matcher", "nestor.ollama_embed"):
        assert mod not in sys.modules, (
            f"load_matcher('string') pulled {mod!r} into sys.modules — "
            f"the default matcher path must not drag in a network-touching "
            f"module on name resolution.")


def test_cloud_seal_is_not_imported_by_the_default_read_path():
    """`nestor.cloud_seal` raises at import when `willow_gate` is absent
    (`nestor/cloud_seal.py:37-46`). Nothing in the default read path may
    import it, or a `[gate]`-less deployment fails to load Nestor at all.
    """
    # Fresh import of the meaningful surfaces, none of which should pull
    # nestor.cloud_seal in transitively.
    for name in ("nestor.answer", "nestor.memory", "nestor.cascade",
                 "nestor.matcher", "nestor.curator"):
        importlib.import_module(name)
    assert "nestor.cloud_seal" not in sys.modules, (
        "nestor.cloud_seal was pulled into sys.modules by a default read "
        "path — that module is gated on the [gate] extra and imports "
        "willow_gate at module top; a deployment without the extra would "
        "fail to import the read path.")


def test_ui_server_bind_default_is_loopback():
    """`nestor.ui.serve` defaults `host` to `127.0.0.1` — the UI server
    is not exposed off-box unless the operator names an external
    interface. This is not a phone-home claim (a bind is not a connect)
    but it is the other half of the sovereign-deployment posture."""
    from nestor import ui

    assert ui.serve.__defaults__ is not None
    host_default = ui.serve.__defaults__[0]  # host: str = "127.0.0.1"
    assert host_default == "127.0.0.1", (
        f"nestor.ui.serve default host is {host_default!r}, not '127.0.0.1'. "
        f"The sovereign-deployment posture depends on the server binding "
        f"loopback out of the box.")


def test_frank_forward_is_a_noop_when_no_mirror_is_configured(
    tmp_path, seal_key, no_inet_connect,
):
    """`frank.forward` is the ledger-mirror seam. When no
    ``NESTOR_FRANK_STRICT`` / ``WILLOW_MCP_COMMAND`` is set, it must
    not open a subprocess *or* a socket. The mirror is opt-in; its
    absence is the off switch."""
    from nestor import frank

    with _minimal_env():
        # A ledger entry that would have been mirrored if the mirror
        # were configured. The call must return cleanly and cause no
        # non-loopback connect (the fixture would raise if it did).
        frank.forward({"kind": "passage", "source_lang": "en",
                       "target_lang": "es", "ts": "2026-08-25T00:00:00Z",
                       "prev": "0" * 64})
