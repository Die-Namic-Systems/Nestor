# Progress catalog

Consolidated inventory of bench results, training runs, archives, and progress docs across live `~/github` and greenfield cold trees.

## Quick start

```bash
# CLI (no pip install needed):
python3 -m nestor.cli ui --db docs/dogfood/nestor.db --open    # seal 0228 drafts
python3 -m nestor.cli check <label> <observed>                 # after numeric seal

# Optional: pip install -e .  →  nestor ui / nestor check ...

# Browse catalog (filterable table)
cd ui && python3 -m http.server 8771
```

## Artifacts

| File | Purpose |
|------|---------|
| `catalog.jsonl` | Machine index (28 rows, 2026-08-31) |
| `INVENTORY.md` | Human listing by tier |
| `FINDINGS.md` | Signal vs noise analysis |
| `THRESHOLD-POLICY.md` | Three-bar operating policy + calibrate output |
| `calibrate/` | Live `nestor calibrate` + triage sweep (2026-08-31) |
| `draft-pairs/` | Seal-ready decision + numeric baseline drafts (0228) |
| `PROGRESS-SNAPSHOT.md` | Shareable narrative |
| `config/roots.yaml` | Scan roots for nest_scan |
| `nest-dbs/` | SQLite indexes from `willow-mcp nest_scan` |
| `ui/` | Static catalog browser |

## MCP session

- Session: `progress-catalog-2026-08-31` (`session_enter`)
- SOIL: `willow_progress_catalog` (2 summary records; `progress_catalog` denied by store_scope)
- Gap logged: no sealed baseline for false-seal rate

## Archives included

See `config/roots.yaml` and [`GREENFIELD-FOR-CLAUDE.md`](../../../../GREENFIELD-FOR-CLAUDE.md).
