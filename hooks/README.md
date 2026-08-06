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

Codex / other CLIs: point their hook command at the same `hooks/nestor-hook` line when the product supports project hooks.

## Env

`NESTOR_PROJECT_ROOT` (or `CLAUDE_PROJECT_DIR` / `CURSOR_PROJECT_DIR`) must be the repo root when the hook runs.

Household-bound Nestor state uses **`~/.homestead`** (`HOMESTEAD_HOME`), not `.nestor` — see [`docs/homestead-paths.md`](../docs/homestead-paths.md).

Cold-start for agents: [`AGENTS.md`](../AGENTS.md) (git sync + `scripts/ci-lint.sh`).
