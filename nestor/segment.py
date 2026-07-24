"""Segment splitting — vendored from the host translator.

Nestor's cascade runs one loop per segment, so it needs to break a block of
text into segments the same way the host does. This is a verbatim copy of
``_split_segments`` from semantic-translator's ``translator.py`` so that
Nestor carries no upward import.
"""
from __future__ import annotations

import re


def _split_segments(text: str) -> list[str]:
    """Paragraphs first; fall back to sentences for short texts."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paragraphs) >= 3:
        return paragraphs
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]
