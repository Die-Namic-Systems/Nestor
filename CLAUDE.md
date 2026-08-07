# Agent instructions (Claude, Cursor, Codex, compatible CLIs)

**Read first:** [`AGENTS.md`](AGENTS.md) (cold-start) · [`docs/agent-guide.md`](docs/agent-guide.md) (operating rules).

Do not duplicate policy here — it drifts. Change `docs/agent-guide.md`, `hooks/seat.md`, and `AGENTS.md` instead.

Two lines stay, because this file is the one an agent is *made* to read and the
guide is one it has to choose to open:

- **You may propose. You may not confirm.** No `status="sealed"` and no
  `verifier=` carrying a human's name unless they signed in `nestor ui`.
- Decisions worth keeping go in `docs/dogfood/decisions/`, then
  `python scripts/dogfood_store.py --rebuild`.

Both are stated in full in the guide. These are the pointers, not the policy.
