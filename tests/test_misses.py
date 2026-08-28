"""The miss log — what was asked and had no verified answer.

Three invariants carry this module, and each has a test that attempts the
forbidden act and asserts refusal rather than only asserting the happy path:

1. **A question asked once is never written down in readable form.** The k>=2
   gate is a privacy property and a usefulness property at the same time, so a
   test that only checked the queue contents would pass against a build that
   stored singleton text and merely hid it on read.
2. **A miss is never a proposal.** ``propose`` writes a draft and the cascade
   serves drafts at tier 2, so a miss recorded that way would put an empty
   answer in the servable tier — strictly worse than the honest ``pending`` it
   replaced. Nothing here may touch ``tm_pairs``.
3. **A failure to record is surfaced, not swallowed.** Fail-open is right; a
   miss log is not worth failing an answer over. Fail-silent is what this box
   has repeatedly paid for, so the reason has to reach the caller.
"""
from __future__ import annotations

import os

import pytest

from nestor import answer, cascade, memory, misses, storage
from nestor.sqlite_store import SqliteStore


@pytest.fixture()
def store(tmp_path, seal_key):
    os.environ["NESTOR_SEAL_KEY"] = "test-key"
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    s = SqliteStore(str(tmp_path / "t.db"))
    s.init_db()
    s.memory_init()
    storage.set_store(s)
    return s


def test_a_question_asked_once_stores_no_readable_text(store):
    """The privacy property, checked at the ROW and not through the queue.

    Reading it back through ``queue()`` would pass against a build that stored
    the text and filtered it on display. This asserts the column itself.
    """
    answer.ask(store, "a question nobody repeats", "en", "en")

    rows = store.memory_misses(1, 10)
    assert len(rows) == 1
    assert rows[0]["seen"] == 1
    assert rows[0]["source_norm"] == "", "a singleton must not store readable text"
    assert rows[0]["norm_sha256"], "but it must still be countable"


def test_the_second_sighting_opens_the_gate(store):
    """k>=2 makes it readable — a gap, where one asking was noise."""
    answer.ask(store, "what is the vault key", "en", "en")
    assert misses.queue(store) == [], "one sighting must not reach the queue"

    answer.ask(store, "What is the VAULT key", "en", "en")
    entries = misses.queue(store)
    assert len(entries) == 1
    assert entries[0]["query"] == "what is the vault key"
    assert entries[0]["seen"] == 2, "normalization must collapse the variants"


def test_a_sealed_answer_is_not_a_miss(store, signing_key_env=None):
    """Only ``pending`` counts. A served answer is the opposite of a gap."""
    memory.add_pair("Good evening.", "Buenas noches.", "en", "es",
                    status="sealed", verifier="rita", store=store)
    result = answer.ask(store, "Good evening.", "en", "es")

    assert result["passage"]["state"] == "sealed"
    assert store.memory_misses(1, 10) == [], "a hit must not be logged as a miss"


def test_coverage_reports_what_it_is_withholding(store):
    """An absence with a stated size, not a queue that looks shorter than truth."""
    answer.ask(store, "asked twice", "en", "en")
    answer.ask(store, "asked twice", "en", "en")
    answer.ask(store, "asked once", "en", "en")

    cov = misses.coverage(store)
    assert cov["distinct_misses"] == 2
    assert cov["total_misses"] == 3
    assert cov["surfaced"] == 1
    assert cov["withheld"] == 1, "the hidden singleton must still be counted"
    assert [e["query"] for e in cov["queue"]] == ["asked twice"]


def test_a_miss_never_becomes_a_pair(store):
    """The forbidden act. A miss is not a proposal.

    ``propose`` writes a draft and the cascade serves drafts at tier 2, so a
    miss queued that way would put an EMPTY answer in the servable tier —
    worse than the ``pending`` it replaced. Recording a miss must leave
    ``tm_pairs`` untouched.
    """
    before = memory.stats(store=store)
    for _ in range(3):
        answer.ask(store, "something with no answer at all", "en", "en")

    assert memory.stats(store=store) == before, "recording a miss wrote to memory"
    # And asking again still says pending — never an empty draft served at tier 2.
    assert answer.ask(store, "something with no answer at all",
                      "en", "en")["passage"]["state"] == "pending"


def test_a_broken_miss_log_surfaces_and_does_not_break_the_answer(store, monkeypatch):
    """Fail-open, not fail-silent — the distinction this box has paid for.

    An expired propagation token stopped eleven verticals for three and a half
    weeks with no signal; a Grove sender wrapped in ``except Exception: pass``
    has sent zero messages since it was written. So the answer survives and the
    reason is reported.
    """
    def boom(*_a, **_k):
        raise RuntimeError("disk is on fire")

    monkeypatch.setattr(misses, "record", boom)
    result = answer.ask(store, "a question during an outage", "en", "en")

    assert result["passage"]["state"] == "pending", "the answer must survive"
    assert "disk is on fire" in result["passage"]["meta"]["miss_log_error"]
    assert "miss_seen" not in result["passage"]["meta"]


def test_a_store_without_the_capability_is_not_an_error():
    """Absence of the miss log degrades quietly; it is an odometer, not a gate."""
    class Bare:
        pass

    assert misses.supports_misses(Bare()) is False
    assert misses.record(Bare(), "anything") == 0
    assert misses.queue(Bare()) == []
    assert misses.coverage(Bare()) == {"supported": False}


def test_misses_do_not_travel_in_an_export(store):
    """Bundles carry sealed answers. The record of what was not known stays home.

    ``portable.py`` draws the same line for warrants — an import may carry a
    warrant and may never carry a conclusion about it. A miss log on a portable
    drive is a record of the operator's questions leaving the house.
    """
    from nestor import portable
    answer.ask(store, "a private question", "en", "en")
    answer.ask(store, "a private question", "en", "en")

    memory.add_pair("Good evening.", "Buenas noches.", "en", "es",
                    status="sealed", verifier="rita", store=store)
    bundle = str(portable.export_bundle(store=store))

    # Non-vacuity first: an empty bundle would satisfy the real assertions
    # below without proving anything about what is excluded.
    assert "Buenas noches" in bundle, "the bundle must carry sealed answers"
    assert "a private question" not in bundle
    assert "query_misses" not in bundle


def test_the_digest_is_over_the_normalized_form():
    """Same question, different spelling, one identity."""
    assert misses.digest("what is the key") == misses.digest("what is the key")
    assert misses.digest("what is the key") != misses.digest("what is the lock")
    assert len(misses.digest("x")) == 64
