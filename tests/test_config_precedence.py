"""Precedence and the missing/broken distinction for :mod:`nestor.config`.

The resolver's whole promise is one total order — env > file > default — plus one
refusal: a malformed or unreadable config file never degrades to the default. It
surfaces as unknown (a raised ``ConfigError``), because "no file" and "broken
file" are different facts and only the first is a legitimate empty layer.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from nestor import config
from nestor.config import ConfigError, Resolver


# --- precedence: env > file > default ---------------------------------------
def test_default_when_neither_env_nor_file():
    r = Resolver(env={}, file_data={})
    assert r.get_str("ledger", "data/ledger.jsonl") == "data/ledger.jsonl"
    assert r.source_of("ledger") == "default"


def test_file_overrides_default():
    r = Resolver(env={}, file_data={"ledger": "keep/ledger.jsonl"})
    assert r.get_str("ledger", "data/ledger.jsonl") == "keep/ledger.jsonl"
    assert r.source_of("ledger") == "file"


def test_env_overrides_file():
    r = Resolver(
        env={"NESTOR_LEDGER": "/env/ledger.jsonl"},
        file_data={"ledger": "keep/ledger.jsonl"},
    )
    assert r.get_str("ledger", "data/ledger.jsonl") == "/env/ledger.jsonl"
    assert r.source_of("ledger") == "env"


def test_env_overrides_default_with_no_file():
    r = Resolver(env={"NESTOR_LEDGER": "/env/ledger.jsonl"}, file_data={})
    assert r.get_str("ledger", "data/ledger.jsonl") == "/env/ledger.jsonl"
    assert r.source_of("ledger") == "env"


def test_full_ladder_one_key():
    # Same key resolved at each rung: default -> file -> env.
    assert Resolver(env={}, file_data={}).get_int("n", 1) == 1
    assert Resolver(env={}, file_data={"n": 2}).get_int("n", 1) == 2
    assert Resolver(env={"NESTOR_N": "3"}, file_data={"n": 2}).get_int("n", 1) == 3


# --- empty env value is transparent, not an override ------------------------
def test_empty_env_string_falls_through_to_file():
    # An exported-but-blank var is not an override; it defers to the file layer.
    r = Resolver(env={"NESTOR_LEDGER": ""}, file_data={"ledger": "keep/l.jsonl"})
    assert r.get_str("ledger", "d") == "keep/l.jsonl"
    assert r.source_of("ledger") == "file"


def test_explicit_env_name_override():
    r = Resolver(env={"WILLOW_APP_ID": "x"}, file_data={})
    assert r.get_str("app_id", "nestor", env="WILLOW_APP_ID") == "x"


# --- typed accessors --------------------------------------------------------
def test_typed_accessors_determinism():
    r = Resolver(
        env={"NESTOR_TIMEOUT": "12.5", "NESTOR_STRICT": "yes", "NESTOR_MAX": "7"},
        file_data={},
    )
    # Deterministic: repeated calls, identical answers.
    for _ in range(3):
        assert r.get_float("timeout", 60.0) == 12.5
        assert r.get_bool("strict", False) is True
        assert r.get_int("max", 0) == 7


def test_bool_from_file_native_and_string():
    assert Resolver(env={}, file_data={"strict": True}).get_bool("strict", False) is True
    assert Resolver(env={}, file_data={"strict": "off"}).get_bool("strict", True) is False


def test_get_path_expands_user():
    r = Resolver(env={"NESTOR_HOME": "~/keep"}, file_data={})
    assert r.get_path("home", "/tmp").is_absolute()
    assert "~" not in str(r.get_path("home", "/tmp"))


# --- casting failures are errors, never silent wrong values -----------------
def test_bad_int_from_env_raises_not_default():
    r = Resolver(env={"NESTOR_MAX": "not-a-number"}, file_data={})
    with pytest.raises(ConfigError):
        r.get_int("max", 5)  # must NOT silently return 5


def test_bad_float_from_file_raises():
    r = Resolver(env={}, file_data={"timeout": "quick"})
    with pytest.raises(ConfigError):
        r.get_float("timeout", 60.0)


def test_unrecognized_bool_raises():
    r = Resolver(env={"NESTOR_STRICT": "maybe"}, file_data={})
    with pytest.raises(ConfigError):
        r.get_bool("strict", False)


def test_bool_is_not_an_int():
    # JSON true must not be read out as an integer 1.
    r = Resolver(env={}, file_data={"n": True})
    with pytest.raises(ConfigError):
        r.get_int("n", 0)


# --- the missing / broken file distinction (the refusal) --------------------
def test_missing_file_is_empty_layer_not_an_error(tmp_path: Path):
    absent = tmp_path / "does-not-exist.json"
    assert config.load_file(absent) == {}  # declared fallback, no raise


def test_none_path_is_empty_layer():
    assert config.load_file(None) == {}


def test_valid_file_layer_roundtrip(tmp_path: Path):
    p = tmp_path / "nestor.config.json"
    p.write_text(json.dumps({"ledger": "keep/l.jsonl", "max": 9}), encoding="utf-8")
    data = config.load_file(p)
    assert data == {"ledger": "keep/l.jsonl", "max": 9}


def test_malformed_json_raises_never_returns_default(tmp_path: Path):
    p = tmp_path / "nestor.config.json"
    p.write_text("{ this is not json ", encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        config.load_file(p)
    # The error must name the file and say broken != empty.
    assert str(p) in str(exc.value)


def test_top_level_non_object_raises(tmp_path: Path):
    p = tmp_path / "nestor.config.json"
    p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(ConfigError):
        config.load_file(p)


def test_unreadable_file_raises_not_empty(tmp_path: Path):
    # A path that exists but is a directory cannot be read as a file: it is
    # unknown, and unknown must raise rather than degrade to {} (which would
    # hand back defaults over a present-but-unreadable override).
    d = tmp_path / "nestor.config.json"
    d.mkdir()
    with pytest.raises(ConfigError):
        config.load_file(d)


def test_load_integration_env_beats_file(tmp_path: Path, monkeypatch):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({"ledger": "from-file"}), encoding="utf-8")
    monkeypatch.setenv("NESTOR_LEDGER", "from-env")
    r = config.load(env={"NESTOR_LEDGER": "from-env"}, path=p)
    assert r.get_str("ledger", "from-default") == "from-env"
    # And file still beats default when env is absent.
    r2 = config.load(env={}, path=p)
    assert r2.get_str("ledger", "from-default") == "from-file"


def test_load_missing_file_uses_default(tmp_path: Path):
    r = config.load(env={}, path=tmp_path / "nope.json")
    assert r.get_str("ledger", "from-default") == "from-default"


def test_load_malformed_file_raises(tmp_path: Path):
    p = tmp_path / "cfg.json"
    p.write_text("nonsense{", encoding="utf-8")
    with pytest.raises(ConfigError):
        config.load(env={}, path=p)


# --- secrets seam: env-only, blank is None ----------------------------------
def test_get_secret_env_only():
    assert config.get_secret("NESTOR_SEAL_KEY", env={"NESTOR_SEAL_KEY": "s3cr3t"}) == "s3cr3t"
    assert config.get_secret("NESTOR_SEAL_KEY", env={}) is None
    assert config.get_secret("NESTOR_SEAL_KEY", env={"NESTOR_SEAL_KEY": "  "}) is None


def test_default_config_path_respects_env(monkeypatch):
    monkeypatch.setenv("NESTOR_CONFIG", "/custom/place.json")
    assert config.default_config_path() == Path("/custom/place.json")
    monkeypatch.delenv("NESTOR_CONFIG", raising=False)
    assert config.default_config_path().name == config.DEFAULT_CONFIG_FILENAME
