"""One prompt-submit process preserves all three deterministic advisories."""
from __future__ import annotations

import json
import os
import pathlib
import subprocess

from hooks import hook_runner

REPO = pathlib.Path(__file__).resolve().parent.parent


def test_manifest_runs_one_prompt_submit_process():
    manifest = json.loads((REPO / "hooks" / "wiring.json").read_text(encoding="utf-8"))
    prompt_hooks = [hook for hook in manifest["hooks"] if hook["event"] == "prompt_submit"]

    assert prompt_hooks == [{"event": "prompt_submit", "action": "prompt_submit"}]


def test_prompt_submit_combines_anchor_build_and_proposal_context(monkeypatch, tmp_path):
    monkeypatch.setattr(hook_runner, "reinject_for_event", lambda event, root: "anchor")
    monkeypatch.setattr(hook_runner, "before_build_for_prompt", lambda prompt, root: "build")
    monkeypatch.setattr(hook_runner, "before_propose_for_prompt", lambda prompt, root: "propose")

    context = hook_runner.prompt_submit_context({"prompt": "build and open a PR"}, tmp_path)

    assert context == "anchor\n\nbuild\n\npropose"


def test_one_broken_advisory_does_not_drop_the_other_two(monkeypatch, tmp_path):
    def broken(prompt, root):
        raise RuntimeError("advisory bug")

    monkeypatch.setattr(hook_runner, "reinject_for_event", lambda event, root: "anchor")
    monkeypatch.setattr(hook_runner, "before_build_for_prompt", broken)
    monkeypatch.setattr(hook_runner, "before_propose_for_prompt", lambda prompt, root: "propose")

    assert hook_runner.prompt_submit_context({"prompt": "open a PR"}, tmp_path) == "anchor\n\npropose"


def test_combined_hook_emits_one_context_envelope_end_to_end():
    done = subprocess.run(
        [str(REPO / "hooks" / "nestor-hook"), "claude", "prompt_submit"],
        input=json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": "Build a parser"}),
        capture_output=True,
        text=True,
        cwd=REPO,
        timeout=60,
        env={**os.environ, "NESTOR_PROJECT_ROOT": str(REPO)},
        check=False,
    )

    assert done.returncode == 0, done.stderr
    payload = json.loads(done.stdout)
    context = payload["hookSpecificOutput"]["additionalContext"]
    assert "[NESTOR ANCHOR]" in context
    assert "[NESTOR before-build]" in context
