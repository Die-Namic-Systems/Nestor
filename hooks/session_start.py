"""Session-start seat context for Nestor (CLI-agnostic).

What a fresh agent is handed before it touches anything. It is four sections,
each produced by a guarded helper so a failure in one is a status line, never a
traceback that takes the whole boot down:

* **seat** — ``hooks/seat.md``, the rules of this repo.
* **pytest** — is the test runner ready (``.venv`` + pytest), hardened so a
  missing venv reads as a clear next step rather than an exception.
* **lint** — can ``bash scripts/ci-lint.sh`` actually run — every gate, not just
  the first. The seat tells each agent to run it before pushing, so a venv
  missing one of its tools is a boot-time fact, not a push-time surprise.
* **nestor** — is a Nestor stood up at all. Present: one line saying where, and
  nothing is asked. Absent: the agent is handed the question to put to the user,
  and the hook builds nothing.
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

#: Every module ``scripts/ci-lint.sh`` runs as ``python -m <module>``, in the
#: order it runs them. Importability in the repo interpreter is exactly what
#: "ready" means for that script, so this list is what the boot check probes.
#: ``tests/test_session_start.py`` parses ci-lint.sh and fails if the two drift —
#: a boot check that reports on two of three gates is how the third one stayed
#: broken.
LINT_MODULES = ("ruff", "bandit", "detect_secrets")

#: What proves a household home was laid out rather than merely existing.
#: ``nestor.home_init`` writes it once and never overwrites it, so its presence
#: is the marker — the directory itself is not, because unrelated tooling
#: (``hooks/review_receipt``) already creates paths under the same root.
HOME_MARKER = "layout.json"


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


def _lint_line(root: Path) -> str:
    """Can the repo run ``bash scripts/ci-lint.sh`` — every gate, not just the first.

    The pytest line alone let a half-installed venv boot green. ``[dev]`` shipped
    ruff and bandit but not detect-secrets, and the secret scan is the *third*
    gate — so the documented pre-push command cleared two checks and died on
    ``No module named detect_secrets``, at push time, after the work was done.
    Nothing at boot had looked at the gate that was missing.

    One subprocess in the repo interpreter, importability only: this runs before
    the first prompt, and three ``--version`` shell-outs to buy the same fact is
    latency an agent pays on every session. ``find_spec`` is also the honest
    question — ci-lint.sh invokes these as ``python -m``, so "does it import
    here" is precisely what the script needs and no more.
    """
    py = _venv_python(root)
    probe = ("import importlib.util;"
             f"mods = {LINT_MODULES!r};"
             "print(' '.join(m for m in mods if importlib.util.find_spec(m) is None))")
    try:
        proc = subprocess.run(
            [str(py), "-c", probe],
            capture_output=True, text=True, cwd=str(root), timeout=15)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"[check] lint: not ready — {type(exc).__name__} launching {py.name}"
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        hint = detail[-1] if detail else f"exit {proc.returncode}"
        return f"[check] lint: could not probe {py.name} — {hint}"
    missing = proc.stdout.split()
    if not missing:
        return ("[check] lint: ruff, bandit, detect_secrets ready — "
                "`bash scripts/ci-lint.sh` before push")
    return ("[check] lint: MISSING " + ", ".join(missing) +
            " — `bash scripts/ci-lint.sh` will fail at that gate. Fix with: "
            ".venv/bin/pip install -e '.[dev]'")


def _ask_prompt(tag: str, condition: str, why: str, fix: str, doc: str) -> str:
    """The not-yet-stood-up branch: ask, do not act.

    A SessionStart hook cannot run a prompt itself, so it hands the agent the
    question to put to the user. Standing up a store is new scope, and this
    repo's rule is propose-before-acting — so the hook never quietly builds one or
    nags on every boot; it surfaces the choice only when there is one to make.

    Generalised from the brain's own ask so :func:`_nestor_section` can keep the
    same posture without restating it. The wording is the shared part; the tag,
    the reason it matters and the fix belong to the caller — a Nestor missing is
    not the same fact as a decision store missing, and one prompt claiming the
    other's rationale would be the boot lying about what it looked at.
    """
    return (f"[{tag}] {condition}. Ask the user whether to stand one up before "
            f"proposing — {why}. Stand up with: {fix} ({doc}).")


def _stand_up_prompt(condition: str, fix: str) -> str:
    """The brain's ask — see :func:`_ask_prompt` for the shape and the why."""
    return _ask_prompt(
        "brain", condition,
        "a session without it boots blind to what has already been decided",
        fix, "docs/decision-memory.md")


def _cli_default_db(root: Path) -> Path:
    """The store ``nestor`` opens when nobody passes ``--db``.

    Read off the CLI's own parser rather than restated here. A boot check that
    probed a different path from the one the agent's next command opens would
    report on a store nobody uses — the same divergence :func:`_venv_python`
    exists to prevent between the pytest check and the shell.
    """
    from nestor.cli import build_parser
    return root / str(build_parser().get_default("db"))


def _nestor_section(root: Path) -> str:
    """Is a Nestor stood up here? Say so if yes; ask before one is, if no.

    The check the boot never made. :func:`_brain_section` asks this question of
    the *decision store*, which is committed and therefore always present — so
    its ask branch cannot fire in this repo — and nothing asked it about a
    Nestor. Meanwhile ``nestor.home_init.ensure_home_layout``, the scaffolder
    that would answer it, has no caller anywhere in the tree: it is documented in
    the README, announced in the CHANGELOG, covered by tests, and wired to
    nothing.

    Why the question has to be asked *here*, before anything else runs: ``nestor
    stats`` on a tree with no store does not report "no Nestor". It creates
    ``data/nestor.db`` and prints ``0 pair(s)``, so a cold session cannot tell an
    absent Nestor from an empty one — and the first command an agent types
    silently makes the answer yes. Boot is the only moment the question is still
    honest.

    Never modifies the store: it resolves paths and reads what is already there,
    and neither branch creates or alters a Nestor. The one thing it can leave
    behind is a WAL store's ``-wal``/``-shm`` sidecars, which SQLite requires to
    read that journal mode at all — see :func:`_store_summary`, which states the
    limit rather than claiming a cleanliness it cannot deliver. Standing one up
    stays the user's call, the posture :func:`_ask_prompt` keeps.
    """
    try:
        from nestor import homestead_paths
    except Exception as exc:  # noqa: BLE001 — 'not installed' is a state to report
        return _ask_prompt(
            "nestor", "Nestor is not installed here (" + type(exc).__name__ + ")",
            "there is nothing to stand up until the package imports",
            "`pip install -e '.[dev,keys]'` in the repo .venv",
            "docs/agent-guide.md")

    # A household host pins its state outside the repo and is stood up when
    # home_init has written its marker; the product tree uses the CLI default.
    # Two seats, one question — see nestor/homestead_paths.py, which is explicit
    # that the household layout is not this tree's dev default.
    household = os.environ.get(homestead_paths._ROOT_ENV)
    if household:
        home = homestead_paths.home()
        if (home / HOME_MARKER).is_file():
            return (f"[nestor] household home stood up: {home} "
                    f"(keep: {homestead_paths.keep_dir()}). Nothing to ask.")
        return _ask_prompt(
            "nestor",
            f"{homestead_paths._ROOT_ENV} points at {home} but no Nestor is stood up there "
            f"(no {HOME_MARKER})",
            "a household host writes ledger and keep state into that tree, and "
            "the first write would scatter it into a home nobody laid out",
            "`python -m nestor.home_init` — idempotent, creates "
            + ", ".join(f"{d}/" for d in _SUBDIRS()) + f" and {HOME_MARKER}, clobbers nothing",
            "docs/homestead-paths.md")

    db = _cli_default_db(root)
    if not db.is_file():
        return _ask_prompt(
            "nestor", f"no Nestor is stood up in this tree — {db.relative_to(root)} does not exist",
            "the next `nestor` command will create an empty one and report "
            "`0 pair(s)`, which reads identically to a Nestor that was stood up "
            "and holds nothing",
            "`nestor demo` for a seeded store you can open in `nestor ui`, or "
            "`python -m nestor.home_init` for a household home",
            "docs/agent-guide.md")
    return f"[nestor] stood up: {db.relative_to(root)}{_store_summary(db)}. Nothing to ask."


def _SUBDIRS() -> tuple[str, ...]:
    """The household directories, from the scaffolder that creates them."""
    from nestor.home_init import SUBDIRS
    return SUBDIRS


def _store_summary(db: Path) -> str:
    """``' — N pair(s), M sealed'``, or a soft note when the file will not read.

    Opened through a raw ``mode=ro`` URI rather than :class:`SqliteStore`, which
    cannot be asked for a read. ``SqliteStore._connect`` runs ``PRAGMA
    journal_mode=WAL`` on *every* open and ``mkdir(parents=True)`` on the
    store's parent — so the first version of this function, whose docstring
    promised it did not write, silently converted any store not already in WAL
    mode: its bytes changed and it gained ``-wal``/``-shm`` sidecars. The claim
    was false one layer below where the code was looking.

    The counts are restated as SQL here rather than borrowed from
    ``memory.stats``, which is the honest cost of reading without writing.
    ``test_the_read_only_summary_agrees_with_memory_stats`` pins the two
    together so the duplication cannot drift — the same trade
    :func:`_cli_default_db` avoids by introspection and this one cannot.

    Reading a WAL store still creates ``-wal``/``-shm`` sidecars; SQLite needs
    shared memory to read that journal mode at all, and no flag avoids it that
    is safe on a store somebody may be writing to. So the promise this keeps is
    the precise one: **the store's own bytes are never modified.**
    """
    try:
        import sqlite3
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            counts = dict(conn.execute(
                "SELECT status, count(*) FROM tm_pairs GROUP BY status").fetchall())
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 — a summary is a nicety, not the answer
        return f" (present; contents unreadable: {type(exc).__name__})"
    return f" — {sum(counts.values())} pair(s), {counts.get('sealed', 0)} sealed"


def _brain_section(root: Path) -> str:
    """If Nestor is installed and stood up, hand it over. If not, ask.

    An easy if/then. Installed **and** stood up: the live store is handed to the
    agent with the command to query it — nothing is asked, because there is no
    choice to make. Not installed, or no store, or an empty one: a single 'ask
    the user whether to stand one up' prompt, and the hook builds nothing —
    standing up is the user's call, not the boot's.
    """
    # Installed? The import is the check — the hook itself relies on it. A failure
    # is a *state* (not installed), not a crash, so it becomes an ask, not a
    # traceback swallowed by _guard.
    try:
        from nestor import memory, portable
        from nestor.decision import DecisionMemory
        from nestor.sqlite_store import SqliteStore
    except Exception as exc:  # noqa: BLE001 — 'not installed' is a state to report
        return _stand_up_prompt(
            f"Nestor is not installed here ({type(exc).__name__})",
            "`pip install -e .` in the repo .venv, then "
            "`python scripts/dogfood_store.py --rebuild`")

    # Stood up? The committed store must exist and hold rows.
    db = root.joinpath(*BRAIN_DB)
    if not db.is_file():
        return _stand_up_prompt(
            "Nestor is installed but no decision store is stood up",
            "`python scripts/dogfood_store.py --rebuild`")

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

    if not stats["total"]:
        return _stand_up_prompt(
            "Nestor is installed but its decision store is empty",
            "`python scripts/dogfood_store.py --rebuild`")

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
        _guard("lint", lambda: _lint_line(root)),
        _guard("nestor", lambda: _nestor_section(root)),
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
