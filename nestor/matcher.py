"""The matcher seam — Nestor's domain-abstraction boundary.

Nestor's mechanic is domain-agnostic: *normalize an input, fuzzy-match it
against a memory of SEALED pairs, serve the verified match above a threshold
(else queue it for a human seal), and log everything to the hash-chained
ledger.* Only two operations are domain-specific:

  * **normalize(value) -> str** — collapse an input into a canonical key.
  * **similarity(a_norm, b_norm) -> float** — how alike two canonical keys
    are, in ``[0.0, 1.0]`` (``1.0`` == a verified match).

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
from typing import Protocol, runtime_checkable


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
        # coercing, but for str inputs this is byte-for-byte the old result.
        text = value if isinstance(value, str) else str(value)
        return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", text.lower())).strip()

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

    def parse(self, value) -> "float | None":
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

    def similarity(self, a_norm: str, b_norm: str) -> float:
        if a_norm == _NAN_SENTINEL or b_norm == _NAN_SENTINEL:
            return 0.0
        try:
            a = float(a_norm)
            b = float(b_norm)
        except (TypeError, ValueError):
            return 0.0
        diff = abs(a - b)
        tol = max(self.abs_tol, self.pct_tol * max(abs(a), abs(b)))
        if diff <= tol:
            return 1.0
        if tol == 0:
            # No tolerance configured: only an exact match scores above 0.
            return 0.0
        # Continuous at the edge (exp(0)=1) and monotonically -> 0 as diff grows.
        return math.exp(-(diff - tol) / tol)
