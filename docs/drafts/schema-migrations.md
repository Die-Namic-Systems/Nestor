# Schema migrations — draft

*Filling the gap §7.5 names: `memory_init` creates the schema; a store from
before a change is handled by ad-hoc prose, not a versioned path.*

**Status: draft — proposed, not decided.**

---

## What exists today

`sqlite_store.py` already has the machinery:

- `SCHEMA_VERSION = 1` (line 204)
- `PRAGMA user_version` read/stamped in `_apply_schema` (line 478, 496)
- `StoreSchemaTooNewError` — refuses a file from a newer build (line 225)
- `_FORWARD_MIGRATIONS: list[tuple[int, Callable]]` — empty but wired (line 323)
- `_apply_schema` runs self-heal (idempotent DDL) THEN the forward ladder (line 490)
- The migratability test suite injects a real step over a two-generation world

The ladder works. The gap is: no real step has ever been appended to it, so the
machinery is proven by test but not by use.

## What a migration step looks like

A step is a `(target_version, callable)` appended to `_FORWARD_MIGRATIONS`.
The callable receives a `sqlite3.Connection` inside the init transaction.
It runs only when the stored `user_version` is below `target_version`.
It must be idempotent (a crash between "step ran" and "version stamped"
replays the step on next open).

```python
# Example: adding a preferences table in generation 2.
def _migrate_v2(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS preferences (
            id       TEXT PRIMARY KEY,
            user_id  TEXT NOT NULL,
            key      TEXT NOT NULL,
            value    TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_preferences_user_key
            ON preferences(user_id, key);
    """)

# Then in the class body:
_FORWARD_MIGRATIONS = [(2, _migrate_v2)]
SCHEMA_VERSION = 2
```

## Design rules

1. **Append only.** Never edit or renumber a shipped step. A renumbered step
   re-runs on files that already applied it. An inserted-ahead step is silently
   skipped on every file already past its position.

2. **Idempotent.** `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`,
   `ALTER TABLE ... ADD COLUMN` with a guard. A step that fails halfway and runs
   again must produce the same result.

3. **No data loss.** Add columns (with defaults), add tables, add indexes.
   Never drop a column a user's store may hold data in. A column rename is two
   steps: add new, copy data, (next version) drop old.

4. **Bump together.** `SCHEMA_VERSION` increments by exactly 1 per step.
   A step targeting version N means "bring a version N-1 file to N."

5. **Test the two-generation world.** The existing migratability test creates
   a store at version N-1, runs the step, and verifies the result. Every new
   step gets a test that does the same.

6. **The portable bundle is the escape hatch.** `nestor export` / `nestor import`
   already move data between stores. A migration that cannot be expressed as DDL
   (a constraint change, a normalization) is: export from old, create new, import.
   The migration step handles the common case; the bundle handles the edge case.

## The first real migration (proposal)

The visibility field §6.53 names as blocked on this decision:

```python
def _migrate_v2(conn: sqlite3.Connection) -> None:
    # §6.53: origin says what produced the row; visibility says who should
    # see it. A row extracted from a private document should not appear in
    # a public-facing MCP serve, even if the extraction is correct.
    conn.execute("""
        ALTER TABLE tm_pairs ADD COLUMN visibility TEXT NOT NULL DEFAULT 'internal'
    """)
    # 'internal' = operator only (the dogfood default)
    # 'serve'    = available through nestor serve / MCP
    # 'public'   = available in a published bundle
```

This unblocks the visibility field without touching existing data — every
existing row defaults to `'internal'`, which is conservative (the operator
sees it, a model does not until someone promotes it).

## What this does NOT cover

- **Downgrade.** A newer file is refused, not downgraded. The portable bundle
  is the cross-version transport.
- **Multi-step jumps.** The ladder is linear (1→2→3→...); a v1 file opening
  against SCHEMA_VERSION=3 runs steps 2 and 3 in order. No skip paths.
- **Concurrent migration.** SQLite's file lock serializes opens. Two processes
  opening the same file run `_apply_schema` sequentially, and the idempotent
  steps make the second open a no-op.
