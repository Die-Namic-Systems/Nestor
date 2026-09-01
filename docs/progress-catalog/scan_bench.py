#!/usr/bin/env python3
"""Merge nestor/bench/results into catalog.jsonl (idempotent on bench rows)."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CATALOG = ROOT / "catalog.jsonl"
BENCH = Path("/home/sean-campbell/github/Die-Namic-Systems/nestor/bench/results")


def row_id(path: Path) -> str:
    return hashlib.sha256(str(path).encode()).hexdigest()[:16]


def bench_rows() -> list[dict]:
    out: list[dict] = []
    for path in sorted(BENCH.glob("*.json")):
        data = json.loads(path.read_text())
        if isinstance(data, list):
            out.append({
                "id": row_id(path), "path": str(path), "source_tree": "live",
                "kind": "bench_json", "tier": 1, "bench": path.stem,
                "run_count": len(data), "size_bytes": path.stat().st_size,
                "corpus_status": "not_ingested",
                "summary": f"bench={path.stem} list_len={len(data)}",
            })
            continue
        runs = data.get("runs", [])
        latest = runs[-1] if runs else {}
        out.append({
            "id": row_id(path), "path": str(path), "source_tree": "live",
            "kind": "bench_json", "tier": 1, "bench": data.get("bench", path.stem),
            "run_count": len(runs), "latest_run_id": latest.get("run_id"),
            "recorded_at": latest.get("recorded_at"), "size_bytes": path.stat().st_size,
            "corpus_status": "not_ingested",
            "summary": f"bench={data.get('bench', path.stem)} runs={len(runs)}",
        })
    return out


def main() -> None:
    existing = []
    if CATALOG.exists():
        for line in CATALOG.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("kind") != "bench_json":
                existing.append(row)
    rows = existing + bench_rows()
    CATALOG.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    print(f"catalog: {len(rows)} rows ({len(bench_rows())} bench)")


if __name__ == "__main__":
    main()
