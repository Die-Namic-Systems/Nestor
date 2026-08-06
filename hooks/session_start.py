"""Session-start seat context for Nestor (CLI-agnostic)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    env = os.environ.get("NESTOR_PROJECT_ROOT") or os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parent.parent


def seat_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / "hooks" / "seat.md"


def build_context(root: Path | None = None) -> str:
    root = root or repo_root()
    path = seat_path(root)
    if not path.is_file():
        return "[NESTOR] Missing hooks/seat.md"
    seat = path.read_text(encoding="utf-8").rstrip()
    py = root / ".venv" / "bin" / "python"
    if not py.is_file():
        py = Path(sys.executable)
    try:
        proc = subprocess.run(
            [str(py), "-m", "pytest", "--version"],
            capture_output=True,
            text=True,
            cwd=str(root),
            timeout=10,
        )
        if proc.returncode == 0:
            line = (proc.stdout or proc.stderr).strip().splitlines()[0]
            return f"{seat}\n\n[check] pytest: {line}"
    except (OSError, subprocess.TimeoutExpired):
        pass
    return f"{seat}\n\n[check] pytest: not ready — activate .venv per CLAUDE.md (Environment)"


def maybe_bootstrap_claude_venv(root: Path) -> None:
    """Claude Code on the web: reuse the existing venv bootstrap script."""
    if os.environ.get("CLAUDE_CODE_REMOTE") != "true":
        return
    script = root / ".claude" / "hooks" / "session-start.sh"
    if script.is_file():
        subprocess.run([str(script)], cwd=str(root), check=False)
