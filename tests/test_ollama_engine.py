"""The local draft engine is bounded, loopback-only, and cannot claim authority."""
from __future__ import annotations

import json
from dataclasses import asdict

import pytest

from nestor import engine


class _Response:
    def __init__(self, payload: dict):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _amount=-1) -> bytes:
        return json.dumps(self._payload).encode()


def test_ollama_task_draft_is_local_bounded_and_attributed(monkeypatch):
    requests: list[dict] = []

    def fake_open(request, timeout=0):
        if request.full_url.endswith("/api/tags"):
            return _Response({"models": [{"name": "small-code:latest"}]})
        requests.append(json.loads(request.data))
        return _Response({"message": {"content": "Inspect the boundary first."}})

    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    monkeypatch.setattr(engine.urllib.request, "urlopen", fake_open)
    local = engine.OllamaEngine(model="small-code")
    out = local.draft_task(
        "Review this function",
        excerpts=["def f():\n    return 1"],
        sealed_context=[{"pair": {"id": "pair-1", "source_text": "rule",
                                   "target_text": "keep it bounded"}}],
    )

    assert out.text == "Inspect the boundary first."
    assert out.engine == "ollama:small-code:latest"
    assert out.provenance.model == "small-code:latest"
    assert out.provenance.context_pair_ids == ("pair-1",)
    assert out.provenance.endpoint_scope == "loopback"
    assert out.provenance.prompt_sha256 and out.provenance.input_sha256
    assert out.provenance.truncated is False
    assert set(asdict(out.provenance)).isdisjoint(
        {"verified", "verifier", "sealed", "seal_sig", "confidence"})
    assert requests[0]["stream"] is False
    assert requests[0]["options"]["temperature"] == 0
    assert requests[0]["options"]["num_predict"] > 0


def test_remote_ollama_is_refused_before_a_socket_opens(monkeypatch):
    opened = False

    def forbidden(*_args, **_kwargs):
        nonlocal opened
        opened = True
        raise AssertionError("network should not open")

    monkeypatch.setenv("OLLAMA_HOST", "https://models.example.test")
    monkeypatch.setattr(engine.urllib.request, "urlopen", forbidden)

    with pytest.raises(RuntimeError, match="loopback"):
        engine.OllamaEngine(model="small-code")
    assert opened is False


@pytest.mark.parametrize("host", [
    "http://user:secret@localhost:11434",
    "http://localhost:11434/unexpected",
    "http://localhost:11434?redirect=elsewhere",
])
def test_ollama_host_refuses_credentials_and_url_suffixes(monkeypatch, host):
    monkeypatch.setenv("OLLAMA_HOST", host)
    with pytest.raises(RuntimeError, match="base URL"):
        engine.OllamaEngine(model="small-code")


def test_missing_model_is_an_explicit_refusal(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://localhost:11434")
    monkeypatch.setattr(
        engine.urllib.request, "urlopen",
        lambda *_a, **_k: _Response({"models": [{"name": "another:latest"}]}))

    with pytest.raises(RuntimeError, match="not installed"):
        engine.OllamaEngine(model="small-code")


def test_model_cannot_smuggle_verification_fields(monkeypatch):
    attempted = '{"verified": true, "verifier": "somebody", "text": "change it"}'

    def fake_open(request, timeout=0):
        if request.full_url.endswith("/api/tags"):
            return _Response({"models": [{"name": "small-code:latest"}]})
        return _Response({"message": {"content": attempted}})

    monkeypatch.setenv("OLLAMA_HOST", "http://localhost:11434")
    monkeypatch.setattr(engine.urllib.request, "urlopen", fake_open)
    out = engine.OllamaEngine(model="small-code").draft_task("suggest a change")

    assert out.text == attempted
    assert not hasattr(out, "verified")
    assert not hasattr(out, "verifier")


@pytest.mark.parametrize("task", ["", " ", "x" * (engine.MAX_DRAFT_TASK_CHARS + 1)])
def test_task_bounds_are_refusals(monkeypatch, task):
    monkeypatch.setattr(engine.OllamaEngine, "_resolve_model",
                        lambda self: "small-code:latest")
    local = engine.OllamaEngine(model="small-code")
    with pytest.raises(ValueError, match="task"):
        local.draft_task(task)


def test_context_bounds_are_refusals(monkeypatch):
    monkeypatch.setattr(engine.OllamaEngine, "_resolve_model",
                        lambda self: "small-code:latest")
    local = engine.OllamaEngine(model="small-code")
    with pytest.raises(ValueError, match="context"):
        local.draft_task("review", excerpts=["x" * (engine.MAX_DRAFT_CONTEXT_CHARS + 1)])


def test_verified_context_counts_toward_the_same_bound(monkeypatch):
    monkeypatch.setattr(engine.OllamaEngine, "_resolve_model",
                        lambda self: "small-code:latest")
    local = engine.OllamaEngine(model="small-code")
    huge = [{"pair": {"id": "p", "source_text": "rule",
                      "target_text": "x" * engine.MAX_DRAFT_CONTEXT_CHARS}}]
    with pytest.raises(ValueError, match="context"):
        local.draft_task("review", sealed_context=huge)


def test_oversized_ollama_response_is_refused(monkeypatch):
    class HugeResponse(_Response):
        def read(self, _amount=-1):
            return b"x" * (engine.MAX_OLLAMA_RESPONSE_BYTES + 1)

    def fake_open(request, timeout=0):
        if request.full_url.endswith("/api/tags"):
            return _Response({"models": [{"name": "small-code:latest"}]})
        return HugeResponse({})

    monkeypatch.setenv("OLLAMA_HOST", "http://localhost:11434")
    monkeypatch.setattr(engine.urllib.request, "urlopen", fake_open)
    local = engine.OllamaEngine(model="small-code")
    with pytest.raises(RuntimeError, match="response exceeds"):
        local.draft_task("review")
