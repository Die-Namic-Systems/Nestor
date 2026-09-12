"""C4-tests-yml-nestor — the fleet CI floor, held to the files that declare it.

Fleet plan decision 5 names a floor every repo's `tests.yml` stands on: a
Linux matrix derived from `pyproject.toml`'s Python classifiers, a Windows
leg on the floor and ceiling Pythons, ruff pinned in exactly one place, CodeQL
on python and actions, and an aggregate `test` job that fails when any leg
is anything but a success. Each of those is a fact declared once and easy to
repeat by hand somewhere nothing checks — the shape #292 named — so each is
read from its source here and held to the workflow, with a plant per rule.

The workflow is read as text, not YAML: CI's test job installs `.[keys]` and
pytest only, PyYAML is not among them, and a parser that skipped where the
library was absent would clear the very job it exists to check. The shapes
matched are the ones the file actually uses (`python-version: [...]`,
`needs: [...]`, `if: always()`, a step that names `success`), and a rewording
that moves them fails here by name rather than passing vacuously.

CodeQL is GitHub's default setup on this repo (the three `Analyze (...)`
checks: python, actions, javascript-typescript), not a workflow file, so it
is documented in `tests.yml`'s header rather than parsed here — there is no
file to read, and a codeql.yml would be refused by the default setup.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "tests.yml"
PYPROJECT = REPO / "pyproject.toml"
LINT_PINS = REPO / "scripts" / "lint-pins.txt"

#: The job the fleet's branch protection names; every other job feeds it.
AGGREGATE_JOB = "test"
#: The Linux matrix job and the Windows leg, by the names the file gives them.
LINUX_JOB = "test-matrix"
WINDOWS_JOB = "test-windows"


# --- reading the two sources -----------------------------------------------


def _classifier_minors(pyproject_text: str) -> list[str]:
    """Every `Programming Language :: Python :: 3.X` classifier, in file order.
    The bare `:: 3` classifier is not a minor and is not a matrix entry."""
    return re.findall(
        r'"Programming Language :: Python :: (3\.\d+)"', pyproject_text)


def _job_block(workflow_text: str, job: str) -> str:
    """The text of one job under `jobs:` — from its `  <job>:` line to the
    next job at the same indent, or the end of the file."""
    m = re.search(rf"^  {re.escape(job)}:\n(.*?)(?=^  [\w-]+:\n|\Z)",
                  workflow_text, re.MULTILINE | re.DOTALL)
    if not m:
        raise AssertionError(f"no job named {job!r} in the workflow")
    return m.group(1)


def _job_names(workflow_text: str) -> list[str]:
    """Every job name at the two-space indent under `jobs:`."""
    jobs = workflow_text.split("\njobs:\n", 1)[1]
    return re.findall(r"^  ([\w-]+):\n", jobs, re.MULTILINE)


def _matrix_versions(job_text: str) -> list[str]:
    """The `python-version: [...]` list inside one job's matrix."""
    m = re.search(r"^\s*python-version:\s*\[([^\]]*)\]", job_text, re.MULTILINE)
    return re.findall(r'"(3\.\d+)"', m.group(1)) if m else []


def _aggregate_gate(job_text: str) -> dict:
    """What the aggregate job actually does: which jobs it needs, whether it
    runs `if: always()`, and whether its check names `success` and exits
    non-zero on anything else."""
    needs = re.search(r"^\s*needs:\s*\[([^\]]*)\]", job_text, re.MULTILINE)
    return {
        "needs": [n.strip() for n in needs.group(1).split(",")] if needs else [],
        "always": bool(re.search(r"^\s*if:\s*always\(\)\s*$", job_text, re.MULTILINE)),
        "rejects_non_success": bool(
            re.search(r"""!=\s*["']success["']""", job_text) and re.search(r"sys\.exit\(", job_text)),
    }


def _ruff_pin_sites(workflow_text: str, pins_text: str) -> dict:
    """Where `ruff==<exact>` is written: it must be in the pins file exactly
    once, and the workflow must install from that file and never repeat the
    literal itself."""
    return {
        "pins": re.findall(r"^ruff==(\d+\.\d+\.\d+)\s*$", pins_text, re.MULTILINE),
        # A version must follow: the workflow's own comment may *say* `ruff==`
        # while pointing at the pins file, and that is not a second pin.
        "workflow_literals": re.findall(r"ruff==\d[\w.]*", workflow_text),
        "installs_from_pins": "pip install -r scripts/lint-pins.txt" in workflow_text,
    }


# --- the real tree -----------------------------------------------------------


def test_the_linux_matrix_is_every_classifier_minor():
    """The classifiers are the one declaration of what this package supports;
    the matrix used to name two of the four by hand."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    minors = _classifier_minors(PYPROJECT.read_text(encoding="utf-8"))
    assert minors, "pyproject.toml declares no `Programming Language :: Python :: 3.X` classifier"
    assert _matrix_versions(_job_block(workflow, LINUX_JOB)) == minors, (
        f"{LINUX_JOB}'s matrix must equal the classifiers {minors}, in order")


def test_the_windows_leg_runs_the_floor_and_ceiling_pythons():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    minors = _classifier_minors(PYPROJECT.read_text(encoding="utf-8"))
    block = _job_block(workflow, WINDOWS_JOB)
    assert "runs-on: windows-latest" in block
    assert _matrix_versions(block) == [minors[0], minors[-1]]
    assert "bash scripts/ci-test.sh full" in block, (
        "the Windows leg runs the same gate command AGENTS.md names, through bash")


def test_ruff_is_pinned_exactly_once_and_the_workflow_reads_that_pin():
    sites = _ruff_pin_sites(WORKFLOW.read_text(encoding="utf-8"),
                            LINT_PINS.read_text(encoding="utf-8"))
    assert len(sites["pins"]) == 1, f"scripts/lint-pins.txt must pin ruff exactly once: {sites['pins']}"
    assert sites["installs_from_pins"], "the lint job must install from scripts/lint-pins.txt"
    assert sites["workflow_literals"] == [], (
        f"tests.yml repeats the ruff pin instead of reading it: {sites['workflow_literals']}")


def test_the_aggregate_gate_needs_every_job_runs_always_and_rejects_non_success():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    names = _job_names(workflow)
    assert AGGREGATE_JOB in names
    gate = _aggregate_gate(_job_block(workflow, AGGREGATE_JOB))
    assert sorted(gate["needs"]) == sorted(n for n in names if n != AGGREGATE_JOB), (
        f"`{AGGREGATE_JOB}` must need every other job: needs {gate['needs']}, jobs {names}")
    assert gate["always"], f"`{AGGREGATE_JOB}` must run `if: always()` or a skipped leg skips the gate"
    assert gate["rejects_non_success"], (
        f"`{AGGREGATE_JOB}` must fail explicitly on any result other than success")


def test_the_linux_matrix_stays_first_for_ci_venv():
    """`scripts/ci_venv.py` reads the first `python-version: [...]` in the
    file as CI's matrix; the Windows leg's shorter list must never come
    first, or a local venv would be built for a subset."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    names = _job_names(workflow)
    assert names.index(LINUX_JOB) < names.index(WINDOWS_JOB)


# --- the plants --------------------------------------------------------------


def _workflow(jobs: str) -> str:
    return "name: Planted\non: [push]\njobs:\n" + jobs


def test_the_classifier_reader_fires_on_planted_classifiers():
    """Planted: minors in order, the bare `:: 3` ignored, nothing else read."""
    planted = (
        'classifiers = [\n'
        '    "Programming Language :: Python :: 3",\n'
        '    "Programming Language :: Python :: 3.10",\n'
        '    "Programming Language :: Python :: 3.13",\n'
        '    "Operating System :: OS Independent",\n'
        ']\n')
    assert _classifier_minors(planted) == ["3.10", "3.13"]
    assert _classifier_minors("requires-python = \">=3.10\"\n") == []


def test_the_matrix_check_catches_a_planted_hand_kept_matrix():
    """Planted: the defect this file replaced — a matrix naming two of four
    classifiers — must read as unequal, and the right list as equal."""
    stale = _workflow(
        "  test-matrix:\n    strategy:\n      matrix:\n"
        '        python-version: ["3.10", "3.12"]\n')
    assert _matrix_versions(_job_block(stale, "test-matrix")) == ["3.10", "3.12"]
    assert _matrix_versions(_job_block(stale, "test-matrix")) != ["3.10", "3.11", "3.12", "3.13"]
    none = _workflow("  lint:\n    runs-on: ubuntu-latest\n")
    assert _matrix_versions(_job_block(none, "lint")) == []


def test_the_ruff_pin_check_catches_a_planted_second_pin():
    """Planted: the workflow repeating `ruff==` is the two-copies drift
    #292 closed for pre-commit; a pins file with no pin, or two, fails too."""
    twice = _ruff_pin_sites(
        "run: pip install ruff==0.15.0\n", "ruff==0.16.6\n")
    assert twice["workflow_literals"] == ["ruff==0.15.0"]
    assert not twice["installs_from_pins"]
    assert _ruff_pin_sites("", "bandit==1.9.4\n")["pins"] == []
    assert _ruff_pin_sites("", "ruff==0.16.6\nruff==0.16.7\n")["pins"] == ["0.16.6", "0.16.7"]
    clean = _ruff_pin_sites("run: pip install -r scripts/lint-pins.txt\n", "ruff==0.16.6\n")
    assert clean == {"pins": ["0.16.6"], "workflow_literals": [], "installs_from_pins": True}


def test_the_aggregate_check_catches_a_planted_gate_missing_each_half():
    """Planted three ways: the gate this repo shipped before this file (needs
    without `always()` and with no explicit check), a gate that runs always
    but never names success, and a gate that misses a job. Then the whole
    shape, which must pass."""
    legs = "  lint:\n    runs-on: x\n  test-matrix:\n    runs-on: x\n"
    old = _workflow(legs + "  test:\n    needs: [test-matrix, lint]\n    runs-on: x\n"
                    "    steps:\n      - run: echo green\n")
    gate = _aggregate_gate(_job_block(old, "test"))
    assert gate == {"needs": ["test-matrix", "lint"], "always": False, "rejects_non_success": False}

    quiet = _workflow(legs + "  test:\n    needs: [lint, test-matrix]\n    if: always()\n"
                      "    steps:\n      - run: echo green\n")
    assert _aggregate_gate(_job_block(quiet, "test"))["rejects_non_success"] is False

    short = _workflow(legs + "  test:\n    needs: [lint]\n    if: always()\n    steps:\n"
                      "      - run: python3 -c \"import sys; sys.exit(1 if r != 'success' else 0)\"\n")
    gate = _aggregate_gate(_job_block(short, "test"))
    assert gate["needs"] == ["lint"] and "test-matrix" not in gate["needs"]
    assert gate["always"] and gate["rejects_non_success"]
    assert _job_names(short) == ["lint", "test-matrix", "test"]
