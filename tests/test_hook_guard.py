"""The gate-proving harness is a guard too, so it gets the same proof.

`scripts/hook_guard.py` drives every wired gate through the real hook and asserts
the deny lands. These tests assert it passes on the live wiring, that its coverage
pin has no gap (every blocking gate has a deny case), and that it actually reports
a mismatch when a case's expectation is wrong — a harness that always said "pass"
would gate nothing.
"""
from __future__ import annotations

import dataclasses
import os
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import hook_guard  # noqa: E402  (scripts/ is not an installed package)
from hooks import review_receipt  # noqa: E402


def test_every_wired_gate_denies_on_the_wire():
    """End to end through the script, the way CI would."""
    done = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "hook_guard.py")],
        capture_output=True, text=True, cwd=REPO, timeout=180)
    assert done.returncode == 0, f"a gate did not deny:\n{done.stdout}\n{done.stderr}"
    assert f"all {len(hook_guard.BLOCKING)} blocking gates proven" in done.stdout


def test_the_coverage_pin_has_no_gap():
    """Every blocking module in hook_runner.MODULES has a deny/flag case."""
    assert hook_guard._coverage_gaps() == [], "a blocking gate has no deny case"


def test_a_new_blocking_gate_without_a_case_is_a_gap():
    """The pin's teeth: pretend a gate was wired but left uncovered."""
    gaps = hook_guard._coverage_gaps(
        tuple(c for c in hook_guard.CASES if c.module != "before_bash"))
    assert "before_bash" in gaps


@pytest.mark.parametrize("ambient", ["absent", "fresh"])
def test_the_guard_ignores_whatever_receipt_the_developer_holds(tmp_path, ambient):
    """The regression: this harness must prove the gate, not the machine.

    ``before_write`` denies only while the review desk has not been consulted,
    and the receipt clearing it lives outside the tree with a half-hour TTL. The
    harness inherited it, so the write-deny case reported `expect deny, got
    allow` for any developer who had consulted the desk recently — which the gate
    *requires* before editing gated code. Following one command the seat names
    (consult the desk) broke another (`python -m pytest -q`) for thirty minutes,
    on a clean tree, with no diff to blame. Both ambient states must now be
    green."""
    receipt = tmp_path / "ambient.json"
    if ambient == "fresh":
        env = {**os.environ, review_receipt._ENV_PATH: str(receipt)}
        subprocess.run(
            [sys.executable, "-c",
             "from hooks.review_receipt import record; record('.', 'ambient')"],
            cwd=REPO, env=env, check=True, timeout=60)
        assert receipt.exists(), "the fixture did not record a receipt"
    done = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "hook_guard.py")],
        capture_output=True, text=True, cwd=REPO, timeout=180,
        env={**os.environ, review_receipt._ENV_PATH: str(receipt)})
    assert done.returncode == 0, (
        f"a {ambient} ambient receipt changed the verdict:\n{done.stdout}\n{done.stderr}")


def test_the_gate_is_proven_to_open_as_well_as_shut():
    """Both directions of before_write are pinned. A gate proven only to deny
    could have been wired shut permanently and nothing here would notice."""
    write = {c.name: c for c in hook_guard.CASES if c.module == "before_write"}
    opens = [c for c in write.values() if c.receipt == "fresh"]
    assert opens and all(c.expect == "allow" for c in opens), (
        "no case proves a consultation clears the write gate")
    assert any(c.expect == "deny" and c.receipt == "absent" for c in write.values())


def test_the_harness_reports_a_wiring_mismatch():
    """The can-fail proof. A deny case mislabeled 'allow' must be reported wrong,
    not passed — otherwise the harness proves nothing."""
    mislabeled = dataclasses.replace(
        hook_guard.Case("mcp-fleet-blocked", "before_mcp",
                        {"tool_name": "mcp__willow-mcp__store_get", "tool_input": {}}, "deny"),
        expect="allow")
    (_case, got, ok), = hook_guard.run((mislabeled,))
    assert got == "deny" and ok is False
