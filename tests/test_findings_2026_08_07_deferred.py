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

from nestor import cascade, memory, portable, storage
from nestor.matcher import NumericMatcher, StringMatcher
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


# --- Finding 1: a bundle carries a domain's tags but not its matcher -------
#
# A domain is its tags AND its matcher (§6.40): the source_norm a seal is signed
# over is the matcher's output, so a bundle keyed by one matcher landing in a
# domain keyed by another lands sealed rows in a key space the destination never
# computes — and, before this, reported {"sealed": n} with no warning. The fix
# records an advisory matcher label in the bundle and warns on mismatch at
# import; it never refuses (the label is not a stable identifier) and never
# re-normalizes (that would invalidate every seal signature in transit).


def test_export_records_the_matcher_that_keyed_the_bundle(signed):
    store = fresh()
    storage.set_store(store)
    memory.add_pair("hello", "hola", "en", "es", status="sealed", verifier="rita",
                    store=store)
    bundle = portable.export_bundle(store)
    assert bundle["matcher"] == "StringMatcher"
    # Advisory, and outside the digest: recomputing the digest without it must
    # still verify, or the label would be an integrity field it cannot be.
    ok, _ = portable.verify_bundle(bundle)
    assert ok


def test_import_under_a_different_matcher_warns_but_still_lands(signed):
    src = fresh()
    storage.set_store(src)
    memory.add_pair("hello", "hola", "en", "es", status="sealed", verifier="rita",
                    store=src)
    bundle = portable.export_bundle(src)

    dst = fresh()
    with pytest.warns(RuntimeWarning, match="keyed by"):
        report = portable.import_bundle(bundle, store=dst, dry_run=False,
                                        verifier="ops", matcher=NumericMatcher())

    assert report["matcher_mismatch"] is True
    assert report["source_matcher"] == "StringMatcher"
    assert report["dest_matcher"] == "NumericMatcher"
    # Warned, NOT refused: the rows are trusted verbatim and land, because
    # re-normalizing would break the seal signature they carry.
    assert report["sealed"] == 1
    assert dst.memory_find(memory._norm("hello"), "en", "es") is not None


def test_import_under_the_same_matcher_is_silent(signed, recwarn):
    src = fresh()
    storage.set_store(src)
    memory.add_pair("hello", "hola", "en", "es", status="sealed", verifier="rita",
                    store=src)
    bundle = portable.export_bundle(src)

    dst = fresh()
    report = portable.import_bundle(bundle, store=dst, dry_run=False,
                                    verifier="ops", matcher=StringMatcher())
    assert report["matcher_mismatch"] is False
    assert not [w for w in recwarn.list if "keyed by" in str(w.message)]


def test_a_legacy_bundle_without_a_matcher_label_does_not_false_alarm(signed, recwarn):
    """A bundle written before this field existed carries no matcher label.
    Unknown is not a mismatch — it must import without a warning, or every
    pre-existing bundle would cry wolf on first import."""
    src = fresh()
    storage.set_store(src)
    memory.add_pair("hello", "hola", "en", "es", status="sealed", verifier="rita",
                    store=src)
    bundle = portable.export_bundle(src)
    bundle.pop("matcher")                       # as an older exporter left it

    dst = fresh()
    report = portable.import_bundle(bundle, store=dst, dry_run=False,
                                    verifier="ops", matcher=NumericMatcher())
    assert report["source_matcher"] == ""
    assert report["matcher_mismatch"] is False
    assert not [w for w in recwarn.list if "keyed by" in str(w.message)]
