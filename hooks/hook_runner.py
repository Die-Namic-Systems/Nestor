#!/usr/bin/env python3
"""Nestor agent hooks — one implementation, Cursor + Claude Code adapters."""
from __future__ import annotations

import argparse
import json
import sys

from hooks.before_authority import evaluate_authority
from hooks.before_bash import evaluate_bash
from hooks.before_build import for_prompt as before_build_for_prompt
from hooks.before_mcp import evaluate_mcp, normalize_for_mcp_gate
from hooks.before_propose import for_prompt as before_propose_for_prompt
from hooks.before_stop import evaluate_stop
from hooks.before_write import evaluate_write
from hooks.reinject import EVENTS as REINJECT_EVENTS
from hooks.reinject import for_event as reinject_for_event
from hooks.session_start import build_context, maybe_bootstrap_claude_venv, repo_root

#: Modules the runner dispatches. The gate-proving harness
#: (scripts/hook_guard.py) reads this so a newly-wired gate cannot ship without
#: a proof-it-denies case; the advisory (context-injecting) modules are listed
#: there as non-gates.
MODULES = ("session_start", "session_end", "before_mcp", "before_write",
           "before_bash", "before_authority", "before_stop", "reinject",
           "before_build", "before_propose")


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


def _emit_claude_allow() -> None:
    """A clean allow for Claude Code is silence, not a word for 'yes'.

    These hooks used to print ``{"decision": "allow"}``. Claude Code validates
    hook stdout against one schema for every event, and there ``decision`` is
    ``"approve" | "block"`` — ``"allow"`` is in neither, so every clean turn
    ended in *Stop hook error: Hook JSON output validation failed*. The output
    was discarded, so the gates never actually mis-fired; the bug was noise on
    a passing path, on every allowed Bash, Write, MCP call and every Stop.

    Emitting nothing is what the runner already meant. It is also the only
    honest spelling here: for ``PreToolUse`` the valid affirmative is
    ``permissionDecision: "allow"``, and that does *not* mean "no objection" —
    it approves the call outright and skips the user's permission prompt. These
    hooks have no standing to grant that. They decline to block; the normal
    permission flow still decides. Silence says exactly that, and it is what the
    discarded payload amounted to, so this restores no behavior that was lost.

    The Cursor dialect keeps ``{"permission": "allow"}`` — a different schema,
    where the affirmative is read and is not a self-grant.
    """
    return


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
            _emit_claude_allow()
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
    both rather than betting on a version. The Bash guard and the self-grant
    tripwire share this emitter — same PreToolUse deny shape.
    """
    if allow:
        if fmt == "claude":
            _emit_claude_allow()
        else:
            print(json.dumps({"permission": "allow"}))
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


def _emit_before_stop(fmt: str, allow: bool, user: str, agent: str) -> None:
    """Stop is advisory-first, so its shape differs from the PreToolUse gates.

    A deny (a hard 'all tests pass' claim with no evidence) asks Claude to keep
    going — Claude Code's ``Stop`` honors the top-level ``{"decision": "block",
    "reason": …}`` spelling, not ``permissionDecision``. An allow that still
    carries a message is a non-blocking reminder, surfaced as context. A clean
    allow emits nothing blocking.
    """
    if not allow:
        reason = agent or user
        print(json.dumps({"decision": "block", "reason": reason} if fmt == "claude"
                         else {"permission": "deny", "user_message": user,
                               "agent_message": agent}))
        return
    if agent:
        print(json.dumps(
            {"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": agent}}
            if fmt == "claude" else {"additional_context": agent}))
        return
    if fmt == "claude":
        _emit_claude_allow()
        return
    print(json.dumps({"permission": "allow"}))


def _emit_reinject(fmt: str, event: str, context: str) -> None:
    """UserPromptSubmit / PreCompact stdout becomes injected context, the same
    envelope SessionStart uses — the runner only picks the shape."""
    if fmt == "claude":
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": event, "additionalContext": context}}))
        return
    print(json.dumps({"additional_context": context}))


def _first_block(payload: dict, root, *evaluators):
    """Run several PreToolUse evaluators in one process; the first to BLOCK wins,
    else allow.

    Each evaluator fails OPEN on its own exception — exactly what the separate
    single-evaluator dispatch did — so collapsing two hook subprocesses into one
    changes no verdict. Authority is passed first by its callers, so a self-grant
    is refused with the tripwire's own message rather than the gate's.
    """
    for ev in evaluators:
        try:
            allow, user, agent = ev(payload, root)
        except Exception:          # fail OPEN on our own bug, never on the subject
            allow, user, agent = True, "", ""
        if not allow:
            return allow, user, agent
    return True, "", ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Nestor CLI-agnostic hook runner")
    parser.add_argument("format", choices=("cursor", "claude"))
    parser.add_argument("module", choices=MODULES)
    args = parser.parse_args()

    root = repo_root()
    payload = _read_stdin()

    if args.module == "session_start":
        if args.format == "claude":
            maybe_bootstrap_claude_venv(root)
        _emit_session_start(args.format, build_context(root))
        return

    if args.module == "session_end":
        # Cleanup-only: SessionEnd cannot block or inject, so any warning goes to
        # stderr (the one channel it has) and the hook always exits 0.
        from hooks.session_end import run as session_end_run
        for line in session_end_run(root, payload).get("warnings", []):
            print(line, file=sys.stderr)
        return

    if args.module == "reinject":
        event = payload.get("hook_event_name") or payload.get("hookEventName")
        if event not in REINJECT_EVENTS:
            event = "UserPromptSubmit"          # default re-anchor shape
        _emit_reinject(args.format, event, reinject_for_event(event, root))
        return

    if args.module == "before_build":
        # Advisory: on a build-shaped prompt, inject the anti-rediscovery
        # reminder; on anything else, emit nothing at all (cost-free). Fail OPEN
        # on our own bugs — a reminder that crashed a turn would be worse than a
        # reminder that missed one.
        try:
            prompt = payload.get("prompt") or payload.get("user_prompt") or ""
            context = before_build_for_prompt(prompt, root)
        except Exception:          # noqa: BLE001
            context = ""
        if context:
            _emit_reinject(args.format, "UserPromptSubmit", context)
        return

    if args.module == "before_propose":
        # Advisory, same posture as before_build: on a propose/mint/open-a-PR
        # prompt, inject the collision-scan reminder; on anything else, emit
        # nothing. Fail OPEN on our own bugs — advisory.py already turns a scan
        # failure into an honest "UNKNOWN" line rather than a false-clear, so
        # the only thing caught here is a bug in this dispatch itself.
        try:
            prompt = payload.get("prompt") or payload.get("user_prompt") or ""
            context = before_propose_for_prompt(prompt, root)
        except Exception:          # noqa: BLE001
            context = ""
        if context:
            _emit_reinject(args.format, "UserPromptSubmit", context)
        return

    if args.module == "before_write":
        # Authority (the self-grant tripwire) shares a matcher with this gate, so
        # both used to run as two hook subprocesses per Write. Run them in one:
        # first to block wins, authority first so a mint is refused with its own
        # reason. Behaviour is identical to the two separate hooks.
        allow, user, agent = _first_block(payload, root, evaluate_authority, evaluate_write)
        _emit_before_write(args.format, allow, user, agent)
        return

    if args.module == "before_bash":
        # Same collapse for Bash: authority + the bash guard in one process.
        allow, user, agent = _first_block(payload, root, evaluate_authority, evaluate_bash)
        _emit_before_write(args.format, allow, user, agent)
        return

    if args.module == "before_authority":
        try:
            allow, user, agent = evaluate_authority(payload, root)
        except Exception:          # fail OPEN on our own bugs, closed on subject
            allow, user, agent = True, "", ""
        _emit_before_write(args.format, allow, user, agent)
        return

    if args.module == "before_stop":
        try:
            allow, user, agent = evaluate_stop(payload, root)
        except Exception:          # fail OPEN on our own bugs
            allow, user, agent = True, "", ""
        _emit_before_stop(args.format, allow, user, agent)
        return

    normalized = normalize_for_mcp_gate(args.format, payload)
    allow, user, agent = evaluate_mcp(normalized)
    _emit_before_mcp(args.format, allow, user, agent)


if __name__ == "__main__":
    main()
