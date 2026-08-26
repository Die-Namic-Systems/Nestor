import builtins
import functools
import importlib.util
import json
import os
import sys

import pytest

from nestor import cascade, frank, keyring, storage
from nestor.sqlite_store import SqliteStore

# Variables that change what the package trusts, and which a developer running
# these tests plausibly has exported — the README tells them to export two of
# these three. A suite whose result depends on the shell it was launched from
# is not a suite; a test that seals as "rita" must not fail because the person
# running it has a real keyring that has never heard of her.
#
# We clear these explicitly rather than relying on pytest's monkeypatch for
# every name: monkeypatch restores only what a test sets, but many tests need
# the developer's real exports cleared without listing every future variable.
# Tests that need a knob set ``os.environ[...]`` in the test body or request a
# fixture such as :func:`seal_key`; this fixture restores the developer's own
# values afterwards. Fault injection (e.g. a broken ledger append) still uses
# ``monkeypatch`` where that is the right tool.
CONFIGURED_BY_ENV = ("NESTOR_KEYRING", "NESTOR_SEAL_KEY", "NESTOR_REQUIRE_SEAL_KEY",
                     "NESTOR_CACHE_KEY", "NESTOR_LEDGER", "NESTOR_LEDGER_VERIFY_INTERVAL_SEC",
                     "NESTOR_BROWSER_TEST", "NESTOR_GLOSSARY", "NESTOR_OLLAMA_TEST",
                     "NESTOR_FRANK_STRICT", "NESTOR_FRANK_APP_ID", "NESTOR_FRANK_PROJECT",
                     "WILLOW_MCP_COMMAND", "WILLOW_APP_ID", "NESTOR_SEMANTIC_TEST")


def pytest_sessionstart(session):
    """Scrub ambient trust config before session/module fixtures can spawn."""
    del session
    for name in CONFIGURED_BY_ENV:
        if name not in {"NESTOR_BROWSER_TEST", "NESTOR_SEMANTIC_TEST", "NESTOR_OLLAMA_TEST"}:
            os.environ.pop(name, None)


@functools.lru_cache(maxsize=1)
def _semantic_model_loadable() -> bool:
    """True when fastembed is installed AND the default model can embed."""
    if importlib.util.find_spec("fastembed") is None:
        return False
    try:
        from nestor.semantic_matcher import SemanticMatcher
        m = SemanticMatcher()
        m.scores_against("probe", ["other"])
        return True
    except Exception:  # noqa: BLE001
        return False


def semantic_tests_enabled() -> bool:
    """Whether this run explicitly opted into loading the real ONNX model."""
    from nestor.semantic_matcher import integration_tests_enabled

    return integration_tests_enabled() and _semantic_model_loadable()

requires_embedding = pytest.mark.skipif(
    not semantic_tests_enabled(),
    reason=("set NESTOR_SEMANTIC_TEST=1 and install the semantic extra; "
            "the default suite never loads ONNX implicitly"),
)


@pytest.fixture
def seal_key():
    """A signing key for tests that seal or verify signatures."""
    os.environ["NESTOR_SEAL_KEY"] = "test-key"


@pytest.fixture
def without_fastembed(monkeypatch):
    """Make ``import fastembed`` fail as if ``nestor-meaning[semantic]`` were absent.

    Refusal-path tests for the semantic matcher must hold in a venv that also
    has the extra installed — otherwise the suite can never be fully green on
    a developer box that runs the embedding cases.
    """
    for name in list(sys.modules):
        if name == "fastembed" or name.startswith("fastembed."):
            monkeypatch.delitem(sys.modules, name, raising=False)
    real_import = builtins.__import__
    real_find_spec = importlib.util.find_spec

    def blocked(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "fastembed" or name.startswith("fastembed."):
            raise ImportError("No module named 'fastembed'")
        return real_import(name, globals, locals, fromlist, level)

    def find_spec(name, package=None):
        if name == "fastembed" or (isinstance(name, str) and name.startswith("fastembed.")):
            return None
        return real_find_spec(name, package)

    monkeypatch.setattr(builtins, "__import__", blocked)
    monkeypatch.setattr(importlib.util, "find_spec", find_spec)


@pytest.fixture
def store(tmp_path):
    """A fresh, initialized file-backed store per test (same path the CLI opens)."""
    path = tmp_path / "nestor.db"
    s = SqliteStore(str(path))
    s.init_db()
    s.memory_init()
    return s


@pytest.fixture(autouse=True)
def isolate_globals(tmp_path):
    """Reset the process-wide store and point the ledger at a temp file, so
    tests never touch a real database, the repo's data/ dir, or a live FRANK.

    **And unset the environment.** Isolating the injected globals is only half
    of it: every one of them has a second way in through an environment
    variable, and a variable the developer exported an hour ago is not part of
    the test. Tests that need a knob set ``os.environ[...]`` in the test body or
    request a fixture such as :func:`seal_key`; this fixture restores the
    developer's own values afterwards.
    """
    saved_store = storage._store
    saved_ledger = cascade._LEDGER_OVERRIDE
    saved_forwarder = frank.get_forwarder()
    saved_env = {k: os.environ.pop(k, None) for k in CONFIGURED_BY_ENV}
    storage._store = None
    frank.set_forwarder(None)
    # A keyring left installed by one test decides who may seal in the next one.
    keyring.set_keyring(None)
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    yield
    storage._store = saved_store
    cascade._LEDGER_OVERRIDE = saved_ledger
    cascade.reset_ledger_session()
    frank.set_forwarder(saved_forwarder)
    keyring.set_keyring(None)
    for name, value in saved_env.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def read_ledger():
    path = cascade._ledger_path()
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
