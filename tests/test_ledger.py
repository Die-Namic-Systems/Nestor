"""Ledger verification + fail-closed audit (Nestor#2, RT-N2/RT-N3)."""
import json
import threading

import pytest

from nestor import cascade, ledger


def test_verify_intact_then_detects_tamper(tmp_path):
    lp = tmp_path / "ledger.jsonl"
    cascade.set_ledger_path(lp)
    for k in ("a", "b", "c"):
        cascade._ledger_append({"kind": k})

    ok, detail = ledger.verify(str(lp))
    assert ok, detail

    lines = lp.read_text().splitlines()
    rec = json.loads(lines[0]); rec["kind"] = "TAMPERED"
    lines[0] = json.dumps(rec, ensure_ascii=False)
    lp.write_text("\n".join(lines) + "\n")

    ok, detail = ledger.verify(str(lp))
    assert not ok
    assert "broken chain" in detail


def test_ledger_refuses_non_file():
    cascade.set_ledger_path("/dev/null")
    with pytest.raises(ledger.LedgerError):
        cascade._ledger_append({"kind": "vanishes"})


def test_append_refuses_to_extend_a_tampered_chain(tmp_path):
    lp = tmp_path / "ledger.jsonl"
    cascade.set_ledger_path(lp)
    for k in ("a", "b", "c"):
        cascade._ledger_append({"kind": k})

    lines = lp.read_text().splitlines()
    rec = json.loads(lines[0]); rec["kind"] = "TAMPERED"
    lines[0] = json.dumps(rec, ensure_ascii=False)
    lp.write_text("\n".join(lines) + "\n")

    cascade.reset_ledger_session()
    with pytest.raises(ledger.LedgerError):
        cascade._ledger_append({"kind": "d"})


@pytest.fixture
def live_ledger(tmp_path):
    """A ledger this process has already verified and appended to."""
    lp = tmp_path / "ledger.jsonl"
    cascade.set_ledger_path(lp)
    for k in ("a", "b", "c"):
        cascade._ledger_append({"kind": k})
    assert ledger.verify(str(lp))[0]
    return lp


def test_a_mid_run_edit_of_the_newest_entry_is_refused(live_ledger):
    lines = live_ledger.read_text().splitlines()
    rec = json.loads(lines[-1]); rec["kind"] = "TAMPERED"
    lines[-1] = json.dumps(rec, ensure_ascii=False)
    live_ledger.write_text("\n".join(lines) + "\n")

    ok, _ = ledger.verify(str(live_ledger))
    assert ok, "the whole point: the walk cannot see this"

    with pytest.raises(ledger.LedgerError, match="tampered tail"):
        cascade._ledger_append({"kind": "d"})


def test_truncating_the_trail_mid_run_is_refused(live_ledger):
    live_ledger.write_text(live_ledger.read_text().splitlines()[0] + "\n")
    with pytest.raises(ledger.LedgerError, match="truncated"):
        cascade._ledger_append({"kind": "d"})


def test_deleting_the_ledger_mid_run_is_refused(live_ledger):
    live_ledger.unlink()
    with pytest.raises(ledger.LedgerError, match="is gone"):
        cascade._ledger_append({"kind": "d"})


def test_the_refusal_lands_before_the_store_write(live_ledger, store, seal_key):
    from nestor import memory

    lines = live_ledger.read_text().splitlines()
    rec = json.loads(lines[-1]); rec["kind"] = "TAMPERED"
    lines[-1] = json.dumps(rec, ensure_ascii=False)
    live_ledger.write_text("\n".join(lines) + "\n")

    with pytest.raises(ledger.LedgerError):
        memory.add_pair("the invoice is overdue", "la factura está vencida",
                        "en", "es", status="sealed", verifier="rita", store=store)
    assert memory.stats(store=store)["total"] == 0, "no sealed row without a trail"


def test_another_writer_appending_is_not_tampering(live_ledger):
    import hashlib

    last = live_ledger.read_text().splitlines()[-1]
    line = json.dumps({"kind": "from-another-process", "prev":
                       hashlib.sha256(last.encode()).hexdigest()}, ensure_ascii=False)
    with live_ledger.open("a") as fh:
        fh.write(line + "\n")

    cascade._ledger_append({"kind": "d"})
    assert ledger.verify(str(live_ledger))[0]

    with live_ledger.open("a") as fh:
        fh.write(json.dumps({"kind": "orphan", "prev": "genesis"}) + "\n")
    with pytest.raises(ledger.LedgerError, match="does not chain"):
        cascade._ledger_append({"kind": "e"})


def test_the_checkpoint_does_not_refuse_concurrent_writers(live_ledger):
    gate = threading.Barrier(6)
    failures = []

    def spam(n):
        gate.wait(timeout=5)
        for i in range(15):
            try:
                cascade.ledger_preflight()
                cascade._ledger_append({"kind": "passage", "who": n, "i": i})
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{type(exc).__name__}: {exc}")

    threads = [threading.Thread(target=spam, args=(n,)) for n in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not failures, failures[:3]
    assert len(live_ledger.read_text().splitlines()) == 93
    assert ledger.verify(str(live_ledger))[0]


def test_re_asserting_the_same_ledger_path_keeps_the_tail_guard(live_ledger):
    """`set_ledger_path` is how a surface says where its ledger is, and a
    long-lived surface is the one most likely to say it more than once. Saying
    it again is not a change of chain, so it must not drop the checkpoint —
    doing that would hand back the tail guard for the rest of the shift, which
    is the window the checkpoint exists to close."""
    cascade.set_ledger_path(live_ledger)          # the same path, said again

    lines = live_ledger.read_text().splitlines()
    rec = json.loads(lines[-1]); rec["kind"] = "TAMPERED"
    lines[-1] = json.dumps(rec, ensure_ascii=False)
    live_ledger.write_text("\n".join(lines) + "\n")

    with pytest.raises(ledger.LedgerError, match="tampered tail"):
        cascade._ledger_append({"kind": "d"})


def test_pointing_at_another_ledger_does_drop_it(live_ledger, tmp_path):
    """The other half: a different chain must not inherit this one's checkpoint,
    or the first append would check one file's tail against another's."""
    other = tmp_path / "other.jsonl"
    cascade.set_ledger_path(other)
    cascade._ledger_append({"kind": "first"})
    assert ledger.verify(str(other))[0]
    assert len(other.read_text().splitlines()) == 1


def test_the_checkpoint_does_not_replace_the_walk(live_ledger):
    lines = live_ledger.read_text().splitlines()
    assert '"kind": "a"' in lines[0]
    lines[0] = lines[0].replace('"kind": "a"', '"kind": "z"')
    live_ledger.write_text("\n".join(lines) + "\n")

    cascade._ledger_append({"kind": "d"})
    ok, detail = ledger.verify(str(live_ledger))
    assert not ok and "broken chain" in detail


def test_ledger_refuses_a_symlink(tmp_path):
    real = tmp_path / "attacker.jsonl"
    real.write_text("")
    link = tmp_path / "ledger.jsonl"
    link.symlink_to(real)
    cascade.set_ledger_path(link)
    with pytest.raises(ledger.LedgerError):
        cascade._ledger_append({"kind": "redirected"})
