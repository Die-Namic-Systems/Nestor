"""before_build is the anti-rediscovery advisory — it fires on a build request
and stays silent on everything else, and it never blocks.

The pair of directions is the whole guard: a detector that always fired would be
noise every turn, one that never fired would be the rediscovery it exists to
catch. So both are pinned — break `is_build_intent` either way and exactly one of
these goes red. The contract-as-a-test at the bottom asserts the wired hook
injects context on a build prompt, emits nothing otherwise, and always exits 0.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess

from hooks.before_build import advisory, for_prompt, is_build_intent

REPO = pathlib.Path(__file__).resolve().parent.parent


def test_fires_on_build_shaped_prompts():
    for prompt in ("build a new hook for X",
                   "let's implement a matcher",
                   "can you write a script to group these",
                   "re-land the conflict_scan",
                   "stand up the gate",
                   "add a guard that denies self-grants"):
        assert is_build_intent(prompt), prompt
        assert for_prompt(prompt, REPO), prompt


def test_silent_on_non_build_prompts():
    for prompt in ("what's the status of the seal?",
                   "seal it",
                   "add a decision about this",
                   "write it down in IDEAS",
                   "why did that test fail?",
                   ""):
        assert not is_build_intent(prompt), prompt
        assert for_prompt(prompt, REPO) == "", prompt


def test_the_advisory_points_at_the_box_and_both_lenses():
    text = advisory(REPO)
    assert "decision check" in text          # the box's own consult command
    assert "the-house-already-knew" in text  # the lesson it enforces
    assert "both lenses" in text.lower()     # box AND open internet
    assert "not a boundary" in text          # named honestly — a tripwire


def test_the_count_is_derived_from_the_tree_not_asserted():
    """The one number in the advisory must match the decisions on disk now."""
    actual = len(list((REPO / "docs" / "dogfood" / "decisions").glob("*.json")))
    assert f"{actual} recorded decisions" in advisory(REPO)


def test_the_wired_hook_injects_on_a_build_prompt_and_nothing_otherwise():
    build = _run({"prompt": "build a new clustering module"})
    assert build.returncode == 0, build.stderr
    payload = json.loads(build.stdout)
    assert payload["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "before-build" in payload["hookSpecificOutput"]["additionalContext"]

    quiet = _run({"prompt": "seal the oldest decision"})
    assert quiet.returncode == 0, quiet.stderr
    assert quiet.stdout.strip() == ""        # nothing injected on a non-build turn


def test_before_build_is_a_known_module_but_not_a_blocking_gate():
    import sys
    from hooks.hook_runner import MODULES
    assert "before_build" in MODULES
    sys.path.insert(0, str(REPO / "scripts"))
    import hook_guard
    assert "before_build" not in hook_guard.BLOCKING


def _run(payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(REPO / "hooks" / "nestor-hook"), "claude", "before_build"],
        input=json.dumps(payload), capture_output=True, text=True,
        cwd=REPO, timeout=60,
        env={**os.environ, "NESTOR_PROJECT_ROOT": str(REPO)})
