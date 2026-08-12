# Nestor dev skills

Skills a Claude Code / Codex session loads while developing **this** repo.
Discovered by convention (`.claude/skills/<name>/SKILL.md`) — no manifest.

Nestor is deliberately walled off from the willow-mcp fleet plugin
(`hooks/seat.md`: "do not use willow-mcp for routine Nestor work"), so these are
Nestor's own, not the fleet's.

## The suite

| Skill | What it locks in |
|-------|------------------|
| `verification` | Claim only what you derived from the tree; harnesses that fail the build are standard checks, not manufactured evidence |
| `testing` | Every invariant gets a test that performs the forbidden act and asserts refusal — acceptance is mutation, not a green suite |
| `debugging` | Hypothesis-first; search the decision store before reproducing; surgical fix with a test |
| `autonomous-work-boundaries` | User owns intent, you own execution; the one line you never cross is confirming |

## Provenance — re-landed, not vendored

These were derived from the method in the **synapse** workflow suite
(`AllHailSeizure/Synapse`, forked at `rudi193-cmd/synapse`), audited against
Nestor's rules, then **re-landed** in Nestor's voice against Nestor's own
commands, docs, and refusals. They are not copies of synapse's `SKILL.md` files:
copying would create the vendored pair this repo's §16 discipline (and
`quick-stupids`) forbids, and it would drift. There is no shared file to drift —
only a shared idea, credited here.

The diff that informed the selection: synapse's authoring is lean and
stack-agnostic where the fleet's willow-mcp skills are wired to Postgres/Kart/
`app_id`; the disciplines worth harvesting from willow-mcp (search prior context
first, surgical fixes, `fix(<area>): what — why`, never mock the thing under
test) were folded into `debugging`/`testing`.

## Deliberately not landed (yet)

- `thinking`, `writing-plans`, `executing-plans` — useful; a second tranche if
  wanted.
- `code-review` (receiving feedback) — high value for the PR-watch workflow;
  next candidate.
- `finishing-branches`, `bug-capture`, `goal-oriented-development`,
  `worktree-cleanup` — **held**: they shell `gh` (this environment is GitHub-MCP
  only) and/or auto-open PRs (Nestor's rule is no PR unless asked). Adapt before
  landing.
- `asset-churn-audit` — N/A; a game-asset tool, and Nestor ships no binary art.
