"""Documents a proposal, not a behaviour: combining marks after NFC.

``StringMatcher.normalize`` NFC-folds, then deletes every character that is
not ``\\w``, whitespace or an So/Sk emoji. Unicode marks (Mn/Mc) are not
``\\w``, so they are deleted. That is harmless for Arabic and Hebrew optional
vowel marks but wrong where marks are required: Hindi vowel signs and virama,
Thai tone marks. Decision 0200's bar is that the store treats a letter the
way the operator sees it. See decision 0255 (draft, uncommitted).

Each test asserts the keys the proposal (marks kept) WOULD give and is
``xfail(strict=True)``: behaviour is unchanged today, and the test flips to a
failure (XPASS) the day someone changes ``normalize``, prompting this file and
decision 0255 to be revisited. Changing ``normalize`` rekeys sealed non-ASCII
rows, so that is the operator's call.
"""
import pytest

from nestor.matcher import StringMatcher

_REASON = "decision 0255 (proposal): normalize deletes Mn/Mc marks after NFC"


def _n(s: str) -> str:
    return StringMatcher().normalize(s)


@pytest.mark.xfail(strict=True, reason=_REASON + "; today 'हिन्दी भाषा' -> 'हनद भष'")
def test_hindi_keeps_vowel_signs_and_virama():
    assert _n("हिन्दी भाषा") == "हिन्दी भाषा"


@pytest.mark.xfail(strict=True, reason=_REASON + "; today 'कि','की','के','का' all -> 'क'")
def test_hindi_different_words_get_different_keys():
    keys = {_n(w) for w in ("कि", "की", "के", "का")}
    assert len(keys) == 4


@pytest.mark.xfail(strict=True, reason=_REASON + "; today both -> 'ไม'")
def test_thai_mai_ek_and_mai_tho_are_distinct():
    # ไม่ "not" vs ไม้ "wood"
    assert _n("ไม่") != _n("ไม้")


@pytest.mark.xfail(strict=True, reason=_REASON + "; today 'ง่าย' -> 'งาย'")
def test_thai_tone_mark_is_kept():
    assert _n("ง่าย") == "ง่าย"
