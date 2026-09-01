"""Operator helpers for §6.123 git seal files."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

from nestor import keyring, memory
from nestor.sqlite_store import SqliteStore

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "dogfood_seal_export.py"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, cwd=str(ROOT),
                          check=False)


def _fixture_db(tmp_path, monkeypatch):
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    sys.path.insert(0, str(ROOT / "scripts"))
    import dogfood_common
    import dogfood_store

    from nestor import signing

    decisions = tmp_path / "decisions"
    seals = tmp_path / "seals"
    decisions.mkdir()
    seals.mkdir()
    (decisions / "0999-export-fixture.json").write_text(json.dumps({
        "pr": "fixture",
        "date": "2026-08-27",
        "decisions": [
            {
                "question": "First export fixture question?",
                "commitment": "Yes.",
                "why": "one",
            },
            {
                "question": "Second export fixture question?",
                "commitment": "Also yes.",
                "why": "two",
            },
        ],
    }, indent=2) + "\n", encoding="utf-8")

    monkeypatch.setattr(dogfood_store, "DECISIONS_DIR", decisions)
    monkeypatch.setattr(dogfood_common, "DECISIONS_DIR", decisions)
    monkeypatch.setattr(dogfood_store, "SEALS_DIR", seals)
    monkeypatch.setattr(dogfood_common, "SEALS_DIR", seals)

    private = Ed25519PrivateKey.generate()
    pub = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    ring = keyring.Keyring()
    ring.add("rita", key=pub, kind="ed25519")
    keyring.set_keyring(ring)

    db = SqliteStore(str(tmp_path / "review.db"))
    db.memory_init()
    dogfood_store.build(db)
    rows = db.memory_list(limit=10)
    for row in rows:
        sig = private.sign(
            signing._message(row["source_norm"], row["target_text"], "rita")).hex()
        memory.add_pair(
            row["source_text"], row["target_text"], "decision", "decision",
            status="sealed", verifier="rita", seal_sig=sig, store=db,
            pair_id=row["id"], created_at=row["created_at"], audit=False)
    keyring.set_keyring(None)
    return db, rows, decisions


def test_list_shows_pair_ids(tmp_path, monkeypatch, capsys):
    db, rows, _decisions = _fixture_db(tmp_path, monkeypatch)
    db_path = tmp_path / "review.db"
    db.close()

    done = _run("--list", "--from-db", str(db_path))
    assert done.returncode == 0, done.stdout + done.stderr
    assert rows[0]["id"] in done.stdout
    assert "sealed" in done.stdout


def test_export_by_decision_stem(tmp_path, monkeypatch):
    db, rows, decisions = _fixture_db(tmp_path, monkeypatch)
    db_path = tmp_path / "review.db"
    out_dir = tmp_path / "seals"
    db.close()

    done = _run("--decision", "0999", "--from-db", str(db_path),
                "--out-dir", str(out_dir), "--decisions-dir", str(decisions))
    assert done.returncode == 0, done.stdout + done.stderr
    assert (out_dir / f"{rows[0]['id']}.json").is_file()
    assert (out_dir / f"{rows[1]['id']}.json").is_file()


def test_export_by_decision_index(tmp_path, monkeypatch):
    db, rows, decisions = _fixture_db(tmp_path, monkeypatch)
    db_path = tmp_path / "review.db"
    out_dir = tmp_path / "seals"
    db.close()

    done = _run("--decision", "0999#1", "--from-db", str(db_path),
                "--out-dir", str(out_dir), "--decisions-dir", str(decisions))
    assert done.returncode == 0, done.stdout + done.stderr
    assert (out_dir / f"{rows[1]['id']}.json").is_file()
    assert not (out_dir / f"{rows[0]['id']}.json").exists()


def test_export_by_question_substring(tmp_path, monkeypatch):
    db, rows, _decisions = _fixture_db(tmp_path, monkeypatch)
    db_path = tmp_path / "review.db"
    out_dir = tmp_path / "seals"
    db.close()

    done = _run("--question", "Second export", "--from-db", str(db_path),
                "--out-dir", str(out_dir))
    assert done.returncode == 0, done.stdout + done.stderr
    assert (out_dir / f"{rows[1]['id']}.json").is_file()


def test_export_all_writes_every_sealed_row(tmp_path, monkeypatch):
    db, rows, _decisions = _fixture_db(tmp_path, monkeypatch)
    db_path = tmp_path / "review.db"
    out_dir = tmp_path / "seals"
    db.close()

    done = _run("--all", "--from-db", str(db_path), "--out-dir", str(out_dir))
    assert done.returncode == 0, done.stdout + done.stderr
    assert len(list(out_dir.glob("*.json"))) == len(rows)


def test_ambiguous_question_refuses(tmp_path, monkeypatch):
    db, _rows, _decisions = _fixture_db(tmp_path, monkeypatch)
    db_path = tmp_path / "review.db"
    db.close()

    done = _run("--question", "fixture", "--from-db", str(db_path))
    assert done.returncode != 0
    assert "matches" in done.stderr
