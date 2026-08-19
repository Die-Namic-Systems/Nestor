"""`nestor ask` without --from/--to must not default onto a domain the store
doesn't hold.

Mirrors askDomain() in nestor/ui_page.py (landed for the UI in #159): the
configured domain (en -> es) wins when the store actually has rows in it,
otherwise the largest domain present wins, because that is the one being
asked about. An empty store keeps the configured default. Issue #167 piece 2
is the CLI half of that rule, implemented once in cli._ask_domain().
"""
from __future__ import annotations

import os

import pytest

from nestor import cli, memory, storage
from nestor.sqlite_store import SqliteStore


@pytest.fixture()
def db(tmp_path, seal_key):
    os.environ["NESTOR_SEAL_KEY"] = "test-key"
    path = tmp_path / "nestor.db"
    ledger = tmp_path / "ledger.jsonl"
    store = SqliteStore(str(path))
    store.init_db()
    store.memory_init()
    from nestor import cascade
    cascade.set_ledger_path(ledger)
    storage.set_store(store)
    return {"db": str(path), "ledger": str(ledger), "path": tmp_path, "store": store}


def run(db, *argv):
    return cli.main(["--db", db["db"], "--ledger", db["ledger"], *argv])


# --- cli._ask_domain() directly, mirroring the UI's askDomain() unit-for-unit -

def test_a_store_with_only_decision_commitment_does_not_default_to_en_es(db):
    memory.add_pair("may we ship?", "yes", "decision", "commitment",
                    status="sealed", verifier="rita", store=db["store"])
    memory.add_pair("may we ship again?", "yes", "decision", "commitment",
                    status="sealed", verifier="rita", store=db["store"])
    assert cli._ask_domain(db["store"], None, None) == ("decision", "commitment")


def test_a_store_holding_the_configured_domain_keeps_it(db):
    memory.add_pair("Good evening.", "Buenas noches.", "en", "es",
                    status="sealed", verifier="rita", store=db["store"])
    # Even with a larger competing domain present, en->es wins because the
    # store actually holds it — askDomain() checks membership, not size, first.
    for i in range(5):
        memory.add_pair(f"may we ship {i}?", "yes", "decision", "commitment",
                        status="sealed", verifier="rita", store=db["store"])
    assert cli._ask_domain(db["store"], None, None) == ("en", "es")


def test_an_empty_store_keeps_the_configured_default(db):
    assert cli._ask_domain(db["store"], None, None) == ("en", "es")


def test_an_explicit_flag_is_used_as_is_even_if_the_store_lacks_it(db):
    memory.add_pair("may we ship?", "yes", "decision", "commitment",
                    status="sealed", verifier="rita", store=db["store"])
    # A human typing --from/--to is the same as editing the UI's domain boxes
    # directly: it bypasses the smart default rather than being overridden.
    assert cli._ask_domain(db["store"], "fr", "de") == ("fr", "de")
    assert cli._ask_domain(db["store"], "fr", None) == ("fr", "es")
    assert cli._ask_domain(db["store"], None, "de") == ("en", "de")


# --- end to end through `nestor ask` ----------------------------------------

def test_nestor_ask_with_no_flags_finds_a_decision_only_store(db, capsys):
    memory.add_pair("may we ship?", "yes", "decision", "commitment",
                    status="sealed", verifier="rita", store=db["store"])
    assert run(db, "ask", "may we ship?") == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "✓ sealed" in out and "yes" in out


def test_nestor_ask_with_no_flags_and_no_matching_domain_stays_pending(db, capsys):
    # Nothing sealed anywhere: the configured en->es default holds, and the
    # phrase is correctly reported unanswered rather than crashing.
    assert run(db, "ask", "nobody has ever verified this") == cli.EXIT_ANSWER_IS_NO
    assert "! pending" in capsys.readouterr().out
