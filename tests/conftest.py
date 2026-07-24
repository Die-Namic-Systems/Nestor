import json
import pytest

from nestor import cascade, storage
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
    """Reset the process-wide store and point the ledger at a temp file,
    so tests never touch a real database or the repo's data/ dir."""
    saved_store = storage._store
    saved_ledger = cascade._LEDGER_OVERRIDE
    storage._store = None
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    yield
    storage._store = saved_store
    cascade._LEDGER_OVERRIDE = saved_ledger


def read_ledger():
    path = cascade._ledger_path()
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
