# Roots on one machine — `~/.willow`, `~/.nestor`, `~/.homestead`

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

## `~/.nestor` — Nestor's household home

**Who:** Humans (and their apps) running Nestor without running the fleet.

**Canonical definition:** this repo → `nestor/home_paths.py` (`NESTOR_HOME`,
default `Path.home() / ".nestor"`).

| Subtree | Role |
|---------|------|
| `keep/` | Engine state Nestor pins here (e.g. `ledger.jsonl`) |
| `record/` | Canonical read-only household record |
| `logs/` | Sealed log (I-22) |
| `drafts/` | Working drafts |

**Nestor pins here** via `nestor.home_paths.bind_ledger()` (and future seam
store) — see [`home-paths.md`](home-paths.md).

Nestor used to mirror `~/.homestead` instead. It no longer does, and that is
**this file's own audience test applied to Nestor**: the rule is that someone
who only installs a household product should not be handed another product's
vocabulary. `WILLOW_*` was the example; a Nestor-only install being given a
`.homestead` directory is the same mistake one brand along.

## `~/.homestead` — the Homestead · Affairs household home

**Who:** Humans using Homestead · Affairs.

**Canonical definition:** `rudi193-cmd/homestead` → `homestead/keep/paths.py`
(`HOMESTEAD_HOME`, default `Path.home() / ".homestead"`).

Still a real root, still owned by that repo — Nestor simply does not resolve to
it on its own. A homestead host that wants Nestor's keep tree there **names**
it: `NESTOR_HOME="$HOMESTEAD_HOME"`. Setting `HOMESTEAD_HOME` *without*
`NESTOR_HOME` is refused rather than guessed, because guessing either way forks
a hash-chained ledger — see [`home-paths.md`](home-paths.md).

---

## Nestor product — what goes where

| Data | Root | Mechanism |
|------|------|-----------|
| Hash-chained audit ledger (household host) | `$NESTOR_HOME/keep/` (default `~/.nestor/keep/`) | `bind_ledger()` / `nestor_seam.bind()` |
| TM / entity store (household host) | Host-injected `Storage` under `$NESTOR_HOME` | Explicit `store=`, never global `set_store` in seam |
| SOIL gaps, charter seals, fleet KB | `~/.willow/store/` (project paths) | willow-mcp; **not** for Nestor *source* dev |
| Hanuman dispatch handoffs (UI echo) | `$WILLOW_HOME/dispatch/` | `nestor ui` + `NESTOR_GATE_ROLLUP` |
| Developing the Nestor package | Repo `./data/`, `docs/dogfood/` | No home dir required |

---

## How to define `.willow` *better* (shared checklist)

Homestead does this for `.homestead` in one module (`paths.py` + invariant
tests), and Nestor now does it for `.nestor` in `nestor/home_paths.py`. Willow
should stay the authority for `.willow`, but **consumers** (Nestor, homestead,
charter) should repeat the same **four lines** everywhere `WILLOW_HOME` appears:

1. **Purpose** — fleet operator runtime, not household records.
2. **Resolver** — `WILLOW_HOME` / `fleet_home()`; alias `~/.willow`.
3. **Table** — top-level subtrees and env vars (`WILLOW_STORE_ROOT`, …).
4. **Audience test** — if the installer is not a fleet operator, do not require
   `.willow`; use the face’s own root — `.nestor` for Nestor, `.homestead` for
   Homestead · Affairs.

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
| `NESTOR_HOME` | `.nestor` | Nestor household engine paths |
| `HOMESTEAD_HOME` | `.homestead` | Homestead · Affairs paths; Nestor reads it only to refuse |
| `NESTOR_LEDGER` | explicit path | Overrides ledger location (dev or migration) |
| `NESTOR_GATE_ROLLUP` | file path | Charter JSON (not a home root) |

Household Nestor state lives under **`$NESTOR_HOME/keep/`** (default
**`~/.nestor/keep/`**), fleet Nestor wiring under **`.willow/`**.
