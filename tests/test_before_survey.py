"""before_survey is the finding-not-asserting advisory — it fires on a fan-out
survey and stays silent on everything else, and it never blocks.

The pair of directions is the whole guard, same as ``before_build``: a detector
that always fired would be noise on nearly every turn (reading is the most
common thing an agent does), one that never fired would be the over-claiming it
exists to catch. So both are pinned — break ``is_survey_intent`` either way and
exactly one of these goes red.

The narrow-read direction carries more weight here than it does for
``before_build``, and the asymmetry is deliberate: a missed build costs a
rebuilt organ, a missed survey costs a sentence a human usually catches, and a
false positive on "review this function" would train the reader to skip the
line. That is why breadth is required and why half these cases are negative.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess

from hooks.before_survey import advisory, for_prompt, is_survey_intent

REPO = pathlib.Path(__file__).resolve().parent.parent


def test_fires_on_fan_out_surveys():
    for prompt in ("audit how it's wired up across all the repos",
                   "survey the whole box",
                   "go through every module in the fleet",
                   "map the corpus",
                   "compare all the trust models in this codebase",
                   "look at each of the 27 repos and tell me what's there",
                   "review the entire suite"):
        assert is_survey_intent(prompt), prompt
        assert for_prompt(prompt, REPO), prompt


def test_silent_on_narrow_reads_and_ordinary_turns():
    """Breadth is required — reading one thing is not a fan-out survey."""
    for prompt in ("review this function",
                   "look at corpus.py",
                   "why did that test fail?",
                   "audit the seal on decision 0219",
                   "trace this stack",
                   "seal it",
                   "build a new clustering module",
                   ""):
        assert not is_survey_intent(prompt), prompt
        assert for_prompt(prompt, REPO) == "", prompt


def test_the_advisory_carries_the_sealed_rule_and_both_error_classes():
    text = advisory(REPO)
    assert "1878ea86" in text                    # the sealed decision, cited
    assert "FINDING, not for ASSERTING" in text  # its commitment, in its words
    assert "decision check" in text              # the box's own consult command
    assert "the-house-already-knew" in text      # the retraction it points at
    assert "non-" in text.lower() and "independent" in text.lower()
    assert "not a boundary" in text              # named honestly — a tripwire


def test_the_count_is_derived_from_the_tree_not_asserted():
    """The one number in the advisory must match the decisions on disk now."""
    actual = len(list((REPO / "docs" / "dogfood" / "decisions").glob("*.json")))
    assert f"{actual} recorded decisions" in advisory(REPO)


def test_the_wired_hook_injects_on_a_survey_prompt_and_nothing_otherwise():
    survey = _run({"prompt": "audit every repo on this box"})
    assert survey.returncode == 0, survey.stderr
    payload = json.loads(survey.stdout)
    assert payload["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "before-survey" in payload["hookSpecificOutput"]["additionalContext"]

    quiet = _run({"prompt": "seal the oldest decision"})
    assert quiet.returncode == 0, quiet.stderr
    assert quiet.stdout.strip() == ""     # nothing injected on a non-survey turn


def test_prompt_submit_carries_the_survey_advisory_alongside_its_siblings():
    """The consolidated action must not drop the newest evaluator.

    ``prompt_submit`` is the wiring that actually runs in a session; a module
    reachable only by its own name would never fire in practice.
    """
    result = _run({"prompt": "survey all the repos and build a new hook"},
                  module="prompt_submit")
    assert result.returncode == 0, result.stderr
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "before-survey" in context
    assert "before-build" in context      # siblings are joined, not exclusive


def test_before_survey_is_a_known_module_but_not_a_blocking_gate():
    import sys

    from hooks.hook_runner import MODULES
    assert "before_survey" in MODULES
    sys.path.insert(0, str(REPO / "scripts"))
    import hook_guard
    assert "before_survey" not in hook_guard.BLOCKING


def _run(payload: dict, module: str = "before_survey") -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(REPO / "hooks" / "nestor-hook"), "claude", module],
        input=json.dumps(payload), capture_output=True, text=True,
        cwd=REPO, timeout=60,
        env={**os.environ, "NESTOR_PROJECT_ROOT": str(REPO)}, check=False)
