"""The gate-proving harness is a guard too, so it gets the same proof.

`scripts/hook_guard.py` drives every wired gate through the real hook and asserts
the deny lands. These tests assert it passes on the live wiring, that its coverage
pin has no gap (every blocking gate has a deny case), and that it actually reports
a mismatch when a case's expectation is wrong — a harness that always said "pass"
would gate nothing.
"""
from __future__ import annotations

import dataclasses
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import hook_guard  # noqa: E402  (scripts/ is not an installed package)


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


def test_the_harness_reports_a_wiring_mismatch():
    """The can-fail proof. A deny case mislabeled 'allow' must be reported wrong,
    not passed — otherwise the harness proves nothing."""
    mislabeled = dataclasses.replace(
        hook_guard.Case("mcp-fleet-blocked", "before_mcp",
                        {"tool_name": "mcp__willow-mcp__store_get", "tool_input": {}}, "deny"),
        expect="allow")
    (_case, got, ok), = hook_guard.run((mislabeled,))
    assert got == "deny" and ok is False
