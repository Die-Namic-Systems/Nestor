"""Optional live check for nestor-meaning[semantic] — only when NESTOR_SEMANTIC_TEST=1."""

from __future__ import annotations

import pytest

from nestor.matcher import StringMatcher
from nestor.semantic_matcher import SemanticMatcher
from tests.conftest import semantic_tests_enabled


@pytest.mark.semantic
@pytest.mark.skipif(
    not semantic_tests_enabled(),
    reason=("set NESTOR_SEMANTIC_TEST=1 and install the semantic extra; "
            "real ONNX execution is an explicit lane"),
)
def test_aws_amazon_web_services_beats_string_matcher():
    """IDEAS §3.1 motivating case — character ratio ~0.273, semantic should win."""
    sm = StringMatcher()
    raw_a, raw_b = "AWS", "Amazon Web Services"
    lexical = sm.similarity(sm.normalize(raw_a), sm.normalize(raw_b))
    semantic = SemanticMatcher().score(raw_a, raw_b)
    assert lexical < 0.5, f"fixture assumption drifted: StringMatcher={lexical}"
    assert semantic > lexical, (
        f"SemanticMatcher should beat StringMatcher on acronym case; "
        f"got semantic={semantic}, lexical={lexical}"
    )
