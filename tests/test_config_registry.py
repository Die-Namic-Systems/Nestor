"""The registry — one enumerated place every ``NESTOR_*`` var lives (IDEAS §7.5).

Where ``tests/test_config_precedence.py`` pins the resolver's *mechanism*
(env > file > default, missing vs broken), this file pins the *catalog*: every
name the tree reads is one row in ``nestor.config.REGISTRY``, the secret flag
marks exactly the key-material subset, and secrets stay off the file layer no
matter how the registry is consulted. It also covers a few real call sites
that were migrated onto the resolver, to lock in that the migration changed
*how* a value is read, not *what* it resolves to.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from nestor import config
from nestor.config import ConfigError, Resolver, VarSpec

# --- the catalog: every var this tree reads, once ---------------------------

#: Every NESTOR_* name this task's audit confirmed a call site reads (or, for
#: the two NESTOR_IDB_* entries, a browser-side script names) as of this
#: migration. A name added to the product later belongs here too — this list
#: is meant to be exhaustive, not a lower bound.
EXPECTED_NAMES = {
    "NESTOR_HOME",
    "NESTOR_DB",
    "NESTOR_CORPUS_DIR",
    "NESTOR_LEDGER",
    "NESTOR_LEDGER_VERIFY_INTERVAL_SEC",
    "NESTOR_KEYRING",
    "NESTOR_SEAL_KEY",
    "NESTOR_REQUIRE_SEAL_KEY",
    "NESTOR_GLOSSARY",
    "NESTOR_CACHE_KEY",
    "NESTOR_SEMANTIC_TEST",
    "NESTOR_OLLAMA_EMBED_MODEL",
    "NESTOR_OLLAMA_EMBED_TIMEOUT",
    "NESTOR_FRANK_APP_ID",
    "NESTOR_FRANK_PROJECT",
    "NESTOR_FRANK_STRICT",
    "NESTOR_GATE_ROLLUP",
    "NESTOR_IDB_NAME",
    "NESTOR_IDB_STORE",
    "NESTOR_CONFIG",
}

#: The key-material subset (§7.5's motivating example: the self-grant pin had
#: to rediscover this by scanning nestor/signing.py + nestor/keyring.py).
EXPECTED_SECRETS = {"NESTOR_SEAL_KEY", "NESTOR_CACHE_KEY"}

#: Client-side JS literals in nestor/ui_page.py's IndexedDB script — listed in
#: the registry for completeness, but no Nestor process reads them as env vars.
EXPECTED_NON_CONFIGURABLE = {"NESTOR_IDB_NAME", "NESTOR_IDB_STORE"}


def test_registry_enumerates_every_expected_var():
    assert set(config.REGISTRY) == EXPECTED_NAMES


def test_registry_keys_match_their_own_spec_name():
    """Every entry is keyed by its own `.name` — a copy-paste that keyed one
    spec under a different literal would silently shadow the real name."""
    for key, spec in config.REGISTRY.items():
        assert key == spec.name


def test_every_var_starts_with_the_env_prefix():
    for name in config.REGISTRY:
        assert name.startswith(config.ENV_PREFIX), name


def test_no_unknown_var_sneaks_in():
    """The reverse of the enumeration test, spelled out separately so a typo'd
    addition (`NESTOR_SEA_KEY`) fails here with an unambiguous message instead
    of just failing the set-equality test above."""
    unknown = set(config.REGISTRY) - EXPECTED_NAMES
    assert not unknown, f"registered but not in the expected catalog: {unknown}"


# --- the secret flag ----------------------------------------------------------

def test_secret_flag_marks_exactly_the_key_material_subset():
    secret_in_registry = {v.name for v in config.REGISTRY.values() if v.secret}
    assert secret_in_registry == EXPECTED_SECRETS


def test_secret_names_helper_matches_the_flag():
    """The programmatic seam §7.5 asks for: a caller (the self-grant pin among
    them) imports this instead of grepping nestor/*.py for NESTOR_*KEY."""
    assert set(config.secret_names()) == EXPECTED_SECRETS
    # Sorted and deduplicated — a caller building a denylist should not have
    # to do either itself.
    assert list(config.secret_names()) == sorted(config.secret_names())


def test_non_secret_entries_are_not_flagged():
    for name in EXPECTED_NAMES - EXPECTED_SECRETS:
        assert config.REGISTRY[name].secret is False, name


# --- the configurable flag ----------------------------------------------------

def test_configurable_names_excludes_the_js_literals():
    configurable = set(config.configurable_names())
    assert configurable == EXPECTED_NAMES - EXPECTED_NON_CONFIGURABLE
    for name in EXPECTED_NON_CONFIGURABLE:
        assert name not in configurable


def test_non_configurable_entries_are_flagged():
    for name in EXPECTED_NON_CONFIGURABLE:
        assert config.REGISTRY[name].configurable is False, name


# --- VarSpec shape -------------------------------------------------------------

def test_every_kind_is_one_of_the_typed_accessor_names():
    allowed = {"str", "int", "float", "bool", "path"}
    for spec in config.REGISTRY.values():
        assert spec.kind in allowed, (spec.name, spec.kind)


def test_every_entry_documents_itself():
    for spec in config.REGISTRY.values():
        assert spec.doc.strip(), f"{spec.name} has no doc"


def test_varspec_is_a_plain_frozen_dataclass():
    spec = VarSpec("NESTOR_TEST_ONLY", "str", default="x")
    with pytest.raises(Exception):  # noqa: B017 — any frozen-instance error is fine
        spec.name = "changed"  # type: ignore[misc]


# --- secrets are never surfaced from the config file ---------------------------

def test_get_secret_ignores_a_same_named_file_key(tmp_path: Path, monkeypatch):
    """The refusal at the center of this task: a value in nestor.config.json
    under a secret's name must never leak into get_secret(). Only the
    Resolver's file layer knows about `file_data`; get_secret never receives
    it, which is the enforcement — not a runtime check that could be skipped."""
    monkeypatch.delenv("NESTOR_SEAL_KEY", raising=False)
    p = tmp_path / "nestor.config.json"
    p.write_text(json.dumps({"NESTOR_SEAL_KEY": "leaked-from-file",
                             "seal_key": "also-leaked-from-file"}),
                encoding="utf-8")
    # get_secret's signature does not even accept file_data — demonstrated by
    # calling it exactly as every real call site does, with the file present
    # on disk and NESTOR_CONFIG pointed at it.
    monkeypatch.setenv("NESTOR_CONFIG", str(p))
    assert config.get_secret("NESTOR_SEAL_KEY") is None


def test_get_secret_env_wins_even_with_a_file_present(tmp_path: Path, monkeypatch):
    p = tmp_path / "nestor.config.json"
    p.write_text(json.dumps({"cache_key": "file-value"}), encoding="utf-8")
    monkeypatch.setenv("NESTOR_CONFIG", str(p))
    monkeypatch.setenv("NESTOR_CACHE_KEY", "env-value")
    assert config.get_secret("NESTOR_CACHE_KEY") == "env-value"


def test_a_resolver_built_from_a_file_holding_a_secret_key_cannot_answer_it():
    """Even asking the Resolver directly (not get_secret) for a secret's file
    key returns the file's plain string — proving the refusal lives in *which
    function a secret must be resolved with*, not in the file format hiding
    the value. Call sites for NESTOR_SEAL_KEY / NESTOR_CACHE_KEY only ever call
    get_secret(), never Resolver.get_str(), which is what test_signing.py and
    this file's other cases hold them to."""
    r = Resolver(env={}, file_data={"seal_key": "a-file-value"})
    assert r.get_str("seal_key", "") == "a-file-value"  # the resolver is honest
    # ...but nothing in nestor/signing.py ever asks the resolver for this key;
    # it asks get_secret(), which cannot see file_data at all:
    assert config.get_secret("NESTOR_SEAL_KEY", env={}) is None


# --- adopting a var honors env > file > default ---------------------------------

def test_adopted_var_honors_env_file_default_ladder(tmp_path: Path, monkeypatch):
    """A non-secret var migrated onto the resolver (nestor.glossary's
    NESTOR_GLOSSARY) actually climbs the full ladder end to end."""
    from nestor import glossary

    monkeypatch.delenv("NESTOR_GLOSSARY", raising=False)
    monkeypatch.delenv("NESTOR_CONFIG", raising=False)
    glossary.set_glossary_path(None)

    # 1. neither env nor file: the import-captured cwd default.
    default_path = glossary.glossary_path()
    assert default_path == glossary._DEFAULT_PATH

    # 2. file only: wins over the default.
    cfg = tmp_path / "nestor.config.json"
    from_file = tmp_path / "from-file-glossary.json"
    cfg.write_text(json.dumps({"glossary": str(from_file)}), encoding="utf-8")
    monkeypatch.setenv("NESTOR_CONFIG", str(cfg))
    assert glossary.glossary_path() == from_file.expanduser().resolve()

    # 3. env beats file.
    from_env = tmp_path / "from-env-glossary.json"
    monkeypatch.setenv("NESTOR_GLOSSARY", str(from_env))
    assert glossary.glossary_path() == from_env.expanduser().resolve()

    # 4. an explicit override still wins over everything (unchanged contract).
    pinned = tmp_path / "pinned-glossary.json"
    glossary.set_glossary_path(pinned)
    try:
        assert glossary.glossary_path() == pinned.expanduser().resolve()
    finally:
        glossary.set_glossary_path(None)


def test_ledger_verify_interval_honors_env_file_default_ladder(tmp_path: Path, monkeypatch):
    from nestor import cascade

    monkeypatch.delenv("NESTOR_LEDGER_VERIFY_INTERVAL_SEC", raising=False)
    monkeypatch.delenv("NESTOR_CONFIG", raising=False)
    cascade.set_ledger_verify_interval(None)

    assert cascade.ledger_verify_interval_sec() == 0.0  # default

    cfg = tmp_path / "nestor.config.json"
    cfg.write_text(json.dumps({"ledger_verify_interval_sec": 45}), encoding="utf-8")
    monkeypatch.setenv("NESTOR_CONFIG", str(cfg))
    assert cascade.ledger_verify_interval_sec() == 45.0  # file beats default

    monkeypatch.setenv("NESTOR_LEDGER_VERIFY_INTERVAL_SEC", "120")
    assert cascade.ledger_verify_interval_sec() == 120.0  # env beats file


# --- negative / refusal tests ---------------------------------------------------

def test_malformed_int_raises_configerror_not_a_silent_zero():
    r = Resolver(env={"NESTOR_MAX": "not-a-number"}, file_data={})
    with pytest.raises(ConfigError):
        r.get_int("max", 0)


def test_malformed_ledger_verify_interval_from_env_still_raises(monkeypatch):
    """The adopted call site (nestor.cascade) must keep refusing a bad value —
    under its original exception type, since callers (nestor.ui) still catch
    ValueError specifically and this migration must not turn that into an
    unhandled ConfigError traceback where a clean refusal used to print."""
    from nestor import cascade

    monkeypatch.setenv("NESTOR_LEDGER_VERIFY_INTERVAL_SEC", "five minutes")
    cascade.set_ledger_verify_interval(None)
    with pytest.raises(ValueError, match="NESTOR_LEDGER_VERIFY_INTERVAL_SEC"):
        cascade.ledger_verify_interval_sec()


def test_secret_in_config_file_is_not_surfaced_even_under_the_matching_key(
        tmp_path: Path, monkeypatch):
    """The other negative case: place NESTOR_CACHE_KEY's value in the config
    file under every key name a confused operator might try, and confirm none
    of them reach get_secret()."""
    monkeypatch.delenv("NESTOR_CACHE_KEY", raising=False)
    cfg = tmp_path / "nestor.config.json"
    cfg.write_text(json.dumps({
        "cache_key": "should-not-surface",
        "NESTOR_CACHE_KEY": "should-not-surface-either",
    }), encoding="utf-8")
    monkeypatch.setenv("NESTOR_CONFIG", str(cfg))
    assert config.get_secret("NESTOR_CACHE_KEY") is None


def test_get_bool_loose_unrecognized_token_falls_to_default_not_an_error():
    """The permissive-bool seam (NESTOR_REQUIRE_SEAL_KEY / NESTOR_FRANK_STRICT
    / NESTOR_SEMANTIC_TEST) must keep its pre-resolver behavior: an
    unrecognized token is not a ConfigError, it silently reads as `default` —
    changing that would be a behavior change this migration is not supposed
    to make. Every real call site passes ``default=False``, which is also what
    the original ``... in (\"1\", \"true\", ...)`` membership tests always fell
    back to (blank or garbage alike); `default` is this generalization's own
    contract, exercised here with `default=True` precisely because none of
    the three real sites ever do, so this is the one place it is pinned."""
    assert config.get_bool_loose(
        "NESTOR_FOO_BAR", False, frozenset({"1", "true"}),
        env={"NESTOR_FOO_BAR": "maybe"}) is False
    assert config.get_bool_loose(
        "NESTOR_FOO_BAR", True, frozenset({"1", "true"}),
        env={"NESTOR_FOO_BAR": "garbage"}) is False  # unrecognized, not blank: not `default`
    assert config.get_bool_loose(
        "NESTOR_FOO_BAR", True, frozenset({"1", "true"}),
        env={}) is True  # unset: this is the branch that actually reaches `default`


def test_get_bool_loose_exact_true_tokens_only():
    assert config.get_bool_loose(
        "NESTOR_FOO_BAR", False, frozenset({"1"}), env={"NESTOR_FOO_BAR": "1"}) is True
    assert config.get_bool_loose(
        "NESTOR_FOO_BAR", False, frozenset({"1"}), env={"NESTOR_FOO_BAR": "true"}) is False
