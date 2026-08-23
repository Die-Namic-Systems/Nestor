"""A serve decision must be a property of the pair, not of insertion order.

Both bugs pinned here were found by pointing Nestor at a real code corpus
(~1,500 cross-repo Grove functions) rather than at the synthetic bench. Neither
showed up in `bench/`, because every bench corpus normalizes to well under 200
characters — boilerplate to ~70, prose to 40-180 — so the whole autojunk regime
was untested.
"""
from __future__ import annotations

import difflib
import os
import random
import string

import pytest

from nestor import cascade, memory, storage
from nestor.matcher import StringMatcher
from nestor.sqlite_store import SqliteStore


@pytest.fixture()
def store(tmp_path, seal_key):
    os.environ['NESTOR_SEAL_KEY'] = 'test-key'
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    s = SqliteStore(":memory:")
    s.init_db()
    storage.set_store(s)
    return s


def _key(rng: random.Random, n: int) -> str:
    words = ["".join(rng.choice(string.ascii_lowercase)
                     for _ in range(rng.randrange(3, 9)))
             for _ in range(n // 5)]
    return " ".join(words)[:n]


# --- symmetry --------------------------------------------------------------

def test_similarity_is_symmetric_across_lengths():
    m = StringMatcher()
    rng = random.Random(21)
    for _ in range(400):
        a = _key(rng, rng.randrange(20, 1200))
        b = _key(rng, rng.randrange(20, 1200))
        assert m.similarity(a, b) == m.similarity(b, a)


def test_bare_difflib_is_not_symmetric():
    """Pins WHY the canonical ordering exists — remove it and this is the bug.

    If a future difflib makes ratio() symmetric this test fails loudly, which is
    the right prompt to re-examine the workaround rather than carry it forever.
    """
    rng = random.Random(21)
    asymmetric = 0
    for _ in range(400):
        a = _key(rng, rng.randrange(20, 1200))
        b = _key(rng, rng.randrange(20, 1200))
        if (difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
                != difflib.SequenceMatcher(None, b, a, autojunk=False).ratio()):
            asymmetric += 1
    assert asymmetric > 0, "difflib.ratio() is symmetric now — revisit StringMatcher"


# --- the autojunk cliff ----------------------------------------------------

def test_long_keys_do_not_collapse():
    """The regression that started this: two near-identical 200+ char strings.

    With difflib's default autojunk these score far below any serving threshold
    despite being obvious duplicates.
    """
    m = StringMatcher()
    body = ("async def grove_list_channels ctx none rows await fetch channels "
            "return id r id name r name unread r unread for r in rows ") * 3
    a = m.normalize(body + "extra tail one")
    b = m.normalize(body + "extra tail two")
    assert len(a) >= 200 and len(b) >= 200

    assert m.similarity(a, b) >= 0.92, "near-identical long keys must still match"
    # And the shipped default is materially better than difflib's default here.
    stock = difflib.SequenceMatcher(None, a, b).ratio()
    assert m.similarity(a, b) > stock


def test_autojunk_true_is_opt_in_and_still_available():
    fast = StringMatcher(autojunk=True)
    assert fast.autojunk is True
    assert StringMatcher().autojunk is False


# --- backward compatibility ------------------------------------------------

def test_short_keys_score_exactly_as_before():
    """Below 200 chars autojunk is inert; for near-duplicate text — the case
    that decides serving — canonical ordering changes nothing either."""
    m = StringMatcher()
    base = "the annual audit report supersedes any written notice under section"
    for i in range(200):
        a = m.normalize(f"{base} {i}")
        b = m.normalize(f"{base} {i + 1}")
        assert m.similarity(a, b) == difflib.SequenceMatcher(None, a, b).ratio()


def test_equal_normals_still_short_circuit():
    m = StringMatcher()
    assert m.similarity("same key", "same key") == 1.0


# --- end to end: the actual defect -----------------------------------------

def test_serving_does_not_depend_on_which_pair_was_sealed_first(store):
    """The correctness statement: seal A probe B, and seal B probe A, must agree.

    Before the fix these two orders could return SERVED and NO MATCH for the
    same two texts at the same threshold.
    """
    body = ("def grove_bus_send channel sender content bus type event priority "
            "correlation id ttl none conn await pool acquire await conn execute "
            "insert into messages channel id sender content values ") * 2
    A = body + " return message id one"
    B = body + " return message id two variant"
    assert len(StringMatcher().normalize(A)) >= 200

    verdicts = []
    for first, second in ((A, B), (B, A)):
        s = SqliteStore(":memory:")
        s.init_db()
        memory.add_pair(first, "TARGET", "d", "d", status="sealed",
                        verifier="v", store=s)
        hit = memory.best_sealed(second, "d", "d", store=s)
        verdicts.append(hit is not None)

    assert verdicts[0] == verdicts[1], (
        "serve decision flipped with seal order — similarity is not symmetric")
