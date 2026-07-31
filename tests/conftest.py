import json
import pytest

from nestor import cascade, frank, keyring, storage
from nestor.sqlite_store import SqliteStore


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
    tests never touch a real database, the repo's data/ dir, or a live FRANK."""
    saved_store = storage._store
    saved_ledger = cascade._LEDGER_OVERRIDE
    saved_forwarder = frank.get_forwarder()
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


def read_ledger():
    path = cascade._ledger_path()
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
