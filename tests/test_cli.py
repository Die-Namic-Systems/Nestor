"""The terminal surface — and its exit codes, which are the point.

`nestor ledger verify` is a CI gate and `nestor ask` belongs in a shell
conditional, so 0 must mean "the good answer" and 1 must mean "the bad one"
rather than both meaning "the program ran". These tests pin that, and pin that
`nestor import` writes nothing until told to.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import json
import re
import socket

import pytest

from conftest import CONFIGURED_BY_ENV
from nestor import cli, memory, storage
from nestor.sqlite_store import SqliteStore

REPO = pathlib.Path(__file__).resolve().parent.parent


def _cli_subprocess_env() -> dict[str, str]:
    """Hermetic env for a child ``python -m nestor.cli`` (no developer exports)."""
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        x for x in (str(REPO), env.get("PYTHONPATH", "")) if x
    )
    for name in CONFIGURED_BY_ENV:
        env.pop(name, None)
    env["NESTOR_SEAL_KEY"] = "test-key"
    return env


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _run_cli_subprocess(argv: list[str], *, timeout: float = 10.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-u", "-m", "nestor.cli", *argv],
        cwd=REPO,
        env=_cli_subprocess_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@pytest.fixture()
def db(tmp_path, seal_key):
    """A file-backed instance the CLI can open by path, as a user would."""
    os.environ['NESTOR_SEAL_KEY'] = 'test-key'
    path = tmp_path / "nestor.db"
    ledger = tmp_path / "ledger.jsonl"
    store = SqliteStore(str(path))
    store.init_db()
    store.memory_init()
    from nestor import cascade
    cascade.set_ledger_path(ledger)
    storage.set_store(store)
    memory.add_pair("Good evening.", "Buenas noches.", "en", "es",
                    status="sealed", verifier="rita", store=store)
    memory.add_pair("a draft phrase", "una frase", "en", "es", store=store)
    return {"db": str(path), "ledger": str(ledger), "path": tmp_path, "store": store}


def run(db, *argv):
    return cli.main(["--db", db["db"], "--ledger", db["ledger"], *argv])


# --- asking, and what the exit code means ----------------------------------

def test_ask_exits_zero_only_when_a_human_verified_it(db, capsys):
    assert run(db, "ask", "good evening") == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "✓ sealed" in out and "Buenas noches." in out and "rita" in out

    assert run(db, "ask", "nobody has ever verified this") == cli.EXIT_ANSWER_IS_NO
    assert "! pending" in capsys.readouterr().out


def test_json_output_is_machine_readable(db, capsys):
    assert run(db, "--json", "ask", "good evening") == cli.EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["verified"] is True and payload["passage"]["state"] == "sealed"


def test_resolve_and_check_report_their_own_verdicts(db, capsys):
    from nestor.entity import EntityResolver
    from nestor.reconcile import Reconciler
    EntityResolver(db["store"], domain="company").seal("AMZN", "Amazon", verifier="analyst")
    Reconciler(db["store"], domain="contract", pct_tol=0.05).seal_baseline(
        "ceiling", "$1,000,000", verifier="auditor")

    assert run(db, "resolve", "AMZN", "--domain", "company") == cli.EXIT_OK
    assert "Amazon" in capsys.readouterr().out
    assert run(db, "resolve", "Alphabet", "--domain", "company") == cli.EXIT_ANSWER_IS_NO

    assert run(db, "check", "ceiling", "$1,030,000", "--domain", "contract") == cli.EXIT_OK
    assert "within tolerance" in capsys.readouterr().out
    assert run(db, "check", "ceiling", "$1,250,000", "--domain", "contract") == cli.EXIT_ANSWER_IS_NO
    assert "flagged" in capsys.readouterr().out
    assert run(db, "check", "never-sealed", "1", "--domain", "contract") == cli.EXIT_ANSWER_IS_NO
    assert "no sealed baseline" in capsys.readouterr().out


def test_match_is_the_bare_seam(db, capsys):
    assert run(db, "match", "GOOD EVENING!!") == cli.EXIT_OK
    assert "would be served" in capsys.readouterr().out


# --- moving the memory -----------------------------------------------------

def test_export_import_round_trip_through_files(db, capsys, tmp_path):
    out_file = tmp_path / "bundle.json"
    assert run(db, "export", "--out", str(out_file)) == cli.EXIT_OK
    bundle = json.loads(out_file.read_text())
    assert bundle["counts"]["sealed"] == 1

    other = tmp_path / "other.db"
    argv = ["--db", str(other), "--ledger", db["ledger"], "import", str(out_file)]
    assert cli.main(argv) == cli.EXIT_OK
    assert "would import" in capsys.readouterr().out
    assert SqliteStore(str(other)).memory_list() == [], "a dry run writes nothing"

    assert cli.main(argv + ["--apply", "--verifier", "ops"]) == cli.EXIT_OK
    assert "imported" in capsys.readouterr().out
    assert len(SqliteStore(str(other)).memory_list()) == 2


def test_import_of_a_conflicting_bundle_exits_nonzero_and_lists_it(db, capsys, tmp_path):
    out_file = tmp_path / "bundle.json"
    run(db, "export", "--out", str(out_file))
    other = tmp_path / "other.db"
    o = SqliteStore(str(other))
    o.init_db()
    memory.add_pair("Good evening.", "Buenas tardes.", "en", "es", status="sealed",
                    verifier="someone-else", store=o)

    code = cli.main(["--db", str(other), "--ledger", db["ledger"], "import",
                     str(out_file), "--apply", "--verifier", "ops"])
    assert code == cli.EXIT_ANSWER_IS_NO
    assert "conflict" in capsys.readouterr().out
    assert memory.best_sealed("Good evening.", "en", "es",
                              store=o)["pair"]["target_text"] == "Buenas tardes."


def test_csv_export_is_offered_and_is_lossy(db, capsys):
    assert run(db, "export", "--format", "csv") == cli.EXIT_OK
    text = capsys.readouterr().out
    assert "source_text" in text and "seal_sig" not in text


def test_a_file_that_is_not_a_bundle_is_a_usage_error(db, tmp_path, capsys):
    junk = tmp_path / "junk.json"
    junk.write_text('{"hello": "world"}')
    assert run(db, "import", str(junk)) == cli.EXIT_USAGE
    assert "not a usable bundle" in capsys.readouterr().err
    assert run(db, "import", str(tmp_path / "nope.json")) == cli.EXIT_USAGE


# --- auditing --------------------------------------------------------------

def tamper(db, index, **changes):
    lines = (db["path"] / "ledger.jsonl").read_text().splitlines()
    record = json.loads(lines[index])
    record.update(changes)
    lines[index] = json.dumps(record)
    (db["path"] / "ledger.jsonl").write_text("\n".join(lines) + "\n")


def test_ledger_verify_is_a_ci_gate(db, capsys):
    run(db, "ask", "good evening")                 # a second entry to chain onto
    assert run(db, "ledger", "verify") == cli.EXIT_OK
    assert "intact" in capsys.readouterr().out

    tamper(db, 0, verifier="mallory")
    assert run(db, "ledger", "verify") == cli.EXIT_ANSWER_IS_NO
    assert "broken chain" in capsys.readouterr().out


def test_editing_the_newest_entry_needs_a_pinned_head_to_catch(db, capsys):
    """The chain vouches for every line except the last one — so pin the last one."""
    run(db, "ask", "good evening")
    assert run(db, "ledger", "head") == cli.EXIT_OK
    pinned = capsys.readouterr().out.strip()

    tamper(db, -1, state="sealed", verifier="mallory")
    assert run(db, "ledger", "verify") == cli.EXIT_OK, "the walk cannot see this"
    assert "intact" in capsys.readouterr().out

    assert run(db, "ledger", "verify", "--expect-head", pinned) == cli.EXIT_ANSWER_IS_NO
    assert "the last entry was edited" in capsys.readouterr().out


def test_ledger_entries_can_be_read_and_filtered(db, capsys):
    assert run(db, "ledger", "entries", "--kind", "seal") == cli.EXIT_OK
    lines = [x for x in capsys.readouterr().out.splitlines() if x.strip()]
    assert lines and all("seal" in x for x in lines)


def test_stats_says_what_is_in_there_and_whether_signing_is_on(db, capsys):
    assert run(db, "stats") == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "1 sealed" in out and "en→es" in out and "seal signatures: on" in out


# --- delegation ------------------------------------------------------------

def test_ui_and_serve_own_their_own_flags():
    assert cli.split_delegated(["ui", "--port", "9999"]) == ("ui", ["--port", "9999"])
    assert cli.split_delegated(["serve", "--read-only"]) == ("serve", ["--read-only"])


def test_global_flags_still_work_before_a_delegated_subcommand():
    """``nestor --db x.db ui`` — typed by anyone who used --db for anything else."""
    assert cli.split_delegated(
        ["--db", "x.db", "--ledger", "x.jsonl", "--json", "ui", "--port", "1"],
    ) == ("ui", ["--db", "x.db", "--ledger", "x.jsonl", "--port", "1"])
    # An explicit flag after the subcommand still wins, since argparse takes the last.
    assert cli.split_delegated(["--db", "a", "ui", "--db", "b"])[1] == ["--db", "a", "--db", "b"]
    # And a normal subcommand is untouched.
    assert cli.split_delegated(["--db", "a", "stats"]) == (None, ["--db", "a", "stats"])


def test_cli_main_reaches_ui_in_a_subprocess(tmp_path):
    """``nestor ui`` is delegated in a real process, not only via split_delegated."""
    db = tmp_path / "nestor.db"
    ledger = tmp_path / "ledger.jsonl"
    port = _free_loopback_port()
    proc = subprocess.Popen(
        [sys.executable, "-u", "-m", "nestor.cli",
         "ui", "--db", str(db), "--ledger", str(ledger), "--port", str(port)],
        cwd=REPO,
        env=_cli_subprocess_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        banner = proc.stdout.readline()
        store_line = proc.stdout.readline()
        assert "Nestor UI" in banner
        assert re.search(rf":{port}/", banner)
        assert str(db) in store_line
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_cli_main_carries_global_flags_to_ui_in_a_subprocess(tmp_path):
    db = tmp_path / "nestor.db"
    ledger = tmp_path / "ledger.jsonl"
    port = _free_loopback_port()
    proc = subprocess.Popen(
        [sys.executable, "-u", "-m", "nestor.cli",
         "--db", str(db), "--ledger", str(ledger),
         "ui", "--port", str(port)],
        cwd=REPO,
        env=_cli_subprocess_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        proc.stdout.readline()
        store_line = proc.stdout.readline()
        ledger_line = proc.stdout.readline()
        assert str(db) in store_line
        assert str(ledger) in ledger_line
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_cli_main_reaches_serve_in_a_subprocess(tmp_path):
    db = tmp_path / "nestor.db"
    ledger = tmp_path / "ledger.jsonl"
    proc = subprocess.Popen(
        [sys.executable, "-u", "-m", "nestor.cli",
         "--db", str(db), "--ledger", str(ledger),
         "serve", "--read-only"],
        cwd=REPO,
        env=_cli_subprocess_env(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        line = proc.stderr.readline()
        assert "read-only" in line
        assert str(db) in line
        assert str(ledger) in line
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_cli_main_ui_help_in_a_subprocess():
    done = _run_cli_subprocess(["ui", "--help"])
    assert done.returncode == 0
    assert "--port" in done.stdout
