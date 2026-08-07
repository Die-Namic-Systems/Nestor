"""The constitution feeder — held to the extractor, not to willow.

`scripts/feed_willow_constitution.py` reads another repository's compliance
probes by parsing them. The tests that matter are about **the parser**, because
that is where this went wrong: the first version reported that
`const_0_3_capability.py` states no forbidden act, and that CONST-0-3's act was
a sentence fragment. Both were the regex. The repository was fine.

So these pin the two shapes that broke it, on fixtures written here rather than
on willow's files — willow is not a dependency, is not in CI, and a test that
skipped without it would leave the parser ungated in exactly the environment
that runs it.

One test does drive the real checkout when it is present, marked skip otherwise.
"""
from __future__ import annotations

import pathlib
import re
import sys
import textwrap

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import feed_willow_constitution as FEED     # noqa: E402

WILLOW = pathlib.Path("/workspace/rudi193-cmd/willow-2.0")


def case(tmp_path, doc: str, trace="CONST-9-9", clause="A clause.") -> pathlib.Path:
    p = tmp_path / "const_9_9_thing.py"
    p.write_text(f'"""{doc}"""\n\nTRACE_ID = {trace!r}\nCLAUSE = {clause!r}\n')
    return p


def test_the_act_may_wrap_across_lines(tmp_path):
    """The bug that reported a fragment. `[^*\\n]+` stopped at the newline."""
    got = FEED.extract(case(tmp_path, textwrap.dedent("""\
        CONST-9-9 — something.

        The forbidden act, in one line: *an agent trying to reach the network by
        asserting its own authority instead of holding a granted one.*
        """)))
    assert got["forbidden"] == (
        "an agent trying to reach the network by asserting its own authority "
        "instead of holding a granted one")


def test_the_short_spelling_counts_too(tmp_path):
    """The bug that reported a clause as stating no forbidden act at all.

    `const_0_3_capability.py` writes `Forbidden act:` with no "in one line".
    Requiring the long form made a real, stated act invisible — and the script
    would have printed that as a hole in somebody else's constitution.
    """
    got = FEED.extract(case(tmp_path, textwrap.dedent("""\
        CONST-9-9 — something.

        Forbidden act: invoking a capability the manifest does not grant.
        """)))
    assert got["forbidden"] == "invoking a capability the manifest does not grant"


def test_emphasis_markers_are_not_content(tmp_path):
    """A closing `*` mid-value, where a qualifying clause follows (CONST-0-4)."""
    got = FEED.extract(case(tmp_path, textwrap.dedent("""\
        CONST-9-9 — something.

        The forbidden act, in one line: *taking a reserved decision without the
        human key* — including the meta-move of hoping the gate is off.
        """)))
    assert "*" not in got["forbidden"]
    assert got["forbidden"].endswith("hoping the gate is off")


def test_a_case_without_the_required_fields_is_skipped(tmp_path):
    p = tmp_path / "const_9_9_thing.py"
    p.write_text('"""No fields here."""\n\nSOMETHING_ELSE = 1\n')
    assert FEED.extract(p) is None


def test_a_case_that_does_not_parse_is_skipped_not_raised(tmp_path):
    p = tmp_path / "const_9_9_broken.py"
    p.write_text("TRACE_ID = 'X'\nthis is not python\n")
    assert FEED.extract(p) is None


def test_it_never_imports_the_repo_it_reads():
    """Parsing, not importing — willow's modules pull psycopg and run code.

    Pinned on the source because the property is architectural: an `import` or
    `exec` reaching into the target repo would make this script require willow's
    dependency tree and execute a third party's code to read a string.
    """
    src = (REPO / "scripts" / "feed_willow_constitution.py").read_text()
    body = src.split('"""', 2)[-1]          # past the module docstring
    for forbidden in ("importlib", "exec(", "runpy", "__import__"):
        assert forbidden not in body, f"the feeder must not {forbidden}"
    # `eval(` is banned only in its dangerous forms. `ast.literal_eval` parses a
    # literal and refuses anything else, which is the correct tool here — an
    # earlier version of this test banned the substring and so failed on the one
    # safe evaluator in the file.
    assert re.search(r"(?<!literal_)\beval\(", body) is None, \
        "the feeder must not eval anything but a literal"
    assert "ast.parse" in body


@pytest.mark.skipif(not WILLOW.exists(), reason="no willow-2.0 checkout present")
def test_against_the_real_constitution():
    cases = sorted((WILLOW / "constitution" / "cases").glob("const_*.py"))
    assert cases, "expected compliance cases in the checkout"
    rows = [r for r in (FEED.extract(p) for p in cases) if r]
    assert len(rows) == len(cases), "every case should yield a trace id and clause"
    assert all(r["forbidden"] for r in rows), (
        "every case states a forbidden act — if this fails, check the parser "
        "before reporting a gap in willow: it has already been wrong twice")
    assert all(r["trace_id"].startswith("CONST-") for r in rows)
