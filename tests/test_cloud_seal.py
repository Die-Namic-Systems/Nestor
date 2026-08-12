"""Tests for nestor.cloud_seal — the optional cloud-path seam.

Skips entirely if willow-gate is absent (the module fail-closes on import, which
IS the "no gate at this end → no cloud path" rule). With the gate present, this
re-proves what the box-proof showed: an agent seals provisionally, under its own
identity, bound to an authenticated gate crossing, rung-capped, export-gated,
never canonical.
"""
import json
import os

import pytest

pytest.importorskip("willow_gate")
from willow_gate import GateError, WillowGate
from willow_gate.custody import CustodyLedger, file_lineage

from nestor.cloud_seal import (
    ProvisionalSealResult,
    content_fingerprint,
    seal_through_gate,
)

AGENT = "agent:test"
ITEMS = [
    ("dec-1", "the engine holds the venv and Kart"),
    ("dec-2", "the app-builder is a forge-app, not the engine"),
    ("dec-3", "verified_by must be a real human"),
]


def _gate(tmp_path, max_trust=2):
    g = WillowGate(base_dir=str(tmp_path / "gate"), require_pgp=False)
    secret = os.urandom(32)
    g.register_agent(AGENT, secret, max_trust=max_trust)
    return g, secret


def test_bound_provisional_seal_happy_path(tmp_path):
    g, secret = _gate(tmp_path)
    cust = CustodyLedger(path=str(tmp_path / "custody.jsonl"))
    res = seal_through_gate(g, AGENT, secret, ITEMS, custody=cust)
    assert isinstance(res, ProvisionalSealResult)
    assert res.sealed == ["dec-1", "dec-2", "dec-3"]
    assert res.custody_verifies is True
    assert res.session_id
    assert res.actor == AGENT


def test_a_provisional_seal_is_never_canonical(tmp_path):
    g, secret = _gate(tmp_path)
    res = seal_through_gate(g, AGENT, secret, ITEMS, custody=CustodyLedger())
    assert res.canonical is False  # canonical is the home end's checkpoint(), not this tier


def test_seals_carry_the_authenticated_session_id(tmp_path):
    g, secret = _gate(tmp_path)
    p = tmp_path / "custody.jsonl"
    res = seal_through_gate(g, AGENT, secret, ITEMS, custody=CustodyLedger(path=str(p)))
    creates = [json.loads(ln) for ln in p.read_text().splitlines()
               if json.loads(ln).get("kind") == "file.create"]
    assert len(creates) == 3
    assert all(e["session_id"] == res.session_id for e in creates)  # bound to the crossing
    assert all(e["actor"] == AGENT for e in creates)                # under the agent's identity


def test_export_is_gated_at_rookie(tmp_path):
    g, secret = _gate(tmp_path)
    res = seal_through_gate(g, AGENT, secret, ITEMS, custody=CustodyLedger())
    # a fresh agent is Rookie: it may seal, but export must be EARNED (Steady+)
    assert res.export_allowed is False
    assert res.writable is False


def test_overclaimed_rung_is_refused_and_nothing_is_sealed(tmp_path):
    g, secret = _gate(tmp_path)
    cust = CustodyLedger()
    with pytest.raises(GateError):
        seal_through_gate(g, AGENT, secret, ITEMS, custody=cust,
                          trust_level=2, tools=("read", "write"))
    # the crossing was refused before any seal happened
    assert file_lineage(cust, "dec-1") == []  # nothing was sealed


def test_wrong_secret_is_rejected(tmp_path):
    g, _secret = _gate(tmp_path)
    cust = CustodyLedger()
    with pytest.raises(GateError):
        seal_through_gate(g, AGENT, os.urandom(32), ITEMS, custody=cust)
    assert file_lineage(cust, "dec-1") == []  # nothing was sealed


def test_content_fingerprint_is_stable_sha256():
    fp = content_fingerprint("x")
    assert fp.startswith("sha256:") and len(fp) == len("sha256:") + 64
    assert content_fingerprint("x") == fp
    assert content_fingerprint("y") != fp
