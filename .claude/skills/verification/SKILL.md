---
name: verification
description: >-
  Claim only what you derived from the tree. Use before saying something works,
  is fixed, passes, or is done — and before quoting any count (tests, rows,
  gates). Keep the check proportional to the claim; if the standard check can't
  run, say what you checked and what you didn't rather than inventing a
  substitute.
---

# Verification (Nestor)

Nestor's whole product is the refusal to serve a near-miss as verified. Hold the
same bar for your own claims: state only what a command on *this* checkout
showed.

## Rules

1. **Derive, don't recall.** Never quote a test count, row count, or gate count
   from a README, a prior message, or memory — read it off the tree. This repo
   has a documented history of figures in prose the code moved past.
2. **Proportional scope.** A one-line doc fix does not need the full suite; a
   change to a matcher, a hook, or the store does. Match the check to what the
   claim rests on.
3. **Evidence before the assertion.** When you say pass/fixed/done, quote the
   command and its outcome. `bash scripts/ci-lint.sh` and
   `python -m pytest -q` are the standard checks (see `AGENTS.md`).
4. **Absence is `unknown`, not a pass.** A check that could not run is
   "unavailable," never "clean." Say which check didn't run and why.

## Measurement harnesses are standard checks, not manufactured evidence

Building a probe *instead of* running the real check, to fake a green, is the
failure this skill refuses. Building a harness that **fails the build** — the
dogfood demo, the N1 bench, the boot self-test — is not that: it *is* a standard
check, and it is how this repo proves a guard can fail. Write the harness; just
don't let a throwaway probe stand in for the suite the claim actually depends on.

## Before you say "done"

- What exact claim am I making?
- What command supports it, and did that command run on this tree just now?
- Am I quoting any number I did not read off the output?

Can't answer all three → don't claim it.
