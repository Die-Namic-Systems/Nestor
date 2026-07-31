"""IDEAS §5.3 — TTL'd full ledger walks on append, not only once per process."""

from __future__ import annotations

import os
import time

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


def _tamper_first_line_kind(ledger, old='"kind": "seal"', new='"kind": "nope"'):
    """Length-preserving edit so only a full chain walk sees the break."""
    lines = ledger.read_text().splitlines()
    assert old in lines[0]
    lines[0] = lines[0].replace(old, new)
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
    _tamper_first_line_kind(ledger)

    with pytest.raises(Exception, match="chain is broken"):
        memory.add_pair("third", "tercero", "en", "es", status="sealed",
                        verifier="rita", store=store)


def test_positive_interval_rewalks_after_ttl(signed, interval_guard):
    """The setting nestor.ui ships: stale cache must not skip a full walk."""
    cascade.set_ledger_verify_interval(0.2)
    ledger = signed / "ledger.jsonl"
    store = storage.get_store()
    memory.add_pair("first", "primero", "en", "es", status="sealed",
                    verifier="rita", store=store)
    memory.add_pair("second", "segundo", "en", "es", status="sealed",
                    verifier="rita", store=store)
    _tamper_first_line_kind(ledger)
    time.sleep(0.25)

    with pytest.raises(Exception, match="chain is broken"):
        memory.add_pair("third", "tercero", "en", "es", status="sealed",
                        verifier="rita", store=store)


def test_interval_reads_from_env(interval_guard, monkeypatch):
    monkeypatch.setenv("NESTOR_LEDGER_VERIFY_INTERVAL_SEC", "120")
    assert cascade.ledger_verify_interval_sec() == 120.0
    cascade.set_ledger_verify_interval(45)
    assert cascade.ledger_verify_interval_sec() == 45.0


def test_bad_interval_env_raises(interval_guard, monkeypatch):
    monkeypatch.setenv("NESTOR_LEDGER_VERIFY_INTERVAL_SEC", "5m")
    with pytest.raises(ValueError, match="NESTOR_LEDGER_VERIFY_INTERVAL_SEC"):
        cascade.ledger_verify_interval_sec()
