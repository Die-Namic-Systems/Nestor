#!/usr/bin/env python3
"""Token matchers for the seam — the cheap option nobody measured.

Stage 3 of IDEAS.md §3.4 reported 0.000 recall at every shipped threshold on a
real human corpus. Every one of those zeros came from :class:`StringMatcher`,
which is character difflib, and the matcher was held fixed for all three stages.
That is the "failure is never in the step you are watching" rule going
unobserved for three benches: the surfaces were varied and the tool comparing
them never was.

The question these exist to answer is not "can we get a better score". It is:

    **What fraction of real human aliases share no token at all with any sealed
    surface?**

Because that fraction is the part no lexical matcher of any kind can reach, and
it is therefore the size of the case §3.3's semantic matcher would have to
justify itself on. Everything above it is reachable by tokenization, which costs
no dependency, no model call and no vector.

Two measures, both symmetric — `StringMatcher`'s docstring records that
asymmetry broke serving in measurable ways, and a matcher that regressed on that
would be worse than useless here:

* :class:`TokenJaccard` — |A∩B| / |A∪B|. Conservative. Punishes a long alias
  matched against a short canonical even when the canonical is fully contained:
  `{sensitivity}` inside `{sensitivity, ladder}` scores 0.5, not 1.0.
* :class:`TokenOverlap` — |A∩B| / min(|A|,|B|). The containment reading, which
  is what a search box actually wants — a query that contains the name should
  find it. Symmetric because `min` is. **Dangerous on its own**: any single
  shared token against a one-token canonical scores 1.0, so it should be read
  next to its false-seal rate and never alone.

Neither is proposed as a replacement for `StringMatcher` on translation memory,
where character-level edits are the domain. They are proposed as evidence about
where the ceiling is.

Both classes implement ``score(raw_a, raw_b)`` so :mod:`nestor.memory` and the
bench compare probe text to each row's ``source_text`` via token sets, while
``normalize`` remains a sorted bag-of-tokens dedup key (IDEAS §3.1).
"""
from __future__ import annotations

import re

_WORD = re.compile(r"[a-z0-9]+")

# Deliberately tiny. A stopword list tuned until the numbers improve is a way of
# fitting the corpus and calling it a method; these are the function words that
# appear in nearly every referring expression in any English corpus.
STOPWORDS = frozenset({"the", "a", "an", "of", "and", "or", "to", "in", "for",
                       "this", "that", "these", "those", "its", "it", "is"})


def _tokens(value) -> list[str]:
    toks = [t for t in _WORD.findall(str(value).lower()) if t not in STOPWORDS]
    return toks or _WORD.findall(str(value).lower())  # never normalize to empty


class _TokenMatcherBase:
    """Shared normalization: sorted, deduplicated, stopword-stripped tokens.

    ``normalize`` sorts, which makes ``source_norm`` word-order insensitive.
    That is a real design commitment, not an implementation detail — "lane model
    schema" and "schema lane model" become the same key and can no longer be
    told apart by anything downstream. For entity and document names that is
    almost always right; for translation memory, where word order carries
    meaning, it is almost always wrong. Which is why these are bench matchers.

    Idempotent, as the Matcher protocol requires: normalizing a sorted token
    string re-sorts to itself.
    """

    def normalize(self, value) -> str:
        return " ".join(sorted(set(_tokens(value))))

    def _sets(self, a_norm: str, b_norm: str) -> tuple[set[str], set[str]]:
        return set(a_norm.split()), set(b_norm.split())

    def _sets_raw(self, raw_a, raw_b) -> tuple[set[str], set[str]]:
        return set(_tokens(raw_a)), set(_tokens(raw_b))


class TokenJaccard(_TokenMatcherBase):
    """|A∩B| / |A∪B|."""

    name = "token-jaccard"

    def similarity(self, a_norm: str, b_norm: str) -> float:
        a, b = self._sets(a_norm, b_norm)
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)

    def score(self, raw_a, raw_b) -> float:
        a, b = self._sets_raw(raw_a, raw_b)
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)


class TokenOverlap(_TokenMatcherBase):
    """|A∩B| / min(|A|,|B|) — containment, symmetric."""

    name = "token-overlap"

    def similarity(self, a_norm: str, b_norm: str) -> float:
        a, b = self._sets(a_norm, b_norm)
        if not a or not b:
            return 0.0
        return len(a & b) / min(len(a), len(b))

    def score(self, raw_a, raw_b) -> float:
        a, b = self._sets_raw(raw_a, raw_b)
        if not a or not b:
            return 0.0
        return len(a & b) / min(len(a), len(b))


def shares_no_token(probe: str, sealed: list[str]) -> bool:
    """True when a probe has no token in common with ANY sealed surface.

    The floor. No lexical matcher — character, token, or otherwise — can bridge
    these, so this count is the honest size of the semantic gap and the only
    number in this module that argues for or against §3.3.
    """
    p = set(_tokens(probe))
    return not any(p & set(_tokens(s)) for s in sealed)
