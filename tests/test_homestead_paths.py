"""Tests for homestead-aligned path resolver."""
from __future__ import annotations

from nestor import homestead_paths


def test_home_defaults_to_dot_homestead(monkeypatch, tmp_path):
    monkeypatch.delenv("HOMESTEAD_HOME", raising=False)
    monkeypatch.setattr(homestead_paths.Path, "home", lambda: tmp_path)
    assert homestead_paths.home() == tmp_path / ".homestead"


def test_home_respects_homestead_home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path / "hh"))
    assert homestead_paths.home() == tmp_path / "hh"


def test_ledger_path_under_keep(monkeypatch, tmp_path):
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    assert homestead_paths.ledger_path() == tmp_path / "keep" / "ledger.jsonl"


def test_bind_ledger_sets_cascade(monkeypatch, tmp_path):
    from nestor import cascade

    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path))
    cascade.reset_ledger_session()
    path = homestead_paths.bind_ledger()
    assert path == tmp_path / "keep" / "ledger.jsonl"
    assert cascade._ledger_path() == path
    cascade.reset_ledger_session()
    cascade.set_ledger_path("data/ledger.jsonl")
