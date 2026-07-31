"""IDEAS §5.3 — TTL'd full ledger walks on append, not only once per process."""

from __future__ import annotations

import json
import os

import pytest

from nestor import cascade, memory, storage
from nestor.sqlite_store import SqliteStore


@pytest.fixture()
def signed(tmp_path, seal_key):
    os.environ["NESTOR_SEAL_KEY"] = "shared-key"
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    storage.set_store(SqliteStore(":memory:"))
    storage.get_store().memory_init()
    return tmp_path


@pytest.fixture
def interval_guard():
    cascade.set_ledger_verify_interval(None)
    cascade.reset_ledger_session()
    try:
        yield
    finally:
        cascade.set_ledger_verify_interval(None)
        cascade.reset_ledger_session()


def _break_first_line(ledger):
    lines = ledger.read_text().splitlines()
    record = json.loads(lines[0])
    record["verifier"] = "mallory"
    lines[0] = json.dumps(record)
    ledger.write_text("\n".join(lines) + "\n")


def test_always_verify_refuses_a_mid_chain_tamper(signed, interval_guard):
    """With interval < 0 every append re-walks; history edits cannot hide."""
    cascade.set_ledger_verify_interval(-1)
    ledger = signed / "ledger.jsonl"
    store = storage.get_store()
    memory.add_pair("first", "primero", "en", "es", status="sealed",
                    verifier="rita", store=store)
    memory.add_pair("second", "segundo", "en", "es", status="sealed",
                    verifier="rita", store=store)
    _break_first_line(ledger)

    with pytest.raises(Exception, match="chain is broken"):
        memory.add_pair("third", "tercero", "en", "es", status="sealed",
                        verifier="rita", store=store)


def test_interval_reads_from_env(interval_guard, monkeypatch):
    monkeypatch.setenv("NESTOR_LEDGER_VERIFY_INTERVAL_SEC", "120")
    assert cascade.ledger_verify_interval_sec() == 120.0
    cascade.set_ledger_verify_interval(45)
    assert cascade.ledger_verify_interval_sec() == 45.0
