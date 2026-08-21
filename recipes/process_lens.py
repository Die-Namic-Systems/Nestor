"""Recipe — a measured process observation → the rubric grade it earns.

The README's Matcher-seam table has a row reading *yours / yours / whatever you
can normalize and score*. ``patch_review.py`` is the third recipe built that way;
this is the fourth, and it exists to answer a question asked out loud: does
Nestor subsume `corpus-lens`, or only look as though it might?

    source  = a process measurement over your own session corpus
    target  = the grade that measurement earns against the rubric
    sealed  = a person agreed the measurement earns that grade

Nothing in ``nestor/`` changes. The three states, the hash chain, the one-live-
row rule and the refusal to let a machine confirm are inherited, not
reimplemented — which is the entire argument for doing this here rather than in
a separate tool that has to build all four again and keep them right.

The rubric is `willow-seed/GRADING.md` (ten questions to grade your own system).
The measurements are the shape `corpus-lens` computes: ``steering_density``
(where intent arrives), ``composition_mix`` (who writes the code),
``clarification_pull`` (whether you deliberate on purpose).

---

## The wall, and why it is imported rather than assumed

`corpus-lens` carries a design this package has no equivalent of, and it is the
one thing that does **not** come free with the seam. Its own README states the
reason without softening it:

    A custody schedule was once reconstructed from keystroke timing alone —
    content redaction does not scrub the shape of a week.

So the wall is: **relative time is process; the absolute anchor is person.**
Events carry day offsets and deltas only. The calendar anchor (which real date
is day 0), the timezone, and raw filenames (which embed dates and names) are
quarantined at ingest and released only through a Guard with a granted
capability, an owner token, and a logged justification — fail-closed on every
path.

A ``Matcher`` normalizes and scores. It has no opinion about what the values it
is handed might leak, and it runs long after ingest decided. So the wall cannot
be inherited through the seam the way the ledger is; it has to be enforced at
this recipe's own door. :func:`propose` refuses an observation carrying an
absolute anchor rather than trusting the caller to have stripped one.

That refusal is deliberately dumber than `corpus-lens`'s Guard: it has no
capability grant, no owner token, no audit record. It cannot *release* a
quarantined value, because nothing here should ever hold one. If you need
release, you need the Guard, and that is a port rather than an import.

## Why ``StringMatcher`` is the wrong scorer here

The same argument ``patch_review`` makes for defects, in a different key. A
process observation is a metric name carrying numbers:

    steering_density | sessions=8 total_turns=47 mid_task_share_pct=62.1

difflib over characters would score two *different* metrics written in the same
house style as near-identical, and the same metric measured twice a month apart
as different because the digits moved. Both are backwards. What identifies an
observation is its **metric key**; what varies is the **reading**.

So :class:`ProcessMatcher` splits them: the key must match exactly or the
similarity is zero — two metrics are never each other — and the reading is
compared numerically, with a tolerance, the way ``nestor check`` already
compares an observed value against a baseline.

**One inherited limitation, stated because §6.22 exists.** ``normalize`` returns
the metric key alone, so the store permits one live row per metric. That is the
right rule for "what grade does my steering density earn" and the wrong one if
you ever want per-corpus rows live at once. Give the key a corpus-scoped suffix
before you need that, not after.
"""
from __future__ import annotations

import re
from typing import Any

from nestor import memory
from nestor.memory import ConflictingDraftError

DOMAIN = "process"

#: Metric keys this recipe knows how to read. A key outside this set is not
#: refused — the rubric grows — but it is normalized the same way, so a typo
#: silently becomes its own metric rather than colliding with the real one.
KNOWN_METRICS = frozenset({
    "steering_density",
    "composition_mix",
    "clarification_pull",
})

#: Substrings that mean an absolute anchor rode along. Deliberately crude and
#: deliberately over-broad: a false refusal costs a caller one edit, and a false
#: pass costs the wall. See this module's docstring.
_ANCHOR_MARKERS = (
    "base_date", "local_tz", "timezone", "tzinfo", "iso8601",
    "ref_map", "filename", "file:line",
)

_ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_CLOCK = re.compile(r"\b\d{1,2}:\d{2}(:\d{2})?\b")
_NUM = re.compile(r"-?\d+(?:\.\d+)?")


class WallError(ValueError):
    """An observation carried an absolute anchor. Named for corpus-lens's own.

    Subclasses ``ValueError`` rather than anything in ``nestor`` on purpose:
    this is the recipe's door, not a refusal the store made, and conflating the
    two would hide which guard fired.
    """


class RivalGradeError(RuntimeError):
    """One metric was handed two live grades. Names the two exits."""


def check_wall(observation: str) -> None:
    """Raise :class:`WallError` if ``observation`` carries an absolute anchor.

    Checked: ISO dates, wall-clock times, and the field names corpus-lens
    quarantines. Not checked: everything a determined caller could still smuggle
    through. This is a door, not a proof, and calling it one would be the kind
    of claim this package exists to refuse.
    """
    text = str(observation)
    low = text.lower()
    for marker in _ANCHOR_MARKERS:
        if marker in low:
            raise WallError(
                f"observation names {marker!r}, which is a quarantined field. "
                f"Relative time is process; the absolute anchor is person. Pass "
                f"day offsets and deltas, never a calendar anchor, a timezone, "
                f"or a raw filename.")
    if _ISO_DATE.search(text):
        raise WallError(
            "observation contains an ISO date. day_offset is the representable "
            "form of when; a real date is the anchor and does not belong here.")
    if _CLOCK.search(text):
        raise WallError(
            "observation contains a wall-clock time. delta_prev_s is the "
            "representable form of how long; a clock reading is not.")


def _key_of(value: Any) -> str:
    """The metric key — everything before the first separator, lowercased."""
    head = re.split(r"[|:=]", str(value), maxsplit=1)[0]
    return "_".join(head.split()).strip().lower()


def _readings(value: Any) -> list[float]:
    return [float(m) for m in _NUM.findall(str(value))]


def _agreement(a: list[float], b: list[float], *, pct_tol: float) -> float:
    """1.0 when every reading agrees within tolerance; degrades linearly."""
    if not a or not b or len(a) != len(b):
        return 0.0
    hits = 0
    for x, y in zip(a, b):
        scale = max(abs(x), abs(y), 1e-9)
        if abs(x - y) / scale <= pct_tol:
            hits += 1
    return hits / len(a)


class ProcessMatcher:
    """Metric key is identity; the reading is what varies.

    Satisfies ``nestor.matcher.Matcher``: ``normalize`` + ``similarity``, plus
    the optional ``score`` so :mod:`nestor.memory` compares raw observations and
    ``normalize`` can stay a plain dedup key (IDEAS §3.1).
    """

    def __init__(self, pct_tol: float = 0.05) -> None:
        self.pct_tol = pct_tol

    def normalize(self, value) -> str:
        key = _key_of(value)
        return key or "unkeyed"  # never normalize to empty

    def similarity(self, a_norm: str, b_norm: str) -> float:
        return 1.0 if a_norm == b_norm else 0.0

    def score(self, raw_a, raw_b) -> float:
        if _key_of(raw_a) != _key_of(raw_b):
            return 0.0  # two metrics are never each other
        return _agreement(_readings(raw_a), _readings(raw_b),
                          pct_tol=self.pct_tol)


MATCHER = ProcessMatcher()


def propose(observation: str, grade: str, reason: str = "", *, origin: str = "",
            store=None) -> dict:
    """Propose ``grade`` as what ``observation`` earns. Always a draft.

    There is no ``verifier`` parameter and no way to reach ``status="sealed"``
    from this function. A grade is a reading of a measurement by a person; a
    machine that sealed its own grade would be marking its own homework, which
    is the covenant inverted.

    ``reason`` should carry the denominator — corpus-lens states one per
    analyzer ("operator prompt turns with >=12 characters, de-injected") — because
    a percentage without its denominator is not a measurement.
    """
    check_wall(observation)
    check_wall(grade)
    try:
        return memory.add_pair(observation, grade, DOMAIN, DOMAIN,
                               status="draft", reason=reason, origin=origin,
                               store=store, matcher=MATCHER)
    except ConflictingDraftError as exc:
        raise RivalGradeError(
            f"{_key_of(observation)!r} already holds a different live grade. "
            f"Nestor keeps one live row per normalized source, deliberately. "
            f"Two exits: revise() if this replaces the old reading (the old one "
            f"is kept with its reason), or scope the metric key per corpus if "
            f"both are genuinely live — two corpora graded at once are two "
            f"metrics, not one. There is no third exit."
        ) from exc


def revise(observation: str, grade: str, reason: str, *, origin: str = "",
           store=None) -> dict:
    """Replace the live draft for this metric, keeping the old one as history.

    ``reason`` is required here and optional in :func:`propose` — the same place
    ``patch_review`` is stricter than the package, for the same reason. A
    regrade without a reason throws away the only part worth keeping: what
    changed, the process or the reading of it.
    """
    if not reason.strip():
        raise ValueError(
            "revise() needs a reason. A regrade is a claim that something "
            "moved; which thing moved is the whole content of it.")
    check_wall(observation)
    check_wall(grade)
    return memory.revise_draft(observation, grade, DOMAIN, DOMAIN,
                               reason=reason, origin=origin, store=store,
                               matcher=MATCHER)


def observation(metric: str, **readings: Any) -> str:
    """Format a measurement the way :class:`ProcessMatcher` reads best.

        >>> observation("steering_density", sessions=8, mid_task_share_pct=62.1)
        'steering_density | mid_task_share_pct=62.1 sessions=8'

    Readings are sorted by name so the same measurement formats identically
    whatever order the analyzer emitted them — otherwise ``score`` compares
    readings pairwise against the wrong partners and a stable process looks like
    a moving one.
    """
    key = "_".join(str(metric).split()).strip().lower()
    body = " ".join(f"{k}={readings[k]}" for k in sorted(readings))
    out = f"{key} | {body}" if body else key
    check_wall(out)
    return out
