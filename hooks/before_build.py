"""Anti-rediscovery: surface what's already built, before an agent builds it.

`hooks/before_write.py` makes an agent **consult before editing** a gated file.
This is its sibling for **building**: at the moment a build intent arrives, it
surfaces where to look first, because this fleet's largest documented tax is
rediscovery — rebuilding an organ that already existed and was often better
(`safe-app-store/docs/the-house-already-knew.md` records four in one session).
The lesson that named the gap: *search before you build; the promoted organs are
the first place to look, not the last.* This module is IDEAS §7.2 / issue #105.

It rides **UserPromptSubmit**, the moment before the work starts, and injects a
short reminder into the agent's context — the two-lens survey (what's in the box,
what's on the open internet) plus concrete pointers: the decision store's own
`decision check`, the §7 catalog of shipped parts, and Jeles' `conflict_scan`.

Three properties keep it honest, each learned in this repo:

* **Advisory, not a boundary.** A hook cannot run the survey for an agent or
  stop it from building; it can only name where to look. It says so in its own
  text — *say enforcement or ledger* — so it is never mistaken for a gate. It is
  excluded from `scripts/hook_guard.py`'s blocking-gate proof for that reason.
* **Silent unless it's a build.** A reminder on every turn is latency and noise
  (the mistake `reinject` avoids by staying short); this one emits **nothing**
  unless the prompt reads as *build new thing*, so a status question or a seal
  costs zero.
* **Its one number is derived, not asserted.** The count of recorded decisions
  is read from the tree at emit time, never hardcoded — the drift this whole
  repo refuses.

Clean-room: the UserPromptSubmit-stdout-becomes-context mechanism is the official
Claude Code behaviour (shared with `reinject`); the *discipline* is the fleet's
own "the house already knew" lesson. No text lifted from either.
"""
from __future__ import annotations

import pathlib
import re

from hooks.session_start import BRAIN_DB, _guard, repo_root

#: The hook event this anchor rides — the turn a build request arrives on.
EVENT = "UserPromptSubmit"

#: Build intent, deliberately biased: a missed build (rediscovery) costs far more
#: than an extra advisory line on a false positive, so a strong construction verb
#: fires alone, and the softer verbs (write/add/make/wire) fire only next to a
#: construct noun — never on "add a decision" or "write it down".
_STRONG = r"\b(?:build|create|implement|scaffold|re-?land|stand up)\b"
_CONSTRUCT = (r"(?:hook|skill|script|module|tool|gate|guard|check|feature|"
              r"command|class|function|helper|library|system|endpoint|api|"
              r"parser|matcher|recipe|pipeline|bench|test|wrapper|adapter)s?")
_SOFT = rf"\b(?:write|add|make|wire|set up|design)\b(?:\W+\w+){{0,3}}\W+{_CONSTRUCT}\b"
_BUILD_RX = re.compile(f"(?:{_STRONG})|(?:{_SOFT})", re.IGNORECASE)


def is_build_intent(prompt: str) -> bool:
    """True when the prompt reads as *build a new thing*.

    Kept as a named predicate, not an inline regex, so the prove-it-can-fail
    tests can pin both directions: break it to always-True and the silent-on-a
    -question test goes red; break it to always-False and the fires-on-a-build
    test goes red.
    """
    return bool(prompt) and bool(_BUILD_RX.search(prompt))


def _decision_count(root: pathlib.Path | None) -> str:
    """How many decisions the box already holds — read from the tree, now.

    A hardcoded number here would be the exact stale-count drift IDEAS §4.5
    exists to refuse, so it is globbed at emit time. Fail-open: an unreadable
    tree drops the number, never the reminder.
    """
    root = root or repo_root()
    n = len(list((root / "docs" / "dogfood" / "decisions").glob("*.json")))
    return f"{n} recorded decisions"


def advisory(root: pathlib.Path | None = None) -> str:
    """The before-build reminder — deterministic, fail-open, four short lines."""
    try:
        root = root or repo_root()
    except Exception:  # noqa: BLE001 — resolving the root must never crash a reminder
        root = None
    db = "/".join(BRAIN_DB)
    box = _guard("box", lambda: _decision_count(root))
    return "\n".join([
        "[NESTOR before-build] Reads as a build request. Check what already "
        "exists first — the house has a history of rebuilding what it already had "
        "(safe-app-store/docs/the-house-already-knew.md, issue #105).",
        f"  [box] {box} -> `nestor --db {db} decision check \"<the question "
        f"you're about to answer>\"`; scan IDEAS §7 (shipped standard parts) and "
        f"the §6 log before writing.",
        "  [fleet] Jeles `conflict_scan` — search for what refutes, not what "
        "resembles; willow-mcp `nest/selflearn` clusters. Don't re-land a built organ.",
        "  [both lenses] Survey the box AND the open internet before the first "
        "line; license-gate anything re-landed. Advisory tripwire, not a boundary.",
    ])


def for_prompt(prompt: str, root: pathlib.Path | None = None) -> str:
    """The context to inject for this prompt: the advisory on a build intent,
    the empty string otherwise (which the runner emits as nothing at all)."""
    return advisory(root) if is_build_intent(prompt) else ""
