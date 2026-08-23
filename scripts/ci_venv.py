#!/usr/bin/env python3
"""Run the test suite the way CI runs it — same Python, same deps, same command.

    python scripts/ci_venv.py --list           # what CI does, read out of the workflow
    python scripts/ci_venv.py --build          # make a venv per matrix version
    python scripts/ci_venv.py --run            # run CI's test command in each
    python scripts/ci_venv.py --run --python 3.10

`scripts/lint-pins.txt` fixed this for the **lint** job: the versions live in one
file that both the workflow and `scripts/ci-lint.sh` read, so a local gate cannot
answer under tools CI does not use (agent-log §6.114). The **test** job had the
same gap in two places, both measured on 2026-08-23 while verifying a branch —
plus a third that turned out already fixed, and is read anyway:

* **Python version.** The matrix is 3.10 and 3.12. A developer venv is whatever
  `python3` happens to be — 3.14 on the machine this was written on. Two of
  those three interpreters are not the ones the gate will run under.
* **Installed set.** CI installs ``-e '.[keys]' pytest coverage`` and nothing
  else; the lint tools live in the lint job. A local `.[dev]` venv has five
  packages CI's test job does not, and a test that reads what happens to be
  installed passes locally and fails on both matrix legs. That happened.
* **The command itself** — read, but **not** a gap. CI runs bare ``pytest``
  under coverage; `AGENTS.md` says ``python -m pytest -q``. That once mattered —
  the workflow comments that the disagreement hid five tests — and the repo
  closed it on 2026-07-31 in ``319292a`` with ``pythonpath = ["."]``: *"pin the
  path so the invocation stops mattering."* Measured on one tree, one venv, one
  command changed: identical counts. The command is still read from the workflow
  rather than assumed, because a fix that holds today is exactly the kind that
  regresses unwatched, and this is what would notice.

**Everything here is read out of `.github/workflows/tests.yml`.** Not restated,
not defaulted: if a pattern stops matching, this refuses and says which one
rather than falling back to a remembered value. A tool built to stop drift that
carries its own copy of what it is checking is the drift.

**Venvs live outside the repository** (``~/.cache/nestor-ci/pyX.Y``) so there is
nothing to gitignore and nothing to accidentally commit, and they survive
between sessions.

**It does not fetch interpreters silently.** A missing 3.10 is reported with the
command that installs it, because quietly running 3.14 and calling it 3.10 is
the exact failure this script exists to prevent.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github/workflows/tests.yml"
VENV_ROOT = pathlib.Path.home() / ".cache" / "nestor-ci"


class WorkflowUnreadable(RuntimeError):
    """The workflow no longer says what this script needs to read."""


def _workflow_text() -> str:
    if not WORKFLOW.exists():
        raise WorkflowUnreadable(f"{WORKFLOW} does not exist")
    return WORKFLOW.read_text(encoding="utf-8")


def matrix_versions(text: str) -> list[str]:
    """The `python-version: [...]` list from the test job's matrix."""
    m = re.search(r"^\s*python-version:\s*\[([^\]]+)\]", text, re.M)
    if not m:
        raise WorkflowUnreadable(
            "no `python-version: [...]` matrix found in the workflow — this "
            "script reads the versions from there and will not guess them")
    found = re.findall(r"['\"]([\d.]+)['\"]", m.group(1))
    if not found:
        raise WorkflowUnreadable(
            f"the matrix line parsed to nothing usable: {m.group(1)!r}")
    return found


def install_line(text: str) -> str:
    """The test job's `pip install ...` step, verbatim."""
    m = re.search(r"^\s*run:\s*(pip install -e .*)$", text, re.M)
    if not m:
        raise WorkflowUnreadable(
            "no `run: pip install -e ...` step found — the test job's install "
            "line is what makes a local venv comparable to CI's")
    return m.group(1).strip()


def test_command(text: str) -> str:
    """The command the test job actually runs.

    Read rather than assumed, because it is *not* ``python -m pytest``: the
    difference is real enough that the workflow keeps a comment about it.
    """
    m = re.search(r"^\s*(coverage run .*pytest.*)$", text, re.M)
    if not m:
        raise WorkflowUnreadable(
            "no `coverage run ... pytest ...` step found — this script runs "
            "the command CI runs and will not substitute its own")
    return m.group(1).strip()


def _venv(version: str) -> pathlib.Path:
    return VENV_ROOT / f"py{version}"


def _usable(target: pathlib.Path) -> bool:
    """Can this venv actually run the suite? Not "does a python exist in it"."""
    python = target / "bin" / "python"
    if not python.exists():
        return False
    probe = subprocess.run(
        [str(python), "-c", "import pytest, coverage, nestor"],
        capture_output=True, text=True, cwd=str(REPO))
    return probe.returncode == 0


def _interpreter(version: str) -> str:
    """A real CPython of exactly ``version``, or an error naming how to get one."""
    found = shutil.which(f"python{version}")
    if not found and shutil.which("uv"):
        proc = subprocess.run(["uv", "python", "find", version],
                              capture_output=True, text=True)
        if proc.returncode == 0:
            found = proc.stdout.strip().splitlines()[-1].strip() or None
    if not found:
        raise WorkflowUnreadable(
            f"no Python {version} on this machine. Install it with:\n"
            f"    uv python install {version}\n"
            f"Refusing to substitute another interpreter: running {version}'s "
            f"matrix leg under a different version is the thing this script "
            f"exists to stop.")
    # Trust nothing: ask the interpreter what it is. A `python3.10` on PATH that
    # is really 3.12 would otherwise be reported as a 3.10 run.
    got = subprocess.run([found, "-c", "import sys;print('%d.%d' % sys.version_info[:2])"],
                         capture_output=True, text=True).stdout.strip()
    if got != version:
        raise WorkflowUnreadable(
            f"{found} reports itself as {got!r}, not {version!r} — refusing it")
    return found


def build(version: str, text: str, quiet: bool = True) -> pathlib.Path:
    """Create (or refresh) the venv for one matrix version."""
    target = _venv(version)
    interpreter = _interpreter(version)
    if not (target / "bin" / "python").exists():
        subprocess.run([interpreter, "-m", "venv", str(target)], check=True)
    # shlex, not str.split: the workflow's line is `pip install -e '.[keys]'
    # pytest coverage`, and splitting on whitespace hands pip a requirement
    # still wearing its shell quotes — which it rejects as "not a valid
    # editable requirement". The quoting is the shell's, so the shell's own
    # splitter is the one that removes it.
    pip = [str(target / "bin" / "python"), "-m"] + shlex.split(install_line(text))
    if quiet:
        pip.insert(pip.index("install") + 1, "-q")
    subprocess.run(pip, cwd=str(REPO), check=True)
    # Confirm the venv can actually run the suite, rather than trusting that
    # pip exited 0. A venv holding only `pip` and `python` looked built, and the
    # run that followed silently borrowed another interpreter's pytest and
    # reported it as this version's. An install step that cannot be verified is
    # not a step, it is a hope — the same rule dep-audit.sh applies to a skipped
    # dependency.
    probe = subprocess.run(
        [str(target / "bin" / "python"), "-c",
         "import pytest, coverage, nestor; print('ok')"],
        capture_output=True, text=True, cwd=str(REPO))
    if probe.returncode != 0 or probe.stdout.strip() != "ok":
        raise WorkflowUnreadable(
            f"{target} does not import pytest/coverage/nestor after running "
            f"{' '.join(pip[2:])!r} — refusing to run a suite in it and call "
            f"the result Python {version}.\n"
            f"{(probe.stderr or '').strip()[:400]}")
    return target


def run(version: str, text: str, extra: list[str]) -> int:
    """Run CI's test command inside that venv, from the repo root."""
    target = _venv(version)
    # "Has a python binary" is not "can run the suite": the venv that caused the
    # bug below had `python` and `pip` and nothing else, passed this guard, and
    # ran somebody else's pytest. Ask whether it can actually do the job.
    if not _usable(target):
        print(f"no usable venv for {version} yet — building it first",
              file=sys.stderr)
        build(version, text)
    cmd = test_command(text)
    # `$(command -v pytest)` in the workflow resolves to the venv's pytest, so
    # this needs a shell — but **not a login shell**. `bash -lc` re-sources the
    # user's profile, which put the developer venv back at the front of PATH and
    # made `command -v pytest` resolve to a different interpreter entirely. The
    # script then printed "=== python 3.12" over a run that used 3.14. That is
    # the exact substitution this tool exists to refuse, committed by the tool,
    # and it reported green while doing it. `-c` does not source the profile.
    env_path = f"{target / 'bin'}:{os.environ.get('PATH', '')}"
    full = cmd + (" " + " ".join(extra) if extra else "")
    # Resolve, in the same shell and environment the command will run in, and
    # print it. The heading says "python 3.12"; this is the evidence for that
    # claim, and it exists because the heading was once a lie — the run below
    # borrowed another venv's pytest and nothing in the output said so. A label
    # a reader cannot check is how a wrong result reads as a right one.
    which = subprocess.run(
        ["bash", "-c", 'command -v pytest && "$(command -v python)" -V'],
        capture_output=True, text=True, cwd=str(REPO),
        env={**os.environ, "PATH": env_path})
    resolved = " / ".join(which.stdout.split())
    print(f"\n=== python {version} — {full}\n    using: {resolved}", flush=True)
    if f"py{version}" not in which.stdout:
        print(f"    REFUSING: that pytest is not in {target} — this would not "
              f"be a Python {version} run.", file=sys.stderr)
        return 2
    proc = subprocess.run(["bash", "-c", full], cwd=str(REPO),
                          env={**os.environ, "PATH": env_path})
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--list", action="store_true",
                    help="print what CI does, as parsed from the workflow")
    ap.add_argument("--build", action="store_true", help="create/refresh the venvs")
    ap.add_argument("--run", action="store_true", help="run CI's test command")
    ap.add_argument("--python", default="", metavar="X.Y",
                    help="just this matrix version (default: every one)")
    ap.add_argument("pytest_args", nargs="*",
                    help="extra arguments appended to CI's command")
    args = ap.parse_args(argv)

    try:
        text = _workflow_text()
        versions = matrix_versions(text)
        install = install_line(text)
        command = test_command(text)
    except WorkflowUnreadable as exc:
        print(f"ci_venv: {exc}", file=sys.stderr)
        return 2

    if args.python:
        if args.python not in versions:
            print(f"ci_venv: {args.python!r} is not in CI's matrix "
                  f"({', '.join(versions)}) — running it would not tell you "
                  f"anything about this push", file=sys.stderr)
            return 2
        versions = [args.python]

    if args.list or not (args.build or args.run):
        print(f"workflow   {WORKFLOW.relative_to(REPO)}")
        print(f"matrix     {', '.join(versions)}")
        print(f"install    {install}")
        print(f"command    {command}")
        print(f"venvs      {VENV_ROOT}/py<version>")
        if not (args.build or args.run):
            print("\n(nothing run — pass --build or --run)")
        return 0

    worst = 0
    for version in versions:
        try:
            if args.build:
                build(version, text)
                print(f"built {_venv(version)}")
            if args.run:
                worst = max(worst, run(version, text, args.pytest_args))
        except WorkflowUnreadable as exc:
            print(f"ci_venv: {exc}", file=sys.stderr)
            worst = max(worst, 2)
        except subprocess.CalledProcessError as exc:
            print(f"ci_venv: {version}: {exc}", file=sys.stderr)
            worst = max(worst, 1)
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
