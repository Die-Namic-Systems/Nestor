"""The constitution feeder verifies what it ingested — and refuses a mismatch.

`scripts/feed_willow_constitution.py` reads compliance cards, writes each as a
clause → forbidden-act draft, and must then hold what landed in the store to the
hash of what was parsed. A corrupted or partial ingest — the store holding a
forbidden act other than the one parsed, or dropping a clause entirely — is the
gap these pin: it must surface as an error, never pass silently as "no findings".

The forbidden act under test is *accepting an ingest whose content does not
match its expected hash*. So the load-bearing test attempts exactly that and
asserts refusal; the happy path proves a faithful ingest still passes.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import feed_willow_constitution as FEED     # noqa: E402


def _row(file: str, trace: str, clause: str, forbidden: str, doc: str = "doc line") -> dict:
    return {"file": file, "trace_id": trace, "clause": clause,
            "forbidden": forbidden, "doc_first": doc}


def _store(tmp_path: pathlib.Path):
    """A fresh store wired the same way ``main`` wires one."""
    FEED.cascade.set_ledger_path(str(tmp_path / "ledger.jsonl"))
    store = FEED.SqliteStore(str(tmp_path / "nestor.db"))
    store.init_db()
    store.memory_init()
    FEED.storage.set_store(store)
    return store


def test_faithful_ingest_verifies(tmp_path):
    """Happy path: what the store holds matches what was parsed → no raise."""
    rows = [_row("const_1_1.py", "CONST-1-1", "clause one", "act one"),
            _row("const_1_2.py", "CONST-1-2", "clause two", "act two")]
    store = _store(tmp_path)
    FEED.ingest_rows(rows, store)
    assert FEED.verify_ingested(rows, store) == 2


def test_a_clause_with_no_stated_act_still_verifies(tmp_path):
    """The placeholder target is part of the value, so it must hash-match too."""
    rows = [_row("const_2_1.py", "CONST-2-1", "clause with no act", "")]
    store = _store(tmp_path)
    FEED.ingest_rows(rows, store)
    assert FEED.verify_ingested(rows, store) == 1


def test_a_mismatched_forbidden_act_is_refused(tmp_path):
    """The forbidden act: accept an ingest whose content differs from expected.

    The store is fed a tampered forbidden act; verification then holds it to the
    clean parse. The hashes differ, so the feed must RAISE rather than report a
    clean pass.
    """
    tampered = [_row("const_3_1.py", "CONST-3-1", "clause three", "TAMPERED act")]
    clean = [_row("const_3_1.py", "CONST-3-1", "clause three", "the real act")]
    store = _store(tmp_path)
    FEED.ingest_rows(tampered, store)
    with pytest.raises(FEED.ConstitutionIngestMismatch):
        FEED.verify_ingested(clean, store)


def test_a_dropped_clause_is_refused(tmp_path):
    """A partial ingest — the store missing a clause we parsed — must raise,
    not read back as though the clause were absent from the cards."""
    parsed = [_row("const_4_1.py", "CONST-4-1", "clause four", "act four"),
              _row("const_4_2.py", "CONST-4-2", "clause five", "act five")]
    store = _store(tmp_path)
    FEED.ingest_rows(parsed[:1], store)     # only the first lands
    with pytest.raises(FEED.ConstitutionIngestMismatch):
        FEED.verify_ingested(parsed, store)
