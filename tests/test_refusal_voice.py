"""The sentences a human actually reads when Nestor declines to answer.

By volume Nestor's output *is* refusal. A sealed hit is instant and silent —
that is the success case and nobody reads it. What a curator reads, hundreds of
times, is a machine saying *below the bar*, *nobody has verified this*,
*nothing matched*. `portable._canonical` already carries the argument for why
that matters: "an integrity check that fails on a lossless round-trip trains
people to ignore it, which is worse than not having one." A refusal that reads
as officious trains people to route around it, on the same mechanism.

`_why_not_served` had no tests of its own before this file. What coverage
existed was in `test_findings_2026_08_05.py`, which pins these strings as
*substrings* because the classifier has no other identifier — see the
anti-vacuity test below for what that costs.

**Against the unfixed revision: 1 of 10 failed.** Only the duplicated-count
test is a gate. The other nine are labelled and are **no-regression guards** —
they pass before and after, and they exist because this change rewrites the
sentences they read. None of them would have caught the defect and none is
offered as if it would. That ratio is the honest shape of a change that is
mostly prose: there was one bug, and the rest of the file is scaffolding to
keep the next rewrite from quietly making a refusal stop sounding like one.
"""
from __future__ import annotations

import pytest

from nestor import answer, memory
from nestor.matcher import StringMatcher


def _decision(store, question, commitment, status="draft"):
    return memory.add_pair(question, commitment, "decision", "decision",
                           status=status, verifier="rita" if status == "sealed" else "",
                           store=store)


def _candidates(n: int, top: float):
    """`n` scored rows, best first, none sealed and none servable."""
    return [{"similarity": round(max(0.0, top - i * 0.001), 3), "status": "draft",
             "servable": False, "pair": {"id": f"p{i}"}} for i in range(n)]


def _why(store, candidates, threshold=0.92, text="a question"):
    return answer._why_not_served(store, StringMatcher(), text,
                                  StringMatcher().normalize(text),
                                  "decision", "decision", candidates, threshold)


# ------------------------------------------------------------------ gate ----

class TestTheCountIsReportedOnce:
    """The display-slice note re-reported a number already in the sentence."""

    def test_the_candidate_count_is_not_stated_twice(self, store):
        reason = _why(store, _candidates(20_000, 0.71))
        assert reason.count("20000") == 1, (
            f"the count appears more than once — the display-slice note repeats "
            f"a number the sentence already gave: {reason!r}")

    def test_the_display_slice_is_still_disclosed(self, store):
        """Fixing the duplication must not drop the fact that the reader is
        seeing 8 of 20000. That disclosure is the reason the clause exists."""
        reason = _why(store, _candidates(20_000, 0.71))
        assert "8" in reason, reason

    def test_no_slice_note_when_nothing_is_sliced(self, store):
        reason = _why(store, _candidates(3, 0.11))
        assert "showing" not in reason, reason


# ------------------------------------------------- no-regression guards ----

class TestRangeSafety:
    """**Guards, not gates.** A flat sentence is true across its whole format
    domain; a pointed one need not be. The first draft of the below-threshold
    rewrite read "close enough to be tempting, which is why it is not served" —
    a good sentence, and false at 0.11. These render each branch at both ends of
    its range and assert nothing reads as a lie at either.
    """

    @pytest.mark.parametrize("n,top", [(1, 0.919), (3, 0.11), (20_000, 0.71),
                                       (20_000, 0.0)])
    def test_below_threshold_holds_at_every_score(self, store, n, top):
        reason = _why(store, _candidates(n, top))
        assert f"is {top}, below 0.92" in reason, reason
        # It may not imply the near miss was nearly good enough, because at the
        # bottom of the range it was not.
        for lie in ("tempting", "almost", "nearly", "close enough"):
            assert lie not in reason.lower(), (
                f"{lie!r} is not true at similarity {top}: {reason!r}")

    #: A refusal has to *read* as one. Any rendering of a not-served result must
    #: contain at least one of these — the styling may change, the negation may
    #: not disappear into it.
    NEGATIONS = ("nothing", "not ", "no ", "below", "never", "nobody",
                 "unverified", "rejected", "does not", "suppress")

    def test_every_refusal_says_it_is_one(self, store, seal_key):
        """The persona may style a refusal and may not soften the fact of one.

        This is the guard the `warmth=` knob would have needed and the reason
        there is no knob: a rendering that reads as reassuring while `served` is
        False is the exact lie this package exists not to tell.
        """
        _decision(store, "a drafted question", "a drafted answer")
        sealed = _decision(store, "a rejected question", "a wrong answer",
                           status="sealed")
        memory.reject_pair(sealed["id"], verifier="rita", reason="wrong",
                           store=store)
        # Not the empty string: `match` refuses that before classifying, which
        # is a different contract and not a refusal sentence.
        for query in ("a drafted question", "something absent", "a drafted questio",
                      "a rejected question"):
            result = answer.match(store, query, "decision", "decision")
            assert not result["served"], query
            assert any(n in result["reason"].lower() for n in self.NEGATIONS), (
                f"a refusal for {query!r} contains no negation at all — it reads "
                f"as though something was served: {result['reason']!r}")


class TestTheAssertedPhrasesAreRealSince:
    """**A guard against a specific silent degradation, not against a bug.**

    `test_findings_2026_08_05.py` asserts `"nothing in this domain" not in
    reason` in four places, to prove a rejection is not reported as an absence.
    Reword that branch and all four keep passing while checking nothing — no
    branch emits the phrase, so its absence is free. Four tests would go quietly
    vacuous, which is the failure this repository keeps finding one layer down.

    This pins the phrase itself: it must remain producible by the branch those
    negatives are about.
    """

    def test_the_empty_domain_branch_still_says_nothing_in_this_domain(self, store):
        result = answer.match(store, "anything at all", "nosuch", "nosuch")
        assert not result["served"]
        assert "nothing in this domain" in result["reason"], (
            "four negative assertions elsewhere are pinned to this phrase; "
            "reword the branch and they pass vacuously")

    def test_the_rejected_outright_branch_still_says_rejected_outright(self, store,
                                                                      seal_key):
        pair = _decision(store, "a bad mapping", "a wrong answer", status="sealed")
        memory.reject_pair(pair["id"], verifier="rita", reason="wrong", store=store)
        result = answer.match(store, "a bad mapping", "decision", "decision")
        assert "rejected outright" in result["reason"], result["reason"]
