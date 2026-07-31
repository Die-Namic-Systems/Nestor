"""The stored embedding cache: what may be read back out of it, and when.

Under `SemanticMatcher` the serve decision is taken over embedding vectors, so a
vector read out of `tm_embeddings` is an *input to a serve decision*. A seal
signature covers `(source_norm, target_text, verifier)` and says nothing about
what a row matches — so signing the seal and not the vector would leave a
store-writer able to choose which queries a sealed row answers without forging
anything. `source_text_sha` does not close that: it is a digest of text sitting
in the row next to it, so whoever writes the vector writes the sha.

None of this needs a real model, and it must not: CI has no `fastembed`, and a
test that only runs where the optional extra is installed is not a guard on the
serve path. The model is stubbed; everything below it is the shipped code.
"""

from __future__ import annotations

import hashlib
import os
import warnings

import pytest

from nestor import memory, semantic_matcher, signing
from nestor.embedding_store import source_text_sha, vec_to_blob
from nestor.semantic_matcher import SemanticMatcher

DIMS = 64
MODEL = "stub-model"
# Deliberately unlike any sealed source below: a query whose normalized form
# equals a row's short-circuits to 1.0 in `_scores_against_unlocked` and never
# reaches the model — which is correct, and would make every assertion here
# about the cache vacuous.
QUERY = "an entirely different sentence"


def _vec(text: str) -> tuple[float, ...]:
    """A distinct unit vector per string: cosine is 1.0 with itself, 0.0 with
    anything else. Crisp enough that a poisoned score is unmistakable."""
    i = int.from_bytes(hashlib.sha256(text.encode()).digest()[:4], "big") % DIMS
    return tuple(1.0 if j == i else 0.0 for j in range(DIMS))


class _StubModel:
    def __init__(self) -> None:
        self.embedded: list[str] = []

    def embed(self, texts):
        for t in texts:
            self.embedded.append(t)
            yield _vec(t)


@pytest.fixture
def matcher(monkeypatch):
    """A real SemanticMatcher with the model swapped out."""
    monkeypatch.setattr(semantic_matcher, "_require_fastembed", lambda: None)
    m = SemanticMatcher(model_name=MODEL)
    model = _StubModel()
    m._load_model = lambda: model            # type: ignore[method-assign]
    m.model = model
    return m


@pytest.fixture
def cache_key():
    os.environ["NESTOR_CACHE_KEY"] = "cache-test-key"


def _seal(store, matcher, source="the invoice is overdue",
          target="la factura está vencida") -> dict:
    return memory.add_pair(source, target, "en", "es", status="sealed",
                           verifier="rita", store=store, matcher=matcher)


def _poison(store, pair_id: str, as_text: str, sig: str = "") -> None:
    """Write the vector of ``as_text`` onto ``pair_id``, keeping the sha honest.

    The sha stays correct on purpose — that is the whole point. A tamper check
    that the tamperer can satisfy is not a tamper check.
    """
    row = store.memory_get(pair_id)
    store.embedding_save(pair_id, MODEL, source_text_sha(row["source_text"]),
                         vec_to_blob(_vec(as_text)), sig)


def _score(matcher, store, query: str, rows: list[dict]) -> float:
    return matcher.scores_against_for_rows(query, rows, store)[0]


# --- the blocker ------------------------------------------------------------

def test_a_poisoned_vector_does_not_decide_the_match(store, matcher, seal_key, cache_key):
    """The finding: a store-writer who cannot forge a seal must not be able to
    choose what a sealed row matches."""
    pair = _seal(store, matcher)
    rows = [store.memory_get(pair["id"])]

    assert _score(matcher, store, QUERY, rows) == 0.0     # warms the cache too

    _poison(store, pair["id"], as_text=QUERY)             # unsigned forgery
    matcher._cache.clear()                                # force the store path
    assert _score(matcher, store, QUERY, rows) == 0.0, (
        "a vector that does not verify must be recomputed, not scored")


def test_a_poisoned_vector_signed_with_the_wrong_key_is_refused(store, matcher,
                                                                seal_key, cache_key):
    """Signing it with *a* key is not signing it with *the* key."""
    pair = _seal(store, matcher)
    rows = [store.memory_get(pair["id"])]
    sha = source_text_sha(rows[0]["source_text"])
    blob = vec_to_blob(_vec(QUERY))
    forged = signing.sign_embedding(pair["id"], MODEL, sha, blob, key=b"attacker")

    _poison(store, pair["id"], as_text=QUERY, sig=forged)
    matcher._cache.clear()
    assert _score(matcher, store, QUERY, rows) == 0.0


def test_a_signature_does_not_transfer_between_rows(store, matcher, seal_key, cache_key):
    """`pair_id` and `model_name` are inside the signed message, not only in the
    lookup key — otherwise a legitimately signed entry could be moved onto
    another row, which is the same attack with an extra step."""
    a = _seal(store, matcher, "the invoice is overdue", "la factura está vencida")
    b = _seal(store, matcher, "shipping confirmation attached", "confirmación adjunta")
    rows_b = [store.memory_get(b["id"])]

    # A genuine, correctly signed entry for row A...
    _score(matcher, store, QUERY, [store.memory_get(a["id"])])
    entry = store.embedding_load(a["id"], MODEL)
    assert entry is not None and entry[2], "row A really is signed"

    # ...replayed onto row B, whose text is different. Row B's own sha is used,
    # so only the signature can catch this.
    store.embedding_save(b["id"], MODEL, source_text_sha(rows_b[0]["source_text"]),
                         entry[1], entry[2])
    matcher._cache.clear()
    assert _score(matcher, store, "the invoice is overdue", rows_b) == 0.0


def test_a_genuine_cached_vector_is_used(store, matcher, seal_key, cache_key):
    """The other half — the cache has to actually work, or 'it verifies' is just
    a slow way of saying it is never read."""
    pair = _seal(store, matcher)
    rows = [store.memory_get(pair["id"])]

    first = _score(matcher, store, QUERY, rows)
    assert matcher.model.embedded == [QUERY, rows[0]["source_text"]]
    matcher._cache.clear()

    assert _score(matcher, store, QUERY, rows) == first
    assert matcher.model.embedded == [QUERY, rows[0]["source_text"], QUERY], (
        "only the query was embedded again; the row came back from the store")


def test_with_signing_off_the_cache_is_used_unsigned(store, matcher):
    """Documented policy, pinned in the direction that costs something. With no
    key at all the store is *already* fully trusted — any row in it can claim
    status='sealed' — so requiring a MAC here would protect nothing and cost
    every deployment that never turned signing on."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        pair = _seal(store, matcher)
        rows = [store.memory_get(pair["id"])]
        assert _score(matcher, store, QUERY, rows) == 0.0

        _poison(store, pair["id"], as_text=QUERY)
        matcher._cache.clear()
        assert _score(matcher, store, QUERY, rows) == 1.0
    assert signing.cache_trust() == "unsigned"


def test_a_keyring_with_no_deployment_key_disables_the_cache(store, matcher, tmp_path):
    """Signing on, no deployment-wide key: the store is not trusted and the
    cache cannot be checked, so it is neither read nor written. Slower, never
    wrong — and it says so once."""
    from nestor import embedding_store
    from nestor import keyring as keyring_mod

    ring = keyring_mod.Keyring()
    ring.add("rita")
    keyring_mod.set_keyring(ring)
    assert signing.cache_trust() == "unavailable"

    pair = _seal(store, matcher)
    rows = [store.memory_get(pair["id"])]

    embedding_store._warned_unavailable = False
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        assert _score(matcher, store, QUERY, rows) == 0.0
    assert any("embedding cache is disabled" in str(w.message) for w in caught)
    assert store.embedding_load(pair["id"], MODEL) is None, "nothing was written"


# --- write amplification ----------------------------------------------------

def test_a_warm_cache_writes_nothing(store, matcher, seal_key, cache_key):
    """A cache whose steady state is one UPSERT per row per serve is not a
    cache. This is the read path; `serve --read-only` runs it too."""
    rows = []
    for i in range(5):
        pair = _seal(store, matcher, f"the invoice number {i} is overdue", f"factura {i}")
        rows.append(store.memory_get(pair["id"]))

    matcher.scores_against_for_rows(QUERY, rows, store)   # cold: 5 rows written
    assert all(store.embedding_load(r["id"], MODEL) for r in rows)
    matcher._cache.clear()

    saves = []
    real_save = store.embedding_save
    store.embedding_save = lambda *a, **k: (saves.append(a[0]), real_save(*a, **k))[1]
    matcher.scores_against_for_rows(QUERY, rows, store)
    assert saves == [], "every row was already cached and current"


def test_persist_false_reads_the_cache_but_never_writes_it(store, matcher, monkeypatch,
                                                           seal_key, cache_key):
    """`--read-only` promises no write. A match is a read; the matcher wanting to
    cache something does not change that."""
    monkeypatch.setattr(semantic_matcher, "_require_fastembed", lambda: None)
    pair = _seal(store, matcher)
    rows = [store.memory_get(pair["id"])]

    reader = SemanticMatcher(model_name=MODEL, persist=False)
    model = _StubModel()
    reader._load_model = lambda: model            # type: ignore[method-assign]

    reader.scores_against_for_rows(QUERY, rows, store)
    assert store.embedding_load(pair["id"], MODEL) is None, "a read wrote nothing"

    # ...but a cache someone else wrote is still read.
    matcher.scores_against_for_rows(QUERY, rows, store)
    assert store.embedding_load(pair["id"], MODEL) is not None
    reader._cache.clear()
    before = len(model.embedded)
    reader.scores_against_for_rows(QUERY, rows, store)
    assert len(model.embedded) == before + 1, "only the query"


def test_read_only_serve_does_not_write_embeddings(store, matcher, monkeypatch, seal_key):
    """The flag, not the plumbing: the surface a reader actually passes."""
    from nestor import answer

    monkeypatch.setattr(semantic_matcher, "_require_fastembed", lambda: None)
    built = []

    def _stub_semantic(**kwargs):
        m = SemanticMatcher(model_name=MODEL, **kwargs)
        m._load_model = lambda: _StubModel()      # type: ignore[method-assign]
        built.append(m)
        return m

    monkeypatch.setattr(semantic_matcher, "SemanticMatcher", _stub_semantic)
    answer.build_matcher("semantic", persist=False)
    assert built[0].persist is False
    answer.build_matcher("semantic")
    assert built[1].persist is True


# --- staleness, which the sha does close ------------------------------------

def test_a_stale_vector_is_dropped_not_scored(store, matcher, seal_key, cache_key):
    pair = _seal(store, matcher)
    rows = [store.memory_get(pair["id"])]
    matcher.scores_against_for_rows(QUERY, rows, store)

    # The surface text moved on; the vector belongs to text that is gone.
    with store._db() as conn:
        conn.execute("UPDATE tm_pairs SET source_text=? WHERE id=?",
                     ("the invoice is paid", pair["id"]))
    matcher._cache.clear()
    rows = [store.memory_get(pair["id"])]
    matcher.scores_against_for_rows(QUERY, rows, store)
    entry = store.embedding_load(pair["id"], MODEL)
    assert entry is not None and entry[0] == source_text_sha("the invoice is paid")


def test_rejecting_a_pair_takes_its_cached_vector_with_it(store, matcher,
                                                          seal_key, cache_key):
    """A rejected pair is never scored again, so its vector is dead weight that
    nothing else prunes."""
    pair = _seal(store, matcher)
    matcher.scores_against_for_rows(QUERY, [store.memory_get(pair["id"])], store)
    assert store.embedding_load(pair["id"], MODEL) is not None

    memory.reject_pair(pair["id"], verifier="sam", reason="wrong", store=store)
    assert store.embedding_load(pair["id"], MODEL) is None
