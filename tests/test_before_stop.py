"""The Stop gate: a completion claim has to be backed by a quoted run.

These pin the behaviours the guard must have, and — per Nestor doctrine, a guard
that cannot be shown to fail has not been shown to work — the behaviours it must
*not* have. Each test attempts one shape and names itself for it.

The advisory / deny boundary is the load-bearing design choice, so it is made
explicit and tested from both sides:

* a **soft** claim without evidence ("fixed it") → ALLOW, but a non-empty
  reminder (advisory — surfaced, never trapping)
* a **hard** claim without evidence ("all tests pass") → DENY once
* the same hard claim once we have already fired (``stop_hook_active``) →
  downgraded to ALLOW + reminder, so the turn can end and no loop forms
* a claim *with* a quoted run → ALLOW clean (no reminder)
* no completion claim at all → ALLOW clean
* the message text cannot be found → FAIL OPEN (allow, empty messages)

Driven through :func:`evaluate_stop` directly — it is pure over a payload and a
root — plus the text-extraction helper, which is where the payload-shape
defensiveness lives.
"""
from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from hooks.before_stop import evaluate_stop, final_assistant_text


def stop_of(text, **extra) -> dict:
    payload = {"hook_event_name": "Stop", "last_message": text}
    payload.update(extra)
    return payload


def test_soft_claim_without_evidence_is_flagged_advisory():
    """'fixed it' with no run → allow, but a non-empty reminder is surfaced."""
    allow, user, agent = evaluate_stop(stop_of("Done — I fixed the bug."), REPO)
    assert allow, "the soft case must not trap the session"
    assert agent, "a soft claim without evidence must still surface a reminder"
    assert "derived from the tree" in agent
    assert not user


def test_hard_all_tests_pass_claim_without_evidence_is_denied_once():
    """A sweeping 'all tests pass' with zero evidence is the one worth blocking."""
    allow, user, agent = evaluate_stop(stop_of("All tests pass, we're good to ship."), REPO)
    assert not allow, "a hard claim with no evidence should block"
    assert user and agent
    assert "evidence" in agent.lower()


def test_hard_claim_downgrades_to_advisory_after_first_block():
    """stop_hook_active means we already fired — do not trap the turn in a loop."""
    payload = stop_of("All tests pass.", stop_hook_active=True)
    allow, user, agent = evaluate_stop(payload, REPO)
    assert allow, "the block fires once; a re-fire downgrades to advisory"
    assert agent, "still worth a reminder even when we no longer block"
    assert not user


def test_claim_with_quoted_run_is_allowed_clean():
    """A claim backed by a quoted command and its outcome passes with no reminder."""
    text = "All tests pass — ran `pytest -q` → 1011 passed in 4.2s."
    allow, user, agent = evaluate_stop(stop_of(text), REPO)
    assert allow
    assert not user and not agent, "evidence present → no reminder at all"


def test_file_line_and_exit_code_count_as_evidence():
    """pytest file:line and an exit code are evidence even without 'N passed'."""
    text = "Fixed. See nestor/memory.py:42; the check returned exit code 0."
    allow, _, agent = evaluate_stop(stop_of(text), REPO)
    assert allow
    assert not agent


def test_message_with_no_completion_claim_is_allowed_clean():
    """No done/fixed/passing/green language → nothing to gate."""
    text = "Here is a summary of the options; let me know which direction you prefer."
    allow, user, agent = evaluate_stop(stop_of(text), REPO)
    assert allow
    assert not user and not agent


def test_missing_message_text_fails_open():
    """No recoverable final text → allow, empty messages (open on our own gap)."""
    allow, user, agent = evaluate_stop({"hook_event_name": "Stop"}, REPO)
    assert allow
    assert not user and not agent


def test_non_dict_payload_fails_open():
    """A payload that is not even a dict must not wedge the turn."""
    allow, user, agent = evaluate_stop(None, REPO)  # type: ignore[arg-type]
    assert allow
    assert not user and not agent


def test_final_text_extracted_from_messages_list():
    """The last assistant turn is found in a messages[] list, not just last_message."""
    payload = {
        "messages": [
            {"role": "user", "content": "please fix it"},
            {"role": "assistant", "content": "Done — all tests pass."},
        ]
    }
    assert "all tests pass" in final_assistant_text(payload).lower()
    allow, _, agent = evaluate_stop(payload, REPO)
    assert not allow, "the claim in the extracted text should still be gated"
    assert agent


def test_final_text_extracted_from_content_blocks():
    """A content list of {'type':'text','text':...} blocks flattens to text."""
    payload = {
        "last_message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "everything is green"}],
        }
    }
    assert "green" in final_assistant_text(payload).lower()


def test_word_boundaries_avoid_false_positives():
    """'completeness' or 'undone' must not read as a completion claim."""
    text = "I documented the completeness criteria; this work is undone and ongoing."
    allow, user, agent = evaluate_stop(stop_of(text), REPO)
    assert allow
    assert not user and not agent, "substring matches must not trip the guard"
