import pytest

from nestor import memory
from nestor.matcher import Matcher, NumericMatcher, StringMatcher, match_similarity
from nestor.sqlite_store import SqliteStore


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


# --- score(raw) seam (IDEAS §3.1) -------------------------------------------

def test_match_similarity_prefers_score_over_norms():
    class _Split:
        def normalize(self, value):
            return "key"

        def similarity(self, a_norm, b_norm):
            return 0.0

        def score(self, raw_a, raw_b):
            return 0.88

    m = _Split()
    assert match_similarity(m, "query", "key", "stored", "key") == 0.88


def test_match_similarity_blank_stored_text_falls_back_to_norms():
    class _ScoreOnly:
        def normalize(self, value):
            return "k"

        def similarity(self, a_norm, b_norm):
            return 0.42

        def score(self, raw_a, raw_b):
            return 0.99

    m = _ScoreOnly()
    assert match_similarity(m, "q", "k", "   ", "k") == 0.42
    assert match_similarity(m, "q", "k", "", "k") == 0.42


def test_lookup_uses_score_when_present():
    store = SqliteStore(":memory:")

    class _FixedScore:
        def normalize(self, value):
            return "key"

        def similarity(self, a_norm, b_norm):
            return 0.1

        def score(self, raw_a, raw_b):
            return 0.95

    memory.add_pair("stored surface", "answer", "en", "es", status="sealed",
                    verifier="rita", store=store, matcher=StringMatcher())
    hits = memory.lookup("query surface", "en", "es", store=store,
                         matcher=_FixedScore())
    assert hits[0]["similarity"] == 0.95


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


# --- what the seam must preserve, with or without an embedding model ---------
#
# The behaviours below arrived with SemanticMatcher, and testing them only
# through SemanticMatcher means testing them only where fastembed is installed —
# which CI is not. They are properties of the seam, so they are exercised here
# with a matcher shaped like SemanticMatcher (lexical norm for dedup, a raw
# score for comparison) and no model to load.

class ScoreMatcher(StringMatcher):
    """StringMatcher plus a raw ``score``, mirroring SemanticMatcher's contract."""

    def __init__(self, other: float = 0.3, batch: bool = True) -> None:
        super().__init__()
        self._other = other
        self.batch_calls = 0
        if not batch:
            self.scores_against = None      # type: ignore[assignment]

    def score(self, raw_a, raw_b) -> float:
        if self.normalize(raw_a) == self.normalize(raw_b):
            return 1.0
        return self._other

    def scores_against(self, query_text, stored_texts):
        self.batch_calls += 1
        return [self.score(query_text, s) for s in stored_texts]


def _seal(store, source="Good evening.", target="Buenas noches.", matcher=None):
    return memory.add_pair(source, target, "en", "es", status="sealed",
                           verifier="rita", store=store, matcher=matcher)


def test_a_retype_still_serves_under_a_score_matcher(store):
    """The headline promise — right forever after, *including when it is retyped
    differently* — is a short-circuit on equal normalized forms. `score()`
    bypasses `similarity`, so the seam has to keep it or the promise becomes a
    property of whatever metric the matcher happens to use."""
    m = ScoreMatcher()
    _seal(store, matcher=m)
    retyped = "GOOD  evening!!"
    assert m.normalize(retyped) == m.normalize("Good evening.")

    hit = memory.best_sealed(retyped, "en", "es", store=store, matcher=m)
    assert hit is not None and hit["similarity"] == 1.0
    assert memory.lookup(retyped, "en", "es", store=store, matcher=m)[0]["similarity"] == 1.0


def test_a_score_matcher_warns_that_the_threshold_was_not_measured_for_it(store):
    """0.92 was measured for a character ratio. Under another metric it means
    something else, and this package says so rather than serving quietly."""
    import warnings

    m = ScoreMatcher()
    _seal(store, matcher=m)
    memory._warned_score_threshold = False
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        memory.best_sealed("Good evening.", "en", "es", store=store, matcher=m)
    assert any("SEAL_THRESHOLD" in str(w.message) for w in caught)

    # Once per process, not once per serve.
    with warnings.catch_warnings(record=True) as again:
        warnings.simplefilter("always", RuntimeWarning)
        memory.best_sealed("Good evening.", "en", "es", store=store, matcher=m)
    assert not any("SEAL_THRESHOLD" in str(w.message) for w in again)


def test_lookup_batches_when_the_matcher_can(store):
    m = ScoreMatcher()
    _seal(store, matcher=m)
    memory.lookup("Good evening.", "en", "es", store=store, matcher=m)
    assert m.batch_calls == 1, "one call for the candidate set, not one per row"


def test_lookup_and_best_sealed_agree_on_a_row_with_no_surface_text(store):
    """A row with no source_text has nothing to take a raw score over, so
    `match_similarity` answers it from the stored norms. The batch path has to
    reach the same answer.

    `lookup` is what the reviewer and the engine see; `best_sealed` is the serve
    decision. Score one row by two different rules and it can be *missing from
    the candidate list while still being served* — which is the same "one rule,
    two paths in" shape as the defects in TODO.md's closing note.
    """
    m = ScoreMatcher()
    query = "the invoice is overdue"
    # The shape a bundle import or a CSV round-trip can land: the norm survived,
    # the surface text did not.
    store.memory_insert({
        "id": "surfaceless", "source_text": "", "source_norm": m.normalize(query),
        "source_lang": "en", "target_text": "la factura está vencida",
        "target_lang": "es", "status": "sealed", "verifier": "rita",
        "weight": 1.0, "origin": "", "created_at": "2026-07-31T00:00:00+00:00",
        "seal_sig": "",
    })

    served = memory.best_sealed(query, "en", "es", store=store, matcher=m)
    ranked = memory.lookup(query, "en", "es", store=store, matcher=m)

    assert served is not None and served["similarity"] == 1.0
    assert [h["pair"]["id"] for h in ranked] == ["surfaceless"], (
        "the row best_sealed serves must be in the list the reviewer sees")
    assert ranked[0]["similarity"] == served["similarity"]
