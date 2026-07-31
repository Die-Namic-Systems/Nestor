"""SemanticMatcher — requires nestor[semantic] when fastembed is installed."""

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

requires_no_semantic = pytest.mark.skipif(
    _fastembed_installed(),
    reason="fastembed is installed — refusal-path tests need a env without nestor[semantic]",
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


@requires_no_semantic
def test_semantic_matcher_constructor_refuses_without_fastembed():
    with pytest.raises(ImportError, match="nestor\\[semantic\\]"):
        SemanticMatcher()


@requires_no_semantic
def test_build_matcher_semantic_refuses_without_fastembed():
    with pytest.raises(ValueError, match="semantic"):
        answer.build_matcher("semantic")


@requires_semantic
def test_score_returns_one_when_normalized_forms_match():
    """Retype-equivalent queries must not score below 1.0 on the embedding path."""
    m = SemanticMatcher()
    raw_a, raw_b = "Good evening.", "GOOD  evening!!"
    assert m.normalize(raw_a) == m.normalize(raw_b)
    assert m.score(raw_a, raw_b) == 1.0


def test_unknown_matcher_still_refused():
    with pytest.raises(ValueError, match="unknown matcher"):
        answer.build_matcher("vector")
