"""corpus_contamination flags a corpus path that is not in the commit it claims.

The mechanism under test is a port of safe-app-willow-grove
``tests/test_security_audit_scope.py`` (lines 27-33, ``_tracked_sources`` — the
``git ls-files`` scope enumeration): the allowed scope is the tree ``git
ls-files`` reports, and a corpus row whose origin names a path outside that tree
is contamination — a working-tree file that is in no commit.

The forbidden act is a row filed under a repo revision for a path that revision
does not contain (the IDEAS §6.102 ``.venv/site-packages`` case). The refusal
test stages exactly that and asserts the check FLAGS it. The happy path stages a
store whose every origin names a committed file and asserts a clean verdict. A
third test pins the fail-closed edge: when ``git ls-files`` cannot enumerate the
scope, the tool reports UNKNOWN and never "clean".
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import shutil
import sqlite3
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "corpus_contamination.py"

if shutil.which("git") is None:  # pragma: no cover - git is present in CI
    pytest.skip("git is required for the scope enumeration", allow_module_level=True)


def _load_module():
    spec = importlib.util.spec_from_file_location("corpus_contamination", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cc = _load_module()

# A committed file, and a contaminating one that is in the working tree only.
TRACKED = {"CONSTITUTION.md": "law\n", "docs/a.md": "notes\n"}
CONTAMINANT = ".venv/lib/python3.11/site-packages/evil.py"


def _git(repo: pathlib.Path, *args: str) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }
    subprocess.run(["git", "-C", str(repo), *args],
                   check=True, capture_output=True, text=True, env=env)


@pytest.fixture
def repo(tmp_path) -> pathlib.Path:
    """A tmp git checkout: TRACKED committed, CONTAMINANT present but untracked."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    for rel, body in TRACKED.items():
        p = r / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
        _git(r, "add", rel)
    _git(r, "commit", "-q", "-m", "seed")
    # The contaminant sits in the working tree and is committed to nothing.
    evil = r / CONTAMINANT
    evil.parent.mkdir(parents=True, exist_ok=True)
    evil.write_text("import os\n", encoding="utf-8")
    return r


def _origin(path: str, anchor: str = "Sec", shape: str = "decision") -> str:
    """An origin in scripts/corpus/provenance.py's shape."""
    tail = f"#{anchor}" if anchor else ""
    return f"myrepo@abc1234:{path}{tail} [{shape}/deadbee]"


def _store(path: pathlib.Path, origins) -> pathlib.Path:
    con = sqlite3.connect(str(path))
    try:
        con.execute("CREATE TABLE tm_pairs (origin TEXT NOT NULL, created_at TEXT)")
        con.executemany(
            "INSERT INTO tm_pairs (origin, created_at) VALUES (?, '2026-08-13')",
            [(o,) for o in origins],
        )
        con.commit()
    finally:
        con.close()
    return path


# --- the ported unit: git ls-files IS the allowed scope --------------------

def test_tracked_files_are_the_allowed_scope(repo):
    """tracked_files returns exactly the committed paths, not the working tree."""
    allowed = cc.tracked_files(repo)
    assert allowed == set(TRACKED)
    assert CONTAMINANT not in allowed  # in the tree, in no commit


def test_origin_path_parses_the_provenance_shape():
    assert cc.origin_path(_origin("docs/a.md")) == "docs/a.md"
    assert cc.origin_path(_origin(CONTAMINANT, anchor="")) == CONTAMINANT
    assert cc.origin_path("") == ""  # unshaped -> no path


# --- refusal: the forbidden act is detected --------------------------------

def test_flags_a_corpus_path_outside_the_committed_scope(repo, tmp_path):
    """FORBIDDEN ACT: a row filed under a revision for a path it does not contain.

    This is the IDEAS §6.102 case in miniature — a `.venv/site-packages` path
    stamped with the repo's revision. The check must flag it.
    """
    db = _store(tmp_path / "dirty.db", [
        _origin("CONSTITUTION.md"),
        _origin("docs/a.md"),
        _origin(CONTAMINANT, anchor=""),          # contamination
    ])
    allowed = cc.tracked_files(repo)
    total, counts, unshaped = cc.audit(db, allowed)

    assert total == 3
    assert CONTAMINANT in counts, "out-of-scope path was NOT flagged"
    assert counts[CONTAMINANT] == 1
    assert set(counts) == {CONTAMINANT}, "an in-scope path was wrongly flagged"
    assert unshaped == 0


def test_cli_fails_closed_on_contamination(repo, tmp_path):
    """The gate exits 1 and names the contaminated store."""
    db = _store(tmp_path / "dirty.db", [
        _origin("docs/a.md"),
        _origin(CONTAMINANT, anchor=""),
    ])
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo),
         "--db", str(db), "--fail-on-contamination"],
        capture_output=True, text=True, cwd=str(ROOT), check=False,
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert CONTAMINANT in proc.stdout
    assert "contaminated" in proc.stdout


# --- happy path: a clean corpus reads clean --------------------------------

def test_clean_corpus_has_no_out_of_scope_paths(repo, tmp_path):
    db = _store(tmp_path / "clean.db", [
        _origin("CONSTITUTION.md"),
        _origin("docs/a.md", anchor="Other"),
    ])
    allowed = cc.tracked_files(repo)
    total, counts, unshaped = cc.audit(db, allowed)

    assert total == 2
    assert counts == {}, f"clean corpus flagged: {counts}"
    assert unshaped == 0


def test_cli_reports_clean_and_exits_zero(repo, tmp_path):
    db = _store(tmp_path / "clean.db", [_origin("docs/a.md")])
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo),
         "--db", str(db), "--fail-on-contamination"],
        capture_output=True, text=True, cwd=str(ROOT), check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "every origin names a git-tracked path" in proc.stdout


# --- fail-closed: absence surfaces as UNKNOWN, never as "no findings" -------

def test_scope_unavailable_when_not_a_checkout(tmp_path):
    """A non-git dir raises rather than returning an empty (falsely-clean) set."""
    plain = tmp_path / "not_git"
    plain.mkdir()
    with pytest.raises(cc.ScopeUnavailable):
        cc.tracked_files(plain)


def test_cli_reports_unknown_when_scope_cannot_be_read(tmp_path):
    """No scope -> UNKNOWN and a non-zero exit, not a clean verdict."""
    plain = tmp_path / "not_git"
    plain.mkdir()
    db = _store(tmp_path / "some.db", [_origin("docs/a.md")])
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(plain), "--db", str(db)],
        capture_output=True, text=True, cwd=str(ROOT), check=False,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "UNKNOWN" in proc.stdout
    assert "every origin names a git-tracked path" not in proc.stdout
