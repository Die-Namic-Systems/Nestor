"""IDEAS §6.26 — a second reviewer's agreement is recorded, not discarded.

Before this, `add_pair` sealing a row that was *already* sealed with the same
target wrote nothing, appended nothing and raised nothing, and handed the
stored row back to the caller as though they had sealed it. Disagreement was
loud (`ConflictingSealError` names both people and both targets); agreement was
silent. Nestor was better instrumented for reviewers who fight than for
reviewers who concur, which is backwards for a system whose product is *who
checked this*.

The whole fix is one ledger entry. `tm_pairs` has one `verifier` and one
`seal_sig` and they belong to whoever got there first, so the second signature
has nowhere to live but the chain — which is exactly what the chain is for.
"""

from __future__ import annotations

import collections
import json

import pytest

from nestor import cascade, memory, signing


def _chain(tmp_path) -> list[dict]:
    return [json.loads(line) for line
            in (tmp_path / "ledger.jsonl").read_text().splitlines()]


def _kinds(tmp_path) -> collections.Counter:
    return collections.Counter(e["kind"] for e in _chain(tmp_path))


@pytest.fixture()
def led(tmp_path):
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    return tmp_path


# --- the gate --------------------------------------------------------------

def test_a_second_verifier_agreeing_lands_in_the_chain(store, led, seal_key):
    """The finding, as a gate. Fails against the revision that reported it."""
    memory.add_pair("hello", "hola", "en", "es", status="sealed",
                    verifier="rita", store=store)
    memory.add_pair("hello", "hola", "en", "es", status="sealed",
                    verifier="sam", store=store)

    counter = [e for e in _chain(led) if e["kind"] == "countersign"]
    assert len(counter) == 1, (
        f"agreement left no trace; chain is {dict(_kinds(led))}")
    assert counter[0]["verifier"] == "sam"
    assert counter[0]["countersigned"] == "rita"


def test_the_countersignature_is_evidence_about_the_second_person(store, led,
                                                                  seal_key):
    """A log line saying "sam agreed" is worth nothing; anyone can write it.

    The entry carries a signature over the same bound fields a seal signs, made
    with the countersigner's key — so it verifies under *sam*, and does not
    verify under a claim that rita made it."""
    memory.add_pair("hello", "hola", "en", "es", status="sealed",
                    verifier="rita", store=store)
    memory.add_pair("hello", "hola", "en", "es", status="sealed",
                    verifier="sam", store=store)
    entry = next(e for e in _chain(led) if e["kind"] == "countersign")

    assert signing.seal_is_valid("hello", "hola", "sam", entry["sig"])
    assert not signing.seal_is_valid("hello", "hola", "rita", entry["sig"])


# --- what must NOT be recorded ---------------------------------------------

def test_the_same_verifier_resealing_is_a_retry_not_a_countersignature(
        store, led, seal_key):
    """Idempotence was always the behaviour here and stays it. rita agreeing
    with rita is one person pressing the button twice."""
    for _ in range(3):
        memory.add_pair("hello", "hola", "en", "es", status="sealed",
                        verifier="rita", store=store)
    assert _kinds(led)["countersign"] == 0


def test_two_anonymous_seals_do_not_fabricate_a_countersignature(store, led,
                                                                 seal_key):
    """The polarity trap, as a gate.

    `_same_verifier` answers *may we assume the same actor*, and resolves
    unknown to "not the same" so a conflict guard fails closed. Writing this
    branch as `not _same_verifier(...)` inherits the wrong polarity: two
    unidentified callers become a recorded agreement between two people who
    never named themselves. Both sides have to name somebody before there is
    anything to record."""
    memory.add_pair("hello", "hola", "en", "es", status="sealed", store=store)
    memory.add_pair("hello", "hola", "en", "es", status="sealed", store=store)
    assert _kinds(led)["countersign"] == 0


@pytest.mark.parametrize("first,second", [("rita", ""), ("", "sam")])
def test_one_named_and_one_anonymous_is_not_a_countersignature(
        store, led, seal_key, first, second):
    memory.add_pair("hello", "hola", "en", "es", status="sealed",
                    verifier=first, store=store)
    memory.add_pair("hello", "hola", "en", "es", status="sealed",
                    verifier=second, store=store)
    assert _kinds(led)["countersign"] == 0


# --- what must not move ----------------------------------------------------

def test_countersigning_changes_nothing_about_the_row(store, led, seal_key):
    """The row still holds one decision. `tm_pairs` has one verifier and one
    signature; a countersignature does not compete for them, and a reviewer
    reading the Memory page sees exactly what they saw before."""
    memory.add_pair("hello", "hola", "en", "es", status="sealed",
                    verifier="rita", store=store)
    before = dict(store.memory_find("hello", "en", "es"))

    memory.add_pair("hello", "hola", "en", "es", status="sealed",
                    verifier="sam", store=store)
    after = dict(store.memory_find("hello", "en", "es"))

    assert after == before, "the row moved; only the chain should have"


def test_countersigning_changes_nothing_about_what_is_served(store, led,
                                                             seal_key):
    memory.add_pair("hello", "hola", "en", "es", status="sealed",
                    verifier="rita", store=store)
    served_before = memory.best_sealed("hello", "en", "es", store=store)
    memory.add_pair("hello", "hola", "en", "es", status="sealed",
                    verifier="sam", store=store)
    served_after = memory.best_sealed("hello", "en", "es", store=store)

    assert served_after["pair"]["id"] == served_before["pair"]["id"]
    assert served_after["pair"]["verifier"] == "rita"


def test_a_third_reviewer_is_a_third_entry(store, led, seal_key):
    """N-of-M is not implemented and this is not it. But if it is ever wanted,
    the count has to come from somewhere, and §1.4's blocker was that nothing
    was written down at all — so the entries have to accumulate rather than
    collapse."""
    for who in ("rita", "sam", "jo"):
        memory.add_pair("hello", "hola", "en", "es", status="sealed",
                        verifier=who, store=store)
    counter = [e for e in _chain(led) if e["kind"] == "countersign"]
    assert [e["verifier"] for e in counter] == ["sam", "jo"]
    assert {e["countersigned"] for e in counter} == {"rita"}


def test_the_chain_still_verifies_after_a_countersignature(store, led, seal_key):
    from nestor import ledger
    memory.add_pair("hello", "hola", "en", "es", status="sealed",
                    verifier="rita", store=store)
    memory.add_pair("hello", "hola", "en", "es", status="sealed",
                    verifier="sam", store=store)
    ok, detail = ledger.verify(str(led / "ledger.jsonl"))
    assert ok, detail
