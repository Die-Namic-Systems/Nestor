"""The jeles source feeder — held to its parser and to what it claims.

Same discipline as `tests/test_feed_willow_constitution.py`: the fixtures are
written here, not read from jeles, because jeles is not a dependency and a test
that skipped without it would leave the parser ungated in CI — the one place it
runs unattended.

The test worth reading is the last one. This feeder's first draft was about to
report that 43 single-sourced subjects cannot satisfy jeles' two-source
corroboration rule. That was wrong: `jeles._independence` counts distinct
*registrable domains* — the DNS sense — not the subject tags in `SOURCES`. The
word "domain" means two different things in the two files. So the script now
separates what it measured from what it merely suspects, and that separation is
pinned rather than left to prose discipline.
"""
from __future__ import annotations

import pathlib
import sys
import textwrap

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import feed_jeles_sources as FEED       # noqa: E402

JELES = pathlib.Path("/workspace/jeles")


def registry(tmp_path, body: str) -> pathlib.Path:
    p = tmp_path / "sources.py"
    p.write_text(textwrap.dedent(body))
    return p


def test_it_parses_an_annotated_assignment(tmp_path):
    got = FEED.extract(registry(tmp_path, '''
        SOURCES: dict[str, dict] = {
            "openalex": {"name": "OpenAlex", "domain": ["academic"],
                         "key_required": False, "hosts": ["api.openalex.org"]},
        }
        '''))
    assert list(got) == ["openalex"]
    assert got["openalex"]["name"] == "OpenAlex"


def test_it_parses_a_plain_assignment_too(tmp_path):
    got = FEED.extract(registry(tmp_path, '''
        SOURCES = {"loc": {"name": "Library of Congress", "domain": ["history"]}}
        '''))
    assert got["loc"]["domain"] == ["history"]


def test_unreadable_is_none_and_genuinely_empty_is_a_dict(tmp_path):
    """The distinction, at the parser. It was not always there.

    Both of these returned `{}` until 2026-08-06, so a registry the parser could
    not understand reported in the same words as one declaring nothing — the
    conflation this package refuses for answers, made inside the package. Found
    by running the feeders against an empty repository.
    """
    assert FEED.extract(registry(tmp_path, 'SOURCES = {"x": some_call()}\n')) is None
    assert FEED.extract(registry(tmp_path, 'NOTHING = 1\n')) is None
    assert FEED.extract(registry(tmp_path, 'SOURCES: dict[str, dict] = {}\n')) == {}


def test_the_pair_is_source_to_subjects(tmp_path):
    src, tgt = FEED.claim("pubmed", {"name": "PubMed", "domain": ["biology", "medicine"]})
    assert src == "pubmed — PubMed"
    assert tgt == "biology, medicine"


def test_a_source_declaring_no_subjects_says_so_rather_than_serving_blank():
    _, tgt = FEED.claim("mystery", {"name": "Mystery"})
    assert "no subjects declared" in tgt


def test_it_never_imports_the_repo_it_reads():
    body = (REPO / "scripts" / "feed_jeles_sources.py").read_text().split('"""', 2)[-1]
    for forbidden in ("importlib", "exec(", "runpy", "__import__"):
        assert forbidden not in body
    assert "ast.parse" in body


def test_it_separates_what_it_measured_from_what_it_only_asked():
    """The script must always say which half of its own output is evidence.

    This test used to require the literal words "NOT measured", because the two
    corroboration claims were open questions. They have since been measured
    (IDEAS §6.48, jeles#53) and the block now reports CONFIRMED and FALSIFIED —
    so the old assertion started failing, correctly, on the commit that answered
    them. Renamed and widened rather than deleted: the property worth holding
    was never "these two stay unmeasured", it was "routing breadth and the
    corroboration bar are never reported as one finding".
    """
    src = (REPO / "scripts" / "feed_jeles_sources.py").read_text()
    assert "MEASURED: routing breadth only" in src, \
        "the script must keep saying which half of the claim it measured directly"
    assert "registrable" in src, \
        "the script must name the sense of 'domain' the corroboration rule uses"


def test_the_two_corrected_hypotheses_still_carry_their_verdicts():
    """A correction that loses its own history is a quiet edit.

    Both claims were printed as open questions and both turned out wrong — one
    confirmed with the wrong mechanism, one false in the opposite direction. The
    block keeps what each said and what it became, so a reader holding an older
    run can tell it was withdrawn rather than never made.

    Asserted on short phrases, not sentences: these are f-strings wrapped across
    source lines, so a sentence that reads as one line of output is not one
    contiguous string in the file. The first version of this test asserted the
    whole sentence and failed for that reason alone — a test that is wrong about
    where the text lives proves nothing about what the text says.
    """
    src = (REPO / "scripts" / "feed_jeles_sources.py").read_text()
    for phrase in ("now CONFIRMED", "stated reason was wrong",
                   "now FALSIFIED", "OPPOSITE direction"):
        assert phrase in src, f"the correction no longer says {phrase!r}"
    assert "jeles#53" in src, "the correction must cite where it was reported"


@pytest.mark.skipif(not JELES.exists(), reason="no jeles checkout present")
def test_against_the_real_registry():
    got = FEED.extract(JELES / "jeles" / "sources.py")
    assert len(got) > 50, "expected the full institutional registry"
    assert all(isinstance(v, dict) for v in got.values())
    assert all(v.get("name") for v in got.values()), "every source names itself"
