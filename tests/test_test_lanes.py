"""Verification cost is explicit; ambient integrations never enlarge core."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from nestor import memory
from nestor.matcher import StringMatcher
from tests import conftest

REPO = Path(__file__).resolve().parent.parent


def test_semantic_default_does_not_probe_or_load_the_model(monkeypatch):
    monkeypatch.delenv("NESTOR_SEMANTIC_TEST", raising=False)

    def forbidden():
        raise AssertionError("default collection must not initialize FastEmbed/ONNX")

    monkeypatch.setattr(conftest, "_semantic_model_loadable", forbidden)

    assert conftest.semantic_tests_enabled() is False


def test_session_scrub_precedes_module_fixtures_but_keeps_lane_opt_ins(monkeypatch):
    monkeypatch.setenv("NESTOR_KEYRING", "/real/operator/keyring.json")
    monkeypatch.setenv("NESTOR_SEMANTIC_TEST", "1")

    conftest.pytest_sessionstart(None)

    assert "NESTOR_KEYRING" not in os.environ
    assert os.environ["NESTOR_SEMANTIC_TEST"] == "1"


def test_per_test_isolation_resets_and_restores_the_process_matcher(tmp_path):
    class PoisonMatcher:
        def normalize(self, value):
            return "NONE"

        def similarity(self, left, right):
            return 1.0

    saved = memory.get_matcher()
    poison = PoisonMatcher()
    memory.set_matcher(poison)
    guard = conftest.isolate_globals.__wrapped__(tmp_path)
    next(guard)
    try:
        assert isinstance(memory.get_matcher(), StringMatcher)
    finally:
        with pytest.raises(StopIteration):
            next(guard)
    assert memory.get_matcher() is poison
    memory.set_matcher(saved)


def test_lane_runner_names_every_expensive_integration():
    script = (REPO / "scripts" / "ci-test.sh").read_text(encoding="utf-8")

    for lane in ("core", "full", "slow", "performance", "browser", "semantic", "ollama", "external"):
        assert f"{lane})" in script
    for marker in ("slow", "browser", "semantic", "ollama", "external"):
        assert f"not {marker}" in script
    assert "--dist loadgroup" in script
