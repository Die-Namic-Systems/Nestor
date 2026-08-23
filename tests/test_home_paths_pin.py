"""The corpus pin: honoured, and refused rather than fallen back from.

Pins the failure that made this necessary — the willow fleet exported
$NESTOR_DB for weeks while no code in this package had heard of the variable,
so `nestor stats` from a directory without data/ reported "0 pairs, no ledger
yet" against a store holding eleven sealed rows and an intact chain. An empty
corpus and a wrong location printed the same words.
"""
from __future__ import annotations

import pytest

from nestor import home_paths

# --- honoured -------------------------------------------------------------

def test_nestor_db_is_honoured(tmp_path, monkeypatch):
    db = tmp_path / "corpus.db"
    db.touch()
    monkeypatch.setenv("NESTOR_DB", str(db))
    assert home_paths.db_path() == db


def test_nestor_home_supplies_a_keep_tree(tmp_path, monkeypatch):
    monkeypatch.delenv("NESTOR_DB", raising=False)
    monkeypatch.setenv("NESTOR_HOME", str(tmp_path))
    assert home_paths.db_path() == tmp_path / "keep" / "nestor.db"


def test_nestor_db_wins_over_nestor_home(tmp_path, monkeypatch):
    db = tmp_path / "explicit.db"
    db.touch()
    monkeypatch.setenv("NESTOR_DB", str(db))
    monkeypatch.setenv("NESTOR_HOME", str(tmp_path / "elsewhere"))
    assert home_paths.db_path() == db


def test_no_pin_returns_none_rather_than_inventing_one(monkeypatch):
    """None means 'caller keeps its own default'. It must not guess a path."""
    monkeypatch.delenv("NESTOR_DB", raising=False)
    monkeypatch.delenv("NESTOR_HOME", raising=False)
    assert home_paths.db_path() is None


# --- refused --------------------------------------------------------------

def test_a_pin_naming_a_directory_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("NESTOR_DB", str(tmp_path))
    with pytest.raises(home_paths.PinRefused):
        home_paths.db_path()


def test_a_pin_with_no_parent_directory_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("NESTOR_DB", str(tmp_path / "nope" / "gone" / "x.db"))
    with pytest.raises(home_paths.PinRefused):
        home_paths.db_path()


def test_refusal_names_the_variable_and_the_remedy(tmp_path, monkeypatch):
    """A refusal the operator has to decode is worth less than one they read."""
    monkeypatch.setenv("NESTOR_DB", str(tmp_path))
    with pytest.raises(home_paths.PinRefused) as e:
        home_paths.db_path()
    msg = str(e.value)
    assert "NESTOR_DB" in msg
    assert str(tmp_path) in msg


# --- the chain follows the corpus ----------------------------------------

def test_ledger_follows_the_db_when_the_suffixed_file_exists(tmp_path, monkeypatch):
    monkeypatch.delenv("NESTOR_LEDGER", raising=False)
    db = tmp_path / "nestor.db"
    db.touch()
    chain = tmp_path / "nestor.db.ledger.jsonl"   # what the fleet has on disk
    chain.touch()
    assert home_paths.ledger_for(db) == chain


def test_ledger_finds_the_checkpoint_spelling_too(tmp_path, monkeypatch):
    monkeypatch.delenv("NESTOR_LEDGER", raising=False)
    db = tmp_path / "nestor.db"
    db.touch()
    chain = tmp_path / "nestor.ledger.jsonl"      # what `db checkpoint` writes
    chain.touch()
    assert home_paths.ledger_for(db) == chain


def test_ledger_env_wins(tmp_path, monkeypatch):
    db = tmp_path / "nestor.db"
    db.touch()
    (tmp_path / "nestor.db.ledger.jsonl").touch()
    monkeypatch.setenv("NESTOR_LEDGER", str(tmp_path / "chosen.jsonl"))
    assert home_paths.ledger_for(db) == tmp_path / "chosen.jsonl"


def test_ledger_names_what_would_be_created_when_neither_exists(tmp_path, monkeypatch):
    monkeypatch.delenv("NESTOR_LEDGER", raising=False)
    db = tmp_path / "nestor.db"
    assert home_paths.ledger_for(db) == tmp_path / "nestor.db.ledger.jsonl"
