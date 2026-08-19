"""The git-decisions pipeline: merged pull requests as decisions already made.

Every case here is a defect the first run actually produced, kept as a test
because each was invisible to the code and obvious in the output:

* the pair mapped a title to itself, so the store learned nothing it could serve
* the branch-suffix stripper ate ``master`` off ``repin-nestor-to-master``
* eleven of twenty-two repositories died on ``ConflictingDraftError`` because a
  topic decided twice is a revision, not a collision
* forty-three ``Merge branch 'master' into …`` back-merges arrived as decisions
  with an empty question

The last invariant is the one that matters most and is easiest to lose: a merge
proves a person chose something once. It is not a seal, and nothing in this
pipeline is entitled to write one.
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts" / "git_decisions"
EMAIL = "operator@example.com"


def git(repo: pathlib.Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, check=True)
    return done.stdout


def make_repo(root: pathlib.Path, name: str, remote: str | None = None) -> pathlib.Path:
    """A real repository — these tests exercise git, so they use one."""
    repo = root / name
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "master")
    git(repo, "config", "user.email", EMAIL)
    git(repo, "config", "user.name", "Operator")
    if remote:
        git(repo, "remote", "add", "origin", f"https://github.com/{remote}.git")
    (repo / "f.txt").write_text("0\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "initial")
    return repo


def merge_pr(repo: pathlib.Path, number: int, branch: str, title: str,
             owner: str = "owner") -> None:
    """A merge shaped exactly like GitHub's: PR number and branch in the
    subject, the pull request's title in the body."""
    git(repo, "checkout", "-q", "-B", branch, "master")
    f = repo / "f.txt"
    f.write_text(f.read_text() + f"{number}\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", f"work for {branch}")
    git(repo, "checkout", "-q", "master")
    git(repo, "merge", "--no-ff", "-q", branch,
        "-m", f"Merge pull request #{number} from {owner}/{branch}\n\n{title}")


def run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args],
                          capture_output=True, text=True, cwd=str(ROOT))


def pairs(db: pathlib.Path) -> list[tuple[str, str, str]]:
    """Live rows only.

    A revision keeps the old proposal as history rather than deleting it, and it
    stays a ``draft`` — being revised is not a change of status, it is a change
    of which row is current. So "live" is ``superseded_by`` being empty, not
    anything in ``status``; reading ``status`` alone counts the history as if it
    were the answer.
    """
    return sqlite3.connect(db).execute(
        "SELECT source_text, target_text, status FROM tm_pairs "
        "WHERE superseded_by IS NULL OR superseded_by = ''").fetchall()


def every_row(db: pathlib.Path) -> list[tuple[str, str, str]]:
    """Live rows and their history — what the revision test needs to see."""
    return sqlite3.connect(db).execute(
        "SELECT source_text, target_text, status FROM tm_pairs").fetchall()


# --- the covenant, first ----------------------------------------------------

def test_nothing_the_pipeline_writes_is_ever_sealed(tmp_path):
    """The forbidden act. A merge is evidence a person chose something once; it
    is not that person sealing it now, and no volume of merges may add up to a
    seal nobody performed."""
    repo = make_repo(tmp_path, "r", remote="owner/r")
    merge_pr(repo, 1, "claude/first-thing", "feat: the first thing")
    merge_pr(repo, 2, "claude/second-thing", "fix: the second thing")
    out = tmp_path / "r.db"

    done = run("extract.py", "--repo", str(repo), "--email", EMAIL,
               "--out", str(out), "--quiet")
    assert done.returncode == 0, done.stderr
    rows = pairs(out)
    assert rows, "expected decisions"
    assert {status for _, _, status in rows} == {"draft"}


# --- the pair -------------------------------------------------------------

def test_the_pair_is_not_a_title_mapped_to_itself(tmp_path):
    """The first flaw. Source and target were both the PR title, so asking the
    title returned the title and nothing was learnable from the store."""
    repo = make_repo(tmp_path, "r", remote="owner/r")
    merge_pr(repo, 1, "claude/soft-nestor-seam",
             "fix: make the Nestor citation seam soft (optional dependency)")
    out = tmp_path / "r.db"
    run("extract.py", "--repo", str(repo), "--email", EMAIL,
        "--out", str(out), "--quiet")

    (source, target, _), = pairs(out)
    assert source != target
    assert source == "soft nestor seam"
    assert target.startswith("fix: make the Nestor citation seam soft")


def test_a_real_word_is_not_mistaken_for_an_agent_suffix(tmp_path):
    """``repin-nestor-to-master`` lost ``master`` to a suffix rule meant for
    random agent tags. Only agent-prefixed branches carry those."""
    repo = make_repo(tmp_path, "r", remote="owner/r")
    merge_pr(repo, 1, "chore/repin-nestor-to-master",
             "chore: repin Nestor dep from deleted branch to master")
    merge_pr(repo, 2, "claude/llm-only-joke-ei08dl", "feat: the joke")
    out = tmp_path / "r.db"
    run("extract.py", "--repo", str(repo), "--email", EMAIL,
        "--out", str(out), "--quiet")

    sources = {source for source, _, _ in pairs(out)}
    assert "repin nestor to master" in sources     # the word survives
    assert "llm only joke" in sources              # the random tag does not


# --- what is not a decision ------------------------------------------------

def test_a_back_merge_is_not_a_decision(tmp_path):
    """``Merge branch 'master' into feature`` keeps a branch current. It has no
    PR, no title and no body, and arrived as a row with an empty question."""
    repo = make_repo(tmp_path, "r", remote="owner/r")
    git(repo, "checkout", "-q", "-b", "feature")
    (repo / "g.txt").write_text("feature work\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "work on the feature")
    git(repo, "checkout", "-q", "master")
    merge_pr(repo, 1, "claude/real-work", "feat: real work")
    # master has moved on; only now is pulling it into `feature` a real merge.
    git(repo, "checkout", "-q", "feature")
    git(repo, "merge", "--no-ff", "-q", "master",
        "-m", "Merge branch 'master' into feature")
    git(repo, "checkout", "-q", "master")
    out = tmp_path / "r.db"

    done = run("extract.py", "--repo", str(repo), "--email", EMAIL, "--out", str(out))
    assert done.returncode == 0, done.stderr
    assert len(pairs(out)) == 1, "only the real merge is a decision"
    assert "back-merge" in done.stdout, "and the pipeline says what it set aside"


def test_a_robot_merge_is_counted_and_set_aside(tmp_path):
    """A release bot's merge happened; nobody chose it in the moment. Counted
    rather than dropped, so the totals can be checked."""
    repo = make_repo(tmp_path, "r", remote="owner/r")
    merge_pr(repo, 1, "claude/real-work", "feat: real work")
    merge_pr(repo, 2, "release-please--branches--master",
             "chore(master): release 1.2.3")
    out = tmp_path / "r.db"

    done = run("extract.py", "--repo", str(repo), "--email", EMAIL, "--out", str(out))
    assert len(pairs(out)) == 1
    assert "robot merge" in done.stdout


# --- the same topic, decided again -----------------------------------------

def test_deciding_one_topic_twice_revises_rather_than_failing(tmp_path):
    """Eleven repositories died here. One long-running branch carried eighteen
    merges; the store refused to let a second proposal overwrite the first, and
    was right to. A repeat is a revision — the earlier proposal is kept as
    history, and the newest is the one left standing."""
    repo = make_repo(tmp_path, "r", remote="owner/r")
    merge_pr(repo, 1, "claude/mcp-sandbox-setup", "feat: sandbox, first pass")
    merge_pr(repo, 2, "claude/mcp-sandbox-setup", "fix: sandbox, second pass")
    merge_pr(repo, 3, "claude/mcp-sandbox-setup", "fix: sandbox, third pass")
    out = tmp_path / "r.db"

    done = run("extract.py", "--repo", str(repo), "--email", EMAIL, "--out", str(out))
    assert done.returncode == 0, done.stderr
    live = [r for r in pairs(out) if r[0] == "mcp sandbox setup"]
    kept = [r for r in every_row(out) if r[0] == "mcp sandbox setup"]
    assert len(live) == 1, "one live proposal for the topic"
    assert live[0][1] == "fix: sandbox, third pass", "the newest one stands"
    assert len(kept) == 3, "and the earlier two are kept as history, not dropped"
    assert "revision" in done.stdout


# --- identity ---------------------------------------------------------------

def test_a_repository_is_owner_and_name_because_the_name_is_not_unique(tmp_path):
    """Five organisations on the box each have a ``.github``. Keyed on the bare
    name they are one row silently overwriting four others."""
    root = tmp_path / "box"
    make_repo(root, "orgA/dotgithub", remote="orgA/.github")
    make_repo(root, "orgB/dotgithub", remote="orgB/.github")
    manifest = tmp_path / "m.json"

    done = run("inventory.py", "--root", str(root), "--email", EMAIL,
               "--out", str(manifest))
    assert done.returncode == 0, done.stderr
    names = {r["name"] for r in json.loads(manifest.read_text())["repos"]}
    assert names == {"orgA/.github", "orgB/.github"}


def test_the_manifest_is_ordered_smallest_first(tmp_path):
    """The ordering is the method: the smallest rung is the one a person can
    read in full, so it is the one that proves the shape."""
    root = tmp_path / "box"
    big = make_repo(root, "big", remote="owner/big")
    for i in range(1, 4):
        merge_pr(big, i, f"claude/thing-{i}", f"feat: thing {i}")
    small = make_repo(root, "small", remote="owner/small")
    merge_pr(small, 1, "claude/only-thing", "feat: the only thing")
    manifest = tmp_path / "m.json"

    run("inventory.py", "--root", str(root), "--email", EMAIL, "--out", str(manifest))
    order = [r["name"] for r in json.loads(manifest.read_text())["repos"]]
    assert order == ["owner/small", "owner/big"]


# --- the runner -------------------------------------------------------------

@pytest.mark.parametrize("flag,expect_second", [([], True), (["--stop-after", "1"], False)])
def test_the_runner_walks_the_manifest_in_order(tmp_path, flag, expect_second):
    root = tmp_path / "box"
    big = make_repo(root, "big", remote="owner/big")
    for i in range(1, 4):
        merge_pr(big, i, f"claude/thing-{i}", f"feat: thing {i}")
    small = make_repo(root, "small", remote="owner/small")
    merge_pr(small, 1, "claude/only-thing", "feat: the only thing")
    manifest = tmp_path / "m.json"
    out_dir = tmp_path / "stores"
    run("inventory.py", "--root", str(root), "--email", EMAIL, "--out", str(manifest))

    done = run("run_all.py", "--manifest", str(manifest), "--out-dir", str(out_dir),
               "--email", EMAIL, *flag)
    assert done.returncode == 0, done.stderr
    assert (out_dir / "owner__small.db").exists()
    assert (out_dir / "owner__big.db").exists() is expect_second


def test_resume_does_not_redo_a_rung_already_extracted(tmp_path):
    root = tmp_path / "box"
    small = make_repo(root, "small", remote="owner/small")
    merge_pr(small, 1, "claude/only-thing", "feat: the only thing")
    manifest = tmp_path / "m.json"
    out_dir = tmp_path / "stores"
    run("inventory.py", "--root", str(root), "--email", EMAIL, "--out", str(manifest))
    run("run_all.py", "--manifest", str(manifest), "--out-dir", str(out_dir),
        "--email", EMAIL)

    again = run("run_all.py", "--manifest", str(manifest), "--out-dir", str(out_dir),
                "--email", EMAIL, "--resume")
    assert again.returncode == 0, again.stderr
    assert "skipped" in again.stdout
