"""Property-based tests for the normalizer, matcher, and signing surfaces.

IDEAS §7.5 names these three as where property tests earn their keep:
round-trips, invariants under permutation, and domain separation.
"""

from __future__ import annotations

import json
import math

import pytest

hypothesis = pytest.importorskip("hypothesis")
given = hypothesis.given
settings = hypothesis.settings
st = hypothesis.strategies

from nestor.matcher import NumericMatcher, StringMatcher
from nestor.signing import (
    _edge_message,
    _embedding_message,
    _message,
    _rejection_message,
)

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Text that exercises the normalizer: unicode, punctuation, whitespace.
any_text = st.text(min_size=0, max_size=200)
nonempty_text = st.text(min_size=1, max_size=200)

# Finite floats only — NaN/inf break numeric comparison by design.
finite_floats = st.floats(allow_nan=False, allow_infinity=False)


# ---------------------------------------------------------------------------
# §1  Normalizer properties
# ---------------------------------------------------------------------------


class TestStringMatcherNormalize:
    sm = StringMatcher()

    @given(text=any_text)
    def test_idempotent(self, text: str) -> None:
        once = self.sm.normalize(text)
        twice = self.sm.normalize(once)
        assert once == twice

    @given(text=any_text)
    def test_deterministic(self, text: str) -> None:
        assert self.sm.normalize(text) == self.sm.normalize(text)

    @given(text=any_text)
    def test_output_is_lowercase_alnum_and_spaces(self, text: str) -> None:
        norm = self.sm.normalize(text)
        for ch in norm:
            assert ch.isalnum() or ch == " " or ch == "_"

    @given(text=any_text)
    def test_no_leading_or_trailing_whitespace(self, text: str) -> None:
        norm = self.sm.normalize(text)
        assert norm == norm.strip()

    @given(text=any_text)
    def test_no_consecutive_spaces(self, text: str) -> None:
        norm = self.sm.normalize(text)
        assert "  " not in norm


class TestNumericMatcherNormalize:
    nm = NumericMatcher()

    @given(n=finite_floats)
    def test_idempotent_on_repr(self, n: float) -> None:
        norm = self.nm.normalize(repr(n))
        again = self.nm.normalize(norm)
        assert norm == again

    @given(n=finite_floats)
    def test_round_trip_preserves_value(self, n: float) -> None:
        norm = self.nm.normalize(repr(n))
        assert norm != "__NAN__"
        assert float(norm) == n


# ---------------------------------------------------------------------------
# §2  Matcher properties
# ---------------------------------------------------------------------------


class TestStringMatcherSimilarity:
    sm = StringMatcher()

    @given(a=nonempty_text, b=nonempty_text)
    def test_symmetric(self, a: str, b: str) -> None:
        na, nb = self.sm.normalize(a), self.sm.normalize(b)
        assert self.sm.similarity(na, nb) == self.sm.similarity(nb, na)

    @given(text=nonempty_text)
    def test_self_similarity_is_one(self, text: str) -> None:
        n = self.sm.normalize(text)
        if n:
            assert self.sm.similarity(n, n) == 1.0

    @given(a=nonempty_text, b=nonempty_text)
    def test_score_in_unit_interval(self, a: str, b: str) -> None:
        na, nb = self.sm.normalize(a), self.sm.normalize(b)
        score = self.sm.similarity(na, nb)
        assert 0.0 <= score <= 1.0

    @given(a=nonempty_text, b=nonempty_text)
    def test_bound_is_upper_bound(self, a: str, b: str) -> None:
        na, nb = self.sm.normalize(a), self.sm.normalize(b)
        score = self.sm.similarity(na, nb)
        bound = self.sm.similarity_bound(na, nb)
        assert bound >= score or math.isclose(bound, score, abs_tol=1e-12)


class TestNumericMatcherSimilarity:
    nm = NumericMatcher()

    @given(a=finite_floats, b=finite_floats)
    def test_symmetric(self, a: float, b: float) -> None:
        na, nb = repr(a), repr(b)
        assert self.nm.similarity(na, nb) == self.nm.similarity(nb, na)

    @given(n=finite_floats)
    def test_self_similarity_is_one(self, n: float) -> None:
        norm = repr(n)
        assert self.nm.similarity(norm, norm) == 1.0

    @given(a=finite_floats, b=finite_floats)
    def test_score_in_unit_interval(self, a: float, b: float) -> None:
        score = self.nm.similarity(repr(a), repr(b))
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# §3  Signing — frozen encoding properties
# ---------------------------------------------------------------------------


class TestSigningDeterminism:
    @given(src=any_text, tgt=any_text, ver=any_text)
    def test_seal_message_deterministic(self, src: str, tgt: str, ver: str) -> None:
        assert _message(src, tgt, ver) == _message(src, tgt, ver)

    @given(q=any_text, pid=any_text, tgt=any_text, ver=any_text)
    def test_rejection_message_deterministic(
        self, q: str, pid: str, tgt: str, ver: str
    ) -> None:
        assert _rejection_message(q, pid, tgt, ver) == _rejection_message(
            q, pid, tgt, ver
        )

    @given(src=any_text, dst=any_text, kind=any_text)
    def test_edge_message_deterministic(
        self, src: str, dst: str, kind: str
    ) -> None:
        assert _edge_message(src, dst, kind) == _edge_message(src, dst, kind)

    @given(
        pid=any_text,
        model=any_text,
        sha=any_text,
        blob=st.binary(min_size=0, max_size=200),
    )
    def test_embedding_message_deterministic(
        self, pid: str, model: str, sha: str, blob: bytes
    ) -> None:
        assert _embedding_message(pid, model, sha, blob) == _embedding_message(
            pid, model, sha, blob
        )


class TestSigningRoundTrip:
    @given(src=any_text, tgt=any_text, ver=any_text)
    def test_seal_message_recovers_fields(
        self, src: str, tgt: str, ver: str
    ) -> None:
        msg = _message(src, tgt, ver)
        recovered = json.loads(msg.decode("utf-8"))
        assert recovered == [src, tgt, ver]

    @given(q=any_text, pid=any_text, tgt=any_text, ver=any_text)
    def test_rejection_message_recovers_fields(
        self, q: str, pid: str, tgt: str, ver: str
    ) -> None:
        msg = _rejection_message(q, pid, tgt, ver)
        recovered = json.loads(msg.decode("utf-8"))
        assert recovered == ["rejection", q, pid, tgt, ver]

    @given(src=any_text, dst=any_text, kind=any_text)
    def test_edge_message_recovers_fields(
        self, src: str, dst: str, kind: str
    ) -> None:
        msg = _edge_message(src, dst, kind)
        recovered = json.loads(msg.decode("utf-8"))
        assert recovered == ["edge", src, dst, kind]

    @given(
        pid=any_text,
        model=any_text,
        sha=any_text,
        blob=st.binary(min_size=0, max_size=200),
    )
    def test_embedding_message_recovers_tag_and_text_fields(
        self, pid: str, model: str, sha: str, blob: bytes
    ) -> None:
        msg = _embedding_message(pid, model, sha, blob)
        recovered = json.loads(msg.decode("utf-8"))
        assert recovered[0] == "embedding"
        assert recovered[1] == pid
        assert recovered[2] == model
        assert recovered[3] == sha
        assert len(recovered) == 5


class TestSigningDomainSeparation:
    @given(src=any_text, tgt=any_text, ver=any_text)
    @settings(max_examples=200)
    def test_seal_and_rejection_never_collide(
        self, src: str, tgt: str, ver: str
    ) -> None:
        seal = _message(src, tgt, ver)
        rej = _rejection_message(src, tgt, ver, ver)
        assert seal != rej

    @given(src=any_text, tgt=any_text, ver=any_text)
    @settings(max_examples=200)
    def test_seal_and_edge_never_collide(
        self, src: str, tgt: str, ver: str
    ) -> None:
        seal = _message(src, tgt, ver)
        edge = _edge_message(src, tgt, ver)
        assert seal != edge

    @given(a=any_text, b=any_text, c=any_text, d=any_text)
    @settings(max_examples=200)
    def test_rejection_and_edge_never_collide(
        self, a: str, b: str, c: str, d: str
    ) -> None:
        rej = _rejection_message(a, b, c, d)
        edge = _edge_message(a, b, c)
        assert rej != edge
