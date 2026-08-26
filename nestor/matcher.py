"""The matcher seam — Nestor's domain-abstraction boundary.

Nestor's mechanic is domain-agnostic: *normalize an input, fuzzy-match it
against a memory of SEALED pairs, serve the verified match above a threshold
(else queue it for a human seal), and log everything to the hash-chained
ledger.* Only two operations are domain-specific:

  * **normalize(value) -> str** — collapse an input into a canonical key.
  * **similarity(a_norm, b_norm) -> float** — how alike two canonical keys
    are, in ``[0.0, 1.0]`` (``1.0`` == a verified match).
  * **score(raw_a, raw_b) -> float** *(optional)* — compare original inputs.
    When present, :mod:`nestor.memory` prefers this over ``similarity`` on the
    stored norms so ``normalize`` can stay aggressive for dedup without smuggling
    scoring structure through ``source_norm`` (IDEAS §3.1).

Everything else — sealing, thresholds, the ledger, storage inversion — is
identical whether Nestor is matching TRANSLATIONS, ENTITIES, or NUMBERS. This
module defines the :class:`Matcher` Protocol and ships the two reference
matchers:

  * :class:`StringMatcher` — the original translation behavior (lowercase +
    strip punctuation + collapse whitespace, then difflib ratio). It reproduces
    Nestor's historical translation-memory scoring bit-for-bit and is the
    module-wide default.
  * :class:`NumericMatcher` — parses a number out of a value and scores by
    tolerance, so Nestor can reconcile FIGURES instead of phrases.
"""
from __future__ import annotations

import difflib
import math
import re
import unicodedata
from typing import Protocol, runtime_checkable

#: Precompiled single-character match for the ``\w`` or ``\s`` classes —
#: the historical strip pass's "keep" set. Compiled once so
#: :meth:`StringMatcher.normalize` does not recompile per character.
_WORD_OR_SPACE = re.compile(r"[\w\s]")

#: Unicode General_Category codes for emoji-shaped symbols. ``So`` is
#: *Symbol, other* (most emoji live here — smileys, transport, weather,
#: flags-as-single-codepoints), ``Sk`` is *Symbol, modifier* (skin-tone
#: modifiers, and some non-spacing keycap-like glyphs). Decision 0202
#: preserves these through :meth:`StringMatcher.normalize` so a pure-emoji
#: key does not collapse to the empty string.
_EMOJI_CATEGORIES = frozenset({"So", "Sk"})


@runtime_checkable
class Matcher(Protocol):
    """The domain-specific half of Nestor's match mechanic.

    A ``Matcher`` turns raw inputs into canonical keys and scores two keys for
    similarity. Nestor supplies the rest (sealing, thresholds, ledger). Any
    object exposing these two methods can be injected wherever a matcher is
    accepted.
    """

    def normalize(self, value) -> str:
        """Return a canonical, comparable string key for ``value``.

        The output is what Nestor persists as ``source_norm`` and what
        :meth:`similarity` compares. Deterministic and idempotent:
        ``normalize(normalize(x)) == normalize(x)`` should hold for keys.
        """

    def similarity(self, a_norm: str, b_norm: str) -> float:
        """Score two normalized keys in ``[0.0, 1.0]`` — ``1.0`` == verified match."""

    # One optional method, deliberately NOT part of this Protocol:
    #
    #     similarity_bound(a_norm, b_norm, floor=0.0) -> float
    #
    # An UPPER bound on ``similarity(a_norm, b_norm)`` that is cheaper to
    # compute than the real thing. ``memory.best_sealed`` uses it to discard
    # candidates that cannot possibly clear the seal threshold without scoring
    # them at all — lossless, since a candidate whose upper bound is below the
    # bar cannot be above it. See :meth:`StringMatcher.similarity_bound`.
    #
    # It is optional because a matcher whose ``similarity`` is already cheap
    # (:class:`NumericMatcher` is arithmetic on two floats) gains nothing, and
    # requiring it would break every custom matcher already injected against
    # this Protocol. A matcher without it is scanned exactly as before.
    #
    # Optional raw scoring, also deliberately NOT part of this Protocol:
    #
    #     score(raw_a, raw_b) -> float
    #
    # ``memory.lookup`` and ``memory.best_sealed`` call this when implemented,
    # passing the query text and each row's ``source_text``. ``similarity`` remains
    # required for paths that only have norms (e.g. calibration on stored keys
    # when no ``score`` is offered). A matcher whose ``score`` disagrees with
    # ``similarity`` on the same pair must not offer ``similarity_bound`` — the
    # bound is defined on normalized keys only.


def uses_raw_score(matcher) -> bool:
    """True when ``matcher`` exposes a callable ``score`` method."""
    return callable(getattr(matcher, "score", None))


def match_similarity(matcher: Matcher, query_text: str, query_norm: str,
                     stored_text: str, stored_norm: str,
                     *, _raw_score: bool | None = None) -> float:
    """How alike a query is to one stored row.

    Uses ``matcher.score(query_text, stored_text)`` when available and
    ``stored_text`` is non-empty after strip; otherwise ``similarity(query_norm,
    stored_norm)``.

    Pass ``_raw_score`` when calling in a loop (the result of
    :func:`uses_raw_score`) so the check is not repeated per candidate.
    """
    stored = (stored_text or "").strip()
    use_raw = uses_raw_score(matcher) if _raw_score is None else _raw_score
    if use_raw and stored:
        return matcher.score(query_text, stored)  # type: ignore[attr-defined]
    return matcher.similarity(query_norm, stored_norm)


def matcher_audit_fields(matcher) -> dict:
    """Ledger fields naming which matcher (and model) scored a tier-1 serve.

    Enough to answer "why was this served at 0.94" after the scoring changes
    underneath a memory — an embedding model upgrade moves every score, and a
    trail that records the number without the thing that produced it cannot say
    so.

    **Not a stable identifier.** A matcher that sets no ``name`` is recorded by
    its class name, which a rename or a move changes without changing any
    behaviour, and two unrelated matchers may share one. Read it as a label for
    a human comparing entries from the same deployment, not as a key to join on
    or a version to pin against. A matcher that wants to be identifiable across
    refactors should carry its own ``name``, and one whose scoring is versioned
    should carry that in ``model_name``.

    Fields are metadata only — no query text and no stored surface — because
    :mod:`nestor.frank` mirrors ledger entries verbatim into a ledger somebody
    else holds.
    """
    fields: dict[str, str] = {
        "matcher": str(getattr(matcher, "name", None) or type(matcher).__name__),
    }
    model = getattr(matcher, "model_name", None)
    if model:
        fields["matcher_model"] = str(model)
    if uses_raw_score(matcher):
        fields["matcher_scoring"] = "score"
    return fields


# --------------------------------------------------------------------------
# StringMatcher — the translation-memory behavior, made explicit
# --------------------------------------------------------------------------

class StringMatcher:
    """Text matcher: casefold + strip punctuation + collapse whitespace, then
    difflib similarity. This is the algorithm the translation memory used inline
    (``_norm`` + ``difflib.SequenceMatcher(...).ratio()``), lifted behind the
    :class:`Matcher` seam. It is Nestor's default matcher.

    Two properties are enforced here that a bare ``SequenceMatcher(...).ratio()``
    does NOT give you, because both broke serving in measurable ways:

    **1. Scores do not collapse on keys of 200+ characters.** ``difflib``
    defaults ``autojunk=True``, which — once the second sequence reaches 200
    elements — treats every element occurring in more than 1% of it as junk and
    excludes it from matching blocks. On a *character* sequence drawn from a
    ~40-symbol alphabet that is most of the alphabet, and scores do not degrade
    gracefully, they fall off a cliff. Measured on two genuinely duplicate
    functions with 255- and 299-character keys: ``0.3177`` as difflib defaults,
    ``0.9206`` with ``autojunk=False`` — the difference between "queued for a
    human" and "served". So ``autojunk`` defaults to ``False`` here.

    **2. ``similarity(a, b) == similarity(b, a)``, always.** ``ratio()`` is not
    symmetric: its matching-block search is greedy and order-dependent, and
    ``autojunk`` is applied to the *second* operand only. ``memory.lookup``
    always scores ``similarity(query, stored_row)``, so without this, *which
    member of a pair happened to be sealed first* could decide whether a match
    is served. For an engine whose promise is "a sealed pair either serves or it
    does not", a serve decision that depends on insertion order is a correctness
    defect — and it makes the ledger record a decision that cannot be reproduced
    from the pair's contents. Operands are therefore put in a canonical order
    before scoring.

    Compatibility: below 200 characters ``autojunk`` is inert (measured: 0
    differences over 3,000 random pairs), and canonical ordering changes nothing
    for near-duplicate text (measured: 0 of 500 realistic near-duplicate pairs
    are order-dependent). Order-dependence below 200 characters shows up only on
    *dissimilar* pairs, which score far below any serving threshold either way.
    So real translation segments score exactly as they did.

    Cost: ``autojunk=False`` is dramatically slower on long keys — measured
    ~1.0x at 100 characters, ~43x at 400, ~78x at 800. It is free precisely
    where it is inert and expensive precisely where the old answer was wrong.
    ``StringMatcher(autojunk=True)`` restores the fast path for callers whose
    keys are short, but it is unsafe above 200 characters and reintroduces both
    problems above.
    """

    def __init__(self, autojunk: bool = False) -> None:
        self.autojunk = autojunk

    def normalize(self, value) -> str:
        # Historically ``_norm(text: str)``. Accept non-str defensively by
        # coercing. NFC-fold first (decision 0200) so composed and decomposed
        # forms of the same visible word produce the same key — Vietnamese
        # ``ư`` typed as U+01B0 vs typed as ``u`` + U+031B, decomposed
        # ``café`` vs composed ``café``, Arabic letters with combining marks.
        # Then strip anything that is not ``\w``, whitespace, or a symbol emoji
        # (Unicode categories ``So`` and ``Sk``) — decision 0202. Historically
        # this was a bare ``re.sub(r"[^\w\s]", "", ...)`` which stripped every
        # emoji to the empty string, so any two pure-emoji rows collided in
        # the same store on the empty key; ``So``/``Sk`` preservation makes
        # different emoji strings key distinctly. What the historical pipeline
        # stripped for non-emoji reasons — punctuation, currency (``$``,
        # ``€``), math symbols (``×``, ``÷``) — is still stripped, so
        # baselines like ``"$4.20B"`` still normalize as they did.
        # NFC does *not* collapse legitimate distinctions: Cyrillic ``а`` and
        # Latin ``a`` stay distinct (Unicode homoglyph question, not a
        # composition question), and fullwidth digits stay fullwidth. For
        # 7-bit ASCII text the output is byte-for-byte identical to the
        # pre-NFC pipeline.
        text = value if isinstance(value, str) else str(value)
        text = unicodedata.normalize("NFC", text)
        kept = "".join(
            ch for ch in text
            if _WORD_OR_SPACE.match(ch)
            or unicodedata.category(ch) in _EMOJI_CATEGORIES
        )
        return re.sub(r"\s+", " ", kept.lower()).strip()

    def similarity(self, a_norm: str, b_norm: str) -> float:
        # Equal normals short-circuit to 1.0 (matching the old ``EXACT`` path
        # in ``memory.lookup``).
        if a_norm == b_norm:
            return 1.0
        # Canonical operand order, so the score is a property of the PAIR rather
        # than of which side the caller happened to pass first. Any total order
        # works; lexicographic is deterministic and costs a single comparison.
        if a_norm > b_norm:
            a_norm, b_norm = b_norm, a_norm
        return difflib.SequenceMatcher(None, a_norm, b_norm,
                                       autojunk=self.autojunk).ratio()

    def similarity_bound(self, a_norm: str, b_norm: str, floor: float = 0.0) -> float:
        """An upper bound on :meth:`similarity`, cheap first, tighter on demand.

        ``difflib`` publishes two bounds on ``ratio()``:
        ``real_quick_ratio()`` (lengths only) and ``quick_ratio()`` (a multiset
        count), with ``ratio() <= quick_ratio() <= real_quick_ratio()``.
        Confirmed in-repo on 20,000 random pairs, no violations. So a candidate
        whose bound is below the bar cannot clear the bar, and its real score
        never needs computing — **the answer does not change, only the cost**
        (IDEAS §2.1).

        ``floor`` is what the caller needs to beat. The length bound is computed
        first and returned immediately if it already settles the question; only
        a candidate that survives it pays for the multiset count. The length
        bound is inlined rather than taken from a ``SequenceMatcher``, because
        constructing one indexes the second sequence — which costs more than the
        bound it would give us, and would throw away the whole point of asking a
        cheap question first.

        No shared scratch object: :mod:`nestor.ui` scores from a thread pool, and
        a ``SequenceMatcher`` reused across candidates is mutable state two
        threads would interleave. Reusing one would buy back difflib's ``b2j``
        cache, and it is not worth a scoring race.
        """
        if a_norm == b_norm:
            return 1.0
        la, lb = len(a_norm), len(b_norm)
        if not la or not lb:
            return 0.0
        # difflib.real_quick_ratio(), inlined: the most matches two sequences
        # can possibly share is the length of the shorter one.
        bound = 2.0 * min(la, lb) / (la + lb)
        if bound < floor:
            return bound
        if a_norm > b_norm:
            a_norm, b_norm = b_norm, a_norm
        return min(bound, difflib.SequenceMatcher(
            None, a_norm, b_norm, autojunk=self.autojunk).quick_ratio())


# --------------------------------------------------------------------------
# NumericMatcher — reconcile figures instead of phrases
# --------------------------------------------------------------------------

# A canonical key that no real parse produces and that never scores > 0, so
# non-parseable inputs are stored but can never be served as a match.
_NAN_SENTINEL = "\x00nestor:nan"

# Grab the first numeric token, tolerating a leading sign, decimals and
# scientific notation. Currency/percent/grouping symbols are stripped first.
_NUM_RE = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def _no_parse(text: str) -> dict:
    """The :meth:`NumericMatcher.parse_detail` shape for "no number in there".

    ``partial`` is False: nothing was compared, so nothing was silently dropped
    from a comparison. The caller learns this from ``value is None``, which is
    the louder signal — a non-parseable figure normalizes to a sentinel that
    never matches anything.
    """
    return {"text": text, "value": None, "matched": "", "residue": text,
            "partial": False}


class NumericMatcher:
    """Numeric matcher: parse a number, score by tolerance.

    ``normalize`` extracts a number from a str/int/float (stripping ``$ , %``
    and whitespace) and returns the ``repr`` of the resulting float as its
    canonical key; anything non-parseable normalizes to a sentinel that never
    matches.

    ``similarity`` is defined by a tolerance band with exponential decay::

        tol = max(abs_tol, pct_tol * max(|a|, |b|))
        d   = |a - b|
        sim = 1.0                       if d <= tol
              exp(-(d - tol) / tol)     if d >  tol  (tol > 0)
              0.0                       if d >  tol  (tol == 0)

    So similarity is ``1.0`` everywhere inside the tolerance band, exactly
    ``1.0`` again at the band's edge (continuous), then decays smoothly and
    monotonically toward ``0`` as the deviation grows: it is ~``0.37`` one
    tolerance-width past the edge, ~``0.14`` two widths past, and asymptotically
    ``0`` for a wildly different figure. With no tolerance at all
    (``abs_tol=pct_tol=0``) only an exact match scores above ``0``.
    Non-parseable operands score ``0.0``.

    Tolerances are constructor config:

    * ``abs_tol`` — an absolute slack (same units as the values).
    * ``pct_tol`` — a proportional slack (fraction of the larger magnitude);
      the default ``0.05`` means "within 5%."
    """

    def __init__(self, abs_tol: float = 0.0, pct_tol: float = 0.05) -> None:
        self.abs_tol = float(abs_tol)
        self.pct_tol = float(pct_tol)

    # -- parsing ----------------------------------------------------------

    def parse(self, value) -> float | None:
        """Extract a number from ``value`` (stripping ``$ , %``/whitespace), or
        ``None`` if none is found. Public so consumers like the Reconciler can
        recover the parsed figure without reaching into internals."""
        return self.parse_detail(value)["value"]

    def parse_detail(self, value) -> dict:
        """:meth:`parse`, plus what it had to ignore to get there.

        Returns ``{"text", "value", "matched", "residue", "partial"}``:

        * ``text`` — ``value`` as given, stringified.
        * ``value`` — the parsed figure, or ``None``.
        * ``matched`` — the substring of the cleaned input that became ``value``.
        * ``residue`` — the cleaned input with ``matched`` removed.
        * ``partial`` — **there are digits in the residue.**

        That last flag is the whole point of this method. :meth:`parse`
        *searches* for a number rather than requiring the input to be one, so
        ``"1,00o,000"`` — one typo — is the figure **100**, and ``"12/31/2024"``
        is **12**. Both are the documented contract and the failure direction is
        safe (a wildly wrong figure gets flagged and a human looks), but "the
        number I compared was not the number you typed" is a bad sentence to have
        to say in an audit, and until now nothing said it at all.

        Requiring the whole cleaned string to parse would have been the other
        fix, and it is wrong: it breaks ``"$1,000,000 USD"``, which is a
        perfectly ordinary way to write a figure. So the signal is not "was
        anything left over" but "was a *digit* left over" — ``"USD"`` is
        decoration, ``"o000"`` and ``"/31/2024"`` are the rest of a number that
        did not make it into the comparison. That distinguishes the two example
        failures from the legitimate case exactly, with no false alarm on
        currency or unit suffixes.

        Reporting it beats refusing it: a reconciler that rejected every
        partially-parsed figure would refuse real inputs, and the caller who can
        actually tell a typo from a unit suffix is the human this package exists
        to put in the loop.
        """
        text = "" if value is None else str(value)
        if isinstance(value, bool):
            # bool is a subclass of int; treat True/False as non-numeric so a
            # stray flag can never masquerade as the figure 1 or 0.
            return _no_parse(text)
        if isinstance(value, (int, float)):
            return {"text": text, "value": float(value), "matched": text,
                    "residue": "", "partial": False}
        s = text.strip()
        if not s:
            return _no_parse(text)
        # Strip currency/percent/grouping decoration, then extract a number.
        cleaned = s.replace("$", "").replace(",", "").replace("%", "").replace(" ", "")
        m = _NUM_RE.search(cleaned)
        if not m:
            return _no_parse(text)
        try:
            num = float(m.group())
        except ValueError:
            return _no_parse(text)
        residue = cleaned[:m.start()] + cleaned[m.end():]
        return {"text": text, "value": num, "matched": m.group(),
                "residue": residue, "partial": any(c.isdigit() for c in residue)}

    def normalize(self, value) -> str:
        num = self.parse(value)
        if num is None:
            return _NAN_SENTINEL
        return repr(num)

    # -- scoring ----------------------------------------------------------

    def tolerance_for(self, a: float, b: float) -> float:
        """The absolute slack this matcher allows between ``a`` and ``b``.

        ``max(abs_tol, pct_tol * max(|a|, |b|))`` — the one number the
        comparison actually turns on, and the reason it is public: a caller
        that reports a variation needs to report what the variation was
        measured against, or the reader cannot check the verdict.

        Note the proportional leg is a fraction of the **larger magnitude**,
        which keeps the comparison symmetric (``a`` vs ``b`` scores the same as
        ``b`` vs ``a``). A reconciliation reporting a *baseline*-relative
        percentage is therefore quoting a different denominator; see
        :meth:`nestor.reconcile.Reconciler.check`.
        """
        return max(self.abs_tol, self.pct_tol * max(abs(a), abs(b)))

    def similarity(self, a_norm: str, b_norm: str) -> float:
        if a_norm == _NAN_SENTINEL or b_norm == _NAN_SENTINEL:
            return 0.0
        try:
            a = float(a_norm)
            b = float(b_norm)
        except (TypeError, ValueError):
            return 0.0
        diff = abs(a - b)
        tol = self.tolerance_for(a, b)
        if diff <= tol:
            return 1.0
        if tol == 0:
            # No tolerance configured: only an exact match scores above 0.
            return 0.0
        # Continuous at the edge (exp(0)=1) and monotonically -> 0 as diff grows.
        return math.exp(-(diff - tol) / tol)
