"""The bench must exercise the regime where the matcher changes behaviour.

`difflib` engages its ``autojunk`` heuristic once the compared sequence reaches
200 elements, and that is exactly where `StringMatcher` was found to be broken:
scores collapsing from ~0.95 to ~0.55, and `similarity` not symmetric, so which
member of a pair was sealed first decided whether a match served.

The bench reported everything healthy throughout, because **every corpus it had
normalized to well under 200 characters** — boilerplate to ~70, prose to 40-180.
A real code corpus found both defects in one pass; the bench could not have.

These tests exist so that blind spot cannot silently return. They are cheap and
live in the main suite rather than in `bench/`, because a coverage gap that only
CI-for-the-bench would catch is a coverage gap nobody catches.
"""
from __future__ import annotations

# A plain import, deliberately. This was `pytest.importorskip("bench.corpora")`,
# which is the polite thing to write and exactly wrong here: the module docstring
# above says these tests exist so a blind spot cannot *silently* return, and an
# importorskip is a silent return. It skipped for anyone who typed `pytest`
# rather than `python -m pytest` — the command the README gives — and CI ran the
# other one, so nothing said so. If the path setup ever breaks again this fails
# loudly instead. See `pythonpath` in pyproject.toml.
import bench.corpora as bench_corpora
from nestor.matcher import StringMatcher


def test_corpora_span_the_autojunk_threshold():
    """At least one corpus must produce keys long enough to engage autojunk.

    If this fails, the accuracy bench is blind to the regime that hid two real
    matcher bugs — whatever else it reports.
    """
    cov = bench_corpora.length_coverage(sample=120)
    assert cov["spans_autojunk_threshold"], (
        "no corpus reaches difflib's autojunk threshold "
        f"({cov['autojunk_threshold']} chars) — the bench cannot see the regime "
        f"where StringMatcher was broken. Coverage: {cov['corpora']}")


def test_a_corpus_is_predominantly_long():
    """Spanning the boundary is not enough — one corpus must live above it.

    A handful of long outliers inside a short corpus would satisfy
    `spans_autojunk_threshold` while still leaving the regime effectively
    untested.
    """
    cov = bench_corpora.length_coverage(sample=120)
    shares = {n: c["share_over_autojunk_threshold"] for n, c in cov["corpora"].items()}
    assert max(shares.values()) >= 0.9, (
        f"no corpus is predominantly above the autojunk threshold: {shares}")


def test_the_short_corpora_are_still_short():
    """The other end must stay covered too.

    Translation segments and entity aliases are short, and that is Nestor's
    primary case. If every corpus drifted long, the bench would lose the regime
    it was originally built for.
    """
    cov = bench_corpora.length_coverage(sample=120)
    shares = {n: c["share_over_autojunk_threshold"] for n, c in cov["corpora"].items()}
    assert min(shares.values()) == 0.0, (
        f"every corpus now crosses the autojunk threshold: {shares}")


def test_code_corpus_units_all_clear_the_threshold():
    """The long corpus is only useful if every unit is genuinely in the regime."""
    m = StringMatcher()
    lengths = [len(m.normalize(x)) for x in bench_corpora.code(60)]
    assert min(lengths) >= bench_corpora.AUTOJUNK_THRESHOLD, (
        f"code corpus has units below the threshold: min={min(lengths)}")


def test_corpora_are_deterministic():
    """A bench whose corpus shifts between runs cannot be compared against its
    own recorded results."""
    for name, gen in bench_corpora.CORPORA.items():
        assert gen(25) == gen(25), f"{name} is not deterministic"
