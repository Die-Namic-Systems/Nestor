# Agent hooks (CLI-agnostic)

One policy, one code path. IDEs only differ in **config shape** and **JSON dialect**.

| Entry | Role |
|-------|------|
| `hooks/nestor-hook` | Shell wrapper — call as `hooks/nestor-hook <cursor\|claude> <session_start\|before_mcp>` |
| `hooks/hook_runner.py` | Adapts Cursor vs Claude stdout |
| `hooks/seat.md` | Local-first seat copy (session start) |
| `hooks/before_mcp.py` | Block willow-mcp / nestor MCP; allow codebase-memory |

## Wiring

| CLI | Config file | Events |
|-----|-------------|--------|
| **Cursor** | `.cursor/hooks.json` | `sessionStart`, `beforeMCPExecution` |
| **Claude Code** | `.claude/settings.json` | `SessionStart`, `PreToolUse` (`matcher`: `mcp__`) |

Claude Code on the web still runs `.claude/hooks/session-start.sh` **inside** `session_start` when `CLAUDE_CODE_REMOTE=true` (venv bootstrap only).

## What `session_start` hands the agent

Five guarded sections; a broken one degrades to a status line rather than taking the boot down.

| Section | Question | When it is quiet |
|---------|----------|------------------|
| seat | the rules of this repo (`hooks/seat.md`) | never — a missing seat is the one hard error |
| `[check] pytest:` | is the test runner ready | reports either way |
| `[check] lint:` | can `scripts/ci-lint.sh` run — **every** gate | reports either way |
| `[nestor]` | is a Nestor stood up | one line when it is; **asks the user** when it is not |
| `[brain]` | is the decision store stood up | hands it over when it is; asks when it is not |

The last two **ask, they never act**. A SessionStart hook cannot put a question to the user itself, so it hands the agent the question — standing something up is the user's call, not the boot's. Neither probe writes: `[nestor]` in particular must not touch `data/nestor.db`, because `nestor stats` on a tree with no store *creates* one and reports `0 pair(s)`, so any probe that touched the path would destroy the answer before reporting it.

`[nestor]` reads the store path off the CLI's own `--db` default, and switches to the household home (`$HOMESTEAD_HOME`, marker `layout.json`, scaffolded by `python -m nestor.home_init`) when that variable is set.

Codex / other CLIs: point their hook command at the same `hooks/nestor-hook` line when the product supports project hooks.

## Env

`NESTOR_PROJECT_ROOT` (or `CLAUDE_PROJECT_DIR` / `CURSOR_PROJECT_DIR`) must be the repo root when the hook runs.

Household-bound Nestor state uses **`~/.nestor`** (`NESTOR_HOME`) — see [`docs/home-paths.md`](../docs/home-paths.md).

Cold-start for agents: [`AGENTS.md`](../AGENTS.md) (git sync + `scripts/ci-lint.sh`).
Operating rules: [`docs/agent-guide.md`](../docs/agent-guide.md).
