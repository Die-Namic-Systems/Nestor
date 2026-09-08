"""``memory_list`` hides superseded rows — §6.127.

A superseded row is already outside the live key space; that is what
``idx_tm_pairs_key_live``'s ``WHERE superseded_by = ''`` says. Until this
bench, ``memory_list`` listed it anyway, so the review desk and the unique
index disagreed about what exists.

What that cost, measured 2026-09-07 on a live store: a curator retires a
duplicate draft, still sees it queued, seals it again, and gets HTTP 200 —
because ``_seal_draft`` recomputes the key, lands on the *live* twin, and
upgrades that instead. Nothing retires. 45 rows in one store behaved this
way and the operator pressed seal on them repeatedly, with no error to read.

Contract locked here:

* ``memory_list`` omits a superseded row by default.
* ``include_superseded=True`` returns it, for callers that mean the whole
  history (export, audit) rather than the working set.
* The filter composes with the other filters rather than replacing them.
* ``memory_get`` still reaches a superseded row by id — hiding it from a
  listing is not deleting it.
"""
import pytest

from nestor import memory
from nestor.sqlite_store import SqliteStore


@pytest.fixture()
def store(tmp_path):
    return SqliteStore(str(tmp_path / "nestor.db"))


def _pair(store, source, target, **kw):
    return memory.add_pair(source, target, "decision", "decision",
                           store=store, origin="test:6127", **kw)


def _superseded_pair(store):
    """A live sealed row and a draft superseded by it."""
    live = _pair(store, "does the desk agree with the index?", "now it does",
                 status="sealed", verifier="a person")
    shadow = _pair(store, "does the desk agree with the index, restated?",
                   "now it does")
    store.memory_mark_superseded(shadow["id"], live["id"])
    return live, shadow


def test_superseded_row_is_not_listed(store):
    live, shadow = _superseded_pair(store)
    ids = {r["id"] for r in store.memory_list(limit=50)}
    assert live["id"] in ids
    assert shadow["id"] not in ids, "a superseded row is out of the working set"


def test_superseded_row_is_listed_when_asked_for(store):
    live, shadow = _superseded_pair(store)
    ids = {r["id"] for r in store.memory_list(limit=50, include_superseded=True)}
    assert {live["id"], shadow["id"]} <= ids, "history is still reachable"


def test_filter_composes_rather_than_replaces(store):
    """The new clause must not swallow the status filter."""
    live, shadow = _superseded_pair(store)
    _pair(store, "an unrelated question", "an unrelated answer")
    drafts = store.memory_list(status="draft", limit=50)
    ids = {r["id"] for r in drafts}
    assert shadow["id"] not in ids, "superseded is still excluded"
    assert live["id"] not in ids, "the status filter still applies"
    assert all(r["status"] == "draft" for r in drafts)
    assert drafts, "the unrelated draft is still listed"


def test_superseded_row_is_hidden_not_deleted(store):
    _live, shadow = _superseded_pair(store)
    still_there = store.memory_get(shadow["id"])
    assert still_there is not None, "hiding from a listing is not deleting"
    assert still_there["superseded_by"]
