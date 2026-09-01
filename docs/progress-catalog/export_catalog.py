#!/usr/bin/env python3
"""Export catalog.jsonl to INVENTORY.md and ui/data/catalog.json."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CATALOG = ROOT / "catalog.jsonl"


def main() -> None:
    rows = [json.loads(line) for line in CATALOG.read_text().splitlines() if line.strip()]
    by_tier: dict[int, list] = defaultdict(list)
    for row in rows:
        by_tier[int(row.get("tier", 3))].append(row)

    lines = [
        "# Progress Catalog Inventory",
        "",
        f"Generated from `{CATALOG.name}` — **{len(rows)}** rows.",
        "",
    ]
    for tier in sorted(by_tier):
        lines.extend([f"## Tier {tier}", ""])
        for row in sorted(by_tier[tier], key=lambda r: r.get("summary", "")):
            lines.append(
                f"- **{row.get('summary', row.get('id'))}** — "
                f"`{row.get('kind', '?')}` / `{row.get('source_tree', '?')}`"
            )
            if row.get("path"):
                lines.append(f"  - path: `{row['path']}`")
        lines.append("")

    (ROOT / "INVENTORY.md").write_text("\n".join(lines) + "\n")
    ui = ROOT / "ui" / "data"
    ui.mkdir(parents=True, exist_ok=True)
    (ui / "catalog.json").write_text(json.dumps(rows, indent=2) + "\n")
    print(f"exported {len(rows)} rows")


if __name__ == "__main__":
    main()
