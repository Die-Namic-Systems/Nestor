---
name: debugging
description: >-
  Hypothesis-first debugging — search prior context, name 2–4 competing causes,
  instrument to tell them apart, reproduce once, fix surgically with a test.
  Trigger on a bug report, stack trace, failing test, or "this isn't behaving
  right." Not for filing a bug to look at later.
---

# Debugging (Nestor)

Hypotheses first, reading second. The failure this replaces: an hour tracing
call paths from whatever file you opened first, arriving at one theory you're now
invested in.

## 1. Search prior context (don't skip)

Before reproducing, check what's already known: grep the repo for the error,
tool, or module; read the relevant `docs/`; and search the decision store —
`nestor --db docs/dogfood/nestor.db decision check "<the thing you're about to
change>"` — a recorded rejection or a superseded choice is often the root cause.
The house often already knew.

## 2. Cursory exploration (minutes)

Read only enough to name causes: the stack trace top-first, the failing function
(not the whole module), recent changes (`git log -n 5 --oneline -- <path>`).
Stop as soon as you can write hypotheses.

## 3. Two to four hypotheses

Fewer than two means you anchored; more than four means you listed instead of
thought. Each needs a **distinct predicted observation** — true in the
logs/state if this cause is real, false if not.

```
H1: <cause> → expect <observable> at <location>
H2: <cause> → expect <observable> at <location>
```

Two hypotheses predicting identical evidence are one — sharpen until they
diverge. Show the list to the user as a heads-up; don't wait for approval.

## 4. Instrument the disagreement

Add logging/asserts where the hypotheses *differ*, so a single repro splits the
field. An already-failing test needs no user repro — run it yourself. Anything
deterministic and scriptable — write the throwaway repro and run it yourself.
Never ask the user to reproduce what you can trigger.

## 5. Diagnose, then fix — surgically

- One change that fixes the named cause. **No surrounding cleanup, no drive-by
  refactor** — a bug fix does not get free changes.
- Never fix without a test. Write the regression test that fails on the old
  behavior first (see `testing`), then fix. A fix without a test is a guess.
- Re-run the standard checks (`bash scripts/ci-lint.sh`, `python -m pytest -q`)
  and quote the outcome (see `verification`).

## Finish

Commit with `fix(<area>): <what was wrong> — <why>` — the format that is still
useful in the git log months later. **Propose; don't confirm** — no PR unless
asked, and nothing seals in the store without a human.
