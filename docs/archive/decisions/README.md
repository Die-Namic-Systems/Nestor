# Archived dogfood decisions

Decision JSON files that are **audit record only** — not fed into
``scripts/dogfood_store.py`` (active corpus is ``docs/dogfood/decisions/`` only).

| Cut | What moved here |
|-----|-----------------|
| **Consolidated** (decision 0216) | Seven files with ``consolidated_onto: claude/the-box`` (0055–0061) |
| **Pre-0150** (decision 0217) | Every numbered file below 0150 — closed arc history |

Copies named in ``tests/fixtures/dogfood_smoke/manifest.txt`` still appear in the
pinned CI smoke corpus under ``tests/fixtures/dogfood_smoke/decisions/`` (built
from active + archive via ``scripts/build_dogfood_smoke_fixture.py``).
