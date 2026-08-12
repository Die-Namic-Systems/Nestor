"""SessionEnd is cleanup-only — it warns and flushes, it never blocks.

These assert the drift warning fires on a mismatch and stays quiet when the store
matches, that the WAL checkpoint is safe with or without a dev store, that the
run never raises, and — the contract as a test — that the wired hook emits nothing
blocking and exits 0. A SessionEnd that tried to block would be a gate nothing
routes through.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import types

from hooks import session_end
from hooks.session_end import run, verify_drift

REPO = pathlib.Path(__file__).resolve().parent.parent


def test_no_drift_warning_when_the_store_matches():
    """On this checkout the committed store matches its files, so no warning."""
    assert verify_drift(REPO) is None


def test_drift_warning_fires_when_verify_fails(monkeypatch):
    """A non-zero --verify (store drifted, or a sealed row) yields the reminder."""
    def fake_run(*_a, **_k):
        return types.SimpleNamespace(returncode=1, stdout="", stderr="")
    monkeypatch.setattr(session_end.subprocess, "run", fake_run)
    warning = verify_drift(REPO)
    assert warning and "dogfood_store.py --rebuild" in warning


def test_checkpoint_is_a_quiet_noop_without_a_dev_store(tmp_path):
    assert session_end.checkpoint(tmp_path) is False


def test_checkpoint_flushes_an_existing_dev_store(tmp_path):
    from nestor.sqlite_store import SqliteStore
    (tmp_path / "data").mkdir()
    db = tmp_path / "data" / "nestor.db"
    s = SqliteStore(str(db))
    s.memory_init()
    s.close()
    assert db.is_file()
    assert session_end.checkpoint(tmp_path) is True   # opens, checkpoints, no raise


def test_run_never_raises_and_reports_the_shape():
    out = run(REPO, {"reason": "logout"})
    assert out["reason"] == "logout"
    assert set(out) == {"reason", "checkpointed", "warnings"}
    assert isinstance(out["warnings"], list)


def test_the_wired_hook_cannot_block_and_exits_zero():
    """The contract, on the wire: SessionEnd emits nothing blocking to stdout and
    exits 0 — warnings, if any, go to stderr."""
    done = subprocess.run(
        [str(REPO / "hooks" / "nestor-hook"), "claude", "session_end"],
        input=json.dumps({"reason": "exit"}), capture_output=True, text=True,
        cwd=REPO, timeout=60, env={**_env(), "NESTOR_PROJECT_ROOT": str(REPO)})
    assert done.returncode == 0, done.stderr
    assert "block" not in done.stdout and "\"decision\"" not in done.stdout
    assert done.stdout.strip() == ""   # SessionEnd has no envelope to emit


def _env() -> dict:
    import os
    return dict(os.environ)


def test_session_end_is_a_known_module_but_not_a_blocking_gate():
    from hooks.hook_runner import MODULES
    assert "session_end" in MODULES
    sys.path.insert(0, str(REPO / "scripts"))
    import hook_guard
    assert "session_end" not in hook_guard.BLOCKING
