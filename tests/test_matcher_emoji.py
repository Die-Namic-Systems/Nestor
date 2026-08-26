"""``StringMatcher.normalize`` preserves emoji through the strip pass.

Decision 0202 replaced the pre-fix behaviour PR #180 filed as an
observational finding: pure-emoji strings normalized to ``""`` because
emoji are not ``\\w`` characters, so any two emoji-only rows collided
on the empty key (and any second seal in the same domain raised
``ConflictingSealError``). The fix preserves Unicode symbol categories
``So`` (Symbol, other — most emoji) and ``Sk`` (Symbol, modifier —
skin-tone modifiers, keycap-like glyphs) through the strip pass, so
distinct emoji key distinctly.

Every test here is paired with a **must-preserve** assertion for a
distinction the fix does NOT touch. The seat rule: any invariant the
tree used to guarantee stays guaranteed unless a decision explicitly
retires it, and the pairs make that explicit. In particular:

* Currency (``$``, ``€``), math (``×``, ``÷``) and punctuation stay
  stripped. Categories ``Sc``/``Sm``/``P*``/``C*`` are not preserved.
  Baselines like ``"$4.20B"`` still normalize as they did.
* Cyrillic ``а`` stays distinct from Latin ``a``. Same homoglyph
  question as in ``test_matcher_nfc.py``; the strip pass does not fold
  confusables.
* 7-bit ASCII text normalizes byte-for-byte as before.

PR #180's two locked emoji tests
(``tests/test_unconventional.py::test_emoji_only_stories_key_distinctly_after_0202``
and ``test_single_emoji_seal_distinctly_after_0202``) have been rewritten
in place against the new invariant; this file adds the round-trip and
edge-case coverage.
"""
from __future__ import annotations

import pytest

from nestor import cascade, memory
from nestor.matcher import StringMatcher
from nestor.sqlite_store import SqliteStore


@pytest.fixture
def m() -> StringMatcher:
    return StringMatcher()


def _fresh_store(tmp_path) -> SqliteStore:
    cascade.set_ledger_path(str(tmp_path / "ledger.jsonl"))
    cascade._verified_ledgers.clear()
    cascade._checkpoints.clear()
    store = SqliteStore(":memory:")
    store.init_db()
    store.memory_init()
    return store


# --- the fix ---------------------------------------------------------------

def test_pure_emoji_is_preserved_not_stripped(m):
    """Single emoji keys must produce a non-empty ``normalize`` output
    — before decision 0202 this was ``""``, which collided every emoji
    row in a store."""
    for emoji in ["🌍", "🚀", "❤", "💡", "🎉", "🐻"]:
        assert m.normalize(emoji) != "", (
            f"emoji {emoji!r} must not collapse to empty after 0202")


def test_distinct_emoji_key_distinctly(m):
    """Every pair of distinct emoji must produce distinct ``normalize``
    keys — the direct inverse of the pre-0202 collision behaviour."""
    seen: dict[str, str] = {}
    for emoji in ["🌍", "🚀", "❤", "💡", "🎉", "🐻", "🐶", "🌟"]:
        norm = m.normalize(emoji)
        assert norm not in seen, (
            f"emoji {emoji!r} normalized to {norm!r}, which already keys "
            f"{seen[norm]!r} — two emoji must not share a normalize output")
        seen[norm] = emoji


def test_multi_emoji_string_preserves_all_of_them(m):
    """A story told in emoji keeps every codepoint through normalize.
    Order matters (``\U0001f680\U0001f31f`` ≠ ``\U0001f31f\U0001f680``)."""
    assert m.normalize("🚀🌟") == "🚀🌟"
    assert m.normalize("🌟🚀") == "🌟🚀"
    assert m.normalize("🚀🌟") != m.normalize("🌟🚀")


def test_zwj_sequence_survives(m):
    """A zero-width-joiner sequence like ``👨‍💻`` (man + ZWJ + computer)
    is three codepoints that render as one glyph. ZWJ (U+200D) is
    category ``Cf`` (Format), which the strip pass removes — so the
    sequence normalizes to man+computer without the joiner, which is
    the compositional shape. The key point: it does NOT collapse to
    empty, and two different ZWJ sequences remain distinct."""
    dev = m.normalize("👨‍💻")
    baker = m.normalize("👨‍🍳")
    assert dev != "", "ZWJ sequence must not collapse to empty"
    assert baker != ""
    assert dev != baker


def test_skin_tone_modifier_is_preserved(m):
    """Skin-tone modifiers (U+1F3FB–U+1F3FF) are category ``Sk``
    (Symbol, modifier), which is one of the two categories the fix
    preserves. A waving hand with each of the five tones keys
    distinctly."""
    base = "👋"
    tones = ["👋\U0001F3FB", "👋\U0001F3FC", "👋\U0001F3FD",
             "👋\U0001F3FE", "👋\U0001F3FF"]
    keys = {m.normalize(base)} | {m.normalize(t) for t in tones}
    assert len(keys) == 6, (
        f"base wave + five skin-tone waves must produce six distinct "
        f"keys; got {len(keys)}: {keys}")


def test_interspersed_emoji_keys_distinctly_from_letters_only(m):
    """Grok's peer-review test matrix: ``a🔥b`` must not normalize the
    same way as ``ab``. Before the fix these collided (both → ``ab``);
    after, ``a🔥b`` keeps the fire in the middle."""
    assert m.normalize("a🔥b") == "a🔥b"
    assert m.normalize("ab") == "ab"
    assert m.normalize("a🔥b") != m.normalize("ab")


def test_emoji_with_text_keeps_both(m):
    """Text + emoji surface — the shape a policy-shaped seed uses if
    it ever ships emoji-decorated aliases or baselines."""
    assert m.normalize("hello 🌍 world") == "hello 🌍 world"
    # Case-folding still applies to the letter portion.
    assert m.normalize("Hello 🌍 World") == "hello 🌍 world"
    # Whitespace still collapses.
    assert m.normalize("  hello   🌍   world  ") == "hello 🌍 world"


def test_normalize_is_idempotent_on_emoji(m):
    """``normalize(normalize(x)) == normalize(x)`` for every emoji
    input this file exercises. The Matcher Protocol requires it, and a
    strip pass that produced a different result on its own output would
    silently break every dedup path."""
    for x in ["🌍", "🚀", "❤", "hello 🌍 world", "🚀🌟", "story: 🐻🌲"]:
        once = m.normalize(x)
        assert m.normalize(once) == once


# --- what must NOT change --------------------------------------------------

def test_currency_symbol_is_still_stripped(m):
    """``$``, ``€``, ``£`` are Unicode category ``Sc`` (Symbol, currency).
    The fix preserves ``So``/``Sk`` only, so currency stays stripped and
    baselines like ``"$4.20B"`` normalize as they did before this PR."""
    assert m.normalize("$4.20B") == "420b"
    assert m.normalize("€4.20B") == "420b"
    assert m.normalize("£4.20B") == "420b"


def test_math_symbol_is_still_stripped(m):
    """``×``, ``÷``, ``±``, ``≠`` are Unicode category ``Sm`` (Symbol,
    math). The fix does not preserve them — a currency demo written by
    someone using ``×`` for a multiplier still normalizes to the digits
    alone, matching pre-fix behaviour."""
    assert m.normalize("4 × 20 = 80") == "4 20 80"


def test_infinity_symbol_still_collapses_to_empty(m):
    """``∞`` (U+221E, category ``Sm``) is a good illustrative case
    raised in the mid-turn peer review from a Grok session that reached
    the same diagnosis (see decision 0202's "why so narrow" note).
    Under the narrow fix, a pure-``∞`` source STILL collapses to ``""``
    just like it did before, and two ``∞``-only rows in the same domain
    would still collide. This test locks that limitation so a later PR
    that widens to ``Sm`` or refuses-empty-norms sees this test fire and
    knows a decision has to move first."""
    assert m.normalize("∞") == "", (
        "the narrow fix intentionally does not preserve Sm (math) "
        "symbols; widening to include them is a separate deferred "
        "decision named in 0202. If ∞ starts preserving, this test "
        "fires — check whether the widening was decided-on before "
        "changing normalize.")
    assert m.normalize("∞") == m.normalize("∞∞"), (
        "and two ∞-only strings still collide on empty until either "
        "(a) Sm is preserved or (b) empty-norm seals are refused")


def test_punctuation_is_still_stripped(m):
    """Every ``P*`` category (Po, Pc, Pd, Ps, Pe, Pi, Pf) stays
    stripped — the fix only reached the symbol categories."""
    assert m.normalize("hello, world!") == "hello world"
    assert m.normalize("q3-revenue") == "q3revenue"
    assert m.normalize("she said 'hi'") == "she said hi"


def test_cyrillic_a_is_still_distinct_from_latin_a(m):
    """PR #180's ``test_homoglyph_pair_creates_distinct_entries`` locks
    that Cyrillic а (U+0430) and Latin a (U+0061) create distinct sealed
    rows. The strip-pass change does not touch confusable folding, so
    this invariant must survive."""
    assert m.normalize("aaa") != m.normalize("ааа")


def test_ascii_normalizes_byte_for_byte_as_before(m):
    """7-bit ASCII gets no emoji, no combining marks, no symbols. The
    output for ASCII text must be exactly what the pre-fix pipeline
    produced, or the change is silently rekeying every sealed row."""
    assert m.normalize("The agreement enters into force on ratification.") == \
        "the agreement enters into force on ratification"
    assert m.normalize("hello world") == "hello world"
    assert m.normalize("") == ""
    assert m.normalize("   spaces   collapse   ") == "spaces collapse"


# --- integration through memory --------------------------------------------

def test_add_pair_keys_two_emoji_stories_distinctly(tmp_path):
    """End-to-end: seal two emoji-only stories, then retrieve each.
    Before decision 0202 the second seal raised ``ConflictingSealError``
    (both keyed to the same empty ``source_norm``); now each stores and
    retrieves under its own key."""
    store = _fresh_store(tmp_path)

    boy_forest = "🐻🌲👦"
    rocket_star = "🚀🌟💫"

    memory.add_pair(boy_forest, "A boy met a bear in the forest",
                    "emoji", "en", status="sealed",
                    verifier="test-verifier", origin="test-emoji",
                    store=store)
    memory.add_pair(rocket_star, "A rocket to a star",
                    "emoji", "en", status="sealed",
                    verifier="test-verifier", origin="test-emoji",
                    store=store)

    hit1 = memory.best_sealed(boy_forest, "emoji", "en", store=store)
    hit2 = memory.best_sealed(rocket_star, "emoji", "en", store=store)
    assert hit1 is not None and hit2 is not None
    assert hit1["pair"]["target_text"] == "A boy met a bear in the forest"
    assert hit2["pair"]["target_text"] == "A rocket to a star"


def test_existing_prose_pair_still_serves_at_same_confidence(tmp_path):
    """Grok's peer-review test matrix: a sealed prose pair must still
    serve after this change with the same behaviour it had before. If
    the strip pass silently rekeyed prose rows, every seal in every
    deployed store would need re-migration — the change would be a
    breaking one.
    """
    store = _fresh_store(tmp_path)
    src = "The agreement enters into force on ratification."
    tgt = "El acuerdo entra en vigor tras la ratificación."
    memory.add_pair(src, tgt, "en", "es", status="sealed",
                    verifier="test-verifier", origin="test-prose",
                    store=store)

    # Verbatim serve
    hit = memory.best_sealed(src, "en", "es", store=store)
    assert hit is not None, "verbatim query must serve"
    assert hit["pair"]["target_text"] == tgt
    assert hit["similarity"] == 1.0, (
        f"verbatim query must serve at similarity 1.0; got "
        f"{hit['similarity']} — the strip pass rekeyed prose")

    # Casefolded + punctuation-varied serve (still handled by the strip)
    hit2 = memory.best_sealed(
        "the agreement enters into force on ratification",
        "en", "es", store=store)
    assert hit2 is not None, (
        "casefolded + no-period query must serve at 1.0 — this is what "
        "the strip pass exists for and it must not regress")
    assert hit2["similarity"] == 1.0
