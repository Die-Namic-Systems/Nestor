#!/usr/bin/env python3
"""Nestor agent hooks — one implementation, Cursor + Claude Code adapters."""
from __future__ import annotations

import argparse
import json
import sys

from hooks.before_mcp import evaluate_mcp, normalize_for_mcp_gate
from hooks.before_write import evaluate_write
from hooks.session_start import build_context, maybe_bootstrap_claude_venv, repo_root


def _read_stdin() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _emit_session_start(fmt: str, context: str) -> None:
    if fmt == "claude":
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": context,
                    }
                }
            )
        )
        return
    print(json.dumps({"additional_context": context}))


def _emit_before_mcp(fmt: str, allow: bool, user: str, agent: str) -> None:
    """Both dialects, and for Claude the deny spelling PreToolUse honors.

    Same failure as :func:`_emit_before_write`: Claude Code's ``PreToolUse``
    reads ``hookSpecificOutput.permissionDecision``, not the top-level
    ``{"decision": "block"}`` this used to emit alone — that spelling was never
    honored for ``PreToolUse``, so the MCP gate degraded to advice and let
    willow-mcp / nestor-as-MCP through. Emit both, matching the write gate, so
    the block lands on old and new builds alike.
    """
    if allow:
        if fmt == "claude":
            print(json.dumps({"decision": "allow"}))
        else:
            print(json.dumps({"permission": "allow"}))
        return
    reason = agent or user
    if fmt == "claude":
        print(json.dumps({
            "decision": "block",
            "reason": reason,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            },
        }))
        return
    print(
        json.dumps(
            {
                "permission": "deny",
                "user_message": user,
                "agent_message": agent,
            }
        )
    )


def _emit_before_write(fmt: str, allow: bool, user: str, agent: str) -> None:
    """Both dialects, and for Claude both spellings of a deny.

    Claude Code has moved from ``{"decision": "block"}`` to
    ``hookSpecificOutput.permissionDecision``; older builds read the first and
    newer ones the second. A gate that silently degrades to advice on half the
    installed base is the exact failure this hook exists to fix, so it emits
    both rather than betting on a version.
    """
    if allow:
        print(json.dumps({"decision": "allow"} if fmt == "claude"
                         else {"permission": "allow"}))
        return
    if fmt == "claude":
        print(json.dumps({
            "decision": "block",
            "reason": agent or user,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": agent or user,
            },
        }))
        return
    print(json.dumps({"permission": "deny", "user_message": user,
                      "agent_message": agent}))


def main() -> None:
    parser = argparse.ArgumentParser(description="Nestor CLI-agnostic hook runner")
    parser.add_argument("format", choices=("cursor", "claude"))
    parser.add_argument("module",
                    choices=("session_start", "before_mcp", "before_write"))
    args = parser.parse_args()

    root = repo_root()
    payload = _read_stdin()

    if args.module == "session_start":
        if args.format == "claude":
            maybe_bootstrap_claude_venv(root)
        _emit_session_start(args.format, build_context(root))
        return

    if args.module == "before_write":
        try:
            allow, user, agent = evaluate_write(payload, root)
        except Exception:          # fail OPEN on our own bugs — see before_write
            allow, user, agent = True, "", ""
        _emit_before_write(args.format, allow, user, agent)
        return

    normalized = normalize_for_mcp_gate(args.format, payload)
    allow, user, agent = evaluate_mcp(normalized)
    _emit_before_mcp(args.format, allow, user, agent)


if __name__ == "__main__":
    main()
