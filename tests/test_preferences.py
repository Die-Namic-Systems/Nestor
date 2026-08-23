"""Tests for the user-preferences module (nestor/preferences.py).

The preference store is a JSON file under NESTOR_HOME, not a SQLite table.
These tests use an isolated tmp directory as the home so nothing touches
the real ``~/.nestor``.
"""
from __future__ import annotations

import json
import subprocess
import sys

import pytest

from nestor import preferences


@pytest.fixture()
def home(tmp_path):
    """An isolated preferences home — no bleed into the real household."""
    return tmp_path


# -- load / save / round-trip ------------------------------------------------

def test_load_returns_empty_dict_when_file_is_absent(home):
    assert preferences.load(home) == {}


def test_save_creates_the_file_and_load_reads_it_back(home):
    preferences.save({"ui.theme": "dark"}, user="test@example.com", home=home)
    assert preferences.load(home) == {"ui.theme": "dark"}


def test_save_is_atomic_the_envelope_is_well_formed(home):
    preferences.save({"cli.color": False}, user="rudi@test.com", home=home)
    raw = json.loads((home / "preferences.json").read_text())
    assert raw["nestor_preferences"] == 1
    assert raw["user"] == "rudi@test.com"
    assert raw["preferences"] == {"cli.color": False}
    assert "updated_at" in raw


def test_save_preserves_user_from_existing_file(home):
    preferences.save({"a": 1}, user="first@test.com", home=home)
    preferences.save({"a": 2}, home=home)
    raw = json.loads((home / "preferences.json").read_text())
    assert raw["user"] == "first@test.com"


# -- get / set / clear -------------------------------------------------------

def test_get_returns_default_for_known_key_when_not_set(home):
    assert preferences.get("ui.theme", home=home) == "system"


def test_get_returns_explicit_default_for_unknown_key(home):
    assert preferences.get("unknown.key", "fallback", home=home) == "fallback"


def test_set_and_get_round_trip(home):
    preferences.set_pref("ui.theme", "dark", home=home)
    assert preferences.get("ui.theme", home=home) == "dark"


def test_set_coerces_bool_from_string(home):
    preferences.set_pref("cli.color", "false", home=home)
    assert preferences.get("cli.color", home=home) is False


def test_set_coerces_int_from_string(home):
    preferences.set_pref("ui.page_size", "50", home=home)
    assert preferences.get("ui.page_size", home=home) == 50


def test_set_validates_choices(home):
    with pytest.raises(preferences.PreferencesError, match="must be one of"):
        preferences.set_pref("ui.theme", "neon", home=home)


def test_set_validates_bool_type(home):
    with pytest.raises(preferences.PreferencesError, match="expected bool"):
        preferences.set_pref("cli.color", "maybe", home=home)


def test_set_validates_int_type(home):
    with pytest.raises(preferences.PreferencesError, match="expected int"):
        preferences.set_pref("ui.page_size", "abc", home=home)


def test_clear_removes_one_key(home):
    preferences.set_pref("ui.theme", "dark", home=home)
    assert preferences.clear("ui.theme", home=home) is True
    assert preferences.get("ui.theme", home=home) == "system"


def test_clear_returns_false_when_key_was_not_set(home):
    assert preferences.clear("ui.theme", home=home) is False


# -- reset -------------------------------------------------------------------

def test_reset_deletes_the_file(home):
    preferences.save({"a": 1}, home=home)
    assert preferences.reset(home) is True
    assert not (home / "preferences.json").exists()


def test_reset_returns_false_when_no_file(home):
    assert preferences.reset(home) is False


# -- unknown keys are preserved, not stripped --------------------------------

def test_unknown_keys_survive_a_round_trip(home):
    preferences.set_pref("custom.plugin.mode", "turbo", home=home)
    assert preferences.get("custom.plugin.mode", home=home) == "turbo"
    preferences.set_pref("ui.theme", "dark", home=home)
    assert preferences.get("custom.plugin.mode", home=home) == "turbo"


# -- error handling ----------------------------------------------------------

def test_load_raises_on_corrupt_file(home):
    (home / "preferences.json").write_text("not json{{{", encoding="utf-8")
    with pytest.raises(preferences.PreferencesError, match="cannot read"):
        preferences.load(home)


def test_load_raises_on_non_object(home):
    (home / "preferences.json").write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(preferences.PreferencesError, match="not a JSON object"):
        preferences.load(home)


# -- CLI integration ---------------------------------------------------------

def _run_prefs(*cli_args, home):
    cmd = [sys.executable, "-m", "nestor.cli", "--json", "prefs",
           "--home", str(home), *cli_args]
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def test_cli_prefs_list_empty(home):
    r = _run_prefs(home=home)
    assert r.returncode == 0
    assert json.loads(r.stdout)["preferences"] == {}


def test_cli_prefs_set_and_get(home):
    r = _run_prefs("set", "ui.theme", "dark", home=home)
    assert r.returncode == 0
    payload = json.loads(r.stdout)
    assert payload["key"] == "ui.theme"
    assert payload["value"] == "dark"

    r = _run_prefs("get", "ui.theme", home=home)
    assert r.returncode == 0
    assert json.loads(r.stdout)["value"] == "dark"


def test_cli_prefs_clear(home):
    _run_prefs("set", "cli.color", "false", home=home)
    r = _run_prefs("clear", "cli.color", home=home)
    assert r.returncode == 0
    assert json.loads(r.stdout)["existed"] is True


def test_cli_prefs_reset(home):
    _run_prefs("set", "ui.theme", "dark", home=home)
    r = _run_prefs("reset", home=home)
    assert r.returncode == 0
    assert json.loads(r.stdout)["existed"] is True


def test_cli_prefs_list_shows_set_values(home):
    _run_prefs("set", "ui.theme", "dark", home=home)
    _run_prefs("set", "cli.color", "false", home=home)
    r = _run_prefs(home=home)
    assert r.returncode == 0
    payload = json.loads(r.stdout)
    assert payload["preferences"]["ui.theme"] == "dark"
    assert payload["preferences"]["cli.color"] is False


# -- MCP integration (nestor_prefs tool) -------------------------------------

def test_mcp_prefs_returns_all(home, monkeypatch):
    monkeypatch.setenv("NESTOR_HOME", str(home))
    preferences.save({"ui.theme": "dark", "cli.color": False}, home=home)
    from nestor.serve import Server
    from nestor.sqlite_store import SqliteStore
    store = SqliteStore(":memory:")
    store.init_db(); store.memory_init()
    server = Server(store=store, source_lang="en", target_lang="es")
    result = server.call("nestor_prefs", {})
    assert result["preferences"]["ui.theme"] == "dark"


def test_mcp_prefs_returns_one_key(home, monkeypatch):
    monkeypatch.setenv("NESTOR_HOME", str(home))
    preferences.save({"ui.theme": "dark"}, home=home)
    from nestor.serve import Server
    from nestor.sqlite_store import SqliteStore
    store = SqliteStore(":memory:")
    store.init_db(); store.memory_init()
    server = Server(store=store, source_lang="en", target_lang="es")
    result = server.call("nestor_prefs", {"key": "ui.theme"})
    assert result["value"] == "dark"


# -- the preference store never seals anything --------------------------------

class TestNeverSeals:
    """Structural guard: the preferences module must not touch the seal trail."""

    def test_no_verifier_parameter(self):
        import inspect
        for name in ("load", "save", "get", "set_pref", "clear", "reset"):
            sig = inspect.signature(getattr(preferences, name))
            assert "verifier" not in sig.parameters, \
                f"preferences.{name} must not accept a verifier= parameter"

    def test_no_status_parameter(self):
        import inspect
        for name in ("load", "save", "get", "set_pref", "clear", "reset"):
            sig = inspect.signature(getattr(preferences, name))
            assert "status" not in sig.parameters, \
                f"preferences.{name} must not accept a status= parameter"

    def test_module_does_not_import_seal_machinery(self):
        import inspect
        source = inspect.getsource(preferences)
        for forbidden in ("signing", "seal_sig", "cascade", "ledger"):
            assert f"import {forbidden}" not in source and \
                   f"from . import {forbidden}" not in source, \
                f"preferences.py must not import {forbidden}"
