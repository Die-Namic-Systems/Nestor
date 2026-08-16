"""Tests for Nestor's own household path resolver (``$NESTOR_HOME`` / ``~/.nestor``)."""
from __future__ import annotations

import pytest

from nestor import home_paths


@pytest.fixture(autouse=True)
def _no_inherited_roots(monkeypatch):
    """Neither root leaks in from the developer's shell or a host's env."""
    monkeypatch.delenv("NESTOR_HOME", raising=False)
    monkeypatch.delenv("HOMESTEAD_HOME", raising=False)


def test_home_defaults_to_dot_nestor(monkeypatch, tmp_path):
    monkeypatch.setattr(home_paths.Path, "home", lambda: tmp_path)
    assert home_paths.home() == tmp_path / ".nestor"


def test_home_respects_nestor_home(monkeypatch, tmp_path):
    monkeypatch.setenv("NESTOR_HOME", str(tmp_path / "nh"))
    assert home_paths.home() == tmp_path / "nh"


def test_ledger_path_under_keep(monkeypatch, tmp_path):
    monkeypatch.setenv("NESTOR_HOME", str(tmp_path))
    assert home_paths.ledger_path() == tmp_path / "keep" / "ledger.jsonl"


def test_bind_ledger_sets_cascade(monkeypatch, tmp_path):
    from nestor import cascade

    monkeypatch.setenv("NESTOR_HOME", str(tmp_path))
    cascade.reset_ledger_session()
    path = home_paths.bind_ledger()
    assert path == tmp_path / "keep" / "ledger.jsonl"
    assert cascade._ledger_path() == path
    cascade.reset_ledger_session()
    cascade.set_ledger_path("data/ledger.jsonl")


# --- the forbidden act: relocating a live keep tree by saying nothing --------

def test_legacy_root_alone_is_refused_not_guessed(monkeypatch, tmp_path):
    """$HOMESTEAD_HOME without $NESTOR_HOME must raise, not silently resolve.

    The old root is where a host's hash-chained keep/ledger.jsonl already is.
    Resolving to ~/.nestor instead would not move that chain, it would begin a
    second one — so the resolver is required to stop, and this test fails if
    anyone makes it 'helpful' by falling back either way.
    """
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path / "old"))
    monkeypatch.setattr(home_paths.Path, "home", lambda: tmp_path)

    with pytest.raises(home_paths.HomeRelocationRefused) as excinfo:
        home_paths.home()

    # The refusal has to be actionable: it names both roots and the way out.
    message = str(excinfo.value)
    assert "HOMESTEAD_HOME" in message and "NESTOR_HOME" in message
    assert str(tmp_path / "old") in message
    assert "docs/home-paths.md" in message


def test_refusal_reaches_the_callers_that_resolve_a_path(monkeypatch, tmp_path):
    """keep_dir/ledger_path/bind_ledger inherit the refusal — no side door."""
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path / "old"))

    for resolve in (home_paths.keep_dir, home_paths.ledger_path, home_paths.bind_ledger):
        with pytest.raises(home_paths.HomeRelocationRefused):
            resolve()


def test_nestor_home_settles_it_even_when_legacy_is_set(monkeypatch, tmp_path):
    """Naming the root explicitly is the documented way out of the refusal.

    Both directions are legitimate — pinning the old location keeps an
    existing chain in place, so the resolver must not treat the legacy var as
    poison once the operator has actually answered.
    """
    monkeypatch.setenv("HOMESTEAD_HOME", str(tmp_path / "old"))
    monkeypatch.setenv("NESTOR_HOME", str(tmp_path / "old"))
    assert home_paths.home() == tmp_path / "old"

    monkeypatch.setenv("NESTOR_HOME", str(tmp_path / "new"))
    assert home_paths.home() == tmp_path / "new"
