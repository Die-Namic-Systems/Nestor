"""``memory.add_pair`` refuses a pair whose ``source_norm`` is ``""``.

Decision 0204 (Grok Direction C, named as deferred in 0202 Q3): every
input that ever normalizes to the empty string shares the same key, so a
store that accepts empty-norm rows treats its per-domain uniqueness
constraint as last-writer-wins. This bench locks the refusal at the
boundary — sealed or draft, with any matcher, from any surface — and
locks the ``override_empty_norm=True`` escape hatch so a caller who
genuinely wants an empty-norm row can pass through explicitly.

The collision-prone class as of this PR:

* Pure punctuation (``"..."``, ``"!!!"``, ``"???"``) — Unicode ``P*``
  categories, stripped by :class:`StringMatcher`.
* Math symbols (``"∞"``, ``"×"``, ``"±"``) — category ``Sm``, deliberately
  not preserved by decision 0202's narrow ``So``/``Sk`` widening.
* Pure whitespace after strip.

Every one of these normalized to ``""`` before this PR; every seal or
draft of them now raises :class:`EmptyNormError`.
"""
from __future__ import annotations

import pytest

from nestor import cascade, memory
from nestor.memory import EmptyNormError
from nestor.sqlite_store import SqliteStore


def _fresh_store(tmp_path):
    cascade.set_ledger_path(str(tmp_path / "ledger.jsonl"))
    cascade._verified_ledgers.clear()
    cascade._checkpoints.clear()
    store = SqliteStore(":memory:")
    store.init_db()
    store.memory_init()
    return store


# --- the refusal ------------------------------------------------------------

@pytest.mark.parametrize("source_text", [
    "...",         # pure Po (punctuation)
    "!!!",         # pure Po
    "???",         # pure Po
    "∞",           # pure Sm (math)
    "× ± ÷",       # pure Sm, whitespace
    "   ",         # pure whitespace
    "",            # empty string
    "$$$",         # pure Sc (currency, not preserved)
])
def test_seal_with_empty_norm_source_raises(tmp_path, source_text):
    """A sealed pair whose ``source_text`` normalizes to ``""`` under
    the default :class:`StringMatcher` raises :class:`EmptyNormError`
    before any store write. Every one of these inputs collapses to the
    empty key today; sealing any of them would put them all under the
    same ``source_norm``."""
    store = _fresh_store(tmp_path)
    with pytest.raises(EmptyNormError):
        memory.add_pair(source_text, "some target", "en", "es",
                        status="sealed", verifier="test-verifier",
                        origin="test-empty-norm", store=store)


@pytest.mark.parametrize("source_text", ["...", "!!!", "∞", "$$$", "", "   "])
def test_draft_with_empty_norm_source_raises(tmp_path, source_text):
    """Drafts refuse for the same reason: the collision-prone key is
    the danger, and it doesn't care about sealing state. A draft under
    ``""`` blocks a later legitimate seal from taking that slot the
    same way a sealed one does."""
    store = _fresh_store(tmp_path)
    with pytest.raises(EmptyNormError):
        memory.add_pair(source_text, "some target", "en", "es",
                        status="draft", store=store)


def test_error_message_names_the_source_and_the_matcher(tmp_path):
    """The refusal has to be clear enough for a caller to figure out
    what to do. The message names the offending source_text and the
    matcher class so a debugger doesn't have to spelunk to see which
    matcher's strip pass produced the empty."""
    store = _fresh_store(tmp_path)
    with pytest.raises(EmptyNormError) as info:
        memory.add_pair("...", "target", "en", "es",
                        status="sealed", verifier="v", store=store)
    msg = str(info.value)
    assert "'...'" in msg or repr("...") in msg
    assert "StringMatcher" in msg
    assert "override_empty_norm" in msg


# --- the override ----------------------------------------------------------

def test_override_empty_norm_lets_caller_through(tmp_path):
    """A caller with a specific reason to store an empty-norm row can
    pass ``override_empty_norm=True`` and take responsibility for the
    collision themselves. The row is written; the escape hatch is
    named in the error message so a caller who sees the refusal knows
    the path forward."""
    store = _fresh_store(tmp_path)
    pair = memory.add_pair("...", "puntos suspensivos", "en", "es",
                           status="sealed", verifier="test-verifier",
                           origin="test-empty-norm",
                           override_empty_norm=True, store=store)
    assert pair["source_norm"] == ""
    assert pair["target_text"] == "puntos suspensivos"


def test_override_still_collides_on_the_empty_key(tmp_path):
    """The override does NOT paper over the underlying collision — it
    just makes the collision the caller's problem, not the guard's.
    Two empty-norm seals in the same domain still contest the same
    source_norm and the second one raises the ordinary
    ``ConflictingSealError`` (or overwrites, depending on verifier
    identity — same rule as any other pair)."""
    store = _fresh_store(tmp_path)
    memory.add_pair("...", "puntos suspensivos", "en", "es",
                    status="sealed", verifier="alice",
                    override_empty_norm=True, store=store)
    # Second override, different target, different verifier — collides.
    from nestor.memory import ConflictingSealError
    with pytest.raises(ConflictingSealError):
        memory.add_pair("!!!", "excitement", "en", "es",
                        status="sealed", verifier="bob",
                        override_empty_norm=True, store=store)


# --- what must NOT change --------------------------------------------------

def test_ordinary_prose_still_seals(tmp_path):
    """Real translation content still seals. Refuse-empty-norm targets
    only the empty-key class; everything with a non-empty norm goes
    through unchanged."""
    store = _fresh_store(tmp_path)
    pair = memory.add_pair(
        "The agreement enters into force on ratification.",
        "El acuerdo entra en vigor tras la ratificación.",
        "en", "es", status="sealed", verifier="test-verifier",
        origin="test", store=store)
    assert pair["source_norm"] == "the agreement enters into force on ratification"


def test_pure_emoji_still_seals_after_0202(tmp_path):
    """Decision 0202 made pure-emoji strings normalize to a non-empty
    key (So/Sk preservation). This test asserts they still seal
    end-to-end — emoji pass BOTH the 0202 preservation AND the 0204
    empty-norm refusal, because their key is now ``"🌍"`` (non-empty),
    not ``""``."""
    store = _fresh_store(tmp_path)
    pair = memory.add_pair("🌍", "the world",
                           "emoji", "en", status="sealed",
                           verifier="test-verifier",
                           origin="test", store=store)
    assert pair["source_norm"] == "🌍"


def test_currency_symbol_still_stripped_from_prose(tmp_path):
    """``"$4.20B"`` still normalizes to ``"420b"`` (currency stripped,
    per PR #217's narrow-scope decision). It has a non-empty norm,
    so refuse-empty-norm does not touch it."""
    store = _fresh_store(tmp_path)
    pair = memory.add_pair("$4.20B", "the price",
                           "money", "en", status="sealed",
                           verifier="test-verifier",
                           origin="test", store=store)
    assert pair["source_norm"] == "420b"
