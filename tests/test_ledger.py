"""Ledger verification + fail-closed audit (Nestor#2, RT-N2/RT-N3)."""
import json
import threading

import pytest

from nestor import cascade, ledger


def test_verify_intact_then_detects_tamper(tmp_path):
    lp = tmp_path / "ledger.jsonl"
    cascade.set_ledger_path(lp)
    for k in ("seal", "passage", "restore"):
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


def test_ledger_refuses_non_file(tmp_path):
    """Exists and is not a regular file: a directory, on every platform.
    `/dev/null` was the example; on Windows that is a relative path that
    does not exist, the refusal never fires, and the append would have
    created `\\dev\\null` on the current drive."""
    cascade.set_ledger_path(tmp_path)
    with pytest.raises(ledger.LedgerError, match="not a regular file"):
        cascade._ledger_append({"kind": "seal"})


def test_append_refuses_to_extend_a_tampered_chain(tmp_path):
    lp = tmp_path / "ledger.jsonl"
    cascade.set_ledger_path(lp)
    for k in ("seal", "passage", "restore"):
        cascade._ledger_append({"kind": k})

    lines = lp.read_text().splitlines()
    rec = json.loads(lines[0]); rec["kind"] = "TAMPERED"
    lines[0] = json.dumps(rec, ensure_ascii=False)
    lp.write_text("\n".join(lines) + "\n")

    cascade.reset_ledger_session()
    with pytest.raises(ledger.LedgerError):
        cascade._ledger_append({"kind": "passage"})


@pytest.fixture
def live_ledger(tmp_path):
    """A ledger this process has already verified and appended to."""
    lp = tmp_path / "ledger.jsonl"
    cascade.set_ledger_path(lp)
    # First kind chosen same-length as its tamper replacement below
    # (restore -> passage, 7 bytes each): the tail checkpoint stores a byte
    # offset, so an edit that changed line length would trip the offset
    # guard instead of the chain walk this test exists to prove.
    for k in ("restore", "passage", "seal"):
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
        cascade._ledger_append({"kind": "passage"})


def test_truncating_the_trail_mid_run_is_refused(live_ledger):
    live_ledger.write_text(live_ledger.read_text().splitlines()[0] + "\n")
    with pytest.raises(ledger.LedgerError, match="truncated"):
        cascade._ledger_append({"kind": "passage"})


def test_deleting_the_ledger_mid_run_is_refused(live_ledger):
    live_ledger.unlink()
    with pytest.raises(ledger.LedgerError, match="is gone"):
        cascade._ledger_append({"kind": "passage"})


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


def _checkpoint_facts(raw: bytes, offset: int) -> dict:
    """What the file's bytes say about a checkpoint: whether the offset
    starts on a line boundary, the line it names, and whether a carriage
    return is anywhere in the file — the platform newline the offset
    arithmetic cannot count. The two tests below read the real ledger and
    ask this; the second plants the Windows write and asks it again."""
    return {
        "on_boundary": offset == 0 or raw[offset - 1:offset] == b"\n",
        "line": raw[offset:].split(b"\n", 1)[0].decode("utf-8"),
        "has_cr": b"\r" in raw,
    }


def test_the_checkpoint_offset_is_where_the_lines_bytes_begin(live_ledger):
    """The checkpoint is a byte offset: file size after the write, minus the
    line's UTF-8 length, minus one newline. That arithmetic is only true when
    the newline on disk is one byte. Opened with the platform default, text
    mode on Windows wrote "\\r\\n", the offset landed one byte into the line,
    and the very next append in the same process refused its own tail as
    tampered (PR #297's Windows leg: 413 such refusals). The ledger is now
    written with newline="\\n" on every platform; this holds the offset to
    the bytes it names, and the file to one-byte newlines, which is the
    bytes-appended-only assumption _check_tail states."""
    offset, digest = cascade._checkpoints[str(live_ledger)]
    facts = _checkpoint_facts(live_ledger.read_bytes(), offset)
    assert facts["on_boundary"], "the checkpoint does not start on a line boundary"
    assert cascade._line_sha(facts["line"]) == digest
    assert facts["has_cr"] is False, "the ledger is written with one-byte newlines everywhere"


def test_a_line_appended_with_windows_newlines_is_planted_and_still_chained(live_ledger):
    """Planted: the write the platform default made on Windows, on any
    platform. newline="\\r\\n" is exactly the translation text mode applies
    there, so this is a line an older build (or a foreign writer on Windows)
    left in the file: two bytes of newline where the arithmetic counted one.
    The chain has to survive it in both directions — the walk (`verify`)
    reads it as one entry, and this process's next append chains onto it and
    checkpoints byte-exact — and the bytes this process writes stay one-byte
    newlines regardless of what came before."""
    import hashlib
    last = live_ledger.read_text(encoding="utf-8").splitlines()[-1]
    foreign = json.dumps({"kind": "passage", "prev":
                          hashlib.sha256(last.encode("utf-8")).hexdigest()},
                         ensure_ascii=False)
    with live_ledger.open("a", encoding="utf-8", newline="\r\n") as fh:
        fh.write(foreign + "\n")
    raw = live_ledger.read_bytes()
    assert raw.endswith(foreign.encode("utf-8") + b"\r\n"), "the plant did not land"

    cascade._ledger_append({"kind": "passage"})
    ok, detail = ledger.verify(str(live_ledger))
    assert ok, detail

    raw = live_ledger.read_bytes()
    offset, digest = cascade._checkpoints[str(live_ledger)]
    facts = _checkpoint_facts(raw, offset)
    assert facts["on_boundary"] and facts["has_cr"] is True   # the plant is in the file
    assert cascade._line_sha(facts["line"]) == digest
    assert raw.count(b"\r") == 1, "our append wrote a one-byte newline after the plant"
    assert json.loads(facts["line"])["prev"] == cascade._line_sha(foreign)
    cascade._ledger_append({"kind": "restore"})       # the tail guard still lets us on


def test_another_writer_appending_is_not_tampering(live_ledger):
    import hashlib

    last = live_ledger.read_text().splitlines()[-1]
    line = json.dumps({"kind": "passage", "prev":
                       hashlib.sha256(last.encode()).hexdigest()}, ensure_ascii=False)
    with live_ledger.open("a") as fh:
        fh.write(line + "\n")

    cascade._ledger_append({"kind": "passage"})
    assert ledger.verify(str(live_ledger))[0]

    with live_ledger.open("a") as fh:
        fh.write(json.dumps({"kind": "proposal", "prev": "genesis"}) + "\n")
    with pytest.raises(ledger.LedgerError, match="does not chain"):
        cascade._ledger_append({"kind": "restore"})


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
        cascade._ledger_append({"kind": "passage"})


def test_pointing_at_another_ledger_does_drop_it(live_ledger, tmp_path):
    """The other half: a different chain must not inherit this one's checkpoint,
    or the first append would check one file's tail against another's."""
    other = tmp_path / "other.jsonl"
    cascade.set_ledger_path(other)
    cascade._ledger_append({"kind": "seal"})
    assert ledger.verify(str(other))[0]
    assert len(other.read_text().splitlines()) == 1


def test_the_checkpoint_does_not_replace_the_walk(live_ledger):
    lines = live_ledger.read_text().splitlines()
    assert '"kind": "restore"' in lines[0]
    lines[0] = lines[0].replace('"kind": "restore"', '"kind": "passage"')
    live_ledger.write_text("\n".join(lines) + "\n")

    cascade._ledger_append({"kind": "passage"})
    ok, detail = ledger.verify(str(live_ledger))
    assert not ok and "broken chain" in detail


def test_ledger_refuses_a_symlink(tmp_path):
    real = tmp_path / "attacker.jsonl"
    real.write_text("")
    link = tmp_path / "ledger.jsonl"
    link.symlink_to(real)
    cascade.set_ledger_path(link)
    with pytest.raises(ledger.LedgerError):
        cascade._ledger_append({"kind": "seal"})
