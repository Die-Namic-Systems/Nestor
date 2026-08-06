"""Every script that reads another repository, held to the same three answers.

Six scripts under `scripts/` point at a checkout that is not this one. Each was
written at a different time, and the discipline they share was articulated
*after* two of them existed:

    could not look   the corpus is absent          -> exit 1, and say so
    a true empty     the corpus is there, and bare -> exit 0, and say so
    fed / audited    there was something to read   -> exit 0

The reason this is a gate over all six rather than a paragraph in each is that
the failure it prevents is a *drift*: one reader reporting an empty corpus in
the words the others use for an unreadable one. That already happened twice —
`feed_willow_constitution.py` and `feed_jeles_sources.py` both printed the same
sentence for both cases, and it was found by running them empty rather than by
reading them. A seventh script would have no way to inherit the lesson except
this file.

**The fixtures are the interesting part.** A bare empty directory is *not* a
readable-empty corpus, it is an absent one — a distinction that cost this suite's
author a false finding against `feed_willow19_plans.py`, which correctly said "I
could not look" about a `docs/superpowers/` with no `plans/` or `specs/` inside
it. Each entry below therefore builds the structure its reader expects, empty.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

#: (script, dirs to create, files to write) for a corpus that is present and bare.
READERS = [
    ("feed_willow_constitution.py", ["constitution/cases"], {}),
    ("feed_willow_migrations.py", ["migrations"], {}),
    ("feed_willow19_plans.py", ["docs/superpowers/plans", "docs/superpowers/specs"], {}),
    ("feed_jeles_sources.py", ["jeles"], {"jeles/sources.py": "SOURCES: dict = {}\n"}),
]

#: Readers that cannot answer at all without a corpus — an audit against zero
#: rules is not a clean audit, so these refuse rather than reporting a pass.
AUDITS = ["audit_against_constitution.py", "audit_against_jeles.py"]

ALL = [name for name, _, _ in READERS] + AUDITS

#: The vocabulary. Mirrored rather than imported: these are the words a reader
#: sees, and importing the strings would make the pin true by construction.
COULD_NOT_LOOK = "could not look"
TRUE_EMPTY = "true empty"


def run(script: str, repo: pathlib.Path) -> subprocess.CompletedProcess:
    done = subprocess.run([sys.executable, str(SCRIPTS / script), "--repo", str(repo)],
                          capture_output=True, text=True, timeout=300, cwd=str(ROOT))
    done.stdout = re.sub(r"\x1b\[[0-9;]*m", "", done.stdout)
    done.stderr = re.sub(r"\x1b\[[0-9;]*m", "", done.stderr)
    return done


def build(base: pathlib.Path, dirs, files) -> pathlib.Path:
    for d in dirs:
        (base / d).mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        (base / name).write_text(body, encoding="utf-8")
    return base


@pytest.mark.parametrize("script", ALL)
def test_an_absent_corpus_refuses(script, tmp_path):
    """Exit 1, and the words say it could not look — never a clean zero."""
    done = run(script, tmp_path / "nothing-here")
    assert done.returncode == 1, f"{script} did not refuse an absent corpus"
    assert COULD_NOT_LOOK in (done.stdout + done.stderr).lower(), (
        f"{script} refused without saying it could not look — a reader cannot "
        f"tell that from a corpus that was read and found empty")


@pytest.mark.parametrize("script", ALL)
def test_a_bare_directory_is_still_absent(script, tmp_path):
    """A directory with nothing in it is not the corpus. This is the fixture
    mistake that produced a false finding against feed_willow19_plans.py: the
    parent existed, the corpus directories did not, and "I could not look" was
    the correct answer being read as a defect."""
    done = run(script, tmp_path)
    assert done.returncode == 1, f"{script} treated an empty directory as a corpus"


@pytest.mark.parametrize("script,dirs,files", READERS)
def test_a_present_but_empty_corpus_is_not_a_failure(script, dirs, files, tmp_path):
    """Exit 0, and in different words from the refusal. This is the distinction
    two of these readers did not have until they were run empty."""
    done = run(script, build(tmp_path, dirs, files))
    assert done.returncode == 0, (
        f"{script} failed on a corpus that is present and empty:\n{done.stdout[-500:]}")
    out = done.stdout.lower()
    assert TRUE_EMPTY in out, f"{script} did not name the empty as a true empty"
    assert COULD_NOT_LOOK not in out, (
        f"{script} used the refusal vocabulary for a corpus it successfully read")


def test_the_plans_reader_names_which_directories_it_actually_found(tmp_path):
    """It looks for two and reports on the ones present.

    It said "the plan directories exist and hold 0 .md files" whenever *either*
    existed, so a deployment whose specs/ was missing or misspelled was told both
    were checked and both were empty. The empty case is the one nobody re-reads
    the path for, which is where a plural that is sometimes singular does its
    damage.
    """
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    done = run("feed_willow19_plans.py", tmp_path)
    assert done.returncode == 0
    assert "superpowers/plans" in done.stdout
    assert "not found at all" in done.stdout and "superpowers/specs" in done.stdout, (
        "the directory that was not there must be named, or its absence is "
        "indistinguishable from its being empty")


@pytest.mark.parametrize("script", ALL)
def test_no_reader_writes_into_the_checkout_it_reads(script, tmp_path):
    """A reader that leaves anything behind is not reading. Pinned on the
    directory contents, not on the absence of a write call."""
    repo = tmp_path / "repo"
    repo.mkdir()
    before = sorted(p.relative_to(repo) for p in repo.rglob("*"))
    run(script, repo)
    assert sorted(p.relative_to(repo) for p in repo.rglob("*")) == before
