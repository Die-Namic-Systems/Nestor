# AGENTS.md — Nestor (product repo)

Cold-start map for **any** agent (Cursor, Claude Code, Codex, cloud). **Not** the
willow charter seat — no willow-mcp for routine work here; see `hooks/seat.md`.

## First move (every session, especially cloud)

1. **Sync git** before you edit — cloud containers often start on a stale ref:

   ```bash
   git fetch origin
   git status -sb
   # Open PR work:  gh pr checkout <number>   # or: git checkout <branch> && git pull
   # Default trunk: git checkout master && git pull
   ```

2. **Match CI before you push** — unused imports in tests (`pytest`, `os`,
   `Path`, …) fail **F401** on GitHub even if your buffer looks fine locally.

   **Which gate you owe depends on what you touched** (IDEAS §6.100). The
   agent experiences no duration and is never the party waiting, so it will
   keep choosing the maximal gate unless the cheaper correct option is
   readable. This table makes it readable:

   | Changed paths | Class | Verification command |
   |---|---|---|
   | `nestor/`, `recipes/`, `tests/`, `scripts/`, `hooks/`, `demo/` | full | `bash scripts/ci-lint.sh && bash scripts/ci-test.sh full` |
   | `docs/`, `IDEAS.md`, `docs/dogfood/decisions/*.json` | docs-only | `bash scripts/ci-docs.sh` |
   | `README.md`, `AGENTS.md`, `CLAUDE.md`, `.github/` | lint-only | `bash scripts/ci-lint.sh` |
   | Mixed (any combination of the above) | full | `bash scripts/ci-lint.sh && bash scripts/ci-test.sh full` |

   During implementation, `bash scripts/ci-test.sh core` is the fast deterministic
   lane. It does not replace the full pre-push row above. Installing `fastembed`,
   running Ollama, or having a sibling checkout must never silently enlarge either
   lane; use the explicit `semantic`, `ollama`, `browser`, `slow`, `performance`,
   or `external` lane when changing that integration.

   The table is guidance, not enforcement — no tooling checks which class
   you chose. When in doubt, run full. The point is that "correct and cheap"
   is a real option for docs-only changes, and choosing it is not cutting a
   corner.

   **Background rule:** any verification step estimated over ~10 s goes to
   background (`run_in_background` or equivalent) so the human is not
   staring at a spinner. The docs-only gate runs in ~7 s and can stay
   foreground; the full gate (~100 s) should not.

3. **Environment** — `source .venv/bin/activate` and `pip install -e ".[dev,keys]"`
   if `python -m pytest` is missing (`docs/agent-guide.md` → Environment).

## Read next

| Doc | Why |
|-----|-----|
| [`docs/agent-guide.md`](docs/agent-guide.md) | Operating rules (seals, tests, dogfood, voice) |
| [`hooks/README.md`](hooks/README.md) | CLI-agnostic hooks (`hooks/nestor-hook`) |
| [`hooks/seat.md`](hooks/seat.md) | Injected session policy (local-first, no fleet MCP) |
| [`docs/home-paths.md`](docs/home-paths.md) | `~/.nestor` vs repo `./data/` |
| [`docs/roots-willow-and-homestead.md`](docs/roots-willow-and-homestead.md) | `~/.willow` fleet vs `~/.nestor` household roots |

Claude Code loads [`CLAUDE.md`](CLAUDE.md) as a thin pointer to this map — same
substance as Cursor hooks + this file.

## Hooks

Cursor → `.cursor/hooks.json` · Claude Code → `.claude/settings.json` · both call
`hooks/nestor-hook`. Optional: `pre-commit install` (ruff on `nestor/`, `tests/`,
`hooks/`).

## Governance

You may propose; you may not confirm seals (`docs/agent-guide.md`).
