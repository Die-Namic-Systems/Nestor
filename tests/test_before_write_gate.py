"""The gate that was missing: no writing gated code until the desk was asked.

`.claude/settings.json` registered `SessionStart` and a `PreToolUse` matched on
`mcp__`, and nothing on `Write`/`Edit`. So the seat context arrived as advice, an
agent read it, and then wrote a whole fixture without consulting the review desk
— which is `IDEAS.md` §6.12's own thesis failing in the repo that wrote it.

These pin the behaviours the gate has to have, and the two it must not:

* gated Python with no consultation → **deny**
* markdown, JSON, anything outside the gated trees → allow
* `demo/review_desk.py` itself → allow, because gating the tool that clears the
  gate is a deadlock discovered at the worst moment
* consult, then retry → allow
* let the receipt go stale → deny again

The fourth is the one that failed when this was first wired: `record()` sat
after `cmd_bearing`'s early return, so asking a question that matched nothing
did not count as asking. A receipt attests that somebody looked, not that the
answer was interesting.

Driven through `evaluate_write` directly — it is pure over a payload and a root
— plus two end-to-end runs of the real `hooks/nestor-hook` to cover the wiring
and the emitted JSON, which is the part `evaluate_write` cannot see.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from hooks.before_write import evaluate_write, is_gated       # noqa: E402
from hooks.review_receipt import is_fresh, record             # noqa: E402


@pytest.fixture()
def receipt(tmp_path, monkeypatch):
    path = tmp_path / "receipt.json"
    monkeypatch.setenv("NESTOR_REVIEW_RECEIPT", str(path))
    monkeypatch.delenv("NESTOR_REVIEW_TTL_SEC", raising=False)
    return path


def write_of(path: str) -> dict:
    return {"tool_name": "Write", "tool_input": {"file_path": str(REPO / path)}}


def test_gated_code_is_denied_without_a_consultation(receipt):
    allow, user, agent = evaluate_write(write_of("nestor/memory.py"), REPO)
    assert not allow
    assert "BLOCKED" in agent and "nestor/memory.py" in agent
    assert "review_desk.py" in agent, "a refusal must name the way out of itself"
    assert "memory.py" in user


@pytest.mark.parametrize("path", ["README.md", "IDEAS.md",
                                  "docs/dogfood/decisions/0053-desks-scaffolding.json"])
def test_prose_and_data_are_never_gated(receipt, path):
    allow, _, _ = evaluate_write(write_of(path), REPO)
    assert allow, "a gate that fires on a README edit is a gate people disable"


def test_the_tool_that_clears_the_gate_is_not_gated(receipt):
    allow, _, _ = evaluate_write(write_of("demo/review_desk.py"), REPO)
    assert allow, "gating the consulting tool is a deadlock"
    assert not is_gated(str(REPO / "demo/review_desk.py"), REPO)


def test_a_consultation_opens_it(receipt):
    assert not evaluate_write(write_of("nestor/memory.py"), REPO)[0]
    record(REPO, "changing add_pair")
    assert evaluate_write(write_of("nestor/memory.py"), REPO)[0]


def test_an_empty_consultation_still_counts(receipt):
    """The receipt attests that somebody looked, not that they found something.

    This is the case that failed when the gate was first wired: `record()` sat
    after `cmd_bearing`'s early return, so a query matching nothing recorded
    nothing — and `bearing` scores badly on plain-English risks, so matching
    nothing is the common outcome rather than the rare one.
    """
    record(REPO, "a question nothing in the desk matches")
    fresh, detail = is_fresh(REPO)
    assert fresh, detail


def test_a_stale_consultation_closes_it_again(receipt, monkeypatch):
    record(REPO, "long ago")
    assert evaluate_write(write_of("nestor/memory.py"), REPO)[0]
    monkeypatch.setenv("NESTOR_REVIEW_TTL_SEC", "0")
    allow, _, agent = evaluate_write(write_of("nestor/memory.py"), REPO)
    assert not allow
    assert "ago" in agent, "the refusal should say how stale the consultation is"


def test_a_non_write_tool_is_untouched(receipt):
    allow, _, _ = evaluate_write(
        {"tool_name": "Read", "tool_input": {"file_path": str(REPO / "nestor/memory.py")}},
        REPO)
    assert allow


def test_the_hook_emits_a_deny_both_dialects_understand(receipt):
    """End-to-end through the real wrapper, which `evaluate_write` cannot cover.

    Claude Code has moved from `{"decision": "block"}` to
    `hookSpecificOutput.permissionDecision`. A gate that degrades to advice on
    half the installed base is the failure this hook exists to fix, so both are
    asserted rather than whichever this build happens to read.
    """
    done = subprocess.run(
        [str(REPO / "hooks" / "nestor-hook"), "claude", "before_write"],
        input=json.dumps(write_of("nestor/memory.py")),
        capture_output=True, text=True, cwd=REPO, timeout=60)
    assert done.returncode == 0, done.stderr
    out = json.loads(done.stdout)
    assert out["decision"] == "block"
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "review_desk.py" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_the_gate_fails_open_on_its_own_bugs(receipt):
    """Closed on its subject, open on itself — opposite defaults, on purpose.

    A hook that wedges every write when its own parsing is wrong is a hook
    everybody deletes, and a deleted gate protects nothing.
    """
    done = subprocess.run(
        [str(REPO / "hooks" / "nestor-hook"), "claude", "before_write"],
        input="this is not json at all",
        capture_output=True, text=True, cwd=REPO, timeout=60)
    assert done.returncode == 0
    assert json.loads(done.stdout)["decision"] == "allow"
