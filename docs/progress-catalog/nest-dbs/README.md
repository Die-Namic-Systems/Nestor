# Nest scan databases

Indexed 2026-08-31 via `willow-mcp nest_scan` (dry_run=false, use_embed=false).

| DB | Source folder | Files | Notes |
|------|---------------|-------|-------|
| nestor-bench-results.db | live `nestor/bench/results` | 11 | Tier 1 bench JSON |
| slm-corpus.db | greenfield `workshop/sean-data-vault/slm-corpus` | 1376 | Archive-only training pipeline |
| locomo.db | `.willow-archive/locomo_results` | 2 | LoCoMo eval summaries |
| pikoci-rig.db | `.willow-archive/tools/pikoci-rig/willow-ci` | 1325 | ollama bench + CI artifacts |
| nestor-decisions.db | live `dogfood/decisions` | 78 | Sealed decision JSON |

Run `nest_digest` / `nest_status` against these paths for structure-only maps.
