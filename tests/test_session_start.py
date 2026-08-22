"""The SessionStart seat context — what a fresh agent is handed at boot.

Five sections (seat, pytest, lint, nestor, brain), each guarded so a broken one
degrades to a status line rather than replacing the whole boot with a traceback.
The tests assert the shape an agent depends on and the fail-open posture that
keeps a bad section from taking the session down.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sqlite3
import subprocess

import pytest

from hooks import session_start
from hooks.session_start import build_context

REPO = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _unpinned_corpus(monkeypatch):
    """These tests assert the UNPINNED convention — ``<tree>/data/nestor.db``.

    Made explicit rather than inherited from the shell. The willow fleet exports
    ``$NESTOR_DB``, so on an operator box these were silently probing the
    fleet's corpus instead of their own tmp tree: they passed for a reason
    unrelated to what they assert, and would fail wherever the pin differed. A
    test whose result depends on ambient environment is the same defect the pin
    itself exists to fix.

    The pinned path has its own test below.
    """
    monkeypatch.delenv("NESTOR_DB", raising=False)
    monkeypatch.delenv("NESTOR_HOME", raising=False)


def test_a_pinned_corpus_is_reported_as_is(tmp_path, monkeypatch):
    """A pin is what the next command opens, so the boot check must report IT.

    Joining an absolute pin onto the tree root would report "no nestor stood up"
    beside a live pinned store — ``_cli_default_db``'s own divergence, arriving
    from the other side.
    """
    db = tmp_path / "pinned.db"
    db.touch()
    monkeypatch.setenv("NESTOR_DB", str(db))
    assert session_start._cli_default_db(tmp_path / "some" / "tree") == db


def test_seat_and_checks_are_always_present():
    ctx = build_context(REPO)
    assert "[NESTOR REPO — LOCAL-FIRST SEAT]" in ctx
    assert "[check] pytest:" in ctx
    assert "[check] lint:" in ctx
    assert "[nestor]" in ctx


def test_the_boot_check_covers_every_gate_ci_lint_runs():
    """The drift guard, and the reason the detect-secrets break survived.

    ``scripts/ci-lint.sh`` is the command the seat, AGENTS.md and the agent guide
    all name as the pre-push gate. A boot check that probes a *subset* of what it
    runs reports a readiness the agent's command does not share — so the set is
    read back out of the script rather than trusted to stay in sync by hand. Add
    a fourth gate to ci-lint.sh and this fails until the boot check knows it."""
    # ci-lint.sh runs three gates inline (`python -m ruff/bandit/mypy`) and
    # delegates the secret scan to scripts/secret-scan.sh, so its exclusion list
    # is defined once and cannot drift from the workflow (agent-log §6.111).
    # Follow that delegation: a gate the boot check must know about may live in
    # ci-lint.sh or in any scripts/*.sh it calls.
    scripts_dir = REPO / "scripts"
    texts = [(scripts_dir / "ci-lint.sh").read_text(encoding="utf-8")]
    for name in re.findall(r"[\w-]+\.sh", texts[0]):
        sub = scripts_dir / name
        if sub.exists():
            texts.append(sub.read_text(encoding="utf-8"))
    run = {m.split(".")[0] for t in texts
           for m in re.findall(r"python -m ([\w.]+)", t)}
    assert run == set(session_start.LINT_MODULES), (
        f"ci-lint.sh runs {sorted(run)}; the boot check probes "
        f"{sorted(session_start.LINT_MODULES)}")


def test_the_lint_line_names_every_gate_when_the_venv_is_ready():
    line = session_start._lint_line(REPO)
    assert line.startswith("[check] lint:")
    for mod in session_start.LINT_MODULES:
        assert mod in line


def test_the_lint_line_goes_red_on_a_missing_gate(monkeypatch):
    """Shown to fail before it is trusted — decision 0101's own rule, applied to
    the check that would have caught 0101's omission.

    A readiness line that cannot report *un*ready is a ledger, not a gate: it was
    the silently-absent third gate that let ``bash scripts/ci-lint.sh`` boot green
    and die at push. The line must name the missing module and the one command
    that fixes it.

    The present-module half of the pair is stdlib on purpose. The first version
    used ``ruff``, which is installed in the repo venv and *not* in CI's test job
    (``tests.yml`` installs ``.[keys] pytest coverage``, deliberately — the lint
    tools live in the lint job). So the probe correctly reported
    ``MISSING ruff, nestor_no_such_lint_module`` and the assertion, which had my
    venv's contents baked into it as a fact, failed on both matrix legs. A test
    for a readiness check must not itself depend on what happens to be ready."""
    monkeypatch.setattr(
        session_start, "LINT_MODULES", ("json", "nestor_no_such_lint_module"))
    line = session_start._lint_line(REPO)
    assert "MISSING nestor_no_such_lint_module" in line
    assert "json" not in line.split("—")[0]  # the importable one is not accused
    assert "pip install -e '.[dev]'" in line


def test_a_broken_lint_probe_degrades_to_a_line(monkeypatch):
    """Same fail-open contract as every other section: the boot survives it."""
    def boom(_root):
        raise RuntimeError("simulated probe failure")
    monkeypatch.setattr(session_start, "_lint_line", boom)
    ctx = build_context(REPO)
    assert "[check] lint: unavailable (RuntimeError" in ctx
    assert "[brain] decision store up:" in ctx  # neighbors survive


@pytest.fixture
def bare_tree(tmp_path, monkeypatch):
    """A repo-shaped tree with a seat and no Nestor, and no household env."""
    (tmp_path / "hooks").mkdir()
    (tmp_path / "hooks" / "seat.md").write_text("[seat]", encoding="utf-8")
    monkeypatch.delenv("NESTOR_HOME", raising=False)
    monkeypatch.delenv("HOMESTEAD_HOME", raising=False)
    return tmp_path


def test_the_boot_asks_when_no_nestor_is_stood_up(bare_tree):
    """The check that was missing. `_brain_section` asks this of the decision
    store, which is committed and so always there — the ask could never fire —
    and nothing asked it about a Nestor at all."""
    line = session_start._nestor_section(bare_tree)
    assert line.startswith("[nestor]")
    assert "no Nestor is stood up in this tree" in line
    assert "Ask the user whether to stand one up" in line
    assert "nestor demo" in line


def test_a_stood_up_nestor_is_reported_and_nothing_is_asked(bare_tree):
    """The skip branch: present means one line saying where, and no prompt —
    there is no choice to put to the user when the thing already exists."""
    subprocess.run(["nestor", "--db", str(bare_tree / "data" / "nestor.db"), "demo"],
                   capture_output=True, check=True, timeout=120)
    line = session_start._nestor_section(bare_tree)
    assert "stood up: data/nestor.db" in line
    assert "pair(s)" in line
    assert "Ask the user" not in line


def test_the_nestor_check_stands_nothing_up(bare_tree):
    """The invariant, and the reason this check has to run at boot.

    `nestor stats` on a tree with no store does not say "no Nestor" — it creates
    `data/nestor.db` and prints `0 pair(s)`, so an absent Nestor and an empty one
    are indistinguishable the moment anything runs. A probe that answered the
    question by touching the path would destroy the answer and then report it.
    The forbidden act, asserted to be refused: nothing on disk moves."""
    before = {p for p in bare_tree.rglob("*")}
    session_start._nestor_section(bare_tree)
    assert {p for p in bare_tree.rglob("*")} == before
    assert not (bare_tree / "data").exists(), "the probe stood a Nestor up"


def test_the_stand_up_command_the_ask_names_actually_satisfies_the_check(bare_tree):
    """The guard that was missing, and the class of bug it catches.

    The ask told the agent to run `nestor demo`. `nestor demo` compares *resolved*
    paths and diverts to data/nestor-demo.db so a demo cannot clobber a real
    store (nestor/cli.py) — so it can never create data/nestor.db, which was the
    only path the check looked at. Follow the instruction and the very next boot
    still says "no Nestor is stood up": a fix command that cannot satisfy the
    condition it is offered for.

    Asserting the *text* of the ask would not have caught it, and neither would
    checking that the path matches the CLI — both were already true. Only running
    the named command and re-asking the question closes it, so that is what this
    does. It also means the pin survives the CLI moving the demo store."""
    assert "Ask the user" in session_start._nestor_section(bare_tree)
    subprocess.run(["nestor", "demo"], cwd=bare_tree,
                   capture_output=True, check=True, timeout=120)
    after = session_start._nestor_section(bare_tree)
    assert "Ask the user" not in after, (
        "`nestor demo` is named as the fix but leaves the check still asking:\n" + after)
    assert "stood up:" in after


def test_the_ask_names_where_the_demo_store_actually_lands(bare_tree):
    """A correct check with a misleading fix line is still a trap: an agent told
    to open the default store after `nestor demo` finds nothing there."""
    ask = session_start._nestor_section(bare_tree)
    assert "/".join(session_start.DEMO_DB) in ask
    assert "refuses to write the default store" in ask


def test_a_non_wal_store_is_not_rewritten_by_the_probe(bare_tree):
    """The regression, and the case the first version of this suite never covered.

    `_store_summary` used to open the store through `SqliteStore`, whose
    `_connect` runs `PRAGMA journal_mode=WAL` on every open — a write to the
    file header. Every fixture here builds its store with `nestor demo` or
    `memory_init()`, both of which set WAL at creation, so re-opening was a true
    no-op and the read-only claim passed while being false. A store in SQLite's
    default `delete` mode — restored from a backup, copied off another machine,
    or set that way for a filesystem where WAL is unsafe — was silently
    converted by the boot check, bytes and all."""
    db = bare_tree / "data" / "nestor.db"
    subprocess.run(["nestor", "--db", str(db), "demo"],
                   capture_output=True, check=True, timeout=120)
    con = sqlite3.connect(db)
    con.execute("PRAGMA journal_mode=delete")
    con.close()
    for sidecar in db.parent.glob("nestor.db-*"):
        sidecar.unlink()

    before = hashlib.sha256(db.read_bytes()).hexdigest()
    line = session_start._nestor_section(bare_tree)
    assert "pair(s)" in line, line
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before, (
        "the boot probe rewrote the store it was only supposed to read")
    con = sqlite3.connect(db)
    assert con.execute("PRAGMA journal_mode").fetchone()[0] == "delete", (
        "the boot probe changed the store's journal mode")
    con.close()


def test_the_read_only_summary_agrees_with_memory_stats(bare_tree):
    """Pins the duplicated count query to the authority it had to stop calling.

    Reading without writing costs a restatement of what `memory.stats` computes
    (there is no read-only door into `SqliteStore`). Left unpinned that is a
    drift waiting to happen, so the two are compared on a real store: change the
    schema or the status vocabulary and this fails rather than the boot quietly
    reporting a number nothing else agrees with."""
    from nestor import memory
    from nestor.sqlite_store import SqliteStore
    db = bare_tree / "data" / "nestor.db"
    subprocess.run(["nestor", "--db", str(db), "demo"],
                   capture_output=True, check=True, timeout=120)
    store = SqliteStore(str(db))
    try:
        stats = memory.stats(store=store)
    finally:
        store.close()
    assert session_start._store_summary(db) == (
        f" — {stats['total']} pair(s), {stats['sealed']} sealed")


def test_a_household_seat_is_asked_about_on_its_own_terms(bare_tree, monkeypatch):
    """$NESTOR_HOME set is a different seat with a different fix: the ask must
    name home_init and the household tree, not `nestor demo`."""
    hh = bare_tree / "household"
    monkeypatch.setenv("NESTOR_HOME", str(hh))
    line = session_start._nestor_section(bare_tree)
    assert "no Nestor is stood up there" in line
    assert "python -m nestor.home_init" in line
    assert "nestor demo" not in line
    assert not hh.exists(), "the probe scaffolded a household home"

    from nestor import home_init
    home_init.ensure_home_layout(hh)
    after = session_start._nestor_section(bare_tree)
    assert "household home stood up" in after
    assert "Ask the user" not in after


def test_the_legacy_root_alone_is_carried_as_its_own_ask(bare_tree, monkeypatch):
    """$HOMESTEAD_HOME without $NESTOR_HOME must not fall through to ./data/.

    `home_paths.home()` refuses to pick between the two roots, and the boot has
    to surface that refusal. Falling through would print a green line about the
    repo tree while the host's real keep state sits unnamed under the old root —
    a boot that looks answered for the one machine the question is about.
    """
    monkeypatch.setenv("HOMESTEAD_HOME", str(bare_tree / "old"))

    line = session_start._nestor_section(bare_tree)

    assert "HOMESTEAD_HOME is set but NESTOR_HOME is not" in line
    assert "Ask the user" in line
    assert "docs/home-paths.md" in line
    # Not the repo-tree ask, and not the household-scaffold ask.
    assert "nestor demo" not in line
    assert "python -m nestor.home_init" not in line


def test_the_probe_opens_the_path_the_cli_opens(bare_tree):
    """Drift guard. A boot check that probed a different store from the one the
    agent's next `nestor` command opens would report on a store nobody uses —
    the divergence `_venv_python` already exists to prevent for the interpreter."""
    from nestor.cli import build_parser
    assert session_start._cli_default_db(bare_tree) == bare_tree / build_parser().get_default("db")


def test_an_unreadable_store_is_a_note_not_a_crash(bare_tree):
    """`_store_summary` is a nicety; a corrupt file must not take the boot down."""
    db = bare_tree / "data" / "nestor.db"
    db.parent.mkdir()
    db.write_text("not a sqlite file", encoding="utf-8")
    line = session_start._nestor_section(bare_tree)
    assert "stood up: data/nestor.db" in line and "unreadable" in line


def test_the_brain_is_stood_up_with_the_query_command():
    """The point of the change: a fresh agent boots knowing the brain is live and
    how to ask it. The count and the consult command are the load-bearing lines."""
    ctx = build_context(REPO)
    assert "[brain] decision store up:" in ctx
    assert "decision check" in ctx
    # The exact-wording caveat must ride along — the blind spot is stated, not hidden.
    assert "re-worded proposal below the bar" in ctx


def test_a_missing_store_asks_the_user_not_crashes(tmp_path):
    """No committed store (a cold checkout that never rebuilt): the if/then asks
    the user whether to stand one up rather than acting — and does not raise,
    because the brain is optional context, not a boot precondition."""
    seat = tmp_path / "hooks"
    seat.mkdir()
    (seat / "seat.md").write_text("[seat]", encoding="utf-8")
    ctx = build_context(tmp_path)
    assert "no decision store is stood up" in ctx
    assert "Ask the user whether to stand one up" in ctx
    assert "dogfood_store.py --rebuild" in ctx


def test_an_empty_store_asks_the_user(tmp_path):
    """Installed but a store with no rows is 'not stood up' too — same ask, not a
    false 'up' on an empty brain."""
    from nestor.sqlite_store import SqliteStore
    (tmp_path / "hooks").mkdir()
    (tmp_path / "hooks" / "seat.md").write_text("[seat]", encoding="utf-8")
    db = tmp_path / "docs" / "dogfood" / "nestor.db"
    db.parent.mkdir(parents=True)
    SqliteStore(str(db)).memory_init()  # a real, empty store
    ctx = build_context(tmp_path)
    assert "its decision store is empty" in ctx
    assert "Ask the user whether to stand one up" in ctx


def test_up_and_stood_up_does_not_ask(tmp_path):
    """The do-nothing branch: with the real committed store present, the section
    hands it over and asks nothing — no stand-up prompt when there is no choice.

    Scoped to `_brain_section` rather than the whole context, which is what the
    sentence above always meant. It read the joined boot text while only one
    section could ask, so the two were the same assertion; adding `[nestor]` —
    which asks legitimately, this tree having no `data/nestor.db` — separated
    them and showed the test had been checking a neighbour's business."""
    section = session_start._brain_section(REPO)
    assert "Ask the user whether to stand one up" not in section
    assert "[brain] decision store up:" in section


def test_a_broken_section_degrades_to_a_line(monkeypatch):
    """The fail-open contract: a section helper that raises becomes one status
    line, and the sections around it still land. A boot hook that could crash on
    its own bug is the failure this guard exists to refuse."""
    def boom(_root):
        raise RuntimeError("simulated section failure")
    monkeypatch.setattr(session_start, "_brain_section", boom)
    ctx = build_context(REPO)
    assert "[check] brain: unavailable (RuntimeError" in ctx
    assert "[NESTOR REPO — LOCAL-FIRST SEAT]" in ctx  # neighbors survive


def test_missing_seat_is_the_one_hard_line(tmp_path):
    ctx = build_context(tmp_path)
    assert ctx == "[NESTOR] Missing hooks/seat.md"


def test_pytest_line_reports_no_venv_without_crashing(tmp_path):
    """A repo tree with no .venv reads as a next step, not an exception."""
    (tmp_path / "hooks").mkdir()
    (tmp_path / "hooks" / "seat.md").write_text("[seat]", encoding="utf-8")
    line = session_start._pytest_line(tmp_path)
    assert "[check] pytest:" in line and "no .venv" in line


def test_session_start_emits_valid_claude_json_end_to_end():
    """Through the real wrapper: SessionStart must emit the envelope Claude Code
    reads (``hookSpecificOutput.additionalContext``), with the brain inside it."""
    done = subprocess.run(
        [str(REPO / "hooks" / "nestor-hook"), "claude", "session_start"],
        capture_output=True, text=True, cwd=REPO, timeout=60,
        env={**_env(), "NESTOR_PROJECT_ROOT": str(REPO)})
    assert done.returncode == 0, done.stderr
    out = json.loads(done.stdout)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "[brain] decision store up:" in ctx


def _env() -> dict:
    import os
    return dict(os.environ)


def test_the_lint_line_goes_red_when_a_pin_differs_from_cis(monkeypatch, tmp_path):
    """The same rule as the missing-gate test, applied to the gate ci-lint.sh
    gained ahead of its first check (agent-log §6.114).

    `scripts/ci-lint.sh` now refuses outright on a tool version CI does not
    pin, so a boot line saying "ready" for such an environment clears a gate
    the script stops at — which is exactly the shape of the silently-absent
    third gate this whole check was built after. Driven by pointing the probe
    at a pins file demanding a version nothing has, so the test does not depend
    on what happens to be installed."""
    pins = tmp_path / "impossible-pins.txt"
    pins.write_text("# a pin nothing can satisfy\njson5==0.0.0\npytest==0.0.0\n",
                    encoding="utf-8")
    monkeypatch.setattr(session_start, "LINT_PINS_FILE", str(pins))
    # LINT_MODULES is patched to stdlib for the same reason the missing-gate
    # test above patches it — and this was learned the same way that test's
    # author learned it, by watching CI fail on both matrix legs. The test job
    # installs `.[keys] pytest coverage` and NOT the five lint tools (those
    # live in the lint job), so the real module probe reports all five missing,
    # returns the MISSING line first, and never reaches the branch under test.
    # A test for a readiness check must not depend on what happens to be ready.
    monkeypatch.setattr(session_start, "LINT_MODULES", ("json",))
    line = session_start._lint_line(REPO)
    assert "MISSING" not in line, (
        "the module probe must be clean for this test to reach the pin branch")
    assert "PINS DIFFER" in line
    assert "pytest 0.0.0" not in line          # the *installed* version is named
    assert "!=0.0.0" in line
    assert "json5" not in line, "an absent distribution is the module probe's to report"
    assert "pip install -r" in line
    assert "ready" not in line


def test_the_boot_check_probes_every_pin_ci_installs(monkeypatch):
    """The §6.111 drift guard, one file further out: the workflow installs from
    scripts/lint-pins.txt and ci-lint.sh refuses against it, so the boot check
    must read that same file rather than a copy of its contents."""
    pins = (REPO / session_start.LINT_PINS_FILE).read_text(encoding="utf-8")
    pinned = {ln.split("==")[0].strip() for ln in pins.splitlines()
              if "==" in ln and not ln.strip().startswith("#")}
    workflow = (REPO / ".github/workflows/tests.yml").read_text(encoding="utf-8")
    assert f"pip install -r {session_start.LINT_PINS_FILE}" in workflow, (
        "the workflow must install from the pins file the boot check reads")
    # And the five distributions map onto the five modules ci-lint.sh runs.
    assert len(pinned) == len(session_start.LINT_MODULES)
