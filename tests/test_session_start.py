"""The SessionStart seat context — what a fresh agent is handed at boot.

Four sections (seat, checks, brain), each guarded so a broken one degrades to a
status line rather than replacing the whole boot with a traceback. The tests
assert the shape an agent depends on and the fail-open posture that keeps a bad
section from taking the session down.
"""
from __future__ import annotations

import json
import pathlib
import subprocess

from hooks import session_start
from hooks.session_start import build_context

REPO = pathlib.Path(__file__).resolve().parent.parent


def test_seat_and_checks_are_always_present():
    ctx = build_context(REPO)
    assert "[NESTOR REPO — LOCAL-FIRST SEAT]" in ctx
    assert "[check] pytest:" in ctx


def test_the_brain_is_stood_up_with_the_query_command():
    """The point of the change: a fresh agent boots knowing the brain is live and
    how to ask it. The count and the consult command are the load-bearing lines."""
    ctx = build_context(REPO)
    assert "[brain] decision store up:" in ctx
    assert "decision check" in ctx
    # The exact-wording caveat must ride along — the blind spot is stated, not hidden.
    assert "re-worded proposal below the bar" in ctx


def test_a_missing_store_asks_the_user_not_crashes(tmp_path):
    """No committed store (a cold checkout that never rebuilt): the if/then asks
    the user whether to stand one up rather than acting — and does not raise,
    because the brain is optional context, not a boot precondition."""
    seat = tmp_path / "hooks"
    seat.mkdir()
    (seat / "seat.md").write_text("[seat]", encoding="utf-8")
    ctx = build_context(tmp_path)
    assert "no decision store is stood up" in ctx
    assert "Ask the user whether to stand one up" in ctx
    assert "dogfood_store.py --rebuild" in ctx


def test_an_empty_store_asks_the_user(tmp_path):
    """Installed but a store with no rows is 'not stood up' too — same ask, not a
    false 'up' on an empty brain."""
    from nestor.sqlite_store import SqliteStore
    (tmp_path / "hooks").mkdir()
    (tmp_path / "hooks" / "seat.md").write_text("[seat]", encoding="utf-8")
    db = tmp_path / "docs" / "dogfood" / "nestor.db"
    db.parent.mkdir(parents=True)
    SqliteStore(str(db)).memory_init()  # a real, empty store
    ctx = build_context(tmp_path)
    assert "its decision store is empty" in ctx
    assert "Ask the user whether to stand one up" in ctx


def test_up_and_stood_up_does_not_ask(tmp_path):
    """The do-nothing branch: with the real committed store present, the section
    hands it over and asks nothing — no stand-up prompt when there is no choice."""
    ctx = build_context(REPO)
    assert "Ask the user whether to stand one up" not in ctx
    assert "[brain] decision store up:" in ctx


def test_a_broken_section_degrades_to_a_line(monkeypatch):
    """The fail-open contract: a section helper that raises becomes one status
    line, and the sections around it still land. A boot hook that could crash on
    its own bug is the failure this guard exists to refuse."""
    def boom(_root):
        raise RuntimeError("simulated section failure")
    monkeypatch.setattr(session_start, "_brain_section", boom)
    ctx = build_context(REPO)
    assert "[check] brain: unavailable (RuntimeError" in ctx
    assert "[NESTOR REPO — LOCAL-FIRST SEAT]" in ctx  # neighbors survive


def test_missing_seat_is_the_one_hard_line(tmp_path):
    ctx = build_context(tmp_path)
    assert ctx == "[NESTOR] Missing hooks/seat.md"


def test_pytest_line_reports_no_venv_without_crashing(tmp_path):
    """A repo tree with no .venv reads as a next step, not an exception."""
    (tmp_path / "hooks").mkdir()
    (tmp_path / "hooks" / "seat.md").write_text("[seat]", encoding="utf-8")
    line = session_start._pytest_line(tmp_path)
    assert "[check] pytest:" in line and "no .venv" in line


def test_session_start_emits_valid_claude_json_end_to_end():
    """Through the real wrapper: SessionStart must emit the envelope Claude Code
    reads (``hookSpecificOutput.additionalContext``), with the brain inside it."""
    done = subprocess.run(
        [str(REPO / "hooks" / "nestor-hook"), "claude", "session_start"],
        capture_output=True, text=True, cwd=REPO, timeout=60,
        env={**_env(), "NESTOR_PROJECT_ROOT": str(REPO)})
    assert done.returncode == 0, done.stderr
    out = json.loads(done.stdout)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "[brain] decision store up:" in ctx


def _env() -> dict:
    import os
    return dict(os.environ)
