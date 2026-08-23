"""Ollama matcher — local nomic-embed-text over stdlib HTTP (IDEAS §6.96).

Skipped when Ollama or the model is absent, so CI without a daemon stays green.
"""
from __future__ import annotations

import pytest

from nestor import answer, ollama_embed
from nestor.matcher import StringMatcher
from nestor.semantic_matcher import SemanticMatcher

requires_ollama = pytest.mark.skipif(
    not ollama_embed.available(),
    reason="Ollama with nomic-embed-text not reachable",
)


@requires_ollama
def test_build_matcher_ollama_returns_named_matcher():
    m = answer.build_matcher("ollama")
    assert isinstance(m, SemanticMatcher)
    assert m.name == "ollama"
    assert m.backend == "ollama"
    assert m.model_name.split(":", 1)[0] == "nomic-embed-text"


@requires_ollama
def test_aws_beats_string_matcher():
    sm = StringMatcher()
    raw_a, raw_b = "AWS", "Amazon Web Services"
    lexical = sm.similarity(sm.normalize(raw_a), sm.normalize(raw_b))
    semantic = SemanticMatcher(backend="ollama").score(raw_a, raw_b)
    assert lexical < 0.5, f"fixture assumption drifted: StringMatcher={lexical}"
    assert semantic > lexical, (
        f"ollama matcher should beat StringMatcher on acronym case; "
        f"got semantic={semantic}, lexical={lexical}"
    )


@requires_ollama
def test_score_is_symmetric():
    m = SemanticMatcher(backend="ollama")
    a, b = "the seal is a human act", "a human act is the seal"
    assert m.score(a, b) == m.score(b, a)


@requires_ollama
def test_scores_against_matches_score():
    m = SemanticMatcher(backend="ollama")
    probe = "Amazon Web Services"
    stored = ["AWS", "completely unrelated gardening tips"]
    batch = m.scores_against(probe, stored)
    for text, got in zip(stored, batch):
        assert got == pytest.approx(m.score(probe, text), abs=1e-9)


def test_constructor_refuses_when_ollama_unreachable(monkeypatch):
    ollama_embed.reset_cache()
    monkeypatch.setattr(ollama_embed, "available", lambda model="nomic-embed-text": False)
    with pytest.raises(RuntimeError, match="Ollama"):
        SemanticMatcher(backend="ollama")
    with pytest.raises(ValueError, match="Ollama"):
        answer.build_matcher("ollama")


def test_host_refuses_non_http_schemes(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "file:///tmp/evil")
    with pytest.raises(ValueError, match="http"):
        ollama_embed.host()


def test_unknown_backend_refused():
    with pytest.raises(ValueError, match="backend"):
        SemanticMatcher(backend="not-a-backend")  # type: ignore[arg-type]
