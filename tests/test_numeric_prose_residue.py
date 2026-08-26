"""NumericMatcher parses prose-containing-a-number as the number.

Observational findings from a Grok-session peer review (2026-08-26) that
walked the numeric edge cases. Every claim here was verified against the
current tree at HEAD before this file landed. None of the tests is a
gate on desired behaviour: they lock the *documented* current behaviour
against silent drift so a future decision to refuse-prose-residue,
require-strict-parse, or add magnitude-suffix awareness can see them
fire.

The design's stated stance (``NumericMatcher.parse_detail`` docstring,
``nestor/matcher.py``): *"USD is decoration, not prose"* and *"Reporting
it beats refusing it: a reconciler that rejected every partially-parsed
figure would refuse real inputs."* The findings below live in the gap
between that stance's intent (unit-suffixed figures should parse) and
what the current heuristic delivers (prose-plus-number also parses).
"""
from __future__ import annotations

import pytest

from nestor.matcher import NumericMatcher


@pytest.fixture
def m() -> NumericMatcher:
    return NumericMatcher(pct_tol=0.05)


# --- Finding 1: prose-plus-number parses as the number ---------------------

@pytest.mark.parametrize("text,expected_value", [
    ("Room 42", 42.0),
    ("the answer is 42", 42.0),
    ("42ish", 42.0),
    ("$42 sandwich", 42.0),
    ("the meeting is in Room 42", 42.0),
])
def test_prose_containing_a_number_parses_as_that_number(m, text, expected_value):
    """A string that contains a number surrounded by prose is parsed as
    the number, exactly as if it had been the bare figure. Verified
    against the current tree; no bug is fixed here — the test locks the
    behaviour so a future refuse-prose-residue decision can find its
    fire signal here."""
    assert m.parse(text) == expected_value


@pytest.mark.parametrize("query_text", [
    "Room 42",
    "the answer is 42",
    "42ish",
    "$42 sandwich",
])
def test_prose_plus_number_similarity_1_against_baseline_42(m, query_text):
    """Consequence of the parse behaviour: a headcount / value baseline
    of 42 scores similarity 1.0 against every one of these prose queries,
    because both sides normalize to the same key ``'42.0'``. In a real
    Reconciler this serves the query as sealed."""
    a_norm = m.normalize(42)
    b_norm = m.normalize(query_text)
    assert a_norm == "42.0"
    assert b_norm == "42.0", (
        f"{query_text!r} normalized to {b_norm!r}; expected '42.0' — "
        f"if this fires, prose-plus-number no longer collapses to the "
        f"bare number, which likely means a fix landed. Check whether "
        f"decision 0203 has been superseded before changing this test.")
    assert m.similarity(a_norm, b_norm) == pytest.approx(1.0)


def test_parse_detail_flags_no_partial_for_prose_residue(m):
    """``parse_detail`` reports ``partial=True`` when residue contains
    digits (a typo like ``1,00o,000``), but ``partial=False`` when
    residue is pure prose. The current ``partial`` flag does not
    distinguish "prose surrounding a number" from "unit suffix"
    (``USD`` reports the same partial=False as ``sandwich``). This is
    the specific gap Grok's Part 3 named."""
    prose = m.parse_detail("Room 42")
    assert prose["value"] == 42.0
    assert prose["residue"] == "Room"
    assert prose["partial"] is False, (
        "the current partial flag only fires on digit residue; a fix "
        "that added a prose_residue field would surface here")

    unit = m.parse_detail("$1,000,000 USD")
    assert unit["value"] == 1_000_000.0
    assert unit["residue"] == "USD"
    assert unit["partial"] is False


# --- Finding 2: magnitude suffix is silently dropped -----------------------

@pytest.mark.parametrize("text,parsed,intended", [
    ("3.90M", 3.9, 3_900_000),
    ("42k", 42.0, 42_000),
    ("1.5B", 1.5, 1_500_000_000),
    ("2T", 2.0, 2_000_000_000_000),
])
def test_magnitude_suffix_is_stripped_not_expanded(m, text, parsed, intended):
    """The letters ``k`` / ``M`` / ``B`` / ``T`` after a number are
    treated as decoration (they end up in residue) rather than as
    magnitude multipliers. Common shorthand where a human wrote ``3.90M``
    meaning three million nine hundred thousand ends up compared as
    ``3.9``. The ``intended`` column is what a human-written figure
    almost certainly means; the ``parsed`` column is what the matcher
    returns today."""
    assert m.parse(text) == parsed
    assert parsed != intended, (
        f"sanity: {text!r} should NOT parse to the intended magnitude "
        f"{intended} today — if it does, magnitude-suffix handling has "
        f"been added and this test should be updated with the new "
        f"expected behavior")


def test_magnitude_shorthand_baseline_vs_query_scores_zero(m):
    """A ``$3M`` baseline and a ``3M`` query score similarity 0, not 1,
    because both parse to 3.0 but the ``$`` and (absent) ``M`` don't
    influence the parsed number — the two agree only because their
    residues happen to be the same length of letters. Same true story:
    the letters are dropped, and the small numbers only match by
    coincidence."""
    baseline = m.normalize("3M")   # 3.0
    query = m.normalize("$3M USD")  # 3.0
    assert baseline == query == "3.0"
    assert m.similarity(baseline, query) == pytest.approx(1.0), (
        "coincidence: both stripped to 3.0 with different residues but "
        "same parsed value; the number 3 is not three million")


# --- Finding 3: date fragmentation -----------------------------------------

@pytest.mark.parametrize("text,parsed", [
    ("2024-08-25", 2024.0),   # hyphen stops the digit run; first int is the year
    ("2024/08/25", 2024.0),   # slash stops the digit run; same story
    ("12/31/2024", 12.0),     # slash stops the digit run; first int is the month
    ("Aug 25, 2024", 252024.0),  # comma is stripped in preclean, so 25 and
                                  # 2024 fuse into a six-digit number that
                                  # is neither the day nor the year — a
                                  # worse finding than the year/month split
])
def test_dates_parse_wrongly_because_they_are_not_numbers(m, text, parsed):
    """A date is not a number, but NumericMatcher extracts a digit run
    anyway. The result depends on which non-digit characters are
    stripped in the preclean pass (``$ , %``/whitespace) and which are
    left in place: hyphens and slashes STOP a digit run, so the first
    integer wins; comma is STRIPPED so any digit-run around it fuses
    into one, and ``"Aug 25, 2024"`` becomes the six-digit number
    ``252024`` — not the day (25), not the year (2024), and not a
    date at all. The Reconciler is for figures, not dates; sealing a
    date as a baseline is a category error today, and this test names
    that boundary so a future date-aware matcher replaces it
    explicitly."""
    assert m.parse(text) == parsed


def test_same_date_two_formats_score_zero_similarity(m):
    """Sealing ``"2024-08-25"`` as a baseline and querying ``"12/31/2024"``
    (the year at the end) scores zero — they parse to different numbers
    (2024 vs 12). A baseline meant to represent a date has no support
    in NumericMatcher today; the Reconciler is for figures, not dates.
    This test locks that boundary so a future date-aware matcher can
    replace this behaviour explicitly."""
    a = m.normalize("2024-08-25")   # 2024
    b = m.normalize("12/31/2024")   # 12
    assert a == "2024.0"
    assert b == "12.0"
    assert m.similarity(a, b) < 0.01


# --- Finding 4: legitimate unit suffixes still work ------------------------
#
# Locked as the counter-case to Finding 1. If a future decision refuses
# prose residue and this test starts failing, the fix has overshot — legitimate
# unit-suffixed figures should still parse.

def test_currency_code_suffix_still_parses(m):
    """``"$1,000,000 USD"`` — the canonical case the design docstring
    names as *"a perfectly ordinary way to write a figure"*. Must
    continue to parse whatever refuse-prose-residue decision lands."""
    assert m.parse("$1,000,000 USD") == 1_000_000.0
    assert m.parse("42 EUR") == 42.0
    assert m.parse("100 GBP") == 100.0


def test_bare_number_parses_unchanged(m):
    """The zero-residue case. Regression check on itself."""
    assert m.parse("42") == 42.0
    assert m.parse("3.14") == 3.14
    assert m.parse("0") == 0.0
    assert m.parse("-17") == -17.0
    assert m.parse("1,000,000") == 1_000_000.0
    assert m.parse("50%") == 50.0
