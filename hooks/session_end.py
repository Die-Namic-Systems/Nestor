"""SessionEnd — cleanup and an advisory drift warning at session close.

SessionEnd is **cleanup-only**: it cannot block termination and cannot inject
context (Claude Code hooks docs — exit 2 shows stderr to the user only, and there
is no next turn to receive anything). So this warns and flushes; it never gates.
Anything that must stop the agent stays on the Stop turn-gate
(``hooks/before_stop.py``), where a block is actually honored.

It is also **best-effort**: SessionEnd does not fire on Ctrl+C (that suspends,
and resuming fires SessionStart, not SessionEnd) and is unreliable on ``/clear``
(anthropics/claude-code#6428). CI's ``test_dogfood_store`` is the real drift gate;
this is the earlier, local reminder that turns a post-push CI failure into an
end-of-session notice.

Two jobs, both already precedented inside ``scripts/dogfood_store.py``:

* **drift warning** — ``dogfood_store.py --verify`` and, on non-zero, tell the
  user to rebuild before pushing. Side-effect-free (``--verify`` builds in a temp
  dir). It also fails on a sealed row, so it doubles as a covenant check — the
  machine may propose, not confirm.
* **WAL checkpoint** — flush the default dev store's ``-wal`` sidecar so a session
  does not leave it mid-write. It never opens the committed dogfood store: that
  one is checkpointed by the rebuild script, and opening it here would merge its
  WAL and dirty a committed file.

Shape from disler's ``session_end.py`` (license unverifiable — reimplemented
clean) and retro-skill's off-by-default reminder (MIT). Always returns cleanly;
the runner prints any warning to stderr and exits 0.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

#: The dev store (gitignored). The committed store (docs/dogfood/nestor.db) is
#: deliberately never opened here — the rebuild script owns its checkpoint.
DEFAULT_DB = ("data", "nestor.db")
VERIFY_SCRIPT = ("scripts", "dogfood_store.py")

_DRIFT = ("[nestor session-end] the committed decision store no longer matches "
          "docs/dogfood/decisions/ — run `python scripts/dogfood_store.py "
          "--rebuild` and commit before pushing. (`--verify` also fails on a "
          "sealed row: the machine may propose, not confirm.) This is a "
          "best-effort reminder; CI's test_dogfood_store is the gate.")


def verify_drift(root: pathlib.Path) -> str | None:
    """Return a warning if the committed store drifted from the decision files,
    else None. Runs the repo's own ``--verify``, which is side-effect-free."""
    script = root.joinpath(*VERIFY_SCRIPT)
    if not script.is_file():
        return None
    try:
        proc = subprocess.run(
            [sys.executable, str(script), "--verify"],
            capture_output=True, text=True, cwd=str(root), timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return None if proc.returncode == 0 else _DRIFT


def checkpoint(root: pathlib.Path) -> bool:
    """Flush the default dev store's WAL if it exists. Never touches the
    committed dogfood store. Returns whether a checkpoint ran; never raises."""
    db = root.joinpath(*DEFAULT_DB)
    if not db.is_file():
        return False
    try:
        from nestor.sqlite_store import SqliteStore
        SqliteStore(str(db)).close()   # SqliteStore.close checkpoints the WAL
        return True
    except Exception:  # noqa: BLE001 — cleanup is best-effort, never fatal
        return False


def run(root: pathlib.Path, payload: dict | None = None) -> dict:
    """Do the end-of-session cleanup. Never raises; the caller emits warnings."""
    payload = payload or {}
    warnings = []
    drift = verify_drift(root)
    if drift:
        warnings.append(drift)
    return {"reason": str(payload.get("reason") or ""),
            "checkpointed": checkpoint(root),
            "warnings": warnings}
