"""Lexicon expansion — pi, Newton, speed of light."""
from __future__ import annotations

import pytest

from nestor import established


@pytest.mark.parametrize("source,sl,tl", [
    ("pi", "math", "value"),
    ("3.14", "math", "value"),
    ("Newton first law", "physics", "law"),
    ("speed of light", "physics", "constant"),
    ("c", "physics", "constant"),
])
def test_expanded_lexicon_hits(source, sl, tl):
    hit = established.recognize_lexicon(source, sl, tl)
    assert hit is not None
    assert hit["rung"] == "established"
    assert hit["locator"].startswith("https://")
