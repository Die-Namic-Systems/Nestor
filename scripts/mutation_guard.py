#!/usr/bin/env python3
"""Prove Nestor's refusal guards can fail — mutation testing, curated.

    python scripts/mutation_guard.py           # run every mutation, report
    python scripts/mutation_guard.py --list    # show the set, run nothing

**The rule this enforces.** *A guard that cannot be shown to fail has not been
shown to work.* Nestor's ``testing`` discipline says every invariant needs a test
that performs the forbidden act and asserts refusal — but a refusal test only
proves the guard if it goes **red when the guard is removed**. A test that passes
whether or not the guard is there asserts nothing. This harness breaks each guard
on purpose and checks that its test notices.

**How.** For each mutation: copy the tree to a temp dir, disable one guard with a
single exact substitution, run *only* the test that should catch it, and assert
that test **fails**. A mutation whose test still passes ("survived") is a guard
the suite does not actually verify — the harness exits non-zero and names it. A
substitution whose ``old`` text is no longer in the file ("stale") also fails,
because a mutation that cannot be applied is silently checking nothing — the
false-green this whole exercise exists to refuse.

**Curated, not blanket.** This is not ``mutmut`` sweeping every operator. It is a
hand-written set of the mutations that matter — the security and covenant guards
— each paired with the exact test that is its reason to exist. The idea is Trail
of Bits' ``mutation-testing`` skill; the implementation is Nestor's own,
stdlib-only, owing their CC-BY-SA text nothing.
"""
from __future__ import annotations

import argparse
import dataclasses
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: Dirs/patterns not worth copying into the throwaway tree (huge or derived).
_IGNORE = shutil.ignore_patterns(
    ".git", ".venv", "__pycache__", "*.pyc", ".pytest_cache", ".ruff_cache",
    ".mypy_cache", "node_modules", ".worktrees")


@dataclasses.dataclass(frozen=True)
class Mutation:
    """One guard, the single edit that disables it, and the test that must then
    fail. ``old`` must occur **exactly once** in ``file`` — a unique anchor, so
    the break is surgical and a drift in the source surfaces as 'stale' rather
    than mutating the wrong line."""
    name: str
    file: str
    old: str
    new: str
    test: str
    why: str


#: The guards whose failure would be a security or covenant breach. Each pairs a
#: one-line disable with the test that is that guard's reason to exist.
MUTATIONS: tuple[Mutation, ...] = (
    Mutation(
        name="mcp-gate-allows-fleet",
        file="hooks/before_mcp.py",
        old="return False, _USER_MESSAGE, _AGENT_MESSAGE",
        new="return True, _USER_MESSAGE, _AGENT_MESSAGE",
        test="tests/test_hooks.py::test_claude_mcp_tool_name_is_blocked",
        why="the seat gate must deny willow-mcp / nestor-as-MCP",
    ),
    Mutation(
        name="write-gate-allows-ungated",
        file="hooks/before_write.py",
        old="return False, user, agent",
        new="return True, user, agent",
        test="tests/test_before_write_gate.py::test_gated_code_is_denied_without_a_consultation",
        why="a gated write with no review receipt must be blocked",
    ),
    Mutation(
        name="seal-accepts-forgery",
        file="nestor/signing.py",
        old="return any(_verifies_with(kind, k, message, seal_sig) for kind, k in refs)",
        new="return True",
        test="tests/test_client_signed_seals.py::TestInvalidProvidedSignatureRefusesAndWritesNothing"
             "::test_forged_signature_refused_no_row",
        why="a forged seal signature must be refused (Nestor#2)",
    ),
    Mutation(
        name="edge-accepts-forgery",
        file="nestor/signing.py",
        old="return any(_verifies_with(k, kb, message, edge_sig) for k, kb in refs)",
        new="return True",
        test="tests/test_decision_edges.py::test_a_seal_signature_cannot_be_replayed_as_an_edge",
        why="an unbacked decision-edge signature must not constrain (the covenant)",
    ),
)


@dataclasses.dataclass
class Result:
    mutation: Mutation
    verdict: str   # "killed" | "survived" | "stale"
    detail: str = ""


def _apply(tree: pathlib.Path, m: Mutation) -> tuple[bool, str]:
    """Apply one mutation in ``tree``. Returns (applied, restore_text). Refuses
    unless ``old`` occurs exactly once — an ambiguous or missing anchor is a
    stale mutation, not a silent no-op."""
    path = tree / m.file
    text = path.read_text(encoding="utf-8")
    count = text.count(m.old)
    if count != 1:
        return False, (f"anchor found {count} times, need exactly 1 "
                       f"(source moved — update the mutation)")
    path.write_text(text.replace(m.old, m.new), encoding="utf-8")
    return True, text


def _run_test(tree: pathlib.Path, test: str) -> int:
    """Run one test node in the mutated tree. Return pytest's exit code."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", test, "-q", "-x", "--no-header",
         "-p", "no:cacheprovider", "-o", "addopts="],
        cwd=str(tree), capture_output=True, text=True)
    return proc.returncode


def run(mutations: tuple[Mutation, ...] = MUTATIONS) -> list[Result]:
    """Copy the tree once, then break-test-restore each guard in it. The real
    working tree is never touched."""
    results: list[Result] = []
    with tempfile.TemporaryDirectory() as tmp:
        tree = pathlib.Path(tmp) / "nestor-tree"
        shutil.copytree(ROOT, tree, ignore=_IGNORE)
        for m in mutations:
            applied, restore = _apply(tree, m)
            if not applied:
                results.append(Result(m, "stale", restore))
                continue
            try:
                rc = _run_test(tree, m.test)
            finally:
                (tree / m.file).write_text(restore, encoding="utf-8")
            # rc != 0 -> the catcher test FAILED with the guard broken = killed.
            # rc == 0 -> it passed anyway = the guard is unverified = survived.
            results.append(Result(m, "killed" if rc != 0 else "survived",
                                  "" if rc != 0 else "test passed with the guard disabled"))
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--list", action="store_true",
                    help="print the mutation set and exit without running")
    args = ap.parse_args()

    if args.list:
        for m in MUTATIONS:
            print(f"{m.name:26} {m.file}  ->  {m.test.split('::')[-1]}")
            print(f"{'':26} why: {m.why}")
        return 0

    results = run()
    killed = [r for r in results if r.verdict == "killed"]
    bad = [r for r in results if r.verdict != "killed"]
    for r in results:
        mark = {"killed": "✓ killed ", "survived": "✗ SURVIVED", "stale": "✗ STALE  "}[r.verdict]
        print(f"{mark} {r.mutation.name}"
              + (f" — {r.detail}" if r.detail else ""))
    print(f"\n{len(killed)}/{len(results)} guards proven "
          f"(each refusal test goes red when its guard is broken).")
    if bad:
        print(f"{len(bad)} unverified — a guard nothing catches is a ledger, not "
              f"a gate. Fix the guard's test, or correct a stale mutation.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
