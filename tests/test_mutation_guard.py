"""The mutation guard is itself a guard — so it needs the same proof.

`scripts/mutation_guard.py` breaks each security/covenant guard and asserts its
test goes red. These tests assert (1) all shipped mutations are killed, and (2)
the harness fails loud on the two ways it could silently check nothing — a guard
whose test passes with it broken ("survived"), and a mutation whose anchor no
longer exists ("stale"). A mutation harness that could not itself report a miss
would be exactly the false-green it exists to catch.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import mutation_guard


def test_all_shipped_guards_are_proven():
    """The real gate: every curated guard's refusal test fails when the guard is
    broken. Run through the script end-to-end, the way CI would."""
    done = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "mutation_guard.py")],
        capture_output=True, text=True, cwd=REPO, timeout=300, check=False)
    assert done.returncode == 0, f"a guard survived or went stale:\n{done.stdout}\n{done.stderr}"
    assert f"{len(mutation_guard.MUTATIONS)}/{len(mutation_guard.MUTATIONS)} guards proven" in done.stdout


def test_list_mode_names_every_mutation_and_runs_nothing():
    done = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "mutation_guard.py"), "--list"],
        capture_output=True, text=True, cwd=REPO, timeout=30, check=False)
    assert done.returncode == 0
    for m in mutation_guard.MUTATIONS:
        assert m.name in done.stdout


def test_the_harness_reports_a_survivor_and_a_stale_mutation():
    """The self-check. One mutation that breaks nothing a behavior test sees
    (a message-only edit under a behavior test) must be reported 'survived'; one
    whose anchor is gone must be reported 'stale'. Both are failures — a harness
    that called these 'killed' would be the false-green it exists to refuse.
    Both run in a single tree copy for speed."""
    survivor = mutation_guard.Mutation(
        name="message-only-change-no-behavior",
        file="hooks/before_mcp.py",
        # The deny MESSAGE, not the deny DECISION — a behavior test cannot see it.
        old="Edit the repo locally",
        new="Edit the repo locally now",
        test="tests/test_hooks.py::test_claude_mcp_tool_name_is_blocked",
        why="demonstrates a guard whose test does not actually cover it",
    )
    stale = mutation_guard.Mutation(
        name="anchor-that-no-longer-exists",
        file="nestor/signing.py",
        old="a phrase that does not occur anywhere in signing dot py 987654",
        new="unused",
        test="tests/test_hooks.py::test_codebase_memory_is_allowed",
        why="demonstrates a mutation that cannot be applied",
    )
    results = mutation_guard.run((survivor, stale))
    verdicts = {r.mutation.name: r.verdict for r in results}
    assert verdicts["message-only-change-no-behavior"] == "survived", verdicts
    assert verdicts["anchor-that-no-longer-exists"] == "stale", verdicts
