#!/usr/bin/env python3
"""Lock in constant-time comparison on the signature-verification path.

    python scripts/constant_time_guard.py           # scan, report, exit 1 on a finding

**Why.** A seal or edge is verified by comparing a computed HMAC to the supplied
signature. If that comparison short-circuits on the first differing byte — the
plain ``==`` operator on strings/bytes does — the time it takes leaks how much of
a forged signature was correct, and an attacker walks the secret out one byte at
a time. ``hmac.compare_digest`` compares in time independent of the content; the
verification path already uses it (``nestor/signing.py``). This guard exists so a
future edit cannot quietly swap it back to ``==`` and reopen the side channel
while every functional test stays green — a timing leak is invisible to a
correctness suite.

**What it flags.** An ``==`` or ``!=`` comparison in the crypto module where an
operand is a signature/MAC/digest — a variable named like one, or a call that
computes one (``.hexdigest()``, ``hmac.new(...)``). It reads the source as an AST,
so it sees the operator, not a substring. Kind/trust/status comparisons
(``entry_kind == "ed25519"``, ``trust == "unsigned"``) are not secrets and are not
flagged — only Name and Call operands are inspected, never string literals.

Curated to the surface that matters, the same shape as ``mutation_guard.py``:
Nestor's own, stdlib-only (``ast``), owing no external CC-BY-SA text.
"""
from __future__ import annotations

import argparse
import ast
import dataclasses
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: The module where seal / edge / rejection / embedding signatures are verified.
#: Only secret-comparison surfaces belong here — a public hash-chain equality
#: (cascade's ledger) is not a timing target and would be a false positive.
SCANNED = ("nestor/signing.py",)

#: Substrings that mark a Name operand as a secret comparand. Matched on the
#: identifier only, so the "sig" in "entry_kind" or the literal "unsigned" never
#: trips it — those are not Name('sig'/'digest'/...).
_SECRET_NAME = ("sig", "signature", "digest", "hexdigest", "hmac", "mac")

#: Calls that COMPUTE a secret/MAC — comparing their result with == is the leak.
_SECRET_CALL = ("hexdigest", "hex", "new")


@dataclasses.dataclass(frozen=True)
class Finding:
    file: str
    line: int
    snippet: str


def _name_is_secret(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        low = node.id.lower()
        return any(tok in low for tok in _SECRET_NAME)
    if isinstance(node, ast.Attribute):
        return any(tok in node.attr.lower() for tok in _SECRET_NAME)
    return False


def _call_is_secret(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    fn = node.func
    if isinstance(fn, ast.Attribute) and fn.attr in _SECRET_CALL:
        return True
    # hmac.new(...) as a bare Name is unusual; the attribute form is what's used.
    return False


def _operand_is_secret(node: ast.AST) -> bool:
    return _name_is_secret(node) or _call_is_secret(node)


def scan_text(text: str, rel: str) -> list[Finding]:
    tree = ast.parse(text, filename=rel)
    lines = text.splitlines()
    out: list[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if not any(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops):
            continue
        operands = [node.left, *node.comparators]
        if any(_operand_is_secret(o) for o in operands):
            ln = node.lineno
            out.append(Finding(rel, ln, lines[ln - 1].strip() if ln <= len(lines) else ""))
    return out


def scan(files: tuple[str, ...] = SCANNED, root: pathlib.Path = ROOT) -> list[Finding]:
    findings: list[Finding] = []
    for rel in files:
        findings.extend(scan_text((root / rel).read_text(encoding="utf-8"), rel))
    return findings


def main() -> int:
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args()
    findings = scan()
    if not findings:
        print(f"✓ constant-time: no ==/!= on a signature/MAC in {', '.join(SCANNED)} "
              f"(verification uses hmac.compare_digest).")
        return 0
    for f in findings:
        print(f"✗ {f.file}:{f.line}: secret compared with ==/!= — use "
              f"hmac.compare_digest\n    {f.snippet}")
    print(f"\n{len(findings)} non-constant-time secret comparison(s) — a timing "
          f"side channel on the seal path.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
