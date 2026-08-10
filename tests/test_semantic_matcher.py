"""SemanticMatcher — the parts that genuinely need an embedding model.

The behaviours this matcher introduced to the *seam* — the retype short-circuit,
the default-threshold warning, and the batch scoring path — are pinned in
`test_matcher.py` against a matcher with a `score()` and no model, because they
are properties of the seam and this file only runs where `fastembed` is
installed, which CI is not. What is left here is what a fake cannot claim: that
an embedding really does rank a paraphrase above a character ratio.

Refusal-without-extra paths use the ``without_fastembed`` fixture so one venv
can hold both the installed-extra and the missing-extra cases.
"""

from __future__ import annotations

import importlib.util

import pytest

from nestor import answer
from nestor.matcher import StringMatcher
from nestor.semantic_matcher import SemanticMatcher, _cosine


def _fastembed_installed() -> bool:
    return importlib.util.find_spec("fastembed") is not None


requires_semantic = pytest.mark.skipif(
    not _fastembed_installed(),
    reason="pip install nestor[semantic]",
)


def test_cosine_clamps_to_unit_interval():
    assert _cosine((1.0, 0.0), (1.0, 0.0)) == 1.0
    assert _cosine((1.0, 0.0), (0.0, 1.0)) == 0.0


@requires_semantic
def test_normalize_delegates_to_dedup_matcher():
    m = SemanticMatcher()
    assert m.normalize("  Hello, WORLD ") == StringMatcher().normalize("  Hello, WORLD ")


@requires_semantic
def test_build_matcher_semantic_returns_matcher():
    assert isinstance(answer.build_matcher("semantic"), SemanticMatcher)


def test_semantic_matcher_constructor_refuses_without_fastembed(without_fastembed):
    with pytest.raises(ImportError, match="nestor\\[semantic\\]"):
        SemanticMatcher()


def test_build_matcher_semantic_refuses_without_fastembed(without_fastembed):
    with pytest.raises(ValueError, match="semantic"):
        answer.build_matcher("semantic")


@requires_semantic
def test_score_returns_one_when_normalized_forms_match():
    """Retype-equivalent queries must not score below 1.0 on the embedding path."""
    m = SemanticMatcher()
    raw_a, raw_b = "Good evening.", "GOOD  evening!!"
    assert m.normalize(raw_a) == m.normalize(raw_b)
    assert m.score(raw_a, raw_b) == 1.0


@requires_semantic
def test_score_matcher_warns_on_default_seal_threshold(store, seal_key):
    """The same guard `test_matcher.py` pins at the seam, once over a real model."""
    import warnings

    from nestor import memory

    m = SemanticMatcher()
    memory.add_pair("Good evening.", "Buenos noches.", "en", "es",
                    status="sealed", verifier="rita", store=store, matcher=m)
    memory._warned_score_threshold = False
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        memory.best_sealed("Good evening", "en", "es", store=store, matcher=m)
    assert any("SEAL_THRESHOLD" in str(w.message) for w in caught)


@requires_semantic
def test_scores_against_batches_uncached_texts():
    m = SemanticMatcher()
    scores = m.scores_against("hello world", ["hello there", "completely different topic"])
    assert len(scores) == 2
    assert all(0.0 <= s <= 1.0 for s in scores)


def test_unknown_matcher_still_refused():
    with pytest.raises(ValueError, match="unknown matcher"):
        answer.build_matcher("vector")
