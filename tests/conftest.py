import json
import os

import pytest

from nestor import cascade, frank, keyring, storage
from nestor.sqlite_store import SqliteStore

# Variables that change what the package trusts, and which a developer running
# these tests plausibly has exported — the README tells them to export two of
# these three. A suite whose result depends on the shell it was launched from
# is not a suite; a test that seals as "rita" must not fail because the person
# running it has a real keyring that has never heard of her.
CONFIGURED_BY_ENV = ("NESTOR_KEYRING", "NESTOR_SEAL_KEY", "NESTOR_REQUIRE_SEAL_KEY",
                     "NESTOR_LEDGER", "NESTOR_FRANK_STRICT")


@pytest.fixture
def store():
    """A fresh, initialized in-memory reference store per test."""
    s = SqliteStore(":memory:")
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
    the test. Tests that want one set it with ``monkeypatch.setenv``, which
    still works — monkeypatch tears down before this fixture does, so the
    developer's own values come back afterwards.
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
