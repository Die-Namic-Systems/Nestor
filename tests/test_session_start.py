"""The SessionStart seat context — what a fresh agent is handed at boot.

Five sections (seat, pytest, lint, nestor, brain), each guarded so a broken one
degrades to a status line rather than replacing the whole boot with a traceback.
The tests assert the shape an agent depends on and the fail-open posture that
keeps a bad section from taking the session down.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess

import pytest

from hooks import session_start
from hooks.session_start import build_context

REPO = pathlib.Path(__file__).resolve().parent.parent


def test_seat_and_checks_are_always_present():
    ctx = build_context(REPO)
    assert "[NESTOR REPO — LOCAL-FIRST SEAT]" in ctx
    assert "[check] pytest:" in ctx
    assert "[check] lint:" in ctx
    assert "[nestor]" in ctx


def test_the_boot_check_covers_every_gate_ci_lint_runs():
    """The drift guard, and the reason the detect-secrets break survived.

    ``scripts/ci-lint.sh`` is the command the seat, AGENTS.md and the agent guide
    all name as the pre-push gate. A boot check that probes a *subset* of what it
    runs reports a readiness the agent's command does not share — so the set is
    read back out of the script rather than trusted to stay in sync by hand. Add
    a fourth gate to ci-lint.sh and this fails until the boot check knows it."""
    script = (REPO / "scripts" / "ci-lint.sh").read_text(encoding="utf-8")
    run = {m.split(".")[0] for m in re.findall(r"python -m ([\w.]+)", script)}
    assert run == set(session_start.LINT_MODULES), (
        f"ci-lint.sh runs {sorted(run)}; the boot check probes "
        f"{sorted(session_start.LINT_MODULES)}")


def test_the_lint_line_names_every_gate_when_the_venv_is_ready():
    line = session_start._lint_line(REPO)
    assert line.startswith("[check] lint:")
    for mod in session_start.LINT_MODULES:
        assert mod in line


def test_the_lint_line_goes_red_on_a_missing_gate(monkeypatch):
    """Shown to fail before it is trusted — decision 0101's own rule, applied to
    the check that would have caught 0101's omission.

    A readiness line that cannot report *un*ready is a ledger, not a gate: it was
    the silently-absent third gate that let ``bash scripts/ci-lint.sh`` boot green
    and die at push. The line must name the missing module and the one command
    that fixes it."""
    monkeypatch.setattr(
        session_start, "LINT_MODULES", ("ruff", "nestor_no_such_lint_module"))
    line = session_start._lint_line(REPO)
    assert "MISSING nestor_no_such_lint_module" in line
    assert "ruff" not in line.split("—")[0]  # the installed one is not accused
    assert "pip install -e '.[dev]'" in line


def test_a_broken_lint_probe_degrades_to_a_line(monkeypatch):
    """Same fail-open contract as every other section: the boot survives it."""
    def boom(_root):
        raise RuntimeError("simulated probe failure")
    monkeypatch.setattr(session_start, "_lint_line", boom)
    ctx = build_context(REPO)
    assert "[check] lint: unavailable (RuntimeError" in ctx
    assert "[brain] decision store up:" in ctx  # neighbors survive


@pytest.fixture
def bare_tree(tmp_path, monkeypatch):
    """A repo-shaped tree with a seat and no Nestor, and no household env."""
    (tmp_path / "hooks").mkdir()
    (tmp_path / "hooks" / "seat.md").write_text("[seat]", encoding="utf-8")
    monkeypatch.delenv("HOMESTEAD_HOME", raising=False)
    return tmp_path


def test_the_boot_asks_when_no_nestor_is_stood_up(bare_tree):
    """The check that was missing. `_brain_section` asks this of the decision
    store, which is committed and so always there — the ask could never fire —
    and nothing asked it about a Nestor at all."""
    line = session_start._nestor_section(bare_tree)
    assert line.startswith("[nestor]")
    assert "no Nestor is stood up in this tree" in line
    assert "Ask the user whether to stand one up" in line
    assert "nestor demo" in line


def test_a_stood_up_nestor_is_reported_and_nothing_is_asked(bare_tree):
    """The skip branch: present means one line saying where, and no prompt —
    there is no choice to put to the user when the thing already exists."""
    subprocess.run(["nestor", "--db", str(bare_tree / "data" / "nestor.db"), "demo"],
                   capture_output=True, check=True, timeout=120)
    line = session_start._nestor_section(bare_tree)
    assert "stood up: data/nestor.db" in line
    assert "pair(s)" in line
    assert "Ask the user" not in line


def test_the_nestor_check_stands_nothing_up(bare_tree):
    """The invariant, and the reason this check has to run at boot.

    `nestor stats` on a tree with no store does not say "no Nestor" — it creates
    `data/nestor.db` and prints `0 pair(s)`, so an absent Nestor and an empty one
    are indistinguishable the moment anything runs. A probe that answered the
    question by touching the path would destroy the answer and then report it.
    The forbidden act, asserted to be refused: nothing on disk moves."""
    before = {p for p in bare_tree.rglob("*")}
    session_start._nestor_section(bare_tree)
    assert {p for p in bare_tree.rglob("*")} == before
    assert not (bare_tree / "data").exists(), "the probe stood a Nestor up"


def test_a_household_seat_is_asked_about_on_its_own_terms(bare_tree, monkeypatch):
    """$HOMESTEAD_HOME set is a different seat with a different fix: the ask must
    name home_init and the household tree, not `nestor demo`."""
    hh = bare_tree / "household"
    monkeypatch.setenv("HOMESTEAD_HOME", str(hh))
    line = session_start._nestor_section(bare_tree)
    assert "no Nestor is stood up there" in line
    assert "python -m nestor.home_init" in line
    assert "nestor demo" not in line
    assert not hh.exists(), "the probe scaffolded a household home"

    from nestor import home_init
    home_init.ensure_home_layout(hh)
    after = session_start._nestor_section(bare_tree)
    assert "household home stood up" in after
    assert "Ask the user" not in after


def test_the_probe_opens_the_path_the_cli_opens(bare_tree):
    """Drift guard. A boot check that probed a different store from the one the
    agent's next `nestor` command opens would report on a store nobody uses —
    the divergence `_venv_python` already exists to prevent for the interpreter."""
    from nestor.cli import build_parser
    assert session_start._cli_default_db(bare_tree) == bare_tree / build_parser().get_default("db")


def test_an_unreadable_store_is_a_note_not_a_crash(bare_tree):
    """`_store_summary` is a nicety; a corrupt file must not take the boot down."""
    db = bare_tree / "data" / "nestor.db"
    db.parent.mkdir()
    db.write_text("not a sqlite file", encoding="utf-8")
    line = session_start._nestor_section(bare_tree)
    assert "stood up: data/nestor.db" in line and "unreadable" in line


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
    hands it over and asks nothing — no stand-up prompt when there is no choice.

    Scoped to `_brain_section` rather than the whole context, which is what the
    sentence above always meant. It read the joined boot text while only one
    section could ask, so the two were the same assertion; adding `[nestor]` —
    which asks legitimately, this tree having no `data/nestor.db` — separated
    them and showed the test had been checking a neighbour's business."""
    section = session_start._brain_section(REPO)
    assert "Ask the user whether to stand one up" not in section
    assert "[brain] decision store up:" in section


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
