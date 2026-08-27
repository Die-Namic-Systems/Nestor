#!/usr/bin/env python3
"""Copy the pinned dogfood smoke corpus into tests/fixtures/dogfood_smoke/decisions/.

Active decision files are read from ``docs/dogfood/decisions/``; archived ones
(named in the manifest but absent there) are copied from ``docs/archive/decisions/``.
"""
from __future__ import annotations

import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests" / "fixtures" / "dogfood_smoke" / "manifest.txt"
ACTIVE = ROOT / "docs" / "dogfood" / "decisions"
ARCHIVE = ROOT / "docs" / "archive" / "decisions"
OUT = ROOT / "tests" / "fixtures" / "dogfood_smoke" / "decisions"


def main() -> int:
    names = [
        line.strip()
        for line in MANIFEST.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.json"):
        old.unlink()
    missing: list[str] = []
    for name in names:
        for src in (ACTIVE / name, ARCHIVE / name):
            if src.is_file():
                shutil.copy2(src, OUT / name)
                break
        else:
            missing.append(name)
    if missing:
        print("missing from active and archive:", ", ".join(missing), file=sys.stderr)
        return 1
    print(f"copied {len(names)} decision file(s) -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
