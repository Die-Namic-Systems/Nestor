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
