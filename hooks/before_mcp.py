"""Shared MCP gate for the Nestor source tree (CLI-agnostic logic)."""
from __future__ import annotations

import json
from typing import Any

_ALLOW_SUBSTR = (
    "codebase-memory",
    "codebase_memory",
    "mcp__nestor__",
)

_BLOCK_SUBSTR = (
    "willow-mcp",
    "willow_mcp",
    "mcp__willow-mcp",
    "mcp__willow__",
    "user-willow-mcp",
    "user-willow",
    "/willow_mcp",
    "nestor_mcp",
)

_USER_MESSAGE = (
    "Fleet MCP is disabled in this workspace. "
    "Edit the repo locally (pytest, ruff, Nestor's household MCP or CLI)."
)
_AGENT_MESSAGE = (
    "Nestor source seat: do not use willow-mcp for routine development. "
    "The household Nestor MCP may retrieve or draft but cannot verify. "
    "Read hooks/seat.md and docs/agent-guide.md."
)


def mcp_blob(payload: dict[str, Any]) -> str:
    parts = [
        str(payload.get("tool_name") or payload.get("toolName") or ""),
        str(payload.get("mcp_server") or payload.get("server") or payload.get("provider") or ""),
        str(payload.get("command") or ""),
        json.dumps(payload.get("tool_input") or payload.get("arguments") or {}),
    ]
    return " ".join(parts).lower()


def evaluate_mcp(payload: dict[str, Any]) -> tuple[bool, str, str]:
    """Return (allow, user_message, agent_message)."""
    blob = mcp_blob(payload)
    if any(a in blob for a in _ALLOW_SUBSTR):
        return True, "", ""
    if any(b in blob for b in _BLOCK_SUBSTR):
        return False, _USER_MESSAGE, _AGENT_MESSAGE
    return True, "", ""


def normalize_for_mcp_gate(fmt: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Map Cursor beforeMCPExecution / Claude PreToolUse into one shape."""
    event = str(payload.get("hook_event_name") or payload.get("hookEventName") or "")
    if fmt == "cursor" and event == "beforeMCPExecution":
        server = str(payload.get("server") or payload.get("mcp_server") or "willow")
        tool = str(payload.get("tool_name") or "")
        tool_input = payload.get("tool_input")
        if isinstance(tool_input, str):
            try:
                tool_input = json.loads(tool_input)
            except json.JSONDecodeError:
                tool_input = {}
        if not isinstance(tool_input, dict):
            tool_input = {}
        return {
            "tool_name": f"mcp__{server}__{tool}",
            "tool_input": tool_input,
        }
    # Claude / generic PreToolUse
    return payload
