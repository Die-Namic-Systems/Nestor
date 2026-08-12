---
name: testing
description: >-
  Tests that lock behavior, and — for every invariant — a test that attempts the
  forbidden act and asserts refusal. Use when adding a feature, fixing a bug, or
  changing behavior. Not for throwaway probes or pure config edits.
---

# Testing (Nestor)

A guard that cannot be shown to fail has not been shown to work. Acceptance is
mutation, not a green suite.

## Mode selection

| Situation | Mode |
|-----------|------|
| API/design not settled | **TDD** — red → green → refactor |
| Behavior clear, coverage nearby | **Verification-first** — implement, then run/extend the check that proves it |
| Bug with no repro | Write the failing repro first, then fix |
| Throwaway / generated / pure config | Skip the formal cycle; don't pretend otherwise |

Use judgment; don't ask permission per mode. Skipped a test that later mattered?
Add it — don't rewrite history with a ritual delete.

## The rule this repo is strict about

Every invariant needs a test that **performs the forbidden act and asserts it is
refused** — not a test that exercises the happy path and infers the guard from
its silence. The hooks tests are the worked example: they feed the gate a fleet
MCP call and assert the *deny* lands on the wire. If you cannot write a test that
fails when the guard is removed, you have not verified the guard.

## Red → Green → Refactor

- **RED:** one minimal test for one behavior; run it; confirm it fails for the
  right reason (missing behavior, not a typo).
- **GREEN:** smallest code that passes. No drive-by refactors.
- **REFACTOR:** only once green; stay green; no new behavior.

Before writing a test, name the production change that would make it fail. If
nothing would, the test asserts nothing.

## Good vs bad

| Do | Don't |
|----|-------|
| One behavior per test | "and" sandwiches |
| Assert observable results | Assert mock call choreography |
| Fail when production breaks | Pass against any implementation |
| Use the real store/ledger under test | Mock the thing the test is about |

## Nestor specifics

- Run from the repo `.venv`: `python -m pytest -q` (bare `pytest` from repo root
  keeps the path CI uses — see `.github/workflows/tests.yml`).
- Coverage floors ratchet up, never down. Don't lower a threshold to go green.
- A decision worth keeping goes to `docs/dogfood/decisions/` + a rebuild, not a
  comment (see `hooks/seat.md`).
