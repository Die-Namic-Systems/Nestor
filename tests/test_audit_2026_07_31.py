"""Regressions for the findings of 2026-07-31 (five auditors, one branch).

Each test was run against the *unfixed* revision first and observed to fail. A
test that passes before the fix is a description, not a gate — the lesson from
`tests/test_findings_2026_07_30.py`, which caught a doc test that could not fail.

  A  an import could resurrect a pair a human had rejected
  B  two threads could seal the same source, and both won
  C  a seal onto a broken chain was accepted and never recorded
  D  concurrent appends wrote every entry and broke the chain
  E  `nestor check` crashed on a figure it could not read
  F  an import discarded a verification it could prove

A and C are the same shape as the finding that started this codebase's rejection
work: a guarantee enforced at one call site, and a second path that reaches the
store without passing it.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import threading

import pytest

from nestor import cascade, cli, memory, portable, storage
from nestor.ledger import verify
from nestor.sqlite_store import SqliteStore


@pytest.fixture()
def signed(tmp_path, monkeypatch):
    monkeypatch.setenv("NESTOR_SEAL_KEY", "shared-key")
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    return tmp_path


def fresh(path=":memory:"):
    s = SqliteStore(path)
    s.init_db()
    s.memory_init()
    return s


# --- A. import vs a rejection ----------------------------------------------

def test_an_import_cannot_resurrect_a_rejected_pair(signed):
    """`--override-conflicts` means "their answer wins where we disagree".

    A rejection is not a competing answer. Reviving one is the leak rejection
    exists to close, arriving through a file instead of through add_pair.
    """
    src = fresh()
    storage.set_store(src)
    memory.add_pair("wire the funds", "transfiera los fondos", "en", "es",
                    status="sealed", verifier="mallory", store=src)
    bundle = portable.export_bundle(src)

    dst = fresh()
    pair = memory.add_pair("wire the funds", "algo distinto", "en", "es",
                           status="sealed", verifier="rita", store=dst)
    memory.reject_pair(pair["id"], verifier="rita", reason="fraudulent", store=dst)

    with pytest.warns(RuntimeWarning, match="were rejected on this instance"):
        report = portable.import_bundle(bundle, store=dst, dry_run=False,
                                        verifier="ops", override_conflicts=True)

    assert len(report["rejected_here"]) == 1
    assert report["rejected_here"][0]["rejected_by"] == "rita"
    assert dst.memory_get(pair["id"])["status"] == "rejected"
    assert memory.best_sealed("wire the funds", "en", "es", store=dst) is None


def test_reviving_a_rejection_has_its_own_deliberate_switch(signed):
    src = fresh()
    storage.set_store(src)
    memory.add_pair("wire the funds", "transfiera los fondos", "en", "es",
                    status="sealed", verifier="rita", store=src)
    bundle = portable.export_bundle(src)

    dst = fresh()
    pair = memory.add_pair("wire the funds", "algo distinto", "en", "es",
                           status="sealed", verifier="rita", store=dst)
    memory.reject_pair(pair["id"], verifier="rita", reason="stale", store=dst)

    portable.import_bundle(bundle, store=dst, dry_run=False, verifier="ops",
                           override_conflicts=True, override_rejections=True)
    assert memory.best_sealed("wire the funds", "en", "es", store=dst) is not None


def test_the_cli_reports_a_refused_rejection_and_exits_nonzero(signed, tmp_path, capsys):
    src = fresh(str(tmp_path / "src.db"))
    storage.set_store(src)
    memory.add_pair("wire the funds", "transfiera los fondos", "en", "es",
                    status="sealed", verifier="rita", store=src)
    out = tmp_path / "b.json"
    argv = ["--db", str(tmp_path / "src.db"), "--ledger", str(tmp_path / "ledger.jsonl")]
    cli.main(argv + ["export", "--out", str(out)])

    dst_path = tmp_path / "dst.db"
    dst = fresh(str(dst_path))
    pair = memory.add_pair("wire the funds", "algo distinto", "en", "es",
                           status="sealed", verifier="rita", store=dst)
    memory.reject_pair(pair["id"], verifier="rita", reason="fraudulent", store=dst)

    code = cli.main(["--db", str(dst_path), "--ledger", str(tmp_path / "ledger.jsonl"),
                     "import", str(out), "--apply", "--verifier", "ops",
                     "--override-conflicts"])
    assert code == cli.EXIT_ANSWER_IS_NO
    assert "REJECTED here by rita" in capsys.readouterr().out


# --- B. two reviewers, one phrase, one instant -----------------------------

def test_two_concurrent_seals_leave_one_row_and_one_refusal(signed, tmp_path):
    """The check-then-write in add_pair was not atomic, and nothing enforced the
    key it assumed. Both threads found nothing and both inserted."""
    store = fresh(str(tmp_path / "race.db"))
    storage.set_store(store)
    gate, refused = threading.Barrier(2), []

    def seal(target, who):
        try:
            gate.wait(timeout=5)
            memory.add_pair("the annual invoice", target, "en", "es",
                            status="sealed", verifier=who, store=store)
        except memory.ConflictingSealError:
            refused.append(who)

    threads = [threading.Thread(target=seal, args=("la factura anual", "rita")),
               threading.Thread(target=seal, args=("otra factura", "sam"))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    rows = store.memory_list(contains="annual")
    assert len(rows) == 1, f"one normalized source, one row — got {len(rows)}"
    assert len(refused) == 1, "the loser must be told, not silently dropped"
    assert memory.best_sealed("the annual invoice", "en", "es", store=store)


def test_the_reference_store_enforces_one_row_per_source(signed):
    store = fresh()
    memory.add_pair("hello", "hola", "en", "es", store=store)
    row = store.memory_find(memory._norm("hello"), "en", "es")
    with pytest.raises(Exception):
        store.memory_insert({**row, "id": "a-second-row"})


# --- C. a seal that could not be audited was accepted anyway ---------------

def _break_the_chain(path: pathlib.Path) -> None:
    lines = path.read_text().splitlines()
    record = json.loads(lines[0])
    record["verifier"] = "mallory"
    lines[0] = json.dumps(record)
    path.write_text("\n".join(lines) + "\n")
    cascade._verified_ledgers.clear()          # as a fresh process would see it


def test_a_seal_onto_a_broken_chain_is_refused_like_a_rejection_is(signed):
    """The priorities were inverted: withdrawing trust failed closed, granting
    it sailed through and wrote nothing."""
    ledger = signed / "ledger.jsonl"
    store = fresh()
    storage.set_store(store)
    first = memory.add_pair("first", "primero", "en", "es", status="sealed",
                            verifier="rita", store=store)
    memory.add_pair("second", "segundo", "en", "es", status="sealed",
                    verifier="rita", store=store)
    _break_the_chain(ledger)
    before = len(ledger.read_text().splitlines())

    with pytest.raises(Exception, match="chain is broken"):
        memory.add_pair("third", "tercero", "en", "es", status="sealed",
                        verifier="rita", store=store)
    assert memory.best_sealed("third", "en", "es", store=store) is None, \
        "nothing may be sealed while the trail cannot record it"
    assert len(ledger.read_text().splitlines()) == before

    with pytest.raises(Exception, match="chain is broken"):
        memory.reject_pair(first["id"], verifier="rita", reason="x", store=store)


def test_a_draft_still_lands_because_it_is_not_a_verification(signed):
    ledger = signed / "ledger.jsonl"
    store = fresh()
    storage.set_store(store)
    memory.add_pair("first", "primero", "en", "es", status="sealed",
                    verifier="rita", store=store)
    memory.add_pair("second", "segundo", "en", "es", status="sealed",
                    verifier="rita", store=store)
    _break_the_chain(ledger)

    memory.add_pair("a machine wrote this", "algo", "en", "es", store=store)
    assert store.memory_find(memory._norm("a machine wrote this"), "en", "es")


# --- D. the chain under concurrent writers ---------------------------------

def test_concurrent_appends_keep_the_chain_intact(signed):
    """Every entry was written and the chain was still broken — an audit trail
    that indicts itself is worse than a slow one."""
    ledger = signed / "ledger.jsonl"
    gate = threading.Barrier(6)

    def spam(n):
        gate.wait(timeout=5)
        for i in range(15):
            cascade.ledger_append({"kind": "passage", "who": n, "i": i})

    threads = [threading.Thread(target=spam, args=(n,)) for n in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(ledger.read_text().splitlines()) == 90
    ok, detail = verify(str(ledger))
    assert ok, detail


def test_a_second_process_appending_at_the_same_time_keeps_it_intact(signed):
    """Two processes over one ledger is a UI plus a cron job, not an exotic case."""
    ledger = signed / "ledger.jsonl"
    code = ("import sys; from nestor import cascade;"
            "cascade.set_ledger_path(sys.argv[1]);"
            "[cascade.ledger_append({'kind': 'passage', 'p': sys.argv[2], 'i': i})"
            " for i in range(25)]")
    procs = [subprocess.Popen([sys.executable, "-c", code, str(ledger), str(n)],
                              stderr=subprocess.PIPE, text=True)
             for n in range(3)]
    for p in procs:
        # stderr is captured and reported: the first version of this test
        # asserted `wait() == 0` and, when CI failed it, said "assert 1 == 0"
        # and nothing else. A gate that cannot say why it failed costs an hour.
        _, err = p.communicate(timeout=60)
        assert p.returncode == 0, f"a writer process died:\n{err}"

    assert len(ledger.read_text().splitlines()) == 75
    ok, detail = verify(str(ledger))
    assert ok, detail


# --- E. a figure the matcher could not read --------------------------------

def test_check_reports_an_unreadable_figure_instead_of_crashing(signed, tmp_path, capsys):
    from nestor.reconcile import Reconciler

    db = tmp_path / "n.db"
    store = fresh(str(db))
    storage.set_store(store)
    Reconciler(store, domain="contract").seal_baseline("ceiling", "$1,000,000",
                                                       verifier="auditor")
    code = cli.main(["--db", str(db), "--ledger", str(signed / "ledger.jsonl"),
                     "check", "ceiling", "not a number", "--domain", "contract"])
    assert code == cli.EXIT_ANSWER_IS_NO
    assert "no number could be read" in capsys.readouterr().out


# --- F. an import that threw away a verification ---------------------------

def test_a_verified_seal_upgrades_a_local_draft_rather_than_being_discarded(signed):
    """Same text on both sides is not the same standing: one of them is verified."""
    src = fresh()
    storage.set_store(src)
    memory.add_pair("good evening", "buenas noches", "en", "es",
                    status="sealed", verifier="rita", store=src)
    bundle = portable.export_bundle(src)

    dst = fresh()
    memory.add_pair("good evening", "buenas noches", "en", "es", store=dst)  # a draft
    report = portable.import_bundle(bundle, store=dst, dry_run=False, verifier="ops")

    assert report["sealed"] == 1 and report["existing"] == 0
    hit = memory.best_sealed("good evening", "en", "es", store=dst)
    assert hit and hit["pair"]["verifier"] == "rita"


def test_an_identical_sealed_row_is_still_a_no_op(signed):
    src = fresh()
    storage.set_store(src)
    memory.add_pair("good evening", "buenas noches", "en", "es",
                    status="sealed", verifier="rita", store=src)
    bundle = portable.export_bundle(src)
    dst = fresh()
    portable.import_bundle(bundle, store=dst, dry_run=False, verifier="ops")
    again = portable.import_bundle(bundle, store=dst, dry_run=False, verifier="ops")
    assert again["existing"] == 1 and again["sealed"] == 0


# --- G. a governance mirror that stops answering ---------------------------

def test_a_wedged_frank_mirror_cannot_hang_a_seal(signed):
    """`timeout` was accepted by the constructor and applied to nothing.

    Every seal, serve and rejection reaches the forwarder through
    `cascade.ledger_append`, so "the mirror is wedged" meant "Nestor is wedged"
    — the exact opposite of this module's stated contract.
    """
    import time

    from nestor import frank
    from nestor.frank import WillowForwarder

    silent = [sys.executable, "-c", "import sys\nfor line in sys.stdin: pass"]
    forwarder = WillowForwarder(command=silent, timeout=1.0)
    frank.set_forwarder(forwarder)
    try:
        started = time.monotonic()
        cascade.ledger_append({"kind": "seal", "verifier": "rita"})
        elapsed = time.monotonic() - started
    finally:
        frank.set_forwarder(None)
        forwarder.close()

    assert elapsed < 10, f"the seal waited {elapsed:.1f}s on a mirror that never answered"
    ok, detail = verify(str(signed / "ledger.jsonl"))
    assert ok, detail
    assert len(cascade._ledger_path().read_text().splitlines()) == 1, \
        "the local entry is written regardless — it is the source of truth"


def test_an_append_waits_for_a_torn_line_instead_of_reading_it(signed):
    """The one that turned master red, pinned deterministically.

    The chain walk used to run *outside* the file lock, so the first append in a
    process could read the file while another process was mid-write, see a line
    without its newline, and refuse a perfectly good seal. It failed exactly
    once per process — the walk is cached — which is why one of three writers
    died and two sailed through.

    Here a helper holds the lock with a torn line on disk, then restores the
    file before releasing. An appender that respects the lock sees only the
    consistent state; one that does not sees `{"kind": "part` and raises.
    """
    ledger = signed / "ledger.jsonl"
    cascade.ledger_append({"kind": "passage", "i": 0})
    cascade._verified_ledgers.clear()          # force this process to walk it

    holder = (
        "import fcntl, os, sys, time\n"
        "path = sys.argv[1]\n"
        "size = os.path.getsize(path)\n"
        "f = open(path, 'a+', encoding='utf-8')\n"
        "fcntl.flock(f.fileno(), fcntl.LOCK_EX)\n"
        "f.write('{\"kind\": \"part')\n"    # a line with no newline yet
        "f.flush()\n"
        "print('held', flush=True)\n"
        "time.sleep(2)\n"
        "f.truncate(size)\n"                    # the write completes or unwinds
        "f.flush()\n"
        "fcntl.flock(f.fileno(), fcntl.LOCK_UN)\n"
    )
    proc = subprocess.Popen([sys.executable, "-c", holder, str(ledger)],
                            stdout=subprocess.PIPE, text=True)
    try:
        assert proc.stdout.readline().strip() == "held", "helper never took the lock"
        cascade.ledger_append({"kind": "passage", "i": 1})   # blocks, then succeeds
    finally:
        proc.wait(timeout=30)

    ok, detail = verify(str(ledger))
    assert ok, detail
    assert len(ledger.read_text().splitlines()) == 2
