# Two roots on one machine — `~/.willow` and `~/.homestead`

Die Rule 2 ([homestead-affairs face / `die-rules.md`](https://github.com/rudi193-cmd/safe-app-store-public/blob/main/docs/die-rules.md)):
**audience**, not brand. Someone who **runs the fleet** uses Willow’s home;
someone who **only installs a household product** gets a vocabulary that is not
`WILLOW_*`.

These directories are **not security boundaries** (same uid, same disk). They
are **namespacing**: what the operator’s agents own vs what the household owns.

---

## `~/.willow` — fleet runtime home

**Who:** Operators running Jarvis seats, MCP apps, Kart, SOIL, dispatch, Grove.

**Canonical definition:** `willow-2.0` → [`docs/WILLOW_CONFIG.md`](https://github.com/rudi193-cmd/willow-2.0/blob/main/docs/WILLOW_CONFIG.md)
and `willow/fylgja/willow_home.py` (`fleet_home()`, `WILLOW_HOME`).

**Resolver:** `WILLOW_HOME` (often `~/github/.willow` with `~/.willow` as alias).

| Subtree (typical) | Role |
|-------------------|------|
| `store/` | SOIL SQLite collections (`WILLOW_STORE_ROOT` default) |
| `mcp_apps/` | Compiled agent manifests |
| `handoffs/` | Session continuity markdown |
| `dispatch/` | Dispatch handoffs + evidence (`dispatch/<id>/handoff.json`) |
| `env`, `settings.global.json` | Fleet env and consent |
| `venvs/` | Product MCP venvs (e.g. willow-mcp) |

**Nestor touches `.willow` only when wired to the fleet** — e.g. gate-echo reads
`$WILLOW_HOME/dispatch/…`, FRANK forwarder calls willow-mcp, import scripts set
`WILLOW_STORE_ROOT` for charter SOIL. That is **orchestration**, not the
household record.

---

## `~/.homestead` — household runtime home

**Who:** Humans (and their apps) using Homestead · Affairs without running the fleet.

**Canonical definition:** `rudi193-cmd/homestead` → `homestead/keep/paths.py`
(`HOMESTEAD_HOME`, default `Path.home() / ".homestead"`).

| Subtree | Role |
|---------|------|
| `keep/` | Engine state Nestor must pin here (e.g. `ledger.jsonl`) |
| `record/` | Canonical read-only household record |
| `logs/` | Homestead sealed log (I-22) |
| `drafts/` | Working drafts |

**Nestor pins here** via `nestor.homestead_paths.bind_ledger()` (and future seam
store) — see [`homestead-paths.md`](homestead-paths.md).

---

## Nestor product — what goes where

| Data | Root | Mechanism |
|------|------|-----------|
| Hash-chained audit ledger (household host) | `~/.homestead/keep/` | `bind_ledger()` / `nestor_seam.bind()` |
| TM / entity store (household host) | Host-injected `Storage` under homestead | Explicit `store=`, never global `set_store` in seam |
| SOIL gaps, charter seals, fleet KB | `~/.willow/store/` (project paths) | willow-mcp; **not** for Nestor *source* dev |
| Hanuman dispatch handoffs (UI echo) | `$WILLOW_HOME/dispatch/` | `nestor ui` + `NESTOR_GATE_ROLLUP` |
| Developing the Nestor package | Repo `./data/`, `docs/dogfood/` | No home dir required |

---

## How to define `.willow` *better* (shared checklist)

Homestead already does this for `.homestead` in one module (`paths.py` + invariant
tests). Willow should stay the authority for `.willow`, but **consumers** (Nestor,
homestead, charter) should repeat the same **four lines** everywhere `WILLOW_HOME`
appears:

1. **Purpose** — fleet operator runtime, not household records.
2. **Resolver** — `WILLOW_HOME` / `fleet_home()`; alias `~/.willow`.
3. **Table** — top-level subtrees and env vars (`WILLOW_STORE_ROOT`, …).
4. **Audience test** — if the installer is not a fleet operator, do not require
   `.willow`; use `.homestead` (or the face’s own root).

Nestor’s [`docs/local-fleet.md`](local-fleet.md) is the **integration** guide;
this file is the **root vocabulary** guide. Homestead remote docs should link
here (or duplicate the table) so `nestor_seam` never implies `data/ledger.jsonl`
or `~/.willow` for the ledger.

---

## Env vars at a glance

| Variable | Root | Used for |
|----------|------|----------|
| `WILLOW_HOME` | `.willow` | Fleet home, dispatch, MCP materialization |
| `WILLOW_STORE_ROOT` | under `.willow` | SOIL store path (often `…/store`) |
| `HOMESTEAD_HOME` | `.homestead` | Household engine paths |
| `NESTOR_LEDGER` | explicit path | Overrides ledger location (dev or migration) |
| `NESTOR_GATE_ROLLUP` | file path | Charter JSON (not a home root) |

No `NESTOR_HOME` and no `~/.nestor` — household Nestor state lives under
**`.homestead/keep/`**, fleet Nestor wiring under **`.willow/`**.
