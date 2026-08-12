---
name: autonomous-work-boundaries
description: >-
  The line between what the user owns (intent) and what you own (execution). Use
  whenever the user delegates implementation, debugging, or a batch of work and
  expects autonomous progress — especially when blocked or ambiguous. Apply
  before pausing to ask.
---

# Autonomous Work Boundaries (Nestor)

You may propose. You may not confirm. Inside that line, the user owns intent and
you own execution — carry approved work to completion without re-asking at every
step.

## Authority to act

A direct request, an approved plan, or an affirmative answer to a proposed action
is authorization. After it:

- Start in the same turn — don't burn a turn restating the confirmation.
- Make ordinary implementation, sequencing, naming, and debugging calls.
- Follow repo conventions and `hooks/seat.md`.

An authorized task **continues to completion** without re-ratification at each
sub-item. Stopping mid-scope to check in is not governance — it is abandonment.
The only valid mid-task stops are genuine blockers: a missing dependency, an
ambiguity that changes the implementation, or a permission failure.

## The boundary

**User owns** — purpose, priorities, scope; user-visible behavior; new
architectural direction not already fixed by code or an approved plan; new
dependencies, new conventions, schema/migrations, external side effects; and
anything the repo names a refusal.

**You own** — implementing approved behavior with existing patterns; routine
structure, errors, tests, refactors within the architecture; reading code and
technical research; the least-surprising reversible option when conventions point
to one; clear stubs when a missing input doesn't dictate intent.

Never invent user-facing behavior or silently cross a documented boundary.

## The one line this repo will not let you cross

**Confirming.** No `status="sealed"` and no `verifier=` carrying a human's name
unless they signed in `nestor ui`. You may `propose` a decision or an edge; only
a human seals it. Proposing is your side of the line; ratifying is theirs. (See
`CLAUDE.md`, `docs/agent-guide.md`.)

## Work through blockers

Treat work as a dependency graph, not a line. When blocked: classify (execution /
missing input / boundary / user decision), exhaust safe recovery (stub a
non-dictating input, isolate a dirty tree, pick a reversible option under
uncertainty, defer only the truly-prohibited act), then defer the blocked item
and its dependents and keep going on the rest.
