"""The terminal surface — and its exit codes, which are the point.

`nestor ledger verify` is a CI gate and `nestor ask` belongs in a shell
conditional, so 0 must mean "the good answer" and 1 must mean "the bad one"
rather than both meaning "the program ran". These tests pin that, and pin that
`nestor import` writes nothing until told to.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import socket
import subprocess
import sys

import pytest
from conftest import CONFIGURED_BY_ENV

from nestor import cli, memory, signing, storage
from nestor.decision import DecisionMemory
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
        check=False,
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


# --- decision: `nestor decision check`, the CI gate over the graph ---------
#
# docs/decision-memory.md N9(1): the same "exit code carries the answer"
# pattern as `nestor ledger verify`, pointed at the decision graph instead of
# the audit chain. 0 = clear to propose, 1 = BLOCKED, 2 = usage error. Every
# BLOCKED case here is an adversarial guard: it sets up exactly the recorded
# state the gate exists to catch and asserts the exit code refuses it, not
# just that some text got printed.

def test_decision_check_exits_zero_when_nothing_is_recorded(db, capsys):
    assert run(db, "decision", "check", "may the mascot be retired?") == cli.EXIT_OK
    assert "clear" in capsys.readouterr().out


def test_decision_check_is_blocked_by_a_permanent_rejection(db, capsys):
    memory.reject_match(
        "may we ship on Fridays?", "decision", "decision",
        target_text="yes", verifier="rita", reason="two prod incidents traced to it",
        store=db["store"])

    assert run(db, "decision", "check", "may we ship on Fridays?") == cli.EXIT_ANSWER_IS_NO
    out = capsys.readouterr().out
    assert "BLOCKED" in out
    assert "two prod incidents traced to it" in out
    assert "permanent" in out
    assert "condition to re-check" not in out


def test_decision_check_distinguishes_not_yet_from_never(db, capsys):
    """A deferred rejection (reopen_when set) must be reported differently
    from a permanent one — conflating them is the exact failure N5 exists to
    close, and a CI gate that cannot tell them apart is worse than none: it
    would enforce a stale 'no' as if it were still the operator's answer."""
    memory.reject_match(
        "may we skip the design review?", "decision", "decision",
        target_text="yes", verifier="rita", reason="not while the team is this new",
        reopen_when="after two more shipped features", store=db["store"])

    assert run(db, "decision", "check", "may we skip the design review?") == cli.EXIT_ANSWER_IS_NO
    out = capsys.readouterr().out
    assert "BLOCKED" in out
    assert "a condition to re-check" in out
    assert "after two more shipped features" in out
    assert "(permanent" not in out


def _sealed_decision(store, question, commitment, verifier="rita"):
    dm = DecisionMemory(store)
    norm = dm.matcher.normalize(question)
    sig = signing.sign_seal(norm, commitment, verifier)
    pair = dm.seal(question, commitment, verifier, sig)
    return dm, pair["id"]


def test_decision_check_is_blocked_by_a_sealed_contradicts_edge(db, capsys):
    dm, a = _sealed_decision(db["store"], "may the joke be authored cold?",
                             "yes — witnessed")
    _, b = _sealed_decision(db["store"], "may the machine seal its own work?",
                            "no — author != witness")
    dm.propose_edge(a, b, "contradicts", reason="A and B cannot both stand")
    sig = signing.sign_edge(a, b, "contradicts", "rita")
    dm.seal_edge(a, b, "contradicts", "rita", sig)

    assert run(db, "decision", "check",
              "may the joke be authored cold?") == cli.EXIT_ANSWER_IS_NO
    out = capsys.readouterr().out
    assert "BLOCKED" in out
    assert "contradicts" in out
    assert "no — author != witness" in out


def test_decision_check_a_merely_proposed_contradicts_edge_does_not_block(db, capsys):
    """The covenant, at the CLI layer: an edge nobody signed is surfaced to a
    curator, never enforced as fact. If this ever blocked, an unsigned
    machine assertion would gate CI the same as a human ratification."""
    dm, a = _sealed_decision(db["store"], "may the joke be authored cold?",
                             "yes — witnessed")
    _, b = _sealed_decision(db["store"], "may the machine seal its own work?",
                            "no — author != witness")
    dm.propose_edge(a, b, "contradicts", reason="unratified — should not block")

    assert run(db, "decision", "check",
              "may the joke be authored cold?") == cli.EXIT_OK
    assert "clear" in capsys.readouterr().out


def test_decision_check_a_tampered_contradicts_edge_does_not_block(db, capsys):
    """A row that merely SAYS sealed must not gate CI — same principle as
    ``test_ledger_verify_is_a_ci_gate``, one object over. This also pins that
    ``cmd_decision`` routes through ``constraints_on``'s own signature
    verification rather than trusting the ``decision_edges`` table directly."""
    dm, a = _sealed_decision(db["store"], "may the joke be authored cold?",
                             "yes — witnessed")
    _, b = _sealed_decision(db["store"], "may the machine seal its own work?",
                            "no — author != witness")
    dm.propose_edge(a, b, "contradicts")
    sig = signing.sign_edge(a, b, "contradicts", "rita")
    dm.seal_edge(a, b, "contradicts", "rita", sig)
    # Flip the leading byte to something it is not. A flat `"00" + sig[2:]` is a
    # no-op on the ~1/256 of signatures that already start with "00" — the edge
    # then still verifies, the contradiction stands, and `decision check` exits
    # non-zero. Measured before this change: 1 failure in 400 runs of this test,
    # against the ~1.6 that rate predicts. A tamper test whose tamper sometimes
    # does nothing is the one shape of flake that reads as the gate working.
    tampered = ("01" if sig.startswith("00") else "00") + sig[2:]
    assert tampered != sig, "the tamper must actually change the signature"
    with db["store"]._db() as conn:
        conn.execute("UPDATE decision_edges SET edge_sig=? WHERE src_id=?",
                     (tampered, a))

    assert run(db, "decision", "check",
              "may the joke be authored cold?") == cli.EXIT_OK
    assert "clear" in capsys.readouterr().out


def test_decision_check_usage_errors(db, capsys):
    assert run(db, "decision", "check", "  ") == cli.EXIT_USAGE
    assert "question is required" in capsys.readouterr().err

    assert run(db, "decision", "check", "q", "--from", "architecture",
              "--to", "governance") == cli.EXIT_USAGE
    assert "must match" in capsys.readouterr().err


def test_decision_check_honors_the_domain_flag(db, capsys):
    """Two disjoint graphs (N8's ``decision:architecture`` /
    ``decision:governance``) must not see each other's rejections."""
    memory.reject_match("shared question text", "architecture", "architecture",
                        target_text="x", verifier="rita", reason="architecture says no",
                        store=db["store"])

    assert run(db, "decision", "check", "shared question text",
              "--from", "architecture", "--to", "architecture") == cli.EXIT_ANSWER_IS_NO
    assert run(db, "decision", "check", "shared question text",
              "--from", "governance", "--to", "governance") == cli.EXIT_OK


def test_decision_check_json_output(db, capsys):
    memory.reject_match("may we ship on Fridays?", "decision", "decision",
                        target_text="yes", verifier="rita", reason="see incidents",
                        store=db["store"])
    assert run(db, "--json", "decision", "check",
              "may we ship on Fridays?") == cli.EXIT_ANSWER_IS_NO
    payload = json.loads(capsys.readouterr().out)
    assert payload["blocked"] is True
    assert payload["rejected"][0]["reason"] == "see incidents"


# --- fuzzy decision check (§6.33/6.94/6.106) --------------------------------

def test_decision_check_fuzzy_finds_paraphrase(db, capsys):
    from nestor.decision import DecisionMemory
    dm = DecisionMemory(db["store"])
    dm.propose("may the machine seal its own work?", "no — author != witness")
    assert run(db, "decision", "check", "--fuzzy-bar", "0.45",
              "can the machine seal its own work?") == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "fuzzy match" in out
    assert "may the machine seal its own work?" in out


def test_decision_check_fuzzy_zero_disables(db, capsys):
    from nestor.decision import DecisionMemory
    dm = DecisionMemory(db["store"])
    dm.propose("may the machine seal its own work?", "no — author != witness")
    assert run(db, "decision", "check", "--fuzzy-bar", "0",
              "can the machine seal its own work?") == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "no decision on record" in out


def test_decision_check_fuzzy_json_includes_match_and_similarity(db, capsys):
    from nestor.decision import DecisionMemory
    dm = DecisionMemory(db["store"])
    dm.propose("may the machine seal its own work?", "no — author != witness")
    assert run(db, "--json", "decision", "check", "--fuzzy-bar", "0.45",
              "can the machine seal its own work?") == cli.EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["match"] == "fuzzy"
    assert payload["similarity"] >= 0.45


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


def test_ui_refuses_malformed_ledger_verify_interval_in_subprocess(tmp_path):
    port = _free_loopback_port()
    env = _cli_subprocess_env()
    env["NESTOR_LEDGER_VERIFY_INTERVAL_SEC"] = "5m"
    done = subprocess.run(
        [sys.executable, "-u", "-m", "nestor.ui",
         "--db", str(tmp_path / "n.db"), "--port", str(port)],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert done.returncode == 2
    assert "NESTOR_LEDGER_VERIFY_INTERVAL_SEC" in done.stderr
    assert "refusing to start" in done.stderr
    assert not (tmp_path / "n.db").exists()


def test_db_checkpoint_cli_writes_copy_and_keeps_store_usable(db, tmp_path):
    out = tmp_path / "copy.db"
    assert run(db, "db", "checkpoint", "--out", str(out)) == cli.EXIT_OK
    assert out.is_file()
    ledger_copy = out.with_name(out.name + ".ledger.jsonl")
    assert ledger_copy.is_file()
    assert ledger_copy.read_text() == pathlib.Path(db["ledger"]).read_text()
    assert run(db, "db", "checkpoint") == cli.EXIT_OK
    assert run(db, "ask", "good evening") == cli.EXIT_OK


def test_db_checkpoint_ledger_sidecar_appends_to_basename(db, tmp_path):
    """Dots in the db filename must not collapse the ledger sidecar name."""
    out_a = tmp_path / "nightly" / "2026.07.30"
    out_b = tmp_path / "nightly" / "2026.07.31"
    assert run(db, "db", "checkpoint", "--out", str(out_a)) == cli.EXIT_OK
    assert (tmp_path / "nightly" / "2026.07.30.ledger.jsonl").is_file()
    assert run(db, "db", "checkpoint", "--out", str(out_b)) == cli.EXIT_OK
    assert (tmp_path / "nightly" / "2026.07.31.ledger.jsonl").is_file()


def test_no_ledger_never_leaves_a_chain_describing_a_different_backup(db, tmp_path, capsys):
    """`--no-ledger` writes no sidecar; it must not leave an older one either.

    A stale chain beside a freshly written database is worse than no chain at
    all: the two files look like a matched pair and the store is the one that
    is ahead, so the backup reads as sealed rows whose ledger entries are
    missing — the state `_ledger_preflight` refuses to create at seal time.
    """
    out = tmp_path / "pair.db"
    assert run(db, "db", "checkpoint", "--out", str(out)) == cli.EXIT_OK
    sidecar = out.with_name(out.name + ".ledger.jsonl")
    assert sidecar.is_file()
    before = sidecar.read_text()

    # The store moves on, and the next backup is taken without the chain.
    memory.add_pair("a later seal", "un sello posterior", "en", "es",
                    status="sealed", verifier="rita", store=db["store"])

    assert run(db, "db", "checkpoint", "--out", str(out), "--no-ledger") == cli.EXIT_USAGE
    assert "refusing to overwrite" in capsys.readouterr().err
    assert sidecar.read_text() == before, "a refusal changes nothing"

    assert run(db, "db", "checkpoint", "--out", str(out),
               "--no-ledger", "--force") == cli.EXIT_OK
    assert out.is_file()
    assert not sidecar.exists(), "the chain that described the old backup is gone"


def test_no_ledger_says_why_a_lone_sidecar_blocks_it(db, tmp_path, capsys):
    """The db name is free, so the refusal names a file the operator did not
    type — it has to say why that file is in the way."""
    out = tmp_path / "orphan.db"
    out.with_name(out.name + ".ledger.jsonl").write_text("{}\n", encoding="utf-8")
    assert run(db, "db", "checkpoint", "--out", str(out), "--no-ledger") == cli.EXIT_USAGE
    assert "describing a different backup" in capsys.readouterr().err


def test_db_checkpoint_refuses_existing_out_without_force(db, tmp_path, capsys):
    out = tmp_path / "copy.db"
    out.write_text("taken", encoding="utf-8")
    assert run(db, "db", "checkpoint", "--out", str(out)) == cli.EXIT_USAGE
    assert "refusing to overwrite" in capsys.readouterr().err


def test_check_prints_the_tolerance_its_verdict_turned_on(db, capsys):
    from nestor.reconcile import Reconciler
    Reconciler(db["store"], domain="q", pct_tol=0.05).seal_baseline(
        "revenue", 3.9, verifier="auditor")

    # 0.2/3.9 is 5.13% — printed against a 5% tolerance, a passing verdict is
    # unreadable without the slack beside it. With it, `variation <= tolerance`
    # is arithmetic the reader can do on the line as printed.
    assert run(db, "check", "revenue", "4.1", "--domain", "q") == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "within tolerance" in out
    assert "(5.13%)" in out
    assert "tolerance 0.205" in out


def test_check_omits_the_tolerance_when_nothing_was_compared(db, capsys):
    from nestor.reconcile import Reconciler
    Reconciler(db["store"], domain="q", pct_tol=0.05).seal_baseline(
        "revenue", 3.9, verifier="auditor")

    assert run(db, "check", "revenue", "abc", "--domain", "q") == cli.EXIT_ANSWER_IS_NO
    out = capsys.readouterr().out
    assert "no number could be read" in out
    assert "tolerance" not in out

    assert run(db, "check", "never-sealed", "1", "--domain", "q") == cli.EXIT_ANSWER_IS_NO
    assert "tolerance" not in capsys.readouterr().out


# --- warrants: attaching one, and reading the set back ----------------------

def _pair_id(db, contains):
    rows = db["store"].memory_list(contains=contains)
    assert len(rows) == 1, f"expected one pair matching {contains!r}, got {len(rows)}"
    return rows[0]["id"]


def _sealed_pair_id(db):
    return _pair_id(db, "Good evening")


def test_warrant_attach_records_a_citation_and_claims_nothing(db, capsys):
    pid = _sealed_pair_id(db)
    assert run(db, "warrant", "attach", pid, "--kind", "citation",
               "--authority", "Crossref", "--locator", "https://doi.org/10.1000/xyz",
               "--check", "follow the DOI", "--by", "agent-7") == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "citation warrant" in out
    # The sentence matters as much as the row: a CLI that says "attached" and
    # stops reads as a confirmation, which is the one thing this cannot do.
    assert "nothing here says it holds" in out


def test_warrant_for_shows_the_seal_as_an_attestation_it_did_not_store(db, capsys):
    """``warrants_for`` composes the seal in, and the terminal must not let that
    read as a row somebody wrote into the warrants table — there is no such row,
    and a stored one would be the forgeable copy."""
    pid = _sealed_pair_id(db)
    run(db, "warrant", "attach", pid, "--kind", "citation",
        "--authority", "Crossref", "--locator", "https://doi.org/1")
    capsys.readouterr()
    assert run(db, "warrant", "for", pid) == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "attestation" in out and "rita" in out
    assert "from the seal, not stored as a warrant" in out
    assert "citation" in out
    assert "a set, in no order" in out


def test_warrant_json_reports_the_kinds_held(db, capsys):
    pid = _sealed_pair_id(db)
    run(db, "warrant", "attach", pid, "--kind", "construction",
        "--authority", "redential", "--locator", "npx redential scan",
        "--expected-digest", "ab" * 16)
    capsys.readouterr()
    run(db, "--json", "warrant", "for", pid)
    payload = json.loads(capsys.readouterr().out)
    assert payload["kinds"] == ["attestation", "construction"]
    assert payload["count"] == 2


def test_the_cli_cannot_be_asked_for_an_attestation_warrant(db):
    """Refused by argparse, before a store is opened: a seal is the only way to
    say a person here checked, and the CLI must not offer a second one."""
    pid = _sealed_pair_id(db)
    with pytest.raises(SystemExit) as exc:
        run(db, "warrant", "attach", pid, "--kind", "attestation",
            "--authority", "rita", "--locator", "x")
    assert exc.value.code == 2


def test_a_refused_warrant_exits_usage_and_writes_nothing(db, capsys):
    pid = _sealed_pair_id(db)
    assert run(db, "warrant", "attach", pid, "--kind", "construction",
               "--authority", "redential",
               "--locator", "npx redential scan") == cli.EXIT_USAGE
    assert "needs an expected_digest" in capsys.readouterr().err
    assert run(db, "warrant", "for", pid) == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "construction" not in out


def test_warrant_for_on_an_unwarranted_draft_says_so_plainly(db, capsys):
    pid = _pair_id(db, "a draft phrase")
    assert run(db, "warrant", "for", pid) == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "no warrant" in out and "not cited" in out


# --- the consult must show what it found -----------------------------------

def _record_live_decision(db, question, commitment, why=""):
    """A recorded, unblocked commitment — the ordinary case, not a rejection."""
    dm = DecisionMemory(db["store"], domain="decision")
    return dm.propose(question, commitment, rationale=why)


def test_a_clear_consult_shows_the_commitment_it_matched(db, capsys):
    """exit 0 means "nothing on record BLOCKS this", which is not the same
    sentence as "nothing is on record" — and the two used to print almost
    identically.

    Measured, not supposed: a consult on IDEAS §1.10(a) matched decision 0164
    at similarity 1.0, printed `✓ clear`, and the recorded commitment was
    visible only under --json. An agent following this repo's own seat rule —
    consult before you propose — would have proposed an answer to a question
    already answered, and the gate it was told to trust would have said the
    coast was clear."""
    _record_live_decision(db, "may the office plant be rehomed?",
                          "Yes, to Rita's desk, which gets the afternoon light.",
                          why="It died twice by the radiator.")
    assert run(db, "decision", "check",
               "may the office plant be rehomed?") == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "clear" in out                       # still clear: nothing blocks it
    assert "A commitment IS on record" in out
    assert "Rita's desk" in out                 # the commitment itself, verbatim
    assert "died twice by the radiator" in out  # and why
    assert "draft — proposed, not human-sealed" in out


def test_a_consult_with_nothing_recorded_still_says_only_that(db, capsys):
    """The other half of the pair: the fix must not make silence look like a
    hit either. `no decision on record` stays exactly what it was."""
    assert run(db, "decision", "check",
               "may the mascot be retired?") == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "no decision on record" in out
    assert "A commitment IS on record" not in out


def test_a_sealed_commitment_is_labelled_differently_from_a_draft(db, capsys):
    """A draft read at a glance is the one most likely to be mistaken for
    settled, so the two are never printed the same way."""
    memory.add_pair("do we keep the Friday demo?", "Yes.", "decision", "decision",
                    status="sealed", verifier="rita", store=db["store"])
    capsys.readouterr()
    assert run(db, "decision", "check", "do we keep the Friday demo?") == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "SEALED by rita" in out
    assert "draft — proposed" not in out


# --- --version ---------------------------------------------------------------

def test_version_flag_prints_and_exits():
    done = _run_cli_subprocess(["--version"])
    assert done.returncode == 0
    assert done.stdout.startswith("nestor ")


# --- completions (shtab) -----------------------------------------------------

def test_completions_bash():
    pytest.importorskip("shtab")
    done = _run_cli_subprocess(["completions", "bash"])
    assert done.returncode == 0
    assert "nestor" in done.stdout
    assert "_shtab_" in done.stdout or "complete" in done.stdout


def test_completions_zsh():
    pytest.importorskip("shtab")
    done = _run_cli_subprocess(["completions", "zsh"])
    assert done.returncode == 0
    assert "#compdef nestor" in done.stdout


# --- uniform --json on db and export -----------------------------------------

def test_db_checkpoint_json_output(db, capsys):
    assert cli.main(["--db", db["db"], "--ledger", db["ledger"],
                     "--json", "db", "checkpoint"]) == cli.EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["action"] == "checkpoint"
    assert payload["db"] == db["db"]


def test_db_checkpoint_out_json_output(db, tmp_path, capsys):
    out = tmp_path / "backup.db"
    assert cli.main(["--db", db["db"], "--ledger", db["ledger"],
                     "--json", "db", "checkpoint",
                     "--out", str(out)]) == cli.EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["action"] == "backup"
    assert str(out) in payload["files"]


def test_export_out_json_output(db, tmp_path, capsys):
    out = tmp_path / "bundle.json"
    assert cli.main(["--db", db["db"], "--ledger", db["ledger"],
                     "--json", "export", "--out", str(out)]) == cli.EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["file"] == str(out)
    assert "counts" in payload
    assert "digest" in payload
