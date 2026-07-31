import pytest

from nestor.matcher import Matcher, NumericMatcher, StringMatcher


# --- StringMatcher: must reproduce the historical translation behavior -------

def test_string_normalize_matches_legacy_norm():
    m = StringMatcher()
    # lowercase, strip punctuation, collapse whitespace, strip ends.
    assert m.normalize("  Hello,  WORLD!! ") == "hello world"
    assert m.normalize("Amazon.com  Inc.") == "amazoncom inc"


def test_string_similarity_equal_is_one_else_difflib():
    import difflib
    m = StringMatcher()
    assert m.similarity("gato", "gato") == 1.0
    a, b = "the weather is nice", "the weather is bad"
    assert m.similarity(a, b) == difflib.SequenceMatcher(None, a, b).ratio()


def test_string_matcher_satisfies_protocol():
    assert isinstance(StringMatcher(), Matcher)
    assert isinstance(NumericMatcher(), Matcher)


# --- NumericMatcher: parsing -------------------------------------------------

def test_numeric_normalize_parses_decorated_values():
    m = NumericMatcher()
    assert m.normalize("$1,250.50") == repr(1250.5)
    assert m.normalize("42%") == repr(42.0)
    assert m.normalize(1000) == repr(1000.0)
    assert m.normalize(3.14) == repr(3.14)
    assert m.normalize("  -7 ") == repr(-7.0)
    assert m.normalize("1.2e3") == repr(1200.0)


def test_numeric_non_parseable_never_matches():
    m = NumericMatcher()
    junk = m.normalize("not a number")
    assert m.similarity(junk, m.normalize("100")) == 0.0
    # even two non-parseables never score a match.
    assert m.similarity(junk, m.normalize("also junk")) == 0.0
    # bool is not treated as a figure.
    assert m.similarity(m.normalize(True), m.normalize("1")) == 0.0


# --- NumericMatcher: tolerance + smooth decay --------------------------------

def test_numeric_within_pct_tolerance_is_one():
    m = NumericMatcher(pct_tol=0.05)          # within 5%
    a, b = m.normalize(100), m.normalize(104)  # 4% off
    assert m.similarity(a, b) == 1.0


def test_numeric_at_tolerance_edge_is_one():
    m = NumericMatcher(pct_tol=0.05)
    a, b = m.normalize(100), m.normalize(105)  # exactly 5%
    assert m.similarity(a, b) == 1.0


def test_numeric_outside_tolerance_decays_smoothly():
    import math
    m = NumericMatcher(abs_tol=0.0, pct_tol=0.05)
    # 100 vs 110: tol = 0.05*110 = 5.5, diff = 10 -> exp(-(10-5.5)/5.5).
    s110 = m.similarity(m.normalize(100), m.normalize(110))
    assert s110 == pytest.approx(math.exp(-(10 - 5.5) / 5.5))
    # 100 vs 120: tol = 6.0, diff = 20 -> smaller than s110 (monotone decay).
    s120 = m.similarity(m.normalize(100), m.normalize(120))
    assert s120 == pytest.approx(math.exp(-(20 - 6.0) / 6.0))
    assert s120 < s110
    # far away -> approaches 0.
    assert m.similarity(m.normalize(100), m.normalize(100000)) < 0.001


def test_numeric_abs_tol_governs_when_larger():
    import math
    m = NumericMatcher(abs_tol=10.0, pct_tol=0.0)  # +/- 10 absolute
    assert m.similarity(m.normalize(50), m.normalize(59)) == 1.0   # within 10
    # diff 20, tol 10 -> exp(-(20-10)/10) = exp(-1).
    assert m.similarity(m.normalize(50), m.normalize(70)) == pytest.approx(math.exp(-1))


def test_numeric_zero_baseline_exact():
    m = NumericMatcher(abs_tol=0.0, pct_tol=0.05)
    assert m.similarity(m.normalize(0), m.normalize(0)) == 1.0


# --- NumericMatcher: what the parse had to ignore (IDEAS 1.9) ----------------

def test_parse_detail_reports_a_dropped_digit():
    m = NumericMatcher()
    d = m.parse_detail("1,00o,000")
    assert d["value"] == 100.0 and d["matched"] == "100"
    assert d["residue"] == "o000" and d["partial"] is True

    d = m.parse_detail("12/31/2024")
    assert d["value"] == 12.0 and d["partial"] is True


def test_parse_detail_does_not_flag_currency_or_units():
    m = NumericMatcher()
    for text in ("$1,000,000 USD", "42%", "  -7 ", "1.2e3", "12.5 kg"):
        assert m.parse_detail(text)["partial"] is False, text


def test_parse_detail_agrees_with_parse_and_covers_the_no_number_case():
    m = NumericMatcher()
    for value in ("$1,250.50", 1000, 3.14, True, "", None, "not a number", "1,00o,000"):
        assert m.parse_detail(value)["value"] == m.parse(value)
    d = m.parse_detail("not a number")
    assert d["value"] is None and d["partial"] is False, "nothing compared, nothing dropped"
