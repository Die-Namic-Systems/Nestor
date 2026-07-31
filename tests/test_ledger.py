"""Ledger verification + fail-closed audit (Nestor#2, RT-N2/RT-N3)."""
import json

import pytest

from nestor import cascade, ledger


def test_verify_intact_then_detects_tamper(tmp_path, monkeypatch):
    lp = tmp_path / "ledger.jsonl"
    monkeypatch.setattr(cascade, "_LEDGER_OVERRIDE", None)
    monkeypatch.setenv("NESTOR_LEDGER", str(lp))
    for k in ("a", "b", "c"):
        cascade._ledger_append({"kind": k})

    ok, detail = ledger.verify(str(lp))
    assert ok, detail

    # Edit a past entry — the chain must break at the next line.
    lines = lp.read_text().splitlines()
    rec = json.loads(lines[0]); rec["kind"] = "TAMPERED"
    lines[0] = json.dumps(rec, ensure_ascii=False)
    lp.write_text("\n".join(lines) + "\n")

    ok, detail = ledger.verify(str(lp))
    assert not ok
    assert "broken chain" in detail


def test_ledger_refuses_non_file(monkeypatch):
    # NESTOR_LEDGER=/dev/null previously suppressed the audit trail silently.
    monkeypatch.setattr(cascade, "_LEDGER_OVERRIDE", None)
    monkeypatch.setenv("NESTOR_LEDGER", "/dev/null")
    with pytest.raises(ledger.LedgerError):
        cascade._ledger_append({"kind": "vanishes"})


def test_append_refuses_to_extend_a_tampered_chain(tmp_path, monkeypatch):
    # B10: verify() now has a caller — a fresh process refuses to chain onto a
    # ledger whose history was edited while it was down.
    lp = tmp_path / "ledger.jsonl"
    monkeypatch.setattr(cascade, "_LEDGER_OVERRIDE", None)
    monkeypatch.setattr(cascade, "_verified_ledgers", set())
    monkeypatch.setenv("NESTOR_LEDGER", str(lp))
    for k in ("a", "b", "c"):
        cascade._ledger_append({"kind": k})

    lines = lp.read_text().splitlines()
    rec = json.loads(lines[0]); rec["kind"] = "TAMPERED"
    lines[0] = json.dumps(rec, ensure_ascii=False)
    lp.write_text("\n".join(lines) + "\n")

    monkeypatch.setattr(cascade, "_verified_ledgers", set())  # simulate reboot
    with pytest.raises(ledger.LedgerError):
        cascade._ledger_append({"kind": "d"})


# --- the append-time checkpoint (IDEAS 5.3, 5.5) ----------------------------
#
# The chain walk runs once per process. nestor.ui is a long-lived process, so a
# reviewer's shift is hours of appends after a single verification — and
# tampering inside that window used to be caught by the next verify(), not by
# the next append, which meanwhile chained onto it.

@pytest.fixture
def live_ledger(tmp_path, monkeypatch):
    """A ledger this process has already verified and appended to."""
    lp = tmp_path / "ledger.jsonl"
    monkeypatch.setattr(cascade, "_LEDGER_OVERRIDE", None)
    monkeypatch.setattr(cascade, "_verified_ledgers", set())
    monkeypatch.setattr(cascade, "_checkpoints", {})
    monkeypatch.setenv("NESTOR_LEDGER", str(lp))
    for k in ("a", "b", "c"):
        cascade._ledger_append({"kind": k})
    assert ledger.verify(str(lp))[0]
    return lp


def test_a_mid_run_edit_of_the_newest_entry_is_refused(live_ledger):
    """The entry the chain cannot vouch for is the one this catches."""
    lines = live_ledger.read_text().splitlines()
    rec = json.loads(lines[-1]); rec["kind"] = "TAMPERED"
    lines[-1] = json.dumps(rec, ensure_ascii=False)
    live_ledger.write_text("\n".join(lines) + "\n")

    # verify() still walks clean — nothing follows the last line to indict it.
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


def test_the_refusal_lands_before_the_store_write(live_ledger, store):
    """A seal refused *after* its row is written is the state this prevents."""
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
    """A second process extending the chain is normal; only a break is not."""
    import hashlib

    last = live_ledger.read_text().splitlines()[-1]
    line = json.dumps({"kind": "from-another-process", "prev":
                       hashlib.sha256(last.encode()).hexdigest()}, ensure_ascii=False)
    with live_ledger.open("a") as fh:
        fh.write(line + "\n")

    cascade._ledger_append({"kind": "d"})            # accepted
    assert ledger.verify(str(live_ledger))[0]

    # But an entry that does NOT chain onto ours is refused, even though it
    # arrived after our checkpoint.
    with live_ledger.open("a") as fh:
        fh.write(json.dumps({"kind": "orphan", "prev": "genesis"}) + "\n")
    with pytest.raises(ledger.LedgerError, match="does not chain"):
        cascade._ledger_append({"kind": "e"})


def test_the_checkpoint_does_not_replace_the_walk(live_ledger):
    """Stated in the docstring, pinned here: an edit *older* than our checkpoint
    is a job for verify(), and the Ledger view calls it on every render.

    The edit has to preserve byte length to get past the checkpoint at all — a
    rewrite that changes the length shifts every offset after it, our own
    included, and gets refused as a moved tail. That is a side effect of the
    mechanism rather than a guarantee it makes, which is exactly why the walk
    stays the complete answer.
    """
    lines = live_ledger.read_text().splitlines()
    assert '"kind": "a"' in lines[0]
    lines[0] = lines[0].replace('"kind": "a"', '"kind": "z"')
    live_ledger.write_text("\n".join(lines) + "\n")

    cascade._ledger_append({"kind": "d"})            # the checkpoint is silent
    ok, detail = ledger.verify(str(live_ledger))
    assert not ok and "broken chain" in detail       # the walk is not


def test_ledger_refuses_a_symlink(tmp_path, monkeypatch):
    # B14b: is_file() follows symlinks, so ledger.jsonl -> attacker_file passed.
    real = tmp_path / "attacker.jsonl"
    real.write_text("")
    link = tmp_path / "ledger.jsonl"
    link.symlink_to(real)
    monkeypatch.setattr(cascade, "_LEDGER_OVERRIDE", None)
    monkeypatch.setattr(cascade, "_verified_ledgers", set())
    monkeypatch.setenv("NESTOR_LEDGER", str(link))
    with pytest.raises(ledger.LedgerError):
        cascade._ledger_append({"kind": "redirected"})
