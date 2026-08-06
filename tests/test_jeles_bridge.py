"""The jeles bridge: an unsigned claim of verification does not cross as one.

`jeles` is the fleet's verified-corpus organ, and its own `put_nugget` docstring
says the thing this bridge exists for:

    ``verified_by`` is a claim: whatever string the writer supplied.

So the load-bearing test here is the boring-looking one: a nugget jeles holds as
``verification_kind="human"``, with a real name in ``verified_by``, arrives in
this store as a **draft** and `answer_for` returns ``None``. Anything else would
be laundering — the same laundering `nestor.portable.import_bundle` already
refuses when a bundle asserts a seal it cannot prove.

Most of these run on plain dicts and need no jeles install, so they hold in CI.
The one that drives a real jeles corpus is skipped when the package is absent
rather than faked, because a fixture that mocks the system under test proves the
mock works.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from nestor import cascade, memory, storage           # noqa: E402
from nestor.sqlite_store import SqliteStore           # noqa: E402
from recipes import jeles_bridge as JB                # noqa: E402

HUMAN = {"question": "What does a seal bind to?",
         "answer": "A key the store does not hold.",
         "sources": ["docs/seal.md"], "verified_by": "sean",
         "verified_at": "2026-08-06", "verification_kind": "human",
         "status": "verified"}
ASSERTED = {"question": "Is the ledger append-only?",
            "answer": "Yes, hash-chained.", "sources": ["README.md"],
            "verified_by": "sean", "written_by": "some-tool",
            "verification_kind": "asserted", "status": "asserted"}


@pytest.fixture()
def store(tmp_path, seal_key):
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    s = SqliteStore(":memory:")
    s.init_db()
    s.memory_init()
    storage.set_store(s)
    return s


def test_a_human_verified_nugget_crosses_as_a_draft(store):
    """The whole point. jeles says human; this store has no way to check it."""
    report = JB.bridge_nuggets([HUMAN], store=store)
    assert report["sealed"] == 0, "nothing may cross as sealed"
    assert report["demoted"] == 1

    rows = list(store.memory_candidates(JB.DOMAIN, JB.DOMAIN))
    assert len(rows) == 1
    assert rows[0]["status"] == "draft"
    assert not rows[0].get("verifier"), \
        "a name jeles was given is not a verifier here"


def test_what_jeles_believed_is_kept_beside_the_row(store):
    """Demoting is not discarding — a reviewer must see what was claimed."""
    JB.bridge_nuggets([HUMAN], store=store)
    row = list(store.memory_candidates(JB.DOMAIN, JB.DOMAIN))[0]
    reason = row.get("reason") or ""
    assert "human" in reason and "sean" in reason
    assert "docs/seal.md" in reason, "the citations must survive the crossing"
    assert "unsigned claim" in reason


def test_a_bridged_nugget_is_not_served(store):
    JB.bridge_nuggets([HUMAN, ASSERTED], store=store)
    assert JB.answer_for(HUMAN["question"], store=store) is None, \
        "nothing re-verified here may be served as verified"
    seen = JB.candidates(HUMAN["question"], store=store)
    assert seen and all(c["pair"]["status"] == "draft" for c in seen), \
        "but it must be visible in the queue view"


def test_it_is_served_once_a_human_seals_it_here(store):
    """The bridge is a queue, not a wall. Sealed in-process with the matcher
    installed, because `nestor.ui` cannot be told about one — IDEAS §6.40."""
    JB.bridge_nuggets([HUMAN], store=store)
    memory.add_pair(HUMAN["question"], HUMAN["answer"], JB.DOMAIN, JB.DOMAIN,
                    status="sealed", verifier="a-human-who-read-it",
                    origin="test", store=store, matcher=JB.MATCHER)
    got = JB.answer_for(HUMAN["question"], store=store)
    assert got is not None
    assert got["pair"]["verifier"] == "a-human-who-read-it"


def test_the_matcher_keeps_jeles_strictness():
    """jeles answers only when the asker's words are all present and the two
    questions overlap symmetrically. Mirrored, not imported."""
    base = JB.MATCHER.normalize(HUMAN["question"])

    def sim(q):
        return JB.MATCHER.similarity(JB.MATCHER.normalize(q), base)

    assert sim(HUMAN["question"]) == 1.0
    assert sim("seal") < memory.SEAL_THRESHOLD, \
        "one shared word must not pull an answer out"
    assert sim("What does a seal bind to in production?") < memory.SEAL_THRESHOLD, \
        "a narrower question must not be answered by a broader nugget"
    assert sim("what colour is the sky") == 0.0


def test_staging_cannot_answer_production():
    """jeles' own example, and the reason the rule is symmetric."""
    a = JB.MATCHER.normalize("Which database does staging use?")
    b = JB.MATCHER.normalize("Which database does production use?")
    assert JB.MATCHER.similarity(a, b) < memory.SEAL_THRESHOLD


def test_a_gap_writes_nothing(store):
    """A gap is a question with no answer. There is nothing to propose."""
    gaps = JB.bridge_gaps([{"question": "who audited the odometer in 1998",
                            "asked_count": 3}])
    assert gaps == [{"question": "who audited the odometer in 1998",
                     "asked_count": 3, "variants": []}]
    assert not list(store.memory_candidates(JB.DOMAIN, JB.DOMAIN)), \
        "reading gaps must not write rows"


def test_gaps_are_ordered_by_how_often_they_were_asked():
    gaps = JB.bridge_gaps([{"question": "rare", "asked_count": 1},
                           {"question": "common", "asked_count": 9}])
    assert [g["question"] for g in gaps] == ["common", "rare"]


def test_against_a_real_jeles_corpus(tmp_path, store, monkeypatch):
    """Skipped rather than mocked when jeles is absent — CI has no clone of it."""
    jeles = pytest.importorskip("jeles.corpus",
                                reason="jeles not installed in this environment")
    monkeypatch.setenv("WILLOW_STORE_ROOT", str(tmp_path / "willow"))
    (tmp_path / "willow").mkdir(parents=True, exist_ok=True)

    made = jeles.put_nugget(HUMAN["question"], HUMAN["answer"], HUMAN["sources"],
                            verified_by="sean", verification_kind="human")
    assert "error" not in made, made
    asked = jeles.ask_corpus(HUMAN["question"])
    assert asked["found"] is True, "jeles serves its own human-verified nugget"

    JB.bridge_nuggets([asked["nugget"]], store=store)
    assert JB.answer_for(HUMAN["question"], store=store) is None, (
        "the same nugget jeles serves as verified must not be served here "
        "until somebody signs for it")
