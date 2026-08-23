"""Gates for `scripts/ci_venv.py` — the tool that runs the suite CI's way.

The script's whole claim is that it *reads* what CI does instead of restating
it, so the tests that earn their place are the refusals: what happens when the
workflow stops saying what the script needs. A drift-detector that silently
falls back to a remembered value is the drift it was built to catch, and it
would look exactly like a working tool right up until the moment it mattered.

Nothing here builds a venv or runs a suite. Those take minutes and need
interpreters this machine may not have; the parsing and the refusals are what
can go quietly wrong.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import ci_venv


@pytest.fixture()
def workflow() -> str:
    return ci_venv._workflow_text()


# --- it reads the real workflow, and agrees with it -------------------------

def test_it_reads_the_matrix_this_repo_actually_has(workflow):
    versions = ci_venv.matrix_versions(workflow)
    assert versions, "the workflow has a matrix; the parser must find it"
    assert all(v[0].isdigit() and "." in v for v in versions)


def test_the_parsed_facts_appear_verbatim_in_the_workflow(workflow):
    """Not 'something plausible was parsed' — the exact substring is in the file.

    This is the assertion that fails when the workflow is reworded and the
    script keeps returning a stale-but-well-formed answer."""
    for parsed in (ci_venv.install_line(workflow), ci_venv.test_command(workflow)):
        assert parsed in workflow


def test_the_test_command_is_not_python_dash_m_pytest(workflow):
    """CI runs bare `pytest` under coverage while `AGENTS.md` says
    `python -m pytest -q` — and that is *not* a gap, which is worth pinning
    precisely because it looks like one.

    `-m` puts the repo root on `sys.path` where bare `pytest` does not, and the
    workflow comments that the disagreement once hid five tests. The repo closed
    it on 2026-07-31 in `319292a` with `pythonpath = ["."]` in pyproject.toml —
    "pin the path so the invocation stops mattering" — and measured on one tree
    with one command changed, the two now give identical counts.

    So this test guards the shape, not a difference: if CI ever moves to
    `python -m`, the script's premise about which command to run changes and
    this fails. The test below guards `pythonpath` itself staying put."""
    command = ci_venv.test_command(workflow)
    assert "python -m pytest" not in command
    assert "pytest" in command


def test_pythonpath_is_pinned_so_the_invocation_cannot_matter():
    """The line that makes the two commands equivalent, and nothing guarded it.

    `pythonpath = ["."]` (pyproject.toml, `319292a`) is why bare `pytest` and
    `python -m pytest` collect the same suite. Delete it and they diverge again
    — silently, and in the direction where a developer's green is a subset of
    CI's. `tests/test_bench_coverage.py` is the file that suffered it: five
    guards that "must not be skippable" vanished for anyone typing the bare
    command, and nothing said so.

    Written while correcting a claim in the test above that said this guard
    existed. It did not. Now it does."""
    import re
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r"^pythonpath\s*=\s*\[([^\]]*)\]", text, re.MULTILINE)
    assert m, ("pyproject.toml no longer pins `pythonpath` — bare `pytest` and "
               "`python -m pytest` now collect different suites, and the "
               "bench-coverage guards are the ones that disappear")
    assert '"."' in m.group(1) or "'.'" in m.group(1), m.group(0)


def test_the_install_line_is_the_test_jobs_and_not_the_lint_jobs(workflow):
    """The lint job installs the five gate tools; the test job installs neither
    them nor anything like them. Picking up the wrong `run:` line is how a
    local venv grows five packages CI's test job does not have — which is the
    failure that put both matrix legs red the day before this was written."""
    install = ci_venv.install_line(workflow)
    assert install.startswith("pip install -e")
    for tool in ("ruff", "bandit", "mypy", "detect-secrets", "pip-audit"):
        assert tool not in install


# --- the refusals: it will not guess ----------------------------------------

@pytest.mark.parametrize("missing,needle", [
    ("python-version", "will not guess them"),
    ("pip install -e", "install line"),
    ("coverage run", "will not substitute its own"),
])
def test_a_workflow_that_stops_saying_it_is_refused(tmp_path, workflow, missing,
                                                    needle):
    """Each fact removed in turn. Every one must refuse by name — a partial
    parse that returns two of three facts and defaults the third is the shape
    this whole file is guarding."""
    gutted = "\n".join(line for line in workflow.splitlines()
                       if missing not in line)
    path = tmp_path / "tests.yml"
    path.write_text(gutted, encoding="utf-8")
    text = path.read_text(encoding="utf-8")

    with pytest.raises(ci_venv.WorkflowUnreadable) as exc:
        ci_venv.matrix_versions(text)
        ci_venv.install_line(text)
        ci_venv.test_command(text)
    assert needle in str(exc.value)


def test_a_version_outside_cis_matrix_is_refused_not_run():
    """Running 3.11 when CI runs 3.10 and 3.12 answers a question nobody asked,
    and answers it in a way that reads like coverage."""
    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "ci_venv.py"),
         "--run", "--python", "3.11"],
        capture_output=True, text=True, cwd=str(REPO), check=False)
    assert proc.returncode == 2
    assert "not in CI's matrix" in proc.stderr


def test_listing_runs_nothing_and_exits_zero():
    """`--list` is the safe verb: it must never build or run anything, because
    it is what somebody types to find out what the tool would do."""
    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "ci_venv.py"), "--list"],
        capture_output=True, text=True, cwd=str(REPO), check=False)
    assert proc.returncode == 0
    for label in ("workflow", "matrix", "install", "command", "venvs"):
        assert label in proc.stdout


def test_an_interpreter_lying_about_its_version_is_refused(monkeypatch):
    """A `python3.10` on PATH that is really 3.12 would otherwise be reported as
    a 3.10 run — the script's own failure mode, arriving through PATH."""
    monkeypatch.setattr(ci_venv.shutil, "which",
                        lambda name: "/fake/python3.10" if "python" in name else None)

    class _Result:
        stdout = "3.12\n"
        returncode = 0

    monkeypatch.setattr(ci_venv.subprocess, "run", lambda *a, **k: _Result())
    with pytest.raises(ci_venv.WorkflowUnreadable, match="reports itself as"):
        ci_venv._interpreter("3.10")


def test_a_missing_interpreter_names_the_command_that_gets_one(monkeypatch):
    monkeypatch.setattr(ci_venv.shutil, "which", lambda name: None)
    with pytest.raises(ci_venv.WorkflowUnreadable) as exc:
        ci_venv._interpreter("3.10")
    assert "uv python install 3.10" in str(exc.value)
    assert "Refusing to substitute" in str(exc.value)
