"""The session-survival anchor — what re-emits the seat's load-bearing rules.

The seat is injected once at boot and decays; ``reinject.anchor()`` re-emits the
subset an agent must not lose (propose-don't-confirm, decisions -> store, the
consult command) cheaply enough to run every turn. These tests assert the rules
are present, that it is genuinely compact (not a second full boot), that it is
fail-open on a missing seat.md, and that it is deterministic — the properties
that make it safe to fire on every ``UserPromptSubmit`` and ``PreCompact``.
"""
from __future__ import annotations

import pathlib

from hooks import reinject
from hooks.reinject import anchor, for_event
from hooks.session_start import build_context

REPO = pathlib.Path(__file__).resolve().parent.parent


def test_anchor_carries_the_load_bearing_rules():
    """The three things an agent must not lose: the governance rule, where
    decisions go, and the command that consults what was already decided."""
    text = anchor(REPO)
    assert "You may propose. You may not confirm." in text
    assert "docs/dogfood/decisions/" in text
    assert 'decision check "<your question>"' in text
    assert "docs/dogfood/nestor.db" in text  # the exact --db the consult uses


def test_anchor_is_compact_not_a_second_boot():
    """A reminder, not a re-boot. It must be far shorter than the full seat
    context — the whole point is to re-anchor without the cost of the boot."""
    text = anchor(REPO)
    assert len(text) < len(build_context(REPO))
    assert len(text) < 700  # a handful of lines, not the seat + checks + brain


def test_anchor_does_not_reboot_the_brain():
    """It must not re-run the boot self-test — no live-retrieval / self-test line
    from session_start leaks in, or it would add that latency every prompt."""
    text = anchor(REPO)
    assert "self-test" not in text
    assert "[check] pytest:" not in text


def test_missing_seat_is_fail_open_not_a_crash(tmp_path):
    """A tree with no hooks/seat.md must degrade to a status line, never raise —
    the anchor rides on the prompt turn and a crash would take the turn down."""
    text = anchor(tmp_path)  # tmp_path has no hooks/seat.md
    assert "source hooks/seat.md unavailable" in text
    # The rule still lands even when its source is gone — it is a constant.
    assert "You may propose. You may not confirm." in text


def test_anchor_is_deterministic():
    """Same tree in, same text out — no clock, no randomness. A reminder that
    varied turn to turn would read as new information every time."""
    assert anchor(REPO) == anchor(REPO)


def test_drift_is_flagged_when_seat_lacks_the_verbatim_line(tmp_path):
    """seat.md present but not carrying the line verbatim is reported as drift,
    not silently trusted — the source is verified, not assumed."""
    (tmp_path / "hooks").mkdir()
    (tmp_path / "hooks" / "seat.md").write_text("no governance line here", encoding="utf-8")
    text = anchor(tmp_path)
    assert "drift: not verbatim in hooks/seat.md" in text


def test_no_drift_flag_against_the_real_seat():
    """The real seat.md carries the line verbatim, so no drift marker appears —
    the guard against a false-positive drift claim."""
    assert "drift:" not in anchor(REPO)


def test_for_event_returns_text_for_both_hook_events():
    """The thin wrapper shapes the anchor for each event it is meant to ride;
    both must come back non-empty and carrying the governance rule."""
    for event in ("UserPromptSubmit", "PreCompact"):
        shaped = for_event(event, REPO)
        assert shaped.strip()
        assert event in shaped
        assert "You may propose. You may not confirm." in shaped


def test_for_event_handles_an_unlisted_event_without_crashing():
    """An unrecognised event is still a re-anchor, not an error — non-empty text
    with the rule intact, flagged as unlisted rather than dropped."""
    shaped = for_event("SomethingElse", REPO)
    assert "unlisted" in shaped
    assert "You may propose. You may not confirm." in shaped


def test_events_tuple_is_the_two_documented_hooks():
    """The wiring targets exactly these two events; a drift here would mean the
    settings.json wiring and the module disagree on where the anchor rides."""
    assert reinject.EVENTS == ("UserPromptSubmit", "PreCompact")
