"""The patch-review recipe: the seam holds, and the covenant holds through it.

A recipe is where Nestor's guarantees are most likely to leak, because a recipe
author is the person most tempted to add a convenience. These gates are aimed at
that author.
"""

from __future__ import annotations

import inspect

import pytest

from nestor import memory
from nestor.matcher import Matcher
from recipes import patch_review


@pytest.fixture()
def store(tmp_path):
    from nestor import cascade
    from nestor.sqlite_store import SqliteStore
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    s = SqliteStore(str(tmp_path / "n.db"))
    s.memory_init()
    try:
        yield s
    finally:
        s.close()


# --- the seam --------------------------------------------------------------

def test_defect_matcher_satisfies_the_protocol():
    assert isinstance(patch_review.MATCHER, Matcher)


def test_normalize_is_idempotent():
    """matcher.py's Protocol asks for normalize(normalize(x)) == normalize(x)."""
    for text in ("memory_init replays the schema on sqlite_store.py:374",
                 "ConflictingSealError names both verifiers",
                 "   ",
                 "the and of"):
        once = patch_review.MATCHER.normalize(text)
        assert patch_review.MATCHER.normalize(once) == once, text


def test_scoring_is_symmetric():
    """bench/token_matchers.py records that StringMatcher's asymmetry broke
    serving in measurable ways. A matcher that regressed on that is worse than
    useless, so this is checked rather than assumed."""
    a = "memory_init replays the whole schema script on every call"
    b = "why is every add_pair running CREATE TABLE again?"
    assert patch_review.MATCHER.score(a, b) == patch_review.MATCHER.score(b, a)
    na, nb = (patch_review.MATCHER.normalize(x) for x in (a, b))
    assert patch_review.MATCHER.similarity(na, nb) == \
           patch_review.MATCHER.similarity(nb, na)


@pytest.mark.parametrize("token", [
    "memory_init", "superseded_by", "ConflictingSealError", "camelCase",
    "sqlite_store.py", "sqlite_store.py:374", "nestor.memory",
])
def test_identifiers_are_recognised(token):
    assert patch_review.looks_like_code(token)


@pytest.mark.parametrize("token", [
    "returns", "silently", "caller", "schema", "the", "374", "REVIEW",
])
def test_prose_is_not_mistaken_for_code(token):
    assert not patch_review.looks_like_code(token)


def test_identifier_weighting_actually_moves_the_ranking():
    """The design claim, as a gate. Two candidate defects: one shares only
    prose with the probe, one shares the identifier. Unweighted token sets
    cannot separate them; weighting is the whole reason this matcher exists."""
    probe = "the call silently returned the stored row for memory_init"
    shares_identifier = "memory_init was reached by a path that did something else"
    shares_prose = "the call silently returned the stored row for something"

    old = patch_review.IDENT_WEIGHT
    try:
        patch_review.IDENT_WEIGHT = 1.0
        flat_id = patch_review.MATCHER.score(probe, shares_identifier)
        flat_prose = patch_review.MATCHER.score(probe, shares_prose)
        patch_review.IDENT_WEIGHT = 8.0
        heavy_id = patch_review.MATCHER.score(probe, shares_identifier)
        heavy_prose = patch_review.MATCHER.score(probe, shares_prose)
    finally:
        patch_review.IDENT_WEIGHT = old

    assert heavy_id / heavy_prose > flat_id / flat_prose, (
        "raising IDENT_WEIGHT did not move the identifier-sharing candidate up "
        "relative to the prose-sharing one, so the weight is decorative")


# --- the covenant ----------------------------------------------------------

def test_propose_offers_no_route_to_a_seal():
    """The gate aimed at a future convenience. `propose` must not grow a
    `status=` or `verifier=` parameter, because the shortest path from here to
    a broken covenant is somebody adding one 'just for scripts'."""
    params = set(inspect.signature(patch_review.propose).parameters)
    assert not params & {"status", "verifier", "seal", "verified"}, params


def test_a_proposed_patch_is_a_draft(store):
    patch_review.propose("a defect in memory_init", "a fix", store=store)
    stats = memory.stats(store=store)
    assert stats["draft"] == 1 and stats["sealed"] == 0


def test_fix_for_never_returns_an_unsealed_row(store):
    """Tier 1 serves seals. A draft coming back from `fix_for` would be the
    recipe serving something nobody checked, which is the single thing putting
    patches in Nestor is supposed to prevent."""
    defect = "glossary.json is resolved against the working directory"
    patch_review.propose(defect, "resolve it absolutely", store=store)
    assert patch_review.fix_for(defect, store=store, seal_threshold=0.0) is None


# --- rival patches ---------------------------------------------------------

def test_a_rival_patch_is_refused_and_both_exits_are_named(store):
    defect = "init_db creates an index over superseded_by"
    patch_review.propose(defect, "call the lineage migration first", store=store)
    with pytest.raises(patch_review.RivalPatchError) as exc:
        patch_review.propose(defect, "drop the index instead", store=store)
    message = str(exc.value)
    assert "revise()" in message and "split" in message


def test_the_refusal_does_not_swallow_which_guard_fired(store):
    """RivalPatchError chains the store's own exception. Losing it would leave a
    caller unable to tell a draft conflict from a seal conflict or a rejection —
    three different refusals with three different remedies."""
    defect = "two threads sealed the same phrase"
    patch_review.propose(defect, "a partial unique index", store=store)
    with pytest.raises(patch_review.RivalPatchError) as exc:
        patch_review.propose(defect, "a lock in Python", store=store)
    assert isinstance(exc.value.__cause__, memory.ConflictingDraftError)


def test_an_identical_re_proposal_is_not_a_rival(store):
    """Idempotence is not a conflict — re-proposing the same patch is a retry,
    not a disagreement, and `add_pair` has always treated it that way."""
    defect = "lookup scores every row"
    fix = "a lossless prefilter on difflib's bounds"
    patch_review.propose(defect, fix, store=store)
    patch_review.propose(defect, fix, store=store)
    assert memory.stats(store=store)["total"] == 1


def test_revise_replaces_the_draft_and_demands_a_reason(store):
    defect = "a refusal message was wrong at low scores"
    patch_review.propose(defect, "reword the sentence", store=store)

    with pytest.raises(ValueError, match="needs a reason"):
        patch_review.revise(defect, "make the claim about the rule", "  ",
                            store=store)

    patch_review.revise(defect, "make the claim about the rule",
                        reason="the first wording was true at 0.71 and false "
                               "at 0.11", store=store)
    live = store.memory_find(patch_review.MATCHER.normalize(defect),
                             patch_review.DOMAIN, patch_review.DOMAIN)
    assert live is not None
    assert live["target_text"] == "make the claim about the rule"
    assert live["status"] == "draft"
