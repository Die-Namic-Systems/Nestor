"""The top — pinned on the distinction it exists to keep.

`scripts/feed_all.py` runs the feeders and reports four states. The one that
matters is that **three different reasons for "0 rows" stay three different
reasons**: the corpus was empty, the corpus could not be read, or no checkout
was supplied. A summary that collapsed them would be the same defect the package
refuses for answers — *nothing matched* and *I could not look* are not the same
sentence.

That defect was real and recent. Both feeders printed identical words for an
unreadable registry and an empty one until running them against an empty
repository showed it. These tests are what stops it coming back.

Everything here builds its own fixture corpora, so it runs in CI with no willow
or jeles checkout present.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
TOP = REPO / "scripts" / "feed_all.py"
sys.path.insert(0, str(REPO / "scripts"))


def run(*args):
    return subprocess.run([sys.executable, str(TOP), "--quiet", *args],
                          capture_output=True, text=True, cwd=REPO, timeout=300)


@pytest.fixture()
def readable_but_empty(tmp_path):
    """A checkout whose corpora exist and declare nothing."""
    (tmp_path / "constitution" / "cases").mkdir(parents=True)
    (tmp_path / "jeles").mkdir()
    (tmp_path / "jeles" / "sources.py").write_text("SOURCES: dict[str, dict] = {}\n")
    return tmp_path


def test_no_checkouts_is_skipped_not_empty():
    done = run()
    assert done.returncode == 0
    assert "4 skipped" in done.stdout
    assert "0 empty" in done.stdout, "supplying nothing is not the same as an empty corpus"


def test_a_readable_empty_corpus_is_empty_not_unreadable(readable_but_empty):
    done = run("--willow-2", str(readable_but_empty), "--jeles", str(readable_but_empty))
    assert done.returncode == 0, "a true empty is not a failure"
    assert "2 empty" in done.stdout and "2 skipped" in done.stdout
    assert "0 unreadable" in done.stdout


def test_a_missing_path_is_unreadable_not_empty(tmp_path):
    done = run("--willow-2", str(tmp_path / "nope"), "--jeles", str(tmp_path / "nope"))
    assert done.returncode == 1, "not knowing must not exit clean"
    assert "2 unreadable" in done.stdout
    assert "0 empty" in done.stdout


def test_an_unparseable_registry_is_unreadable_not_empty(tmp_path):
    """The precise case the feeders used to get wrong."""
    (tmp_path / "jeles").mkdir()
    (tmp_path / "jeles" / "sources.py").write_text('SOURCES = {"x": some_call()}\n')
    done = run("--jeles", str(tmp_path))
    assert done.returncode == 1
    assert "1 unreadable" in done.stdout
    assert "0 empty" in done.stdout, (
        "a registry the parser cannot understand is not an empty registry — "
        "these printed the same words until 2026-08-06")


def test_the_three_zero_row_verdicts_do_not_read_alike(tmp_path, readable_but_empty):
    """All three report no rows. None of them may report it the same way."""
    said = {
        "skipped": run().stdout,
        "empty": run("--jeles", str(readable_but_empty)).stdout,
        "unreadable": run("--jeles", str(tmp_path / "nope")).stdout,
    }
    for state, out in said.items():
        assert "0 fed" in out, f"{state} should still be zero rows fed"
    assert said["skipped"] != said["empty"] != said["unreadable"]
    assert "1 empty" in said["empty"] and "1 empty" not in said["unreadable"]
    assert "1 unreadable" in said["unreadable"]


def test_mixed_outcomes_are_not_averaged(tmp_path, readable_but_empty):
    done = run("--willow-2", str(readable_but_empty), "--jeles", str(tmp_path / "nope"))
    assert done.returncode == 1, "one unreadable corpus fails the run"
    assert "1 empty" in done.stdout and "1 unreadable" in done.stdout


def test_it_runs_feeders_as_subprocesses():
    """Each feeder installs a process-wide store, ledger and matcher.

    Importing them into one interpreter would make the last one win — which is
    `demo/desks.py`'s entire subject, and the reason this is pinned rather than
    left as a comment.
    """
    body = TOP.read_text().split('"""', 2)[-1]
    assert "subprocess.run" in body
    for forbidden in ("importlib", "from feed_", "import feed_"):
        assert forbidden not in body, f"the top must not {forbidden}"


def test_every_registered_feeder_exists():
    """A feed named in the top and missing from disk would report unreadable —
    which would read as a corpus problem rather than a wiring one."""
    import feed_all                      # noqa: E402
    for _, script, _ in feed_all.FEEDS:
        assert (REPO / "scripts" / script).exists(), f"{script} is registered but absent"


def test_all_four_feeds_are_registered():
    import feed_all                      # noqa: E402
    assert len(feed_all.FEEDS) == 4
    flags = {f for f, _, _ in feed_all.FEEDS}
    assert flags == {"willow_2", "jeles", "willow_2_migrations", "willow_19"}


def test_the_archived_and_migration_feeders_refuse_a_missing_corpus(tmp_path):
    """Both late feeders must distinguish absent from empty, like the first two."""
    for flag in ("--willow-2-migrations", "--willow-19"):
        done = run(flag, str(tmp_path / "nope"))
        assert done.returncode == 1, f"{flag} must refuse a path it cannot read"
        assert "1 unreadable" in done.stdout and "0 empty" in done.stdout
