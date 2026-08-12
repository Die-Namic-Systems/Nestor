"""Gate: do not write code in this tree until the review desk has been asked.

The hook that was missing. ``.claude/settings.json`` registered ``SessionStart``
and a ``PreToolUse`` matched on ``mcp__``, and nothing on ``Write`` or ``Edit`` —
so the seat context arrived as **advice**, an agent read it, and then wrote a
whole fixture without consulting the desk that lists what is already known
broken. That is `IDEAS.md` §6.12's own thesis failing in this repo: *the
detection kit as gates, not advice.*

**It blocks, and it redirects.** A refusal that only says no gets routed around;
this one names the two commands that clear it, so the exit is doing the thing
rather than giving up. The receipt written by ``demo/review_desk.py`` is what
clears it, and it expires — see :mod:`hooks.review_receipt`.

What is gated, and what deliberately is not
-------------------------------------------
Python under the directories that carry behaviour: ``nestor/``, ``recipes/``,
``demo/``, ``tests/``, ``scripts/``, ``hooks/``. Markdown, JSON, the dogfood
store and everything outside those trees passes untouched — a gate that fires on
a README edit is a gate people disable, and a disabled gate protects nothing.

``demo/review_desk.py`` itself is never gated. Requiring a consultation before
you may edit the consulting tool is a deadlock, and it is the kind that is only
discovered at the worst moment.

Fail closed on its subject, open on its own bugs
------------------------------------------------
A missing or stale receipt blocks: that is the whole point. An exception *inside
this module* allows the write, because a hook that wedges the session when its
own parsing is wrong teaches everyone to delete the hook. The two failure modes
get opposite defaults on purpose.
"""
from __future__ import annotations

import pathlib
import re
from typing import Any

from hooks.review_receipt import is_fresh

#: Directories whose Python carries behaviour worth reviewing before changing.
GATED_DIRS = ("nestor", "recipes", "demo", "tests", "scripts", "hooks")

#: Never gated: the tool that clears the gate, and its receipt helper.
EXEMPT = ("demo/review_desk.py", "hooks/review_receipt.py", "hooks/before_write.py")

WRITE_TOOLS = ("write", "edit", "notebookedit", "multiedit")

_IDEAS_OPEN = re.compile(r"^### (6\.\d+) (.+?) — (.+)$", re.M)


def open_finding_count(root: pathlib.Path) -> int:
    """How many `### 6.N` entries still say open. 0 if unreadable.

    The §6 agent log moved to `docs/agent-log.md`; the §6.N numbers are
    unchanged. Fall back to `IDEAS.md` for a checkout from before the split.
    """
    for rel in ("docs/agent-log.md", "IDEAS.md"):
        try:
            text = (pathlib.Path(root) / rel).read_text(encoding="utf-8")
        except OSError:
            continue
        hits = _IDEAS_OPEN.findall(text)
        if hits:
            return sum(1 for _, _, status in hits if "open" in status.lower())
    return 0


def target_path(payload: dict[str, Any]) -> str:
    tool_input = payload.get("tool_input") or payload.get("arguments") or {}
    if not isinstance(tool_input, dict):
        return ""
    for key in ("file_path", "path", "notebook_path", "filePath"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def is_gated(path: str, root: pathlib.Path) -> bool:
    if not path.endswith(".py"):
        return False
    try:
        rel = pathlib.Path(path).resolve().relative_to(pathlib.Path(root).resolve())
    except (ValueError, OSError):
        return False
    posix = rel.as_posix()
    if posix in EXEMPT:
        return False
    return bool(rel.parts) and rel.parts[0] in GATED_DIRS


def evaluate_write(payload: dict[str, Any], root: pathlib.Path) -> tuple[bool, str, str]:
    """``(allow, user_message, agent_message)`` for one Write/Edit attempt."""
    tool = str(payload.get("tool_name") or payload.get("toolName") or "").lower()
    if not any(t == tool or tool.endswith(t) for t in WRITE_TOOLS):
        return True, "", ""
    path = target_path(payload)
    if not path or not is_gated(path, root):
        return True, "", ""

    fresh, detail = is_fresh(root)
    if fresh:
        return True, "", ""

    rel = path
    try:
        rel = pathlib.Path(path).resolve().relative_to(pathlib.Path(root).resolve()).as_posix()
    except (ValueError, OSError):
        pass
    count = open_finding_count(root)
    agent = (
        f"BLOCKED — {rel} is gated code and the review desk has not been asked "
        f"({detail}).\n"
        f"{count} finding(s) in IDEAS.md are still open. Do not write around this; "
        f"go and look, then write:\n"
        f"  python demo/review_desk.py --home .review load\n"
        f"  python demo/review_desk.py --home .review bearing "
        f"\"<what you are about to change>\"\n"
        f"Consulting the desk records a receipt and this stops blocking. "
        f"See hooks/before_write.py and IDEAS.md §6.12 — gates, not advice."
    )
    user = (f"Write to {rel} blocked: review desk not consulted ({detail}).")
    return False, user, agent
