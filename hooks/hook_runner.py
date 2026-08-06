#!/usr/bin/env python3
"""Nestor agent hooks — one implementation, Cursor + Claude Code adapters."""
from __future__ import annotations

import argparse
import json
import sys

from hooks.before_mcp import evaluate_mcp, normalize_for_mcp_gate
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
    if allow:
        if fmt == "claude":
            print(json.dumps({"decision": "allow"}))
        else:
            print(json.dumps({"permission": "allow"}))
        return
    reason = agent or user
    if fmt == "claude":
        print(json.dumps({"decision": "block", "reason": reason}))
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Nestor CLI-agnostic hook runner")
    parser.add_argument("format", choices=("cursor", "claude"))
    parser.add_argument("module", choices=("session_start", "before_mcp"))
    args = parser.parse_args()

    root = repo_root()
    payload = _read_stdin()

    if args.module == "session_start":
        if args.format == "claude":
            maybe_bootstrap_claude_venv(root)
        _emit_session_start(args.format, build_context(root))
        return

    normalized = normalize_for_mcp_gate(args.format, payload)
    allow, user, agent = evaluate_mcp(normalized)
    _emit_before_mcp(args.format, allow, user, agent)


if __name__ == "__main__":
    main()
