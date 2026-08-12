"""Session-survival re-injection of Nestor's seat rules (CLI-agnostic).

``hooks/session_start.py`` hands a fresh agent the *whole* seat once, at boot:
the rules, the readiness checks, and the live decision brain. That injection is
load-bearing and it decays. Over a long session the rules slide out of the
window, and a context **compaction** can drop them outright — leaving an agent
that still holds the repo but no longer holds the one rule the repo is built on.

This module re-anchors the *load-bearing* subset — not the whole seat, which
would be latency and noise every turn, but a short, deterministic reminder:

* **propose, don't confirm** — the governance line, quoted from ``hooks/seat.md``;
* **decisions go in the store** — ``docs/dogfood/decisions/`` then a rebuild;
* **consult before you propose** — the ``nestor decision check`` command.

It is a *reminder*, not a re-boot: it never re-runs pytest or the brain
self-test (``session_start`` does that once, and it is not cheap), so it can be
emitted on every ``UserPromptSubmit`` and on ``PreCompact`` without cost. It
reuses ``session_start.repo_root`` / ``seat_path`` / ``BRAIN_DB`` rather than
restating them — a second copy of 'where the store lives' is the drift this
whole repo exists to refuse. And it is **fail-open** the way the boot is: any
failure degrades to one status line, never a traceback that would replace the
agent's prompt turn with a crash.

Clean-room: the pattern (a hook whose stdout becomes injected context) is
reimplemented from the official Claude Code hooks behaviour for
``UserPromptSubmit`` / ``PreCompact``, not lifted from any collection.
"""
from __future__ import annotations

import pathlib

from hooks.session_start import BRAIN_DB, _guard, repo_root, seat_path

#: The load-bearing governance line. A constant, not only a read, for the same
#: reason CLAUDE.md keeps it verbatim in two files and says so: it drifts, and
#: the file it mirrors can be absent at the moment an agent needs the rule most.
#: seat.md is consulted to *verify* this line, never to supply it.
GOVERNANCE = "You may propose. You may not confirm."

#: Hook events this anchor is meant to ride. Both are re-anchor points where the
#: seat may have decayed (a mid-session turn) or is about to be dropped (a
#: compaction); the text is identical because the reminder is not event-specific.
EVENTS = ("UserPromptSubmit", "PreCompact")


def _governance_line(root: pathlib.Path | None) -> str:
    """The propose-don't-confirm rule, verified against ``hooks/seat.md``.

    Returns the rule regardless — it is a constant. seat.md is read only to
    annotate provenance: a missing source is reported (fail-open, the rule still
    lands), and a source that no longer carries the line verbatim is flagged as
    drift rather than silently trusted.
    """
    try:
        text = seat_path(root).read_text(encoding="utf-8")
    except OSError:
        return f"[seat] {GOVERNANCE} (source hooks/seat.md unavailable)"
    suffix = "" if GOVERNANCE in text else " (drift: not verbatim in hooks/seat.md)"
    return f"[seat] {GOVERNANCE}{suffix}"


def anchor(root: pathlib.Path | None = None) -> str:
    """The compact seat anchor — the load-bearing rules, re-emittable every turn.

    Deterministic (same tree in, same text out — no clock, no randomness) and
    fail-open: the one section that touches the filesystem is guarded to a
    status line, so ``anchor()`` never raises. Distilled from three sources the
    seat states in full: the governance line, the decisions-go-in-the-store
    rule, and the ``decision check`` consult command.
    """
    try:
        root = root or repo_root()
    except Exception:  # noqa: BLE001 — resolving the root must never crash a reminder
        root = None
    db = "/".join(BRAIN_DB)
    return "\n".join([
        "[NESTOR ANCHOR] seat rules re-emitted so they survive a long session and a compaction:",
        _guard("seat", lambda: _governance_line(root)),
        "[decisions] Worth keeping? -> docs/dogfood/decisions/, then "
        "`python scripts/dogfood_store.py --rebuild`.",
        f"[brain] Consult before you propose: "
        f"`nestor --db {db} decision check \"<your question>\"` "
        f"(exits non-zero on a recorded rejection or contradiction).",
    ])


def for_event(event: str, root: pathlib.Path | None = None) -> str:
    """Shape the anchor for a named hook event.

    A thin wrapper: the anchor text is the same at every re-anchor point, so
    both ``UserPromptSubmit`` and ``PreCompact`` get it. The event only leads a
    provenance line, so an agent reading its own transcript can tell a
    re-anchor from the one-time boot seat. Always returns non-empty text — an
    unrecognised event is still a re-anchor, not an error.
    """
    lead = event if event in EVENTS else f"{event} (unlisted)"
    return f"[{lead}] {anchor(root)}"
