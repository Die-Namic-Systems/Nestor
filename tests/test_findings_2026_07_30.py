"""Regressions for the three findings of 2026-07-30 (FINDINGS-2026-07-30.md).

Each test was run against the *unfixed* revision first and observed to fail. A
test that passes before the fix is not a gate, it is a description.

  1.5  a forged seal could not serve, but could still be the draft
  1.6  a previously rejected pair halted a bulk seed
  4.5  the README claimed a test count and a refusal the repo had outgrown
"""

import os
import re
import pathlib
import warnings

from conftest import read_ledger
from nestor import engine, memory
from nestor.matcher import StringMatcher
from nestor.sqlite_store import SqliteStore

ROOT = pathlib.Path(__file__).parent.parent


def _forged_row(source, target, verifier="mallory"):
    """A row asserting `sealed` with a signature nobody could have produced."""
    return dict(
        id=f"forged-{source}", source_text=source,
        source_norm=StringMatcher().normalize(source),
        source_lang="en", target_text=target, target_lang="es",
        status="sealed", verifier=verifier, weight=1.0, origin="",
        created_at="2026-07-30T00:00:00+00:00", seal_sig="bogus")


# --------------------------------------------------------------------------
# 1.5 — the forged seal that reached the draft
# --------------------------------------------------------------------------

def test_offline_engine_does_not_draft_from_a_forged_seal():
    """The exact repro from the finding.

    Before the fix this returned 'WIRE FUNDS TO ACCOUNT 9910' while
    `best_sealed` and `_context_pairs` both correctly returned nothing — the
    hardening covered the path that contributes style hints and missed the path
    that copies attacker text verbatim into the first thing a reviewer reads.
    """
    os.environ['NESTOR_SEAL_KEY'] = 'realkey'
    store = SqliteStore(":memory:")
    memory.init_tm(store=store)
    store.memory_insert(_forged_row("the invoice total", "WIRE FUNDS TO ACCOUNT 9910"))

    # The two paths that were already hardened, unchanged.
    assert memory.best_sealed("the invoice total", "en", "es", store=store) is None
    assert engine._context_pairs("the invoice total", "en", "es", store=store) == []

    # The path that was not.
    assert engine.OfflineEngine().translate(
        "the invoice total", "en", "es", store=store) is None


def test_offline_engine_still_drafts_from_a_genuine_draft():
    """The feature the narrow fix had to preserve.

    `verified_sealed` would also have closed 1.5 — by deleting drafts-from-drafts,
    which the README documents. This is the test that makes the difference
    between `verified_sealed` and `without_forged_seals` load-bearing rather
    than a matter of taste.
    """
    os.environ['NESTOR_SEAL_KEY'] = 'realkey'
    store = SqliteStore(":memory:")
    memory.init_tm(store=store)
    memory.add_pair("the invoice total", "el total de la factura", "en", "es",
                    status="draft", store=store)

    draft = engine.OfflineEngine().translate("the invoice total", "en", "es", store=store)
    assert draft is not None
    assert draft.text == "el total de la factura"


def test_a_forged_seal_does_not_deny_service_to_a_real_match():
    """Filtering after `limit=1` would turn a forgery into a denial of service.

    An attacker who cannot make you serve their text should not be able to make
    you serve nothing instead, by planting one row that outranks the real one.
    """
    os.environ['NESTOR_SEAL_KEY'] = 'realkey'
    store = SqliteStore(":memory:")
    memory.init_tm(store=store)
    # The forged row is an exact match; the genuine one is close but not exact,
    # so the forgery ranks first and is removed.
    store.memory_insert(_forged_row("the invoice total", "WIRE FUNDS TO ACCOUNT 9910"))
    memory.add_pair("the invoice totals", "los totales de la factura", "en", "es",
                    status="draft", store=store)

    draft = engine.OfflineEngine().translate("the invoice total", "en", "es", store=store)
    assert draft is not None
    assert draft.text == "los totales de la factura"


# --------------------------------------------------------------------------
# 1.6 — the rejection that halted the load
# --------------------------------------------------------------------------

def _corpus():
    return [
        {"front": "hello", "back": "hola", "lang_front": "en",
         "lang_back": "es", "lesson": "L1"},
        {"front": "goodbye", "back": "adios", "lang_front": "en",
         "lang_back": "es", "lesson": "L1"},
    ]


def test_a_rejected_pair_does_not_halt_the_load(store):
    """Before the fix this raised RejectedPairError and 'goodbye' never landed.

    The docstring's own reasoning for catching conflicts transfers word for
    word: a curated file must not overrule a person, *and must not be able to
    halt the load either.*
    """
    p = memory.add_pair("hello", "hola", "en", "es",
                        status="sealed", verifier="rita", store=store)
    memory.reject_pair(p["id"], verifier="rita", reason="wrong register", store=store)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        written = memory.seed_from_corpus(loader=_corpus, store=store)

    # The rest of the corpus landed.
    assert written > 0
    assert memory.lookup("goodbye", "en", "es", store=store), "'goodbye' never reached the store"

    # And the skip was announced rather than absorbed.
    msg = " ".join(str(w.message) for w in caught)
    assert "previously rejected" in msg


def test_seed_distinguishes_a_rejection_from_a_conflict_in_the_ledger(store):
    """Two different facts about the corpus, kept apart.

    Collapsing them into one ledger `kind` would lose exactly the distinction
    the rejection machinery exists to preserve.
    """
    rejected = memory.add_pair("hello", "hola", "en", "es",
                               status="sealed", verifier="rita", store=store)
    memory.reject_pair(rejected["id"], verifier="rita", reason="wrong register",
                       store=store)
    # A separate phrase a human sealed differently -> conflict, not rejection.
    memory.add_pair("goodbye", "hasta luego", "en", "es",
                    status="sealed", verifier="rita", store=store)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        memory.seed_from_corpus(loader=_corpus, store=store)

    kinds = {e.get("kind") for e in read_ledger()}
    assert "seed_rejected" in kinds
    assert "seed_conflict" in kinds


# --------------------------------------------------------------------------
# 4.5 — the README claims the repo had outgrown
# --------------------------------------------------------------------------

def test_readme_does_not_state_a_stale_test_count():
    """The README quoted 96 in three places while pytest reported 123.

    Deliberately narrow: this asserts the README no longer hardcodes *any*
    bare test count, rather than asserting the current one. A test that pins
    the number would need editing every time a test is added, and would
    re-create the drift it exists to catch.
    """
    text = (ROOT / "README.md").read_text()
    stale = re.findall(r"\b\d{2,4}\s+tests?\b", text)
    assert not stale, f"README hardcodes a test count that will drift: {stale}"


def test_readme_does_not_overstate_the_ledger_refusal():
    """`verify()` is called once per process, so 'never' was too strong.

    Tamper-evidence — the load-bearing property — holds completely; what does
    not hold is the refusal-on-append promise inside one long-lived process.
    A repo that publishes its own false-seal rate should not carry a README
    stronger than its own known limitations.

    Whitespace is collapsed before matching. The first version of this test
    searched for the literal phrase and the README happened to wrap a newline
    between "never" and "launder", so it passed against the unfixed file — a
    test that could not fail, caught only by running it against the revision it
    was written to catch.
    """
    text = " ".join((ROOT / "README.md").read_text().split())
    assert "a new entry can never launder a tampered history" not in text
