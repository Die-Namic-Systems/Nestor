"""Gate: do not end the turn on a completion claim the tree never backed up.

The Stop event fires as the agent is about to hand the turn back. This hook reads
the session's final assistant message and looks for the shape Nestor's covenant
names first — *claim only what you derived from the tree* — failing: a message
that says **done / fixed / passing / verified / green / all tests pass** while
carrying **no evidence of an actually-run check** (no quoted command and its
outcome, no ``N passed``, no exit code, no ``file.py:line``).

Advisory by default, deny available
-----------------------------------
A Stop hook that hard-blocks is a hook that can *trap* a session in a loop, and a
trap teaches everyone to delete the hook — the same lesson :mod:`hooks.before_write`
records. So the default is a **non-blocking reminder**: ``allow=True`` with a
populated ``agent_message`` the runner can surface as advice. The deny path is
kept and used sparingly — only a hard ``all tests pass``-class assertion with
**zero** evidence tokens is worth blocking, and it blocks **once**: when the
runner reports ``stop_hook_active`` (this hook already fired and forced a
continuation), the block downgrades to advisory so the turn can end.

Fail open on our own bugs
-------------------------
If the final assistant text cannot be found — unknown payload shape, empty
transcript, a parse error inside this module — the turn is **allowed** with empty
messages. A hook that wedges the end of every turn when its own parsing is wrong
is the failure mode this file is written to avoid; detection is closed on its
subject and open on itself, opposite defaults on purpose.

Clean-room note
---------------
The idea — a Stop-time guard against unverified "done" — is reused from the
vibeguard project (MIT). No text or code was copied; the tokens, the advisory /
deny boundary, and the fail-open posture are written here against Nestor's own
house style and doctrine.
"""
from __future__ import annotations

import json
import pathlib
import re
from typing import Any

#: Words that assert the work is finished. Matched case-insensitively as whole
#: words / phrases so "predone" or "completeness" do not trip the guard.
_CLAIM_TOKENS = (
    "done",
    "fixed",
    "complete",
    "completed",
    "verified",
    "passing",
    "green",
    "works now",
    "it works",
    "all set",
)

#: The subset worth a one-time hard block when it stands with no evidence at all:
#: a sweeping "the whole suite is green" assertion is the costliest one to take
#: on faith, and the one Nestor has a documented history of getting wrong.
_HARD_CLAIM_PATTERNS = (
    r"all tests? (?:pass|passed|passing)",
    r"all (?:the )?tests are (?:green|passing)",
    r"tests all pass",
    r"everything passes",
    r"(?:the )?(?:full |whole |entire )?suite is green",
    r"(?:the )?(?:full |whole |entire )?suite passes",
    r"all green",
    r"all checks pass(?:ed|ing)?",
)

#: Command names that make a quoted span read as an actually-run check rather
#: than prose. A backtick / fenced span containing one of these counts.
_COMMAND_WORDS = (
    "pytest",
    "py.test",
    "ruff",
    "python",
    "python3",
    "pip",
    "make",
    "git",
    "npm",
    "cargo",
    "go test",
    "node",
    "bandit",
    "coverage",
    "mypy",
    "tox",
    "./",
)

_CLAIM_RE = re.compile(
    r"(?<![a-z0-9])(?:" + "|".join(re.escape(t) for t in _CLAIM_TOKENS) + r")(?![a-z0-9])",
    re.IGNORECASE,
)
_HARD_CLAIM_RE = re.compile("|".join(_HARD_CLAIM_PATTERNS), re.IGNORECASE)

# Evidence that a check was actually run, not merely asserted.
_EVIDENCE_RES = (
    re.compile(r"\d+\s+passed", re.IGNORECASE),          # pytest "1011 passed"
    re.compile(r"\d+\s+failed", re.IGNORECASE),          # a real run that reports failures
    re.compile(r"\d+\s+errors?", re.IGNORECASE),
    re.compile(r"exit(?:\s+code)?\s+\d+", re.IGNORECASE),  # "exit code 0", "exit 1"
    re.compile(r"return(?:ed)?\s*code\s*[:=]?\s*\d+", re.IGNORECASE),
    re.compile(r"\breturncode\b", re.IGNORECASE),
    re.compile(r"\.py:\d+", re.IGNORECASE),              # file:line
    re.compile(r"={2,}\s*\d+\s+passed", re.IGNORECASE),  # pytest summary rule
)

# Inline `code` spans and fenced ```blocks``` — used to look for a command word.
_CODE_SPAN_RE = re.compile(r"```.*?```|`[^`]+`", re.DOTALL)


def _text_from_value(value: Any) -> str:
    """Best-effort flatten of a message-ish value into plain text.

    Handles a bare string, a dict with a ``content`` (string or a list of
    ``{"type": "text", "text": ...}`` blocks), and a list of any of those.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("text", "content", "message"):
            if key in value:
                return _text_from_value(value[key])
        return ""
    if isinstance(value, (list, tuple)):
        return "\n".join(_text_from_value(item) for item in value)
    return ""


def _last_assistant_text(messages: Any) -> str:
    """From a list of message dicts, the text of the last assistant turn."""
    if not isinstance(messages, (list, tuple)):
        return ""
    for msg in reversed(messages):
        if isinstance(msg, dict):
            role = str(msg.get("role") or msg.get("type") or "").lower()
            if role in ("assistant", "ai", "model"):
                return _text_from_value(msg)
        else:
            # A bare string in the list — take it as the last thing said.
            text = _text_from_value(msg)
            if text:
                return text
    return ""


def _read_transcript_path(raw: Any) -> str:
    """Read a JSONL transcript file and return its last assistant message text.

    Claude Code Stop hooks pass ``transcript_path`` to a JSONL file. Reading it
    is optional and entirely defensive — any failure returns "" and the caller
    falls through to fail-open.
    """
    if not isinstance(raw, str) or not raw:
        return ""
    try:
        lines = pathlib.Path(raw).read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    records: list[Any] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    # Records may be raw messages, or wrappers like {"message": {...}}.
    normalized = [r.get("message", r) if isinstance(r, dict) else r for r in records]
    return _last_assistant_text(normalized)


def final_assistant_text(payload: dict[str, Any]) -> str:
    """Extract the final assistant message text from a Stop payload, or "".

    Defensive across the shapes a Stop hook might use. Order of preference:
    an explicit ``last_message``, then a ``messages`` / ``transcript`` list, then
    a plain ``transcript`` string, then a ``transcript_path`` file on disk.
    """
    if not isinstance(payload, dict):
        return ""

    direct = _text_from_value(payload.get("last_message"))
    if direct.strip():
        return direct

    for key in ("messages", "transcript"):
        value = payload.get(key)
        if isinstance(value, (list, tuple)):
            text = _last_assistant_text(value)
            if text.strip():
                return text
        elif isinstance(value, str) and value.strip():
            return value

    return _read_transcript_path(payload.get("transcript_path"))


def _has_evidence(text: str) -> bool:
    """Does the text carry a token of an actually-run check?"""
    for spans in _CODE_SPAN_RE.findall(text):
        low = spans.lower()
        if any(word in low for word in _COMMAND_WORDS):
            return True
    return any(rx.search(text) for rx in _EVIDENCE_RES)


def evaluate_stop(payload: dict[str, Any], root: pathlib.Path) -> tuple[bool, str, str]:
    """``(allow, user_message, agent_message)`` for one Stop event.

    ``allow=True`` lets the turn end; a populated ``agent_message`` with
    ``allow=True`` is the **advisory** case — surface it as a reminder, do not
    block. ``allow=False`` asks for evidence before the turn ends and is used
    only for a hard ``all tests pass``-class claim with zero evidence, and only
    once (it downgrades to advisory when ``stop_hook_active`` is set).
    """
    del root  # unused; kept for signature parity with the other gates
    text = final_assistant_text(payload)
    if not text.strip():
        # Could not find the message — fail OPEN.
        return True, "", ""

    if not _CLAIM_RE.search(text) and not _HARD_CLAIM_RE.search(text):
        # No completion claim at all — nothing to check.
        return True, "", ""

    if _has_evidence(text):
        # Claim made, and a run is quoted to back it — allow clean.
        return True, "", ""

    hard = bool(_HARD_CLAIM_RE.search(text))
    already_fired = bool(payload.get("stop_hook_active"))

    reminder = (
        "Completion claim without evidence. Nestor's covenant is 'claim only "
        "what you derived from the tree' — this message asserts the work is "
        "done but quotes no run: no command and its outcome, no 'N passed', no "
        "exit code, no file.py:line. Before ending: run the check and quote it, "
        "or soften the claim to what you actually verified. "
        "See hooks/before_stop.py and the verification doctrine."
    )

    if hard and not already_fired:
        user = "Turn paused: a hard 'all tests pass'-class claim with no evidence of a run."
        return False, user, reminder

    # Soft claim, or a hard claim we already blocked once — advisory only.
    return True, "", reminder
