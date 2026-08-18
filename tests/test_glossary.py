"""Tests for glossary term locks and the word-boundary matching fix (IDEAS §6.38)."""
from __future__ import annotations

import json

from nestor import glossary


def test_add_and_retrieve_term(tmp_path, monkeypatch):
    monkeypatch.setattr(glossary, "_OVERRIDE", tmp_path / "glossary.json")
    glossary.add_term("house", "Haus", "en", "de")
    terms = glossary.terms_for("en", "de")
    assert terms["house"] == "Haus"


def test_terms_for_empty_when_no_glossary(tmp_path, monkeypatch):
    monkeypatch.setattr(glossary, "_OVERRIDE", tmp_path / "nonexistent.json")
    assert glossary.terms_for("en", "de") == {}


def test_locks_in_text_finds_matching_term(tmp_path, monkeypatch):
    monkeypatch.setattr(glossary, "_OVERRIDE", tmp_path / "glossary.json")
    glossary.add_term("house", "Haus", "en", "de")
    result = glossary.locks_in_text("the house is big", "en", "de")
    assert result == {"house": "Haus"}


def test_locks_in_text_no_match(tmp_path, monkeypatch):
    monkeypatch.setattr(glossary, "_OVERRIDE", tmp_path / "glossary.json")
    glossary.add_term("house", "Haus", "en", "de")
    result = glossary.locks_in_text("the car is red", "en", "de")
    assert result == {}


def test_locks_in_text_case_insensitive(tmp_path, monkeypatch):
    monkeypatch.setattr(glossary, "_OVERRIDE", tmp_path / "glossary.json")
    glossary.add_term("House", "Haus", "en", "de")
    result = glossary.locks_in_text("the HOUSE is big", "en", "de")
    assert result == {"House": "Haus"}


def test_locks_in_text_word_boundary_prevents_substring_match(tmp_path, monkeypatch):
    """IDEAS §6.38: a short term like 'lock' must not fire inside 'blockchain'."""
    monkeypatch.setattr(glossary, "_OVERRIDE", tmp_path / "glossary.json")
    glossary.add_term("lock", "Schloss", "en", "de")
    assert glossary.locks_in_text("the lock is broken", "en", "de") == {"lock": "Schloss"}
    assert glossary.locks_in_text("blockchain technology", "en", "de") == {}
    assert glossary.locks_in_text("locksmith at work", "en", "de") == {}
    assert glossary.locks_in_text("a padlock", "en", "de") == {}


def test_locks_in_text_multi_word_term(tmp_path, monkeypatch):
    monkeypatch.setattr(glossary, "_OVERRIDE", tmp_path / "glossary.json")
    glossary.add_term("ice cream", "Eis", "en", "de")
    assert glossary.locks_in_text("I like ice cream a lot", "en", "de") == {"ice cream": "Eis"}
    assert glossary.locks_in_text("no match here", "en", "de") == {}


def test_locks_in_text_term_at_boundaries(tmp_path, monkeypatch):
    monkeypatch.setattr(glossary, "_OVERRIDE", tmp_path / "glossary.json")
    glossary.add_term("cat", "Katze", "en", "de")
    assert glossary.locks_in_text("cat", "en", "de") == {"cat": "Katze"}
    assert glossary.locks_in_text("cat.", "en", "de") == {"cat": "Katze"}
    assert glossary.locks_in_text("the cat!", "en", "de") == {"cat": "Katze"}
    assert glossary.locks_in_text("concatenate", "en", "de") == {}
    assert glossary.locks_in_text("bobcat", "en", "de") == {}


def test_language_pair_isolation(tmp_path, monkeypatch):
    monkeypatch.setattr(glossary, "_OVERRIDE", tmp_path / "glossary.json")
    glossary.add_term("house", "Haus", "en", "de")
    glossary.add_term("house", "maison", "en", "fr")
    assert glossary.terms_for("en", "de") == {"house": "Haus"}
    assert glossary.terms_for("en", "fr") == {"house": "maison"}
    assert glossary.terms_for("de", "en") == {}


def test_multiple_terms_in_same_text(tmp_path, monkeypatch):
    monkeypatch.setattr(glossary, "_OVERRIDE", tmp_path / "glossary.json")
    glossary.add_term("red", "rot", "en", "de")
    glossary.add_term("car", "Auto", "en", "de")
    result = glossary.locks_in_text("the red car", "en", "de")
    assert result == {"red": "rot", "car": "Auto"}


def test_glossary_path_override(tmp_path, monkeypatch):
    custom = tmp_path / "custom.json"
    monkeypatch.setattr(glossary, "_OVERRIDE", custom)
    assert glossary.glossary_path() == custom


def test_save_creates_parent_dirs(tmp_path, monkeypatch):
    nested = tmp_path / "deep" / "nested" / "glossary.json"
    monkeypatch.setattr(glossary, "_OVERRIDE", nested)
    glossary.add_term("test", "Test", "en", "de")
    assert nested.exists()
    data = json.loads(nested.read_text())
    assert "en->de" in data
