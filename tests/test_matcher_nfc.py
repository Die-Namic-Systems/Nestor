"""``StringMatcher.normalize`` NFC-folds before the legacy pipeline.

Composed and decomposed forms of the same visible word must produce the
same normalized key. Without NFC folding, combining diacritics are
non-``\\w`` characters and get stripped by the ``re.sub(r"[^\\w\\s]")``
pass, silently producing a different key from what the operator sees on
screen — the exact failure mode that would bite a ``--seed policy-vi``
or ``--seed policy-ar`` fixture where source text is often decomposed.

Every test here is paired with a **must-preserve** assertion for a
distinction NFC does NOT touch. The seat rule is that any invariant the
tree used to guarantee stays guaranteed under the new pipeline; the pairs
make that explicit. In particular:

* Cyrillic ``а`` (U+0430) must stay distinct from Latin ``a`` (U+0061).
  That's a homoglyph question, not a composition question — PR 180's
  ``test_homoglyph_pair_creates_distinct_entries`` locks it and this
  file's ``test_cyrillic_a_is_still_distinct_from_latin_a`` reads the
  same invariant through the ``normalize`` seam.
* Fullwidth digits stay fullwidth (NFKC would fold them; NFC does not).
* Pure-emoji strings still normalize to ``""``. NFC does not change
  that — the emoji-collapse question from PR 180 is a separate decision
  and this PR deliberately does not touch it.

7-bit ASCII text must produce byte-for-byte the same key as before this
change; NFC on ASCII is a no-op and the pipeline downstream is
unchanged, but the invariant is asserted so a future edit that regresses
it fails visibly.
"""
from __future__ import annotations

import unicodedata

import pytest

from nestor import memory
from nestor.matcher import StringMatcher


@pytest.fixture
def m() -> StringMatcher:
    return StringMatcher()


# --- the fix ---------------------------------------------------------------

def test_vietnamese_u_horn_composed_and_decomposed_collide(m):
    """``người`` typed with U+01B0 vs typed as ``u`` + U+031B — the two
    forms a keyboard and a paste from PDF respectively produce. Before
    NFC folding, the combining horn is stripped and the second form
    normalizes to ``nguời`` (no horn on the u), which is a different key
    from the first. This is the load-bearing multilingual case for
    hand-off item 5's ``--seed policy-vi``."""
    composed = "Người tốt."
    decomposed = unicodedata.normalize("NFD", composed)
    assert composed != decomposed, (
        "sanity: NFD form must differ from NFC form as bytes, otherwise "
        "this test is not exercising the composition question at all")
    assert m.normalize(composed) == m.normalize(decomposed)


def test_cafe_composed_and_decomposed_collide(m):
    """``café`` composed (é as U+00E9) vs decomposed (e + U+0301). The
    classic latin-1 vs NFD split — same visible word, historically two
    different keys.

    The two forms are constructed via ``unicodedata.normalize`` rather
    than typed as string literals, because most editors save source
    files as NFC and would silently make both literals identical (which
    the sanity assertion below catches — that failure has fired here
    before)."""
    composed = unicodedata.normalize("NFC", "café")
    decomposed = unicodedata.normalize("NFD", "café")
    assert composed != decomposed, (
        "sanity: NFD form must differ from NFC form as bytes, otherwise "
        "this test is not exercising the composition question at all")
    assert m.normalize(composed) == m.normalize(decomposed)


def test_arabic_with_diacritic_composed_and_decomposed_collide(m):
    """Arabic ``ي`` with fatha above. Same story: the diacritic is a
    combining codepoint that gets stripped by ``[^\\w\\s]`` unless it's
    NFC-folded into the letter first."""
    composed = unicodedata.normalize("NFC", "يَ")
    decomposed = unicodedata.normalize("NFD", "يَ")
    assert m.normalize(composed) == m.normalize(decomposed)


def test_normalize_is_idempotent(m):
    """``normalize(normalize(x)) == normalize(x)`` for every input this
    file exercises. Documented in the Matcher Protocol docstring; NFC
    itself is idempotent, and the legacy pipeline was, so the
    composition of them must be."""
    for x in ["Người tốt.", "café", "café",
              "The agreement enters into force on ratification.",
              "aɣa", "🌍", "aaa", "ааа"]:
        once = m.normalize(x)
        assert m.normalize(once) == once


# --- what must NOT change --------------------------------------------------

def test_cyrillic_a_is_still_distinct_from_latin_a(m):
    """PR 180's ``test_homoglyph_pair_creates_distinct_entries`` locks
    that Cyrillic ``а`` (U+0430) and Latin ``a`` (U+0061) create
    distinct sealed rows. NFC does not fold homoglyphs — it folds
    composition — so this invariant must survive the change. If it ever
    stops surviving, this file has been changed at the same time as a
    confusable-folding step slipped in, and both tests should be
    read together before landing."""
    assert m.normalize("aaa") != m.normalize("ааа")


def test_fullwidth_digits_are_not_folded(m):
    """``１２３`` (fullwidth) stays distinct from ``123`` (ASCII). NFKC
    would fold them; NFC does not. PR 180's
    ``test_fullwidth_vs_ascii_digits`` asserts they score below 1.0;
    this asserts the normalization step itself does not collapse them,
    which is the seam that would break the PR 180 test."""
    assert m.normalize("item 123") != m.normalize("item １２３")


def test_pure_emoji_still_normalizes_to_empty(m):
    """PR 180's ``test_emoji_only_story_normalizes_to_empty`` and
    ``test_single_emoji_all_normalize_to_empty`` lock that pure-emoji
    strings normalize to ``""`` and therefore collide on the empty key.
    NFC does not change that — emoji are non-``\\w`` regardless of
    composition — and this PR deliberately does not touch the emoji
    question. If a later PR wants to address it, this test's failure is
    the signal the invariant is moving and a new decision is needed."""
    assert m.normalize("🌍") == ""
    assert m.normalize("❤️") == ""


def test_ascii_normalizes_byte_for_byte_as_before(m):
    """For 7-bit ASCII, NFC is a no-op and the downstream pipeline is
    unchanged. Every sealed row that existed before this PR must
    normalize to the exact same key it normalized to before, or the
    change is silently invalidating stored data."""
    cases = [
        "The agreement enters into force on ratification.",
        "public consultation is required",
        "IBM",
        "q3-revenue",
        "hello world",
        "",
        "   spaces   collapse   ",
    ]
    for text in cases:
        assert m.normalize(text) == memory._norm(text), (
            f"memory._norm wrapper diverged from StringMatcher.normalize "
            f"on {text!r}")
        # And the specific legacy pipeline output for the trivially-scoped
        # cases, so a future refactor of the pipeline breaks this test
        # rather than silently changing keys.
    assert m.normalize("hello world") == "hello world"
    assert m.normalize("   spaces   collapse   ") == "spaces collapse"
    assert m.normalize("q3-revenue") == "q3revenue"


# --- integration through memory --------------------------------------------

def test_add_pair_folds_composed_and_decomposed_source_to_the_same_key(m, tmp_path):
    """The end-to-end shape a user sees: seal a translation typed
    composed, ask with the same sentence typed decomposed, and get the
    sealed hit. Before this PR the ask returned nothing because the
    decomposed query normalized to a different key.
    """
    from nestor import cascade
    from nestor.sqlite_store import SqliteStore

    cascade.set_ledger_path(str(tmp_path / "ledger.jsonl"))
    cascade._verified_ledgers.clear()
    cascade._checkpoints.clear()
    store = SqliteStore(":memory:")
    store.init_db()
    store.memory_init()

    composed = "Người tốt."
    decomposed = unicodedata.normalize("NFD", composed)
    memory.add_pair(composed, "A good person.", "vi", "en",
                    status="sealed", verifier="test-verifier",
                    origin="test-nfc", store=store)

    hit = memory.best_sealed(decomposed, "vi", "en", store=store)
    assert hit is not None, (
        "seal in composed form, ask in decomposed form — this is what a "
        "keyboard user typing and a PDF paste both look like, and the "
        "cascade must find the sealed row for either")
    assert hit["pair"]["target_text"] == "A good person."
