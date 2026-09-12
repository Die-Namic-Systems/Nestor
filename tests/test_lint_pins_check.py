"""Gate for `scripts/lint-pins-check.sh`'s ruff/pre-commit cross-check.

`scripts/lint-pins.txt` pins the ruff `ci-lint.sh` and CI's lint job run; the
same tool is pinned a second, independent way in `.pre-commit-config.yaml` (a
hook `rev:`, not a pip requirement). Nothing kept the two in sync — pre-commit
sat at v0.15.0 while `lint-pins.txt` had moved to 0.16.6 — so
`lint-pins-check.sh` now reads both and refuses on disagreement.

The subprocess tests use a *synthetic*, one-line `lint-pins.txt` (just the
installed ruff's own version) and skip if ruff is not installed: CI's
test-matrix job, which collects this file, installs `.[keys]` + pytest only,
never `[dev]` — that job does not run `lint-pins-check.sh` normally (only
`ci-lint.sh` and a developer's `pre-commit` do), and this file's job is the
ruff/pre-commit comparison, not re-proving the other tools' presence.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _dist_version

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "lint-pins-check.sh"
PINS = REPO / "scripts" / "lint-pins.txt"
PRECOMMIT = REPO / ".pre-commit-config.yaml"

try:
    _INSTALLED_RUFF = _dist_version("ruff")
except PackageNotFoundError:
    _INSTALLED_RUFF = None

needs_ruff = pytest.mark.skipif(
    _INSTALLED_RUFF is None,
    reason="ruff not installed here (CI's test-matrix job never installs [dev])")


def _sandbox(tmp_path: pathlib.Path, precommit_rev: str) -> pathlib.Path:
    """A tmp dir with the real script, a one-line synthetic pins file (just
    the installed ruff), and a `.pre-commit-config.yaml` at `precommit_rev`."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "lint-pins-check.sh").write_text(
        SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "scripts" / "lint-pins.txt").write_text(
        f"ruff=={_INSTALLED_RUFF}\n", encoding="utf-8")
    (tmp_path / ".pre-commit-config.yaml").write_text(
        "repos:\n"
        "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
        f"    rev: {precommit_rev}\n"
        "    hooks:\n"
        "      - id: ruff\n",
        encoding="utf-8",
    )
    return tmp_path


def _run(sandbox: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(sandbox / "scripts" / "lint-pins-check.sh")],
        cwd=sandbox, capture_output=True, text=True, check=False)


@needs_ruff
def test_a_stale_precommit_rev_is_refused(tmp_path):
    """Planted: the exact defect this repo shipped — pre-commit behind
    lint-pins.txt — must fail, and name both numbers."""
    stale = "v0.15.0"
    assert stale != f"v{_INSTALLED_RUFF}", "fixture rev must actually disagree"

    proc = _run(_sandbox(tmp_path, precommit_rev=stale))
    assert proc.returncode != 0
    assert "pre-commit" in proc.stderr and stale in proc.stderr
    assert _INSTALLED_RUFF in proc.stderr


@needs_ruff
def test_a_matching_precommit_rev_passes(tmp_path):
    """Not just "always fails" — corrected to lint-pins.txt's own value, the
    same sandbox must pass."""
    proc = _run(_sandbox(tmp_path, precommit_rev=f"v{_INSTALLED_RUFF}"))
    assert proc.returncode == 0, proc.stderr


def test_the_committed_precommit_config_agrees_with_lint_pins():
    """The real files, parsed the same way the script parses them — no
    subprocess, so this runs even where ruff itself is not installed, and
    still catches the real tree drifting again."""
    ruff_pin = next(line.split("==", 1)[1] for line in
                    PINS.read_text(encoding="utf-8").splitlines()
                    if line.split("#", 1)[0].strip().startswith("ruff=="))
    m = re.search(
        r"repo:\s*https://github\.com/astral-sh/ruff-pre-commit\s*\n\s*rev:\s*v?([\w.]+)",
        PRECOMMIT.read_text(encoding="utf-8"))
    assert m, ".pre-commit-config.yaml's ruff-pre-commit rev moved or was removed"
    assert m.group(1) == ruff_pin, (
        f".pre-commit-config.yaml pins ruff v{m.group(1)}, "
        f"scripts/lint-pins.txt pins {ruff_pin} — lint-pins-check.sh will refuse")
