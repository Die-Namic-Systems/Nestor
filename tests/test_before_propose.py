"""before_propose is the cross-session collision guard (#111, IDEAS §7.5) — the
sibling of before_build (#105): where that one reads the past (what already
exists), this one reads the concurrent present (who else is building right
now). It fires on a propose/mint/open-a-PR prompt and stays silent on
everything else, and it never blocks.

Two things are pinned, each because the guard would be worse than absent if it
got them backwards:

* **Both directions of intent.** A detector that always fired would be noise
  every turn; one that never fired would be the collision it exists to catch.
* **Fail CLOSED into silence, safely.** A scan that cannot determine collision
  state (no resolvable base, not a git repo) must say so — UNKNOWN, not
  "clear" — never fold a failure into false reassurance. This is the guard's
  own explicit design constraint (see `hooks/before_propose.py`'s docstring,
  and decision `0127`, "the read-only probe that wasn't").

The git-scan tests build small throwaway repos under `tmp_path` — never the
real checkout's history — with a `master` and a `sibling` branch, so the
collision, in-flight-elsewhere, derived-file, and clean cases are each
reproduced rather than described.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess

import hooks.before_propose as bp
from hooks.before_propose import advisory, for_prompt, is_collision_intent, scan

REPO = pathlib.Path(__file__).resolve().parent.parent


# --- intent detection --------------------------------------------------------

def test_fires_on_propose_mint_and_open_pr_prompts():
    for prompt in ("mint the next decision number",
                   "let's propose a decision about the seal bar",
                   "record a decision here",
                   "add a decision for this",
                   "open a PR",
                   "create a pull request",
                   "let's raise a PR for this",
                   "submit a pull request",
                   "rebuild the dogfood store",
                   "run dogfood_store.py --rebuild"):
        assert is_collision_intent(prompt), prompt


def test_silent_on_unrelated_prompts():
    for prompt in ("what's the status of the seal?",
                   "seal it",
                   "seal the oldest decision",
                   "why did that test fail?",
                   "write it down in IDEAS",
                   "let's decide on lunch",
                   "build a new hook for X",
                   ""):
        assert not is_collision_intent(prompt), prompt
        assert for_prompt(prompt, REPO) == "", prompt


# --- git fixtures ------------------------------------------------------------

def _git(cwd: pathlib.Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=test@example.com", "-c", "user.name=Test",
         "-C", str(cwd), *args],
        check=True, capture_output=True, text=True, timeout=30)


def _repo_with_sibling(tmp_path: pathlib.Path, sibling_files: dict[str, str],
                       base_branch: str = "master") -> pathlib.Path:
    """A throwaway repo: `base_branch` holds one decision file (0001), a
    `sibling` branch diverges from it and adds `sibling_files`, and HEAD ends
    back on `base_branch` — so `scan()` sees exactly what a real checkout
    would: this branch's own tree, and one sibling branch's commits it does
    not have."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", base_branch)
    ddir = repo / "docs" / "dogfood" / "decisions"
    ddir.mkdir(parents=True)
    (ddir / "0001-first.json").write_text('{"decisions": []}', encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "initial")
    _git(repo, "branch", "sibling")
    _git(repo, "checkout", "sibling")
    for rel, content in sibling_files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "sibling work")
    _git(repo, "checkout", base_branch)
    return repo


# --- the scan: collision cases -----------------------------------------------

def test_collision_on_the_next_number(tmp_path):
    """The worked instance, reproduced: this branch's next number (0002) is
    exactly what the sibling branch already committed."""
    repo = _repo_with_sibling(
        tmp_path, {"docs/dogfood/decisions/0002-second.json": "{}"})
    result = scan(repo)
    assert result.ok, result.error
    assert result.next_number == "0002"
    assert result.claimed_numbers.get("0002") == ["sibling"]
    text = advisory(repo)
    assert "COLLISION" in text
    assert "0002" in text and "sibling" in text


def test_in_flight_elsewhere_but_not_colliding(tmp_path):
    """Sibling minted a number ahead of this branch's next one — worth
    surfacing, but it is not the same collision as claiming the *next* one."""
    repo = _repo_with_sibling(
        tmp_path, {"docs/dogfood/decisions/0005-far-ahead.json": "{}"})
    result = scan(repo)
    assert result.ok, result.error
    assert result.next_number == "0002"
    assert result.claimed_numbers.get("0005") == ["sibling"]
    text = advisory(repo)
    assert "COLLISION" not in text
    assert "in flight elsewhere" in text
    assert "0005" in text and "sibling" in text


def test_derived_file_touched_on_a_sibling_branch(tmp_path):
    repo = _repo_with_sibling(
        tmp_path, {"docs/dogfood/nestor.db": "not-a-real-sqlite-file"})
    result = scan(repo)
    assert result.ok, result.error
    assert result.derived_touched == ["sibling"]
    text = advisory(repo)
    assert "derived files" in text.lower()
    assert "sibling" in text


def test_clean_case_stays_honest_but_quiet(tmp_path):
    """A sibling branch exists and has diverged, but touches neither the
    decisions dir nor the derived store — no signal, and the text says so
    without claiming proof of absence."""
    repo = _repo_with_sibling(tmp_path, {"README.md": "unrelated change"})
    result = scan(repo)
    assert result.ok, result.error
    assert result.claimed_numbers == {}
    assert result.derived_touched == []
    text = advisory(repo)
    assert "COLLISION" not in text
    assert "quiet, not proof" in text


# --- fail-closed-into-silence: unknown state is never reported as clear -----

def test_unknown_when_no_base_is_resolvable(tmp_path):
    """A lone branch with no master/main and no origin: the scan cannot even
    pick a base to diff against, and must say UNKNOWN rather than fall
    through to 'no collision found'."""
    repo = tmp_path / "lonely"
    repo.mkdir()
    _git(repo, "init", "-b", "solo-branch-name")
    (repo / "README.md").write_text("hi", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "only commit")

    result = scan(repo)
    assert result.ok is False
    assert "ref known locally" in result.error

    text = advisory(repo)
    assert "UNKNOWN" in text
    assert "quiet, not proof" not in text   # never a false-clear
    assert "COLLISION" not in text


def test_unknown_when_not_a_git_repo_at_all(tmp_path):
    not_a_repo = tmp_path / "just-a-directory"
    not_a_repo.mkdir()
    result = scan(not_a_repo)
    assert result.ok is False
    text = advisory(not_a_repo)
    assert "UNKNOWN" in text
    assert "quiet, not proof" not in text


def test_unknown_when_branch_listing_itself_fails(tmp_path, monkeypatch):
    """Base resolves, but the `git branch -a --no-merged` call fails — the
    other way `scan()` can come back not-ok, exercised directly since a real
    git that resolves a base and then fails to list branches is not easy to
    provoke honestly."""
    monkeypatch.setattr(bp, "resolve_base", lambda root: "origin/master")
    monkeypatch.setattr(bp, "_candidate_branches", lambda root, base: None)
    result = scan(tmp_path)
    assert result.ok is False
    assert "branch -a --no-merged" in result.error


def test_advisory_never_crashes_and_names_unknown_on_a_scan_exception(
        tmp_path, monkeypatch):
    def _boom(root):
        raise RuntimeError("simulated scan failure")
    monkeypatch.setattr(bp, "scan", _boom)
    text = advisory(tmp_path)
    assert "UNKNOWN" in text
    assert "quiet, not proof" not in text


# --- the advisory always states its own limits ------------------------------

def test_the_advisory_states_its_limits_every_time(tmp_path):
    repo = _repo_with_sibling(tmp_path, {"README.md": "x"})
    text = advisory(repo)
    assert "best-effort" in text.lower()
    assert "invisible here" in text
    assert "cannot serialize two agents" in text
    assert "#111" in text


# --- wiring: registered, advisory (not a blocking gate), fires end to end --

def test_before_propose_is_a_known_module_but_not_a_blocking_gate():
    import sys
    from hooks.hook_runner import MODULES
    assert "before_propose" in MODULES
    sys.path.insert(0, str(REPO / "scripts"))
    import hook_guard
    assert "before_propose" not in hook_guard.BLOCKING


def test_the_wired_hook_injects_on_a_propose_prompt_and_nothing_otherwise():
    fires = _run({"prompt": "let's propose a decision about the collision guard"})
    assert fires.returncode == 0, fires.stderr
    payload = json.loads(fires.stdout)
    assert payload["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "collision" in payload["hookSpecificOutput"]["additionalContext"].lower()

    quiet = _run({"prompt": "why did that test fail?"})
    assert quiet.returncode == 0, quiet.stderr
    assert quiet.stdout.strip() == ""        # nothing injected on an unrelated turn


def _run(payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(REPO / "hooks" / "nestor-hook"), "claude", "before_propose"],
        input=json.dumps(payload), capture_output=True, text=True,
        cwd=REPO, timeout=60,
        env={**os.environ, "NESTOR_PROJECT_ROOT": str(REPO)})
