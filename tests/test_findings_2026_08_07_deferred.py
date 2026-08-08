"""Regressions for IDEAS.md §6.92 — the three findings the §6.40/§6.41 audits
deferred into merged-PR prose, filed into the queue on 2026-08-07.

Finding 3 is a genuine bug, unrelated to the matcher work: ``memory.add_pair``'s
race-retry re-called itself without forwarding ``reason=``. A seal that lost the
insert race therefore had its rationale silently dropped — and, worse, skipped
the ``memory_set_reason`` refusal path a store lacking the op is supposed to hit.

Written against the *unfixed* revision first and observed to fail (the sealed row
came back with an empty ``reason``), per the house rule that a test which passes
before the fix is a description, not a gate.
"""
from __future__ import annotations

import os

import pytest

from nestor import cascade, memory, storage
from nestor.sqlite_store import SqliteStore


@pytest.fixture()
def signed(tmp_path, seal_key):
    os.environ['NESTOR_SEAL_KEY'] = 'shared-key'
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    return tmp_path


def fresh(path=":memory:"):
    s = SqliteStore(path)
    s.init_db()
    s.memory_init()
    return s


def test_a_seal_that_loses_the_insert_race_keeps_its_reason(signed, tmp_path):
    """The winner lands a draft; the loser retries, upgrades that draft to a
    seal, and its ``reason`` must ride along. The retry dropped it.

    The race is made deterministic by lying to the first ``memory_find``: it
    reports nothing, so the seal takes the insert path and collides with the
    draft already in the store — the exact window ``add_pair`` retries around.
    """
    store = fresh(str(tmp_path / "race.db"))
    storage.set_store(store)

    # The winner of the race: a draft for the source, already committed.
    memory.add_pair("the annual invoice", "la factura anual", "en", "es",
                    status="draft", store=store)

    real_find = store.memory_find
    calls = {"n": 0}

    def find_that_hides_the_first_time(norm, source_lang, target_lang):
        calls["n"] += 1
        if calls["n"] == 1:
            return None            # the check-then-write window, forced open
        return real_find(norm, source_lang, target_lang)

    store.memory_find = find_that_hides_the_first_time
    try:
        memory.add_pair("the annual invoice", "la factura anual", "en", "es",
                        status="sealed", verifier="rita",
                        reason="confirmed against the signed PO", store=store)
    finally:
        store.memory_find = real_find

    row = store.memory_find(memory._norm("the annual invoice"), "en", "es")
    assert row["status"] == "sealed"
    assert row["reason"] == "confirmed against the signed PO", (
        "a seal that lost the insert race dropped its recorded reason on retry")
