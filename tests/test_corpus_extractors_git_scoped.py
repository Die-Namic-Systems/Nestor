"""§6.101 / §6.102: the corpus extractors themselves, not just the auditor.

`scripts/corpus_contamination.py` (and its tests) detect a contaminated store
after the fact. These tests are about the earlier failure: the extractors that
*produce* the store in the first place.

§6.101 — every `scripts/corpus/extract_*.py` used to exit 0 against a checkout
that does not exist, printing the same ``0 pair(s)`` a checkout that is present
and genuinely empty prints. `common.require_checkout` is the fix; the first
class here parametrizes every `--repo`-based extractor against it, the way
`tests/test_corpus_readers_fail_closed.py` already does for the `feed_*`
family — a script not named here is a script this suite does not cover.

§6.102 — the extractors took their file list from a filesystem walk, so
`.venv/` after this repo's own documented `pip install -e .` was quoted under
the repository's own revision. `common.tracked_files` restricts to `git
ls-files`; the second class exercises it directly and the third drives one
extractor end to end against a constructed checkout with a gitignored
dependency tree, the way the bug actually happened.
"""
from __future__ import annotations

import pathlib
import re
import shutil
import sqlite3
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORPUS = ROOT / "scripts" / "corpus"

sys.path.insert(0, str(CORPUS))
import common  # noqa: E402

if shutil.which("git") is None:  # pragma: no cover - git is present in CI
    pytest.skip("git is required for these tests", allow_module_level=True)

#: Every extractor that takes a `--repo` checkout, with the extra args each
#: needs to run at all (a couple require `--name`; the rest default it or
#: don't take one). `extract_ideas.py` is deliberately absent: it reads git
#: refs of *this* repository rather than an external checkout, and already
#: fails closed (an unresolvable `--ref` raises out of `git rev-parse`).
REPO_EXTRACTORS = {
    "extract_data_vault.py": [],
    "extract_willow_seed.py": [],
    "extract_safe.py": [],
    "extract_willow_config.py": [],
    "extract_willow_20.py": [],
    "extract_openclaw_sap_gate.py": [],
    "extract_willow_grove.py": [],
    "extract_aionic.py": [],
    "extract_safe_app_store_archive.py": [],
    "extract_yggdrasil.py": [],
    "extract_willow_mcp.py": [],
    "extract_willow_19.py": [],
    "extract_willow.py": [],
    "extract_fork.py": ["--name", "test-fork"],
    "extract_standard.py": ["--name", "test-standard"],
    "extract_willow_bot.py": [],
}

COULD_NOT_LOOK = "could not look"


def run(script: str, repo: pathlib.Path, out: pathlib.Path, extra: list[str],
        timeout: int = 60) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(CORPUS / script), "--repo", str(repo),
           "--out", str(out), *extra]
    done = subprocess.run(cmd, capture_output=True, text=True,
                          timeout=timeout, cwd=str(ROOT))
    done.stdout = re.sub(r"\x1b\[[0-9;]*m", "", done.stdout)
    done.stderr = re.sub(r"\x1b\[[0-9;]*m", "", done.stderr)
    return done


def _git(repo: pathlib.Path, *args: str) -> None:
    env = {
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
        "PATH": __import__("os").environ.get("PATH", ""),
        "HOME": __import__("os").environ.get("HOME", ""),
    }
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True, text=True, env=env)


# --- §6.101: every --repo extractor refuses an absent checkout -------------

@pytest.mark.parametrize("script,extra", sorted(REPO_EXTRACTORS.items()))
def test_extractor_refuses_a_nonexistent_checkout(script, extra, tmp_path):
    """FORBIDDEN ACT: exiting 0 against a checkout that was never there."""
    missing = tmp_path / "nothing-here"
    done = run(script, missing, tmp_path / "out.db", extra)
    assert done.returncode != 0, (
        f"{script} exited 0 against a nonexistent checkout — "
        f"stdout:\n{done.stdout}\nstderr:\n{done.stderr}")
    assert COULD_NOT_LOOK in (done.stdout + done.stderr).lower(), (
        f"{script} refused without saying it could not look — "
        f"stdout:\n{done.stdout}\nstderr:\n{done.stderr}")


def test_require_checkout_refuses_a_missing_directory(tmp_path):
    missing = tmp_path / "gone"
    assert common.require_checkout(missing) is False


def test_require_checkout_accepts_a_present_directory(tmp_path):
    present = tmp_path / "here"
    present.mkdir()
    assert common.require_checkout(present) is True


def test_require_checkout_refuses_a_path_that_is_a_file(tmp_path):
    """Not a directory at all — same refusal, not a crash."""
    f = tmp_path / "not-a-dir"
    f.write_text("x", encoding="utf-8")
    assert common.require_checkout(f) is False


# --- §6.102: tracked_files is git-scoped, not filesystem-scoped ------------

@pytest.fixture
def repo_with_dependency_tree(tmp_path) -> pathlib.Path:
    """A checkout shaped like the measured §6.102 case: one real, tracked
    module, and a `.venv/`-shaped dependency tree that is present on disk
    and gitignored — exactly what `pip install -e .` at the repo root
    leaves behind."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    (r / ".gitignore").write_text(".venv/\n", encoding="utf-8")

    tracked = r / "tracked_module.py"
    tracked.write_text(
        '"""TRACKED_MARKER declared by this repository, committed."""\n'
        "def real_thing():\n"
        '    """A function this repository actually wrote."""\n',
        encoding="utf-8",
    )
    _git(r, "add", "tracked_module.py", ".gitignore")
    _git(r, "commit", "-q", "-m", "seed")

    # Present on disk, gitignored, never committed — the dependency.
    dep = r / ".venv" / "lib" / "site-packages" / "somedep" / "core.py"
    dep.parent.mkdir(parents=True, exist_ok=True)
    dep.write_text(
        '"""UNTRACKED_MARKER a dependency\'s docstring, not this repo\'s work."""\n',
        encoding="utf-8",
    )
    return r


def test_tracked_files_excludes_the_gitignored_dependency_tree(
        repo_with_dependency_tree):
    found = common.tracked_files(repo_with_dependency_tree, "*.py")
    names = {p.name for p in found}
    assert "tracked_module.py" in names
    assert not any(".venv" in p.parts for p in found), (
        f".venv/ leaked into a git-scoped walk: {found}")


def test_docstrings_excludes_the_gitignored_dependency_tree(
        repo_with_dependency_tree):
    rows, total = common.docstrings(repo_with_dependency_tree)
    text_blob = " ".join(doc for _sym, doc, *_ in rows)
    assert "TRACKED_MARKER" in text_blob
    assert "UNTRACKED_MARKER" not in text_blob, (
        "a dependency docstring from .venv/ was extracted as if this "
        "repository declared it")


def test_tracked_files_falls_back_to_a_full_walk_off_git(tmp_path, capsys):
    """Not a git checkout at all: same files a plain walk would have found,
    plus a warning — never a silent empty result standing in for '0 rows'."""
    plain = tmp_path / "not-git"
    (plain / "sub").mkdir(parents=True)
    (plain / "sub" / "a.py").write_text("x = 1\n", encoding="utf-8")

    found = common.tracked_files(plain, "*.py")
    assert [p.name for p in found] == ["a.py"]
    err = capsys.readouterr().err
    assert "not a git checkout" in err


# --- end to end: one extractor, driven the way the bug actually happened ---

def test_extract_standard_end_to_end_excludes_the_dependency_tree(
        repo_with_dependency_tree, tmp_path):
    out = tmp_path / "corpus.db"
    done = run("extract_standard.py", repo_with_dependency_tree, out,
               ["--name", "dep-tree-test"])
    assert done.returncode == 0, done.stdout + done.stderr

    con = sqlite3.connect(str(out))
    try:
        rows = con.execute(
            "SELECT source_text, target_text, origin FROM tm_pairs").fetchall()
    finally:
        con.close()

    blob = " ".join(f"{s} {t} {o}" for s, t, o in rows)
    assert "TRACKED_MARKER" in blob or "real_thing" in blob, (
        "the extractor found nothing from the tracked module at all")
    assert "UNTRACKED_MARKER" not in blob, (
        f".venv/ dependency docstring reached the store: {rows}")
    assert not any(".venv" in o for _s, _t, o in rows), (
        f"a row's origin names a path inside .venv/: {rows}")
