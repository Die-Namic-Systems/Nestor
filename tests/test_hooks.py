"""CLI-agnostic Nestor workspace hooks."""
from __future__ import annotations

import json

from hooks.before_mcp import evaluate_mcp, normalize_for_mcp_gate
from hooks.hook_runner import _emit_before_mcp


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


def test_claude_mcp_allow_emits_decision(capsys):
    _emit_before_mcp("claude", True, "", "")
    out = json.loads(capsys.readouterr().out)
    assert out["decision"] == "allow"


def test_cursor_mcp_deny_keeps_permission_dialect(capsys):
    _emit_before_mcp("cursor", False, "user msg", "agent msg")
    out = json.loads(capsys.readouterr().out)
    assert out["permission"] == "deny"
    assert out["agent_message"] == "agent msg"
