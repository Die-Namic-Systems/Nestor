#!/usr/bin/env python3
"""Prove every wired gate actually denies — end to end, on the wire.

    python scripts/hook_guard.py            # drive each gate, report, exit 1 on a miss

Each gate has a unit test. This proves the next thing up: that the *wiring* holds
— that a forbidden event, fed through the real ``hooks/nestor-hook`` the way
Claude Code feeds it, comes back as a deny in the spelling the harness honors, and
a benign one comes back allow. It is the mutation guard's sibling for the hooks:
a guard that cannot be shown to fail has not been shown to work, so here we make
each guard fail (feed it the forbidden act) and check the block lands.

**The coverage pin.** The set of blocking gates is derived from
``hook_runner.MODULES`` (minus the non-gates that only inject context). A gate in
that set with no deny case here fails the run — a newly-wired gate cannot ship
without a proof-it-denies case, the way ``mcp_federation`` once shipped in
willow-mcp's gate with no guard behind it.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from hooks.hook_runner import MODULES  # noqa: E402

#: Modules that only inject context or clean up, never block — excluded from the
#: deny pin.
_NON_GATES = frozenset({"session_start", "session_end", "reinject"})
#: Every gate the pin requires a deny/flag case for.
BLOCKING = tuple(m for m in MODULES if m not in _NON_GATES)


@dataclasses.dataclass(frozen=True)
class Case:
    name: str
    module: str
    payload: dict
    expect: str   # "deny" | "allow" | "flag"


CASES: tuple[Case, ...] = (
    Case("mcp-fleet-blocked", "before_mcp",
         {"tool_name": "mcp__willow-mcp__store_get", "tool_input": {}}, "deny"),
    Case("mcp-codebase-allowed", "before_mcp",
         {"tool_name": "mcp__codebase-memory-mcp__search_graph", "tool_input": {}}, "allow"),
    Case("write-gated-py-blocked", "before_write",
         {"tool_name": "Write", "tool_input": {"file_path": "tests/x.py", "content": "x=1"}}, "deny"),
    Case("write-prose-allowed", "before_write",
         {"tool_name": "Write", "tool_input": {"file_path": "README.md", "content": "hi"}}, "allow"),
    Case("bash-rm-rf-blocked", "before_bash",
         {"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}}, "deny"),
    Case("bash-pytest-allowed", "before_bash",
         {"tool_name": "Bash", "tool_input": {"command": "pytest -q"}}, "allow"),
    Case("authority-keys-add-blocked", "before_authority",
         {"tool_name": "Bash", "tool_input": {"command": "nestor keys add rita"}}, "deny"),
    Case("authority-keys-list-allowed", "before_authority",
         {"tool_name": "Bash", "tool_input": {"command": "nestor keys list"}}, "allow"),
    Case("stop-claim-no-evidence-flagged", "before_stop",
         {"last_message": "All tests pass, done."}, "deny"),
    Case("stop-claim-with-evidence-allowed", "before_stop",
         {"last_message": "Fixed it: `pytest -q` -> 1011 passed."}, "allow"),
)


def _run(module: str, payload: dict) -> dict:
    """Drive the real wrapper, exactly as Claude Code would."""
    done = subprocess.run(
        [str(REPO / "hooks" / "nestor-hook"), "claude", module],
        input=json.dumps(payload), capture_output=True, text=True,
        cwd=str(REPO), timeout=60,
        env={"NESTOR_PROJECT_ROOT": str(REPO), "PATH": _path()})
    if done.returncode != 0:
        raise RuntimeError(f"{module}: hook exited {done.returncode}: {done.stderr}")
    return json.loads(done.stdout)


def _path() -> str:
    import os
    return os.environ.get("PATH", "/usr/bin:/bin")


def classify(out: dict) -> str:
    """What the emitted envelope actually decided."""
    hso = out.get("hookSpecificOutput") or {}
    if out.get("decision") == "block" or hso.get("permissionDecision") == "deny" \
            or out.get("permission") == "deny":
        return "deny"
    if hso.get("additionalContext") or out.get("additional_context"):
        return "flag"          # advisory reminder (the Stop soft path)
    return "allow"


def run(cases: tuple[Case, ...] = CASES) -> list[tuple[Case, str, bool]]:
    out = []
    for c in cases:
        got = classify(_run(c.module, c.payload))
        # a deny case is satisfied by a block; a flag case by either flag or deny.
        ok = got == c.expect or (c.expect == "flag" and got == "deny")
        out.append((c, got, ok))
    return out


def _coverage_gaps(cases: tuple[Case, ...] = CASES) -> list[str]:
    covered = {c.module for c in cases if c.expect in ("deny", "flag")}
    return [m for m in BLOCKING if m not in covered]


def main() -> int:
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args()
    results = run()
    for c, got, ok in results:
        print(f"{'✓' if ok else '✗'} {c.module:16} {c.name:32} expect {c.expect}, got {got}")
    gaps = _coverage_gaps()
    bad = [r for r in results if not r[2]]
    if gaps:
        print(f"\n✗ blocking gates with no deny case: {gaps}")
    if bad or gaps:
        print(f"\n{len(bad)} wiring mismatch(es), {len(gaps)} uncovered gate(s) — "
              f"a gate that cannot be shown to deny has not been shown to work.")
        return 1
    print(f"\n{len(results)} cases, all {len(BLOCKING)} blocking gates proven on the wire.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
