"""CLI-agnostic Nestor workspace hooks."""
from __future__ import annotations

from hooks.before_mcp import evaluate_mcp, normalize_for_mcp_gate


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
