"""Every prompt advisory must actually fire in a session, not merely exist.

This test exists because of a defect it would have caught. #243 added
``hooks/before_survey.py``, registered it in ``MODULES``, wired it into
``prompt_submit_context``, and shipped with a test asserting that
``prompt_submit`` carries it alongside its siblings. That assertion was true
and it was the wrong surface: ``.claude/settings.json`` named its three
advisories individually — ``reinject``, ``before_build``, ``before_propose`` —
and never named ``prompt_submit``, so the new advisory could not fire in this
repository at all. It was **reachable by name and dead in practice**, which is
precisely the failure the original test was written to prevent.

The lesson generalises past that one module: a hook has two independent halves,
the runner that implements it and the settings that invoke the runner, and a
test that exercises only the first proves nothing about whether anything runs.
So this pins the seam between them.

Two assertions, deliberately kept apart, because they fail for different
reasons and a reader should be able to tell which broke:

1. the settings invoke the consolidated action at all, and
2. every module declaring ``EVENT = "UserPromptSubmit"`` is evaluated by it.

Neither one alone is sufficient. Settings that invoke ``prompt_submit`` while
the joiner has dropped an advisory is the silent half; a joiner that evaluates
everything while the settings name individual actions is the half #243 hit.
"""
from __future__ import annotations

import inspect
import json
import pathlib
import re

from hooks import hook_runner

REPO = pathlib.Path(__file__).resolve().parent.parent
SETTINGS = REPO / ".claude" / "settings.json"

#: How the tracked settings spell a call into the runner: ``... claude <action>``.
_ACTION_RX = re.compile(r"\bclaude\s+(\w+)\b")


def _invoked_actions(event: str, settings: pathlib.Path = SETTINGS) -> set[str]:
    """The runner actions ``settings`` (the tracked ``.claude/settings.json``
    by default) invokes for ``event``."""
    data = json.loads(settings.read_text(encoding="utf-8"))
    return {
        action
        for entry in data.get("hooks", {}).get(event, [])
        for hook in entry.get("hooks", [])
        for action in _ACTION_RX.findall(str(hook.get("command", "")))
    }


def _prompt_advisory_modules(hooks_dir: pathlib.Path = REPO / "hooks") -> list[str]:
    """Every module in ``hooks_dir`` that declares itself as riding
    UserPromptSubmit.

    Read from the modules' own ``EVENT`` constant rather than from a list kept
    here, so a new advisory is covered the moment it is written — a roster in
    this file would be one more thing to forget, which is the shape of the bug
    being guarded against.
    """
    names = []
    for path in sorted(hooks_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if 'EVENT = "UserPromptSubmit"' in text:
            names.append(path.stem)
    return names


def test_the_settings_invoke_the_consolidated_prompt_action():
    """Without this, every advisory has to be named individually and one will
    eventually be forgotten — which is exactly what happened to before_survey.
    """
    assert "prompt_submit" in _invoked_actions("UserPromptSubmit"), (
        "`.claude/settings.json` does not invoke `prompt_submit` for "
        "UserPromptSubmit; advisories wired only into prompt_submit_context "
        "cannot fire in this repository"
    )


def test_every_prompt_advisory_is_evaluated_by_the_consolidated_action():
    """A module in MODULES that the joiner never calls is dead in practice."""
    joiner = inspect.getsource(hook_runner.prompt_submit_context)
    missing = [
        name for name in _prompt_advisory_modules()
        if name not in joiner and name.replace("before_", "") not in joiner
    ]
    assert not missing, (
        f"declared UserPromptSubmit but not evaluated by "
        f"prompt_submit_context: {', '.join(missing)}"
    )


def test_the_advisory_modules_are_registered_as_runner_modules():
    """Reachable through the joiner AND addressable by name, so the standalone
    dispatch used by the tests stays honest about what exists."""
    missing = [n for n in _prompt_advisory_modules() if n not in hook_runner.MODULES]
    assert not missing, f"not in MODULES: {', '.join(missing)}"


def test_the_guards_fire_on_a_planted_settings_file_and_a_planted_hooks_dir(tmp_path):
    """The prove-it-can-fail half, planted for real. Until the meta-scan
    (`tests/test_scans_fire.py`) landed, this test asserted a set literal it
    had built itself and never called either helper — a plant in name only,
    which is the exact shape that file exists to report. Now: a settings file
    naming actions individually — the pre-#246 shape — must come back
    without `prompt_submit`, and a hooks directory with one module riding
    UserPromptSubmit and one riding something else must name only the first.
    Without this, a rewrite of ``_invoked_actions`` that returned everything,
    or of ``_prompt_advisory_modules`` that returned every module, would
    leave the three real tests above green forever.
    """
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"hooks": {"UserPromptSubmit": [{"hooks": [
        {"command": "python hooks/nestor-hook claude reinject"},
        {"command": "python hooks/nestor-hook claude before_build"},
        {"command": "python hooks/nestor-hook claude before_propose"},
    ]}]}}), encoding="utf-8")
    individually = _invoked_actions("UserPromptSubmit", settings=settings)
    assert individually == {"reinject", "before_build", "before_propose"}
    assert "prompt_submit" not in individually
    assert _invoked_actions("Stop", settings=settings) == set(), "an event with no hooks invokes nothing"

    hooks = tmp_path / "hooks"
    hooks.mkdir()
    (hooks / "riding.py").write_text('EVENT = "UserPromptSubmit"\n', encoding="utf-8")
    (hooks / "elsewhere.py").write_text('EVENT = "Stop"\n', encoding="utf-8")
    (hooks / "silent.py").write_text("x = 1\n", encoding="utf-8")
    assert _prompt_advisory_modules(hooks_dir=hooks) == ["riding"]
