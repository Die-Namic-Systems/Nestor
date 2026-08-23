"""`scripts/feed_fleet_repos.py` — presence read from disk, and both gaps named.

The reader-fail-closed family (`tests/test_corpus_readers_fail_closed.py`) pins
the feeders that take a `--repo` and parse a declaration out of it. This one
takes a `--root` full of clones and carries its corpus as a literal, so it gets
its own file rather than a row in that table.

What is worth gating here is not the briefs — they are drafts precisely because
nobody has checked them. It is the two directions of disagreement between the
survey and the disk. A survey that silently skips a repo it does not recognise
is the failure that produced this script's own corrections, so the branch that
reports one is the branch most worth a test.
"""
from __future__ import annotations

import pathlib
import sqlite3
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "feed_fleet_repos.py"

# Mirrored, not imported: importing SURVEY would make every assertion about it
# true by construction. tests/test_ledger_kinds.py sets the precedent.
A_SURVEYED_REPO = "willow-gate"


def make_clone(root: pathlib.Path, name: str) -> pathlib.Path:
    repo = root / name
    (repo / ".git").mkdir(parents=True)
    return repo


def run(root: pathlib.Path, db: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    argv = [sys.executable, str(SCRIPT), "--root", str(root)]
    if db is not None:
        argv += ["--db", str(db)]
    return subprocess.run(argv, capture_output=True, text=True, cwd=str(ROOT),
                          check=False)


def test_a_missing_root_says_it_could_not_look(tmp_path):
    """The distinction the whole reader family exists to keep: 'I could not
    look' is not 'I looked and the box was empty'."""
    done = run(tmp_path / "nope")
    assert done.returncode == 1
    assert "could not look" in done.stdout
    assert "different facts" in done.stdout


def test_only_repos_present_on_disk_get_a_row(tmp_path):
    root = tmp_path / "box"
    root.mkdir()
    make_clone(root, A_SURVEYED_REPO)
    db = tmp_path / "nestor.db"

    done = run(root, db)
    assert done.returncode == 0, done.stdout + done.stderr

    rows = sqlite3.connect(db).execute(
        "SELECT source_text, status FROM tm_pairs").fetchall()
    assert [r[0] for r in rows] == [A_SURVEYED_REPO]
    # The rest of the survey is not on this disk, so it is reported, not written.
    assert "in the survey, not on disk" in done.stdout


def test_every_row_lands_as_a_draft(tmp_path):
    """A brief is a reading of a README. Nothing in this path may seal one."""
    root = tmp_path / "box"
    root.mkdir()
    make_clone(root, A_SURVEYED_REPO)
    db = tmp_path / "nestor.db"

    run(root, db)
    statuses = {r[0] for r in sqlite3.connect(db).execute(
        "SELECT status FROM tm_pairs").fetchall()}
    assert statuses == {"draft"}
    assert not sqlite3.connect(db).execute(
        "SELECT 1 FROM tm_pairs WHERE verifier != ''").fetchall()


def test_a_clone_the_survey_never_covered_is_reported(tmp_path):
    """The failure that already happened: a repo dropped without a word.

    A survey can only be trusted about what it looked at, so the thing it must
    never do is stay quiet about a clone it does not recognise.
    """
    root = tmp_path / "box"
    root.mkdir()
    make_clone(root, A_SURVEYED_REPO)
    make_clone(root, "a-repo-no-survey-has-heard-of")

    done = run(root, tmp_path / "nestor.db")
    assert done.returncode == 0
    assert "on disk, not in the survey" in done.stdout
    assert "a-repo-no-survey-has-heard-of" in done.stdout


def test_agreement_is_only_claimed_when_both_directions_are_empty(tmp_path):
    """'survey and disk agree' is a strong sentence and must not print while
    either gap is non-empty — the two ways of being wrong that this reports."""
    root = tmp_path / "box"
    root.mkdir()
    make_clone(root, A_SURVEYED_REPO)          # absent list is non-empty
    make_clone(root, "an-unsurveyed-clone")    # extra list is non-empty

    done = run(root, tmp_path / "nestor.db")
    assert "survey and disk agree" not in done.stdout


@pytest.mark.parametrize("name", ["not-a-clone"])
def test_a_directory_without_git_is_not_a_checkout(tmp_path, name):
    """Presence is a clone, not a directory that happens to share the name."""
    root = tmp_path / "box"
    root.mkdir()
    (root / A_SURVEYED_REPO).mkdir()           # no .git inside
    (root / name).mkdir()
    db = tmp_path / "nestor.db"

    done = run(root, db)
    assert done.returncode == 0
    assert not sqlite3.connect(db).execute("SELECT 1 FROM tm_pairs").fetchall()
    # and the bare directory is not announced as an unsurveyed clone either
    assert name not in done.stdout


def test_it_does_not_write_into_the_box_it_reads(tmp_path):
    """A reader that mutates what it surveys cannot be run twice honestly."""
    root = tmp_path / "box"
    root.mkdir()
    make_clone(root, A_SURVEYED_REPO)
    before = sorted(p.relative_to(root) for p in root.rglob("*"))

    run(root, tmp_path / "nestor.db")
    assert sorted(p.relative_to(root) for p in root.rglob("*")) == before


# --- Identity is the remote, not the directory ------------------------------
#
# SURVEY is keyed by the GitHub repository name; a clone directory is whatever
# the person cloning it typed. On the fleet box those disagree constantly --
# `willow` holds `Willow`, `dotgithub` holds `.github`, `.willow` holds
# `willow-config`, `willow-grove` holds `safe-app-willow-grove`. Matching on the
# directory surveyed eight repositories as absent and simultaneously reported
# them under "on disk, not in the survey", the branch whose stated job is
# catching a repo the survey dropped: it fired correctly and named the wrong
# cause.

def real_clone(root: pathlib.Path, directory: str, remote: str) -> pathlib.Path:
    """A clone whose directory name and repository name differ, as on the box."""
    repo = root / directory
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "remote", "add", "origin",
                    f"https://github.com/someone/{remote}.git"],
                   cwd=repo, check=True)
    return repo


def test_a_clone_is_found_under_its_repository_name_not_its_directory(tmp_path):
    """The case that was silently missing every flagship repo in the fleet."""
    root = tmp_path / "box"
    root.mkdir()
    real_clone(root, "some-local-name", A_SURVEYED_REPO)

    done = run(root)
    assert done.returncode == 0, done.stderr
    assert "1 repo(s) written" in done.stdout
    # and it must NOT be reported as an uncovered clone
    assert "on disk, not in the survey" not in done.stdout


def test_a_clone_with_no_remote_falls_back_to_its_directory_name(tmp_path):
    """A local-only clone has no better answer than the directory it sits in.

    The fallback is what keeps this change from turning every remote-less
    checkout into an unsurveyed one.
    """
    root = tmp_path / "box"
    root.mkdir()
    repo = root / A_SURVEYED_REPO
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

    done = run(root)
    assert done.returncode == 0, done.stderr
    assert "1 repo(s) written" in done.stdout


def test_two_clones_of_one_repository_do_not_silently_shadow_each_other(tmp_path):
    """Keeping the first and hiding the second would be a survey that lies.

    The duplicate is surfaced under the uncovered-clone branch instead, where a
    person sees it.
    """
    root = tmp_path / "box"
    root.mkdir()
    real_clone(root, "first", A_SURVEYED_REPO)
    real_clone(root, "second", A_SURVEYED_REPO)

    done = run(root)
    assert done.returncode == 0, done.stderr
    assert "1 repo(s) written" in done.stdout
    assert "on disk, not in the survey" in done.stdout
    assert "second" in done.stdout
