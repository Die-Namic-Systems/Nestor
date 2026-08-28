"""A survey is licensed to find, not to assert.

``hooks/before_build.py`` asks *what already exists* before an agent builds.
This is its sibling for the turn a **fan-out survey** arrives on, and it exists
because that hook is deliberately silent on anything that is not build-shaped —
so a session can read the whole box, reach conclusions that were already sealed,
and never trip a single advisory. That happened: an operator ran a 27-repo,
8-org survey on 2026-08-28 and the model asserted five findings that decision
``1878ea86`` had already settled, plus a "pattern" the fleet had measured and
retracted three weeks earlier. No build-shaped prompt was ever issued, so
``before_build`` correctly stayed quiet the entire time.

The rule it should have carried is already sealed — ``1878ea86``, verified by a
human 2026-08-12:

    "What is a fan-out survey actually good for, given the error rate?"
    "Finding, not asserting. The claims about this box ... were sound and cost
    minutes to confirm because the evidence is on disk. Every claim about the
    outside world needed independent checking."

**Fan-out, not any reading.** The predicate deliberately requires a survey verb
*and* a breadth marker, which is the opposite bias from ``before_build``'s. A
missed build costs a rebuilt organ; a missed survey costs an over-claimed
sentence a human usually catches. Reading is also the single most common thing
an agent does, so a detector that fired on "review this function" would be noise
on most turns and would train the reader to skip it — the failure ``reinject``
avoids by staying short. ``1878ea86`` is about fan-out specifically, so the
predicate is too.

Three properties carried over from ``before_build``, on purpose:

* **Advisory, not a boundary.** It cannot make anyone verify anything; it names
  what the difference between finding and asserting costs. Excluded from
  ``scripts/hook_guard.py``'s blocking-gate proof for the same reason.
* **Silent unless it reads as a fan-out survey.** A single-file read, an
  ordinary question, or a build costs nothing.
* **Its one number is derived, not asserted** — read from the tree at emit
  time via ``before_build._decision_count``, never hardcoded.

Clean-room: the UserPromptSubmit-stdout-becomes-context mechanism is the
official Claude Code behaviour (shared with ``reinject`` and its two siblings);
the discipline is this repository's own sealed decision. No text lifted from
either.
"""
from __future__ import annotations

import os
import pathlib
import re

from hooks.before_build import _decision_count
from hooks.session_start import BRAIN_DB, _guard, repo_root

#: The hook event this anchor rides — the turn the survey is asked for.
EVENT = "UserPromptSubmit"

#: A verb that reads as *go and look across things*.
_LOOK = (r"\b(?:audit|survey|sweep|inventor(?:y|ie[sd])|catalogue|catalog|"
         r"map|scan|trace|review|compare|analy[sz]e|assess|examine|"
         r"go through|look (?:at|through|over|into)|read through|"
         r"walk through|dig (?:in|into|through))\b")

#: Breadth. Without one of these the verb is an ordinary reading task, and this
#: advisory has nothing to say about reading one file.
_BREADTH = (r"\b(?:all|every|each|across|everything|entire|whole|both|"
            r"repos?|repositor(?:y|ies)|orgs?|organi[sz]ations?|fleet|"
            r"codebase|corpus|box|machine|system|suite|tree|"
            r"\d+\s+(?:repos?|repositor(?:y|ies)|orgs?|files?|modules?))"
            # Not when the word is really a filename: `corpus.py` and `box.md`
            # are one thing to read, and "look at corpus.py" is the narrow case
            # this advisory must stay quiet on. A trailing extension disqualifies
            # the token; `corpus_store` never matched, since `_` is a word char
            # and leaves no boundary to close on.
            r"(?![\w-]*\.[A-Za-z]{1,5}\b)\b")

_SURVEY_RX = re.compile(rf"(?=.*{_LOOK})(?=.*{_BREADTH})", re.IGNORECASE | re.DOTALL)


def is_survey_intent(prompt: str) -> bool:
    """True when the prompt reads as *go look across many things*.

    Requires a survey verb AND a breadth marker, in either order — the two
    lookaheads scan the whole prompt rather than demanding adjacency, so "audit
    how it's wired up, across all the repos" fires and "audit this function"
    does not.

    Kept as a named predicate, not an inline regex, so the prove-it-can-fail
    tests can pin both directions: break it to always-True and the
    silent-on-a-narrow-read test goes red; break it to always-False and the
    fires-on-a-fan-out test goes red.
    """
    return bool(prompt) and bool(_SURVEY_RX.search(prompt))


#: The consolidated household corpus, when this box has one. A fan-out survey
#: asks about the *box*, and the box's memory is here — 24 repositories of
#: extracted claims plus the sealed pairs — where ``BRAIN_DB`` is nestor's own
#: development record. Preferred when it exists, and the reason this advisory
#: names a different store from ``before_build``'s.
_HOUSEHOLD_DB = pathlib.Path.home() / ".nestor" / "keep" / "nestor.db"


def _store_to_consult(root: pathlib.Path | None) -> str:
    """An **absolute** path to the store a reader should actually open.

    ``BRAIN_DB`` is repo-relative, which is correct for a reminder emitted
    inside this checkout and wrong everywhere else: run from any other
    directory, ``nestor --db docs/dogfood/nestor.db`` names nothing, and a
    suggested command that does not resolve is worse than no suggestion —
    it reads as a path the reader failed to find rather than one that was
    never there. This advisory is the one that rides a *box-wide* seat, so
    it must be true from any cwd.

    ``$NESTOR_DB`` wins when set, because a seat that has been pointed at a
    particular store has already answered this question.
    """
    override = os.environ.get("NESTOR_DB", "").strip()
    if override:
        return str(pathlib.Path(override).expanduser())
    if _HOUSEHOLD_DB.is_file():
        return str(_HOUSEHOLD_DB)
    if root is not None:
        return str(root.joinpath(*BRAIN_DB))
    return "/".join(BRAIN_DB)


def advisory(root: pathlib.Path | None = None) -> str:
    """The before-survey reminder — deterministic, fail-open, four short lines."""
    try:
        root = root or repo_root()
    except Exception:  # noqa: BLE001 — resolving the root must never crash a reminder
        root = None
    db = _guard("db", lambda: _store_to_consult(root)) or "/".join(BRAIN_DB)
    box = _guard("box", lambda: _decision_count(root))
    return "\n".join([
        ("[NESTOR before-survey] Reads as a fan-out survey. A survey is good for "
         "FINDING, not for ASSERTING — decision 1878ea86, sealed 2026-08-12."),
        (f"  [box] {box}. Claims about this box are cheap to confirm because the "
         f"evidence is on disk — confirm them before stating them: `nestor --db "
         f"{db} decision check \"<the claim you're about to make>\"`."),
        ("  [outside] Every claim about the outside world needs independent "
         "checking. Separate instances of one base model are presumed NON-"
         "independent, so agreement across your own passes is not corroboration."),
        ("  [already known] Before concluding a pattern, check it is not one the "
         "box already measured and retracted — safe-app-store-public/docs/the-house-"
         "already-knew.md. Advisory tripwire, not a boundary."),
    ])


def for_prompt(prompt: str, root: pathlib.Path | None = None) -> str:
    """The context to inject for this prompt: the advisory on a survey intent,
    the empty string otherwise (which the runner emits as nothing at all)."""
    return advisory(root) if is_survey_intent(prompt) else ""
