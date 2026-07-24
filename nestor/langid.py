"""Stopword-profile language identification — en/es/fr/de/pt/it.

Replaces the ES-only marker hack for Nestor paths. Not a real langid model;
good enough to route segments in the prototype. Swap for lingua/langdetect
when the language set grows past what stopword profiles can separate.
"""
from __future__ import annotations

import re

_PROFILES: dict[str, set[str]] = {
    "en": {"the", "and", "of", "to", "in", "is", "it", "you", "that", "for",
           "with", "are", "this", "not", "your", "when", "what", "have"},
    "es": {"el", "la", "los", "las", "de", "que", "en", "es", "una", "con",
           "para", "por", "como", "del", "se", "tu", "lo", "más", "pero", "sus"},
    "fr": {"le", "la", "les", "de", "des", "et", "est", "que", "une", "pour",
           "dans", "vous", "qui", "pas", "avec", "sur", "ce", "il", "au", "du"},
    "de": {"der", "die", "das", "und", "ist", "ein", "eine", "nicht", "mit",
           "für", "auf", "den", "von", "sie", "wenn", "was", "dem", "des", "zu"},
    "pt": {"o", "a", "os", "as", "de", "que", "em", "um", "uma", "com", "para",
           "por", "não", "do", "da", "se", "mais", "como", "seu", "sua"},
    "it": {"il", "la", "le", "di", "che", "in", "un", "una", "con", "per",
           "non", "del", "della", "si", "più", "come", "sono", "gli", "nel"},
}

SUPPORTED = sorted(_PROFILES)


def detect(text: str, default: str = "en") -> str:
    words = re.findall(r"\b[\wáéíóúüñçàèìòùâêîôûäöëï]+\b", text.lower())
    if not words:
        return default
    scores = {
        lang: sum(1 for w in words if w in profile) / len(words)
        for lang, profile in _PROFILES.items()
    }
    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    return best if scores[best] > 0.08 else default
