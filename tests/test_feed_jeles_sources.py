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


def test_it_marks_the_corroboration_claim_as_unmeasured():
    """The correction, pinned.

    An earlier draft was going to assert that single-sourced subjects cannot
    clear jeles' two-source bar. `jeles._independence` counts registrable
    domains, not subject tags — a different meaning of the same word. The script
    must keep saying which half it measured.
    """
    src = (REPO / "scripts" / "feed_jeles_sources.py").read_text()
    assert "MEASURED" in src and "NOT measured" in src
    assert "registrable" in src, \
        "the script must name the sense of 'domain' the corroboration rule uses"


@pytest.mark.skipif(not JELES.exists(), reason="no jeles checkout present")
def test_against_the_real_registry():
    got = FEED.extract(JELES / "jeles" / "sources.py")
    assert len(got) > 50, "expected the full institutional registry"
    assert all(isinstance(v, dict) for v in got.values())
    assert all(v.get("name") for v in got.values()), "every source names itself"
