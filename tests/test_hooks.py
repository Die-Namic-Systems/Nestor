"""CLI-agnostic Nestor workspace hooks."""
from __future__ import annotations

import json
import pathlib
import subprocess

import pytest

from hooks.before_mcp import evaluate_mcp, normalize_for_mcp_gate
from hooks.hook_runner import (_emit_before_mcp, _emit_before_stop,
                               _emit_before_write)

REPO = pathlib.Path(__file__).resolve().parent.parent

#: The only values Claude Code's hook output schema accepts for ``decision``,
#: for every event. ``"allow"`` is not among them — see
#: :func:`test_no_claude_emitter_invents_a_decision_value`.
CLAUDE_DECISIONS = {"approve", "block"}


@pytest.mark.parametrize("emit", [_emit_before_mcp, _emit_before_write,
                                  _emit_before_stop])
@pytest.mark.parametrize("allow", [True, False])
def test_no_claude_emitter_invents_a_decision_value(emit, allow, capsys):
    """The invariant behind the bug, asserted at the boundary the schema checks.

    Claude Code validates hook stdout against one schema for every event, and
    a violation is discarded with *Hook JSON output validation failed* — so an
    invented value is not a harmless extra key, it voids the whole payload. The
    deny paths depend on being read, which makes this the gates' own interest.

    Every Claude emitter, on both verdicts: stdout is either empty or JSON whose
    ``decision`` (if it has one) is a value the schema actually accepts. The
    forbidden act is emitting anything else, and ``"allow"`` — the literal that
    shipped — is the case this would have caught.
    """
    emit("claude", allow, "user msg", "agent msg")
    out = capsys.readouterr().out.strip()
    if not out:
        return
    payload = json.loads(out)
    if "decision" in payload:
        assert payload["decision"] in CLAUDE_DECISIONS, (
            f"{emit.__name__} emitted decision={payload['decision']!r}, "
            f"which Claude Code's schema rejects — the whole payload is voided")


def test_fleet_mcp_is_blocked_in_cursor_shape():
    payload = normalize_for_mcp_gate(
        "cursor",
        {
            "hook_event_name": "beforeMCPExecution",
            "server": "willow-mcp",
            "tool_name": "task_submit",
            "tool_input": {},
        },
    )
    allow, _, _ = evaluate_mcp(payload)
    assert not allow


def test_codebase_memory_is_allowed():
    allow, _, _ = evaluate_mcp({"tool_name": "mcp__codebase-memory-mcp__search_graph"})
    assert allow


def test_claude_mcp_tool_name_is_blocked():
    allow, _, _ = evaluate_mcp({"tool_name": "mcp__willow-mcp__store_get", "tool_input": {}})
    assert not allow


def test_claude_mcp_deny_uses_pretooluse_permission_decision(capsys):
    """The deny Claude Code's PreToolUse actually honors.

    ``{"decision": "block"}`` alone was never read for ``PreToolUse``; the gate
    only lands via ``hookSpecificOutput.permissionDecision``. Regression for the
    MCP gate silently degrading to advice — the same bug the write gate fixed.
    """
    _emit_before_mcp("claude", False, "user msg", "agent msg")
    out = json.loads(capsys.readouterr().out)
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"]


def test_claude_mcp_allow_emits_nothing(capsys):
    """A clean allow is silence — Claude Code has no valid word for 'yes' here.

    This printed ``{"decision": "allow"}``, which fails Claude Code's hook
    output schema (``decision`` is ``"approve" | "block"``) and surfaced as
    *Hook JSON output validation failed* on every allowed call. Asserting empty
    stdout also pins the deliberate choice not to substitute
    ``permissionDecision: "allow"``: that approves the tool call and skips the
    user's permission prompt, which this gate has no standing to do.
    """
    _emit_before_mcp("claude", True, "", "")
    assert capsys.readouterr().out == ""


def test_cursor_mcp_deny_keeps_permission_dialect(capsys):
    _emit_before_mcp("cursor", False, "user msg", "agent msg")
    out = json.loads(capsys.readouterr().out)
    assert out["permission"] == "deny"
    assert out["agent_message"] == "agent msg"


def _run_hook(payload: dict) -> dict:
    """Drive the real wrapper end-to-end and return its parsed stdout JSON."""
    done = subprocess.run(
        [str(REPO / "hooks" / "nestor-hook"), "claude", "before_mcp"],
        input=json.dumps(payload),
        capture_output=True, text=True, cwd=REPO, timeout=60)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_the_mcp_gate_denies_end_to_end():
    """Through the real ``hooks/nestor-hook``, which the emit tests cannot cover.

    The bug was that ``{"decision": "block"}`` alone was emitted, and
    ``PreToolUse`` only honors ``hookSpecificOutput.permissionDecision`` — so the
    gate degraded to advice and the fleet MCP call went through. Assert the
    spelling that actually blocks lands on the wire, not just in the unit.
    """
    out = _run_hook({"tool_name": "mcp__willow-mcp__store_get", "tool_input": {}})
    assert out["decision"] == "block"
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert out["hookSpecificOutput"]["permissionDecisionReason"]


def test_the_mcp_gate_allows_end_to_end():
    """Through the real wrapper: an allowed MCP call writes nothing to stdout."""
    done = subprocess.run(
        [str(REPO / "hooks" / "nestor-hook"), "claude", "before_mcp"],
        input=json.dumps({"tool_name": "mcp__codebase-memory-mcp__search_graph",
                          "tool_input": {}}),
        capture_output=True, text=True, cwd=REPO, timeout=60)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == ""
