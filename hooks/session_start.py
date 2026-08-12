"""Session-start seat context for Nestor (CLI-agnostic).

What a fresh agent is handed before it touches anything. It is four sections,
each produced by a guarded helper so a failure in one is a status line, never a
traceback that takes the whole boot down:

* **seat** — ``hooks/seat.md``, the rules of this repo.
* **checks** — is the environment ready (``.venv`` + pytest), hardened so a
  missing venv reads as a clear next step rather than an exception.
* **brain** — the decision store is *stood up* every session: the committed
  ``docs/dogfood/nestor.db`` is opened, self-tested with one live retrieval, and
  handed to the agent with the exact command to consult it. A cold agent that
  boots blind to what has already been decided re-proposes closed doors — the
  rediscovery tax this store exists to stop paying.

Nothing here writes, seals, or mutates the repo. Standing up the brain opens the
committed store read-only and closes it; a missing store is *reported*, never
silently rebuilt (a boot hook that mutates the tree is the failure it would be
diagnosing).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

#: The brain the session is handed. Derived, all-draft, rebuilt from the
#: decision files by ``scripts/dogfood_store.py`` — see ``docs/decision-memory.md``.
BRAIN_DB = ("docs", "dogfood", "nestor.db")


def repo_root() -> Path:
    env = os.environ.get("NESTOR_PROJECT_ROOT") or os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parent.parent


def seat_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / "hooks" / "seat.md"


def _venv_python(root: Path) -> Path:
    """The repo ``.venv`` interpreter, or the one running this hook.

    Extracted so the pytest check and any future in-venv probe agree on which
    Python is 'the repo's' — a check that guessed differently from the shell in
    ``hooks/nestor-hook`` would report a readiness the agent's commands do not
    share.
    """
    py = root / ".venv" / "bin" / "python"
    return py if py.is_file() else Path(sys.executable)


def _guard(label: str, fn) -> str:
    """Run a section helper, and turn any failure into one status line.

    The seat context is the first thing an agent reads; a helper that raises
    would replace the whole of it with a traceback the CLI shows as a broken
    boot. Every section is optional context, so a broken one degrades to a line
    that says so and names where to look — the fail-open posture the write gate
    (``hooks/before_write``) already keeps.
    """
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 — a boot section must never raise
        return f"[check] {label}: unavailable ({type(exc).__name__}: {exc})"


def _pytest_line(root: Path) -> str:
    """Is the repo's test runner ready — hardened to name the fix, not just fail.

    Was a bare 'not ready' on any non-zero exit. Now it separates *no venv* (the
    common cold-start state, with the one command that fixes it) from *venv but
    pytest broken* (a real problem worth the stderr), so the line an agent reads
    tells it what to do next instead of only that something is wrong.
    """
    py = _venv_python(root)
    if py == Path(sys.executable) and not (root / ".venv" / "bin" / "python").is_file():
        return ("[check] pytest: no .venv — create it per docs/agent-guide.md "
                "(Environment), then `python -m pytest -q`")
    try:
        proc = subprocess.run(
            [str(py), "-m", "pytest", "--version"],
            capture_output=True, text=True, cwd=str(root), timeout=15)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"[check] pytest: not ready — {type(exc).__name__} launching {py.name}"
    if proc.returncode == 0 and (proc.stdout or proc.stderr).strip():
        line = (proc.stdout or proc.stderr).strip().splitlines()[0]
        return f"[check] pytest: {line}"
    detail = (proc.stderr or proc.stdout).strip().splitlines()
    hint = detail[-1] if detail else f"exit {proc.returncode}"
    return f"[check] pytest: installed venv but runner errored — {hint}"


def _brain_section(root: Path) -> str:
    """Stand up the decision store for this session and hand it to the agent.

    Opens the committed store read-only, proves it answers with one live
    verbatim retrieval, reports the matcher and the calibration bar it keys on,
    and surfaces the standing blind spot honestly: a re-worded proposal below the
    bar reads as 'no decision', so the bar is a per-corpus `nestor calibrate`
    question, not a fact. The point is that the agent boots knowing the brain is
    live and how to ask it — ``nestor decision check`` — before it proposes.
    """
    db = root.joinpath(*BRAIN_DB)
    if not db.is_file():
        return ("[brain] decision store not built — no closed doors surfaced this "
                "session. Build it: `python scripts/dogfood_store.py --rebuild` "
                "(docs/decision-memory.md).")

    # In-process, not a subprocess: `nestor` is importable because nestor-hook
    # runs `python -m hooks.hook_runner` from the repo root. Guarded by _guard,
    # so an import failure degrades to a status line rather than a broken boot.
    from nestor import memory, portable
    from nestor.decision import DecisionMemory
    from nestor.sqlite_store import SqliteStore

    store = SqliteStore(str(db))
    try:
        store.memory_init()
        stats = memory.stats(store=store)
        # One live round-trip on a question we know is in the store, so 'the
        # brain answers' is measured at boot, not asserted. The question comes
        # from the store itself — nothing hardcoded to drift out from under it.
        pairs = portable.export_bundle(store).get("pairs", [])
        probe = pairs[0]["source_text"] if pairs else ""
        served = bool(DecisionMemory(store).constraints_on(probe)["live"]) if probe else False
    finally:
        store.close()

    doors = stats["sealed"] or stats["total"]
    kind = "sealed" if stats["sealed"] else "recorded (all draft — proposed, none human-sealed)"
    check = "OK" if served else "empty — nothing to retrieve"
    return (
        f"[brain] decision store up: {db.relative_to(root)} — {doors} {kind}.\n"
        f"[brain] self-test: verbatim retrieval {check}; "
        f"matcher StringMatcher, seal bar {memory.SEAL_THRESHOLD:g} "
        f"(context {memory.CONTEXT_THRESHOLD:g}).\n"
        f"[brain] a re-worded proposal below the bar reads as 'no decision' — "
        f"the bar is a per-corpus `nestor calibrate` question, not a fact.\n"
        f"[brain] consult before you propose: "
        f"`nestor --db {db.relative_to(root)} decision check \"<your question>\"` "
        f"(exits non-zero on a recorded rejection or contradiction, "
        f"docs/decision-memory.md N9)."
    )


def build_context(root: Path | None = None) -> str:
    """The seat context: seat rules, readiness checks, and the live brain.

    Assembled from guarded sections joined by blank lines. A missing
    ``hooks/seat.md`` is the one hard error worth a bare line — the rest are
    context the agent can boot without.
    """
    root = root or repo_root()
    path = seat_path(root)
    if not path.is_file():
        return "[NESTOR] Missing hooks/seat.md"
    sections = [
        path.read_text(encoding="utf-8").rstrip(),
        _guard("pytest", lambda: _pytest_line(root)),
        _guard("brain", lambda: _brain_section(root)),
    ]
    return "\n\n".join(sections)


def maybe_bootstrap_claude_venv(root: Path) -> None:
    """Claude Code on the web: reuse the existing venv bootstrap script.

    Best-effort and non-fatal — the readiness check reports whether it worked, so
    a bootstrap that fails here becomes a visible pytest line rather than a
    silent one. ``check=False`` and the broad guard keep a broken script from
    aborting the whole SessionStart hook.
    """
    if os.environ.get("CLAUDE_CODE_REMOTE") != "true":
        return
    script = root / ".claude" / "hooks" / "session-start.sh"
    if not script.is_file():
        return
    try:
        subprocess.run([str(script)], cwd=str(root), check=False, timeout=180)
    except (OSError, subprocess.TimeoutExpired):
        pass
