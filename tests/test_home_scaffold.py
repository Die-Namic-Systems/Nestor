"""Tests for the idempotent household-home scaffolder (:mod:`nestor.home_init`).

Every path here lands under a pytest ``tmp_path`` with ``$NESTOR_HOME``
pointed at it — the scaffolder never touches a real user home.
"""
from __future__ import annotations

import json

import pytest

from nestor import home_init, home_paths


@pytest.fixture
def home(monkeypatch, tmp_path):
    """A throwaway household root; guarantees nothing writes under the real home."""
    root = tmp_path / ".nestor"
    monkeypatch.setenv("NESTOR_HOME", str(root))
    monkeypatch.delenv("HOMESTEAD_HOME", raising=False)
    return root


def test_fresh_scaffold_creates_expected_structure(home):
    assert not home.exists()

    result = home_init.ensure_home_layout()

    # Every declared subdir exists and is a directory.
    for name in home_init.SUBDIRS:
        assert (home / name).is_dir(), name
    # keep/ is the ledger's parent and agrees with home_paths.
    assert home_paths.keep_dir() == home / "keep"
    # The version marker was written with the expected shape.
    manifest = home / "layout.json"
    assert manifest.is_file()
    assert json.loads(manifest.read_text())["format"] == "nestor_household_v1"
    # The report names exactly what it made this run.
    assert set(result["dirs_created"]) == set(home_init.SUBDIRS)
    assert result["files_created"] == ["layout.json"]
    # The ledger file itself is cascade's to create, not the scaffolder's.
    assert not (home / "keep" / "ledger.jsonl").exists()


def test_running_twice_is_a_clean_noop(home):
    first = home_init.ensure_home_layout()
    assert first["dirs_created"]  # first run did real work

    second = home_init.ensure_home_layout()

    # Idempotent: the second pass created nothing.
    assert second["dirs_created"] == []
    assert second["files_created"] == []
    # But the tree is still fully present.
    for name in home_init.SUBDIRS:
        assert (home / name).is_dir()
    assert (home / "layout.json").is_file()


def test_never_overwrites_an_existing_user_file(home):
    """Refusal/safety: operator content in the tree survives scaffolding untouched."""
    # Operator pre-creates the tree partially, with their own files inside it.
    (home / "record").mkdir(parents=True)
    user_record = home / "record" / "mine.json"
    user_record.write_text('{"owner": "operator", "keep": true}\n', encoding="utf-8")

    # And a hand-authored layout.json the scaffolder must not stomp.
    home.mkdir(parents=True, exist_ok=True)
    (home / "layout.json").write_text('{"format": "operator_custom"}\n', encoding="utf-8")

    result = home_init.ensure_home_layout()

    # The user's file is byte-for-byte preserved.
    assert user_record.read_text() == '{"owner": "operator", "keep": true}\n'
    # The pre-existing layout.json is preserved, NOT reset to the default.
    assert json.loads((home / "layout.json").read_text())["format"] == "operator_custom"
    assert "layout.json" not in result["files_created"]
    # record/ already existed, so it is not reported as newly created.
    assert "record" not in result["dirs_created"]
    # The still-missing siblings were filled in.
    assert (home / "keep").is_dir()
    assert (home / "drafts").is_dir()


def test_explicit_home_argument_is_honored(monkeypatch, tmp_path):
    """Passing ``home=`` pins the root and keeps home_paths in agreement."""
    monkeypatch.delenv("NESTOR_HOME", raising=False)
    monkeypatch.delenv("HOMESTEAD_HOME", raising=False)
    root = tmp_path / "explicit"

    result = home_init.ensure_home_layout(home=root)

    assert result["home"] == str(root)
    assert (root / "keep").is_dir()
    # home_paths now resolves to the same place (the where is reused).
    assert home_paths.ledger_path() == root / "keep" / "ledger.jsonl"


def test_required_dirs_lead_with_keep_from_home_paths(home):
    dirs = home_init.required_dirs()
    assert dirs[0] == home_paths.keep_dir()
    assert {d.name for d in dirs} == set(home_init.SUBDIRS)
