"""The hook *wiring* resolves even when the runtime does not set CLAUDE_PROJECT_DIR.

The gap IDEAS §6.108 records: every command in `.claude/settings.json` was
`$CLAUDE_PROJECT_DIR/hooks/nestor-hook …`, and in a multi-repo web session the
runtime left `CLAUDE_PROJECT_DIR` unset, so the command expanded to
`/hooks/nestor-hook` and the whole boot no-op'd — silently, because the runner
does not fail the turn on a missing hook. No test covered the wiring itself; the
end-to-end hook tests all run `hooks/nestor-hook` with `cwd=REPO`, the one
condition under which the bug cannot reproduce.

These tests drive the *literal command strings from settings.json* with the
project-root variables stripped, from the repo root and from a subdirectory, and
assert the chain still resolves and runs. And they prove the scripts are
self-locating: reached from a foreign cwd with no env at all, `nestor-hook` and
`session-start.sh` still find their own repo — so "reached" implies "correct".
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
SETTINGS = REPO / ".claude" / "settings.json"

#: Variables that, if set, would let a command resolve the *easy* way. The bug
#: is what happens when the runtime provides none of them, so every wiring test
#: runs with exactly these stripped from the environment.
ROOT_VARS = ("CLAUDE_PROJECT_DIR", "NESTOR_PROJECT_ROOT", "CURSOR_PROJECT_DIR")


def _commands() -> list[str]:
    data = json.loads(SETTINGS.read_text())
    cmds = [h["command"]
            for groups in data["hooks"].values()
            for g in groups
            for h in g["hooks"]]
    assert cmds, "no hook commands found in settings.json"
    return cmds


def _stripped_env(**extra: str) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ROOT_VARS}
    env.update(extra)
    return env


def _run(cmd: str, *, cwd: pathlib.Path, stdin: str, **env) -> subprocess.CompletedProcess:
    # sh, not bash: the resolver is POSIX on purpose, and settings.json commands
    # run in shell form under whatever /bin/sh the runtime provides.
    return subprocess.run(
        ["sh", "-c", cmd], input=stdin, capture_output=True, text=True,
        cwd=str(cwd), env=_stripped_env(**env), timeout=120, check=False)


def test_no_command_hard_depends_on_claude_project_dir():
    """The regression guard, stated as a property of the text.

    A command that references `nestor-hook` *only* through
    `$CLAUDE_PROJECT_DIR/` breaks the moment that variable is unset. Every
    command must carry a `$PWD`-based fallback so it can locate the hook from the
    working directory alone.
    """
    for cmd in _commands():
        assert "hooks/nestor-hook" in cmd
        assert '"$PWD"' in cmd, f"no cwd fallback — brittle if the var is unset:\n{cmd}"


def test_the_gate_would_reject_the_brittle_form():
    """Prove the guard above can fail: the exact string that shipped the bug does
    not satisfy it. A test that only ever sees the fixed input is a description."""
    brittle = "$CLAUDE_PROJECT_DIR/hooks/nestor-hook claude session_start"
    assert "hooks/nestor-hook" in brittle          # it does reference the hook…
    assert '"$PWD"' not in brittle                 # …but has no cwd fallback, so it is rejected


@pytest.mark.parametrize("module,marker", [
    ("before_mcp", "deny"),        # deterministic: fleet MCP is blocked
    ("session_start", "[brain]"),  # seat + brain injected
])
def test_every_wired_command_resolves_with_the_var_unset(module, marker):
    """The literal settings.json command, run with all root vars stripped and
    cwd at the repo root — the single-repo web case that used to no-op."""
    cmd = next(c for c in _commands() if f"claude {module}" in c)
    stdin = ('{"tool_name":"mcp__willow-mcp__store_get","tool_input":{}}'
             if module == "before_mcp" else "{}")
    proc = _run(cmd, cwd=REPO, stdin=stdin, CLAUDE_CODE_REMOTE="false")
    assert proc.returncode == 0, proc.stderr
    assert marker in proc.stdout


def test_wiring_resolves_from_a_subdirectory_too():
    """cwd drifted into a package subdir, var still unset: the upward walk finds
    the hook rather than only working from the exact root."""
    cmd = next(c for c in _commands() if "claude before_mcp" in c)
    proc = _run(cmd, cwd=REPO / "nestor", stdin='{"tool_name":"mcp__willow-mcp__store_get","tool_input":{}}',
                CLAUDE_CODE_REMOTE="false")
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_nestor_hook_self_locates_from_a_foreign_cwd(tmp_path):
    """Reached by absolute path from outside the repo with no env: it still finds
    its own root (via BASH_SOURCE), so a correct invocation does not depend on the
    caller's cwd being right."""
    proc = subprocess.run(
        [str(REPO / "hooks" / "nestor-hook"), "claude", "before_mcp"],
        input='{"tool_name":"mcp__willow-mcp__store_get","tool_input":{}}',
        capture_output=True, text=True, cwd=str(tmp_path),
        env=_stripped_env(), timeout=60, check=False)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_session_start_script_self_locates_and_is_loud_when_declining(tmp_path):
    """Run from /tmp with no env and CLAUDE_CODE_REMOTE unset: the bootstrap
    script names the *repo* root it resolved (not tmp), and says on stderr that
    it declined — the silent `exit 0` that was indistinguishable from success is
    gone (FINDINGS-2026-08-12 §1.1)."""
    script = REPO / ".claude" / "hooks" / "session-start.sh"
    env = _stripped_env()
    env.pop("CLAUDE_CODE_REMOTE", None)
    proc = subprocess.run(["bash", str(script)], capture_output=True, text=True,
                          cwd=str(tmp_path), env=env, timeout=60, check=False)
    assert proc.returncode == 0
    assert str(REPO) in proc.stderr           # resolved its own root, not tmp
    assert "skipping venv bootstrap" in proc.stderr
