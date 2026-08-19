# User preferences — draft

*Filling the gap §7.5 names: the system has product decisions and governance
rules but no surface for per-user, cross-session "I like it this way."*

**Status: draft — proposed, not decided.**

---

## The problem

The worked instance (§7.5): a user said "stop producing artifacts" — a
preference, not a policy — and the only place to put it was a decision file,
which was wrong (reverted within minutes). The gap is real:

- A preference is not a decision (it binds one person, not the product).
- A preference is not a config var (it's per-user, not per-deployment).
- A preference is not a CLAUDE.md line (that's per-repo, not per-person).
- A preference is not session context (it should survive the session).

## Where it lives

Under `NESTOR_HOME` (`~/.nestor` by default), alongside the ledger:

```
~/.nestor/
  preferences.json    # <-- new
  ledger.jsonl        # existing
  nestor.db           # existing (when a household store is in use)
```

A JSON file, not a SQLite table, because:
- It's small (dozens of keys, not thousands of rows).
- It should be human-readable and hand-editable.
- It should not be coupled to the store schema or its migration ladder.
- It should survive a store rebuild (`nestor import`).

## Schema

```json
{
  "nestor_preferences": 1,
  "user": "rudi193@gmail.com",
  "preferences": {
    "output.artifacts": false,
    "output.format": "text",
    "serve.default_domain": "decision",
    "ui.theme": "system"
  },
  "updated_at": "2026-08-19T12:00:00+00:00"
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `nestor_preferences` | int | yes | Schema version for this file (starts at 1) |
| `user` | string | yes | The user this file belongs to (email or handle) |
| `preferences` | object | yes | Key-value map of preference names to values |
| `updated_at` | string | yes | ISO 8601 timestamp of last write |

### Preference keys

Dotted namespace, grouped by surface:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `output.artifacts` | bool | true | Whether to produce Artifact pages |
| `output.format` | string | "text" | Default output format (text, json, markdown) |
| `output.emoji` | bool | false | Whether to use emoji in output |
| `serve.default_domain` | string | "decision" | Default source_lang for `nestor serve` |
| `serve.read_only` | bool | false | Default `--read-only` for `nestor serve` |
| `ui.theme` | string | "system" | UI theme (system, light, dark) |
| `ui.page_size` | int | 25 | Rows per page in `nestor ui` |
| `cli.color` | bool | true | Colored CLI output |
| `cli.verbose` | bool | false | Verbose mode by default |

New keys can be added without a schema version bump — unknown keys are
preserved on read, not stripped. The version bump is for structural changes
(renaming `preferences` to something else, adding a top-level field).

## API surface

```python
# nestor/preferences.py (new module)

def load(home: Path | None = None) -> dict:
    """Load preferences from NESTOR_HOME/preferences.json.
    Returns the preferences dict (empty dict if file missing)."""

def save(prefs: dict, home: Path | None = None) -> None:
    """Write preferences to NESTOR_HOME/preferences.json.
    Atomic write (write-to-tmp, rename)."""

def get(key: str, default=None, home: Path | None = None):
    """Read one preference. Dotted key lookup."""

def set(key: str, value, home: Path | None = None) -> None:
    """Set one preference. Atomic read-modify-write."""

def clear(key: str, home: Path | None = None) -> None:
    """Remove one preference (revert to default)."""
```

## CLI surface

```
nestor prefs                        # list all preferences
nestor prefs get output.artifacts   # read one
nestor prefs set output.artifacts false  # set one
nestor prefs clear output.artifacts     # revert to default
nestor prefs reset                  # delete the file entirely
```

## MCP surface

A new tool `nestor_prefs` in `serve.py`:

```json
{
  "name": "nestor_prefs",
  "description": "Read the user's preferences (read-only from MCP).",
  "inputSchema": {
    "type": "object",
    "properties": {
      "key": {"type": "string", "description": "Dotted preference key, or omit for all"}
    }
  }
}
```

Write is CLI-only. A model should not set preferences on the user's behalf
without the user typing the command — same reason `nestor_propose` exists
but `nestor_seal` does not.

## What this is NOT

- **Not config.** `nestor.config` is deployment configuration (env vars, the
  resolver, secrets). Preferences are personal choices that don't affect the
  system's correctness. A preference that said "skip chain verification" would
  be a config var, not a preference.
- **Not a decision.** Preferences don't go in the dogfood corpus, don't get
  sealed, don't constrain future decisions. "I prefer dark mode" is not a
  product decision.
- **Not synced.** The file lives under `NESTOR_HOME` on one machine. No cloud
  sync, no merge. Two machines = two preference files. The portable bundle
  does not carry preferences (by design — a bundle is the product's data,
  not the person's taste).
- **Not enforced.** A preference is a hint. Code that reads `output.artifacts`
  should respect it; code that ignores it is a bug, not a governance violation.
  There is no covenant here — just manners.

## Interaction with embedding hosts

When Nestor is embedded in another face (`NESTOR_HOME="$HOMESTEAD_HOME"`),
the preferences file lives under that face's root. A user's preferences
travel with their household, not with Nestor's default `~/.nestor`. This
matches the die-rules §Rule 2: the root belongs to the household, not to
the face.
