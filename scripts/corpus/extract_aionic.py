#!/usr/bin/env python3
"""Shapes declared by `rudi193-cmd/Aionic-Claude-Skills` — rung 3.

    python scripts/corpus/extract_aionic.py --repo /workspace/aionic-claude-skills \
        --out data/corpus/aionic.db

A skills repository, so the dominant structure is the skill contract itself:
front matter naming the skill and saying what it is for, and a section saying
when it fires. Those are two different pairs about one skill and are kept apart
— *what it does* and *when it runs* fail differently.

**The repository carries two incompatible skill formats.** 19 of 26 `SKILL.md`
use `name:`/`description:` front matter; the four framework skills named in
`MANIFEST.json` use `Skill-Name:`/`Version:` instead, one of them inside a stray
code fence. Both are extracted, and which format a row came from is recorded in
its reason, because that difference is the most interesting fact in the corpus.

**The source is private.** The store belongs in gitignored `data/`; nothing it
produces is committed. See IDEAS §6.41.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

import common                                                    # noqa: E402
import provenance                                                # noqa: E402

from nestor.sqlite_store import SqliteStore                      # noqa: E402

TRIGGER_HEADINGS = ("when to activate", "when to use", "auto-invoke", "trigger")
DEFN_KEYS = ("term", "concept", "field", "key", "name", "skill", "command",
             "idiom", "pattern")


def skills(root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(p for p in root.rglob("SKILL.md") if ".git" not in p.parts)


def described(root: pathlib.Path) -> list[tuple]:
    """The skill contract: what this skill is for. Both formats."""
    rows = []
    for path in skills(root):
        text = path.read_text(encoding="utf-8")
        fm = common.frontmatter(text)
        name = fm.get("name")
        desc = fm.get("description")
        fmt = "front matter name/description"
        if not (name and desc):
            # The framework format: `Skill-Name:` with the summary in the
            # first paragraph under the H1 rather than in a description key.
            m = re.search(r"^Skill-Name:\s*(\S.*)$", text, re.M)
            if not m:
                continue
            name, fmt = m.group(1).strip(), "Skill-Name + first paragraph"
            body = re.split(r"^# .*$", text, maxsplit=1, flags=re.M)
            para = ""
            if len(body) > 1:
                for chunk in body[1].split("\n\n"):
                    if chunk.strip() and not chunk.lstrip().startswith(("#", "```")):
                        para = " ".join(chunk.split())
                        break
            desc = para
        if not desc:
            continue
        rows.append((name, desc, f"format: {fmt}", path, name))
    return rows


def triggers(root: pathlib.Path) -> list[tuple]:
    """When the skill fires — a different claim from what it does."""
    rows = []
    for path in skills(root):
        text = path.read_text(encoding="utf-8")
        fm = common.frontmatter(text)
        name = fm.get("name") or path.parent.name
        for heading, block in common.sections(text):
            if heading.lower().strip() not in TRIGGER_HEADINGS:
                continue
            body = " ".join(block.splitlines()[1:])
            body = " ".join(re.sub(r"^[-*]\s*", "", body).split())
            if len(body) < 6:
                continue
            rows.append((name, body[:600], f"section: {heading}", path, heading))
    return rows


def frameworks(root: pathlib.Path) -> list[tuple]:
    """`MANIFEST.json` — the only place in the repo that versions anything."""
    path = root / "MANIFEST.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [(f["id"], f"{f.get('version', '?')} @ {f.get('path', '?')}",
             "MANIFEST.json frameworks[]", path, "frameworks")
            for f in data.get("frameworks", [])]


def definitions(root: pathlib.Path) -> list[tuple]:
    rows = []
    for path, heading, header, row in common.tables(root):
        if header[0] not in DEFN_KEYS:
            continue
        tgt = " · ".join(c for c in row[1:] if c)
        if len(row[0]) < 2 or len(tgt) < 4:
            continue
        rows.append((row[0], tgt, f"columns: {' | '.join(header)}", path, heading))
    return rows


def declined(root: pathlib.Path) -> collections.Counter:
    out: collections.Counter = collections.Counter()
    for _p, _h, header, row in common.tables(root):
        if header[0] in DEFN_KEYS:
            continue
        if len(row[0]) < 2 or len(" · ".join(row[1:])) < 4:
            continue
        out[" | ".join(header)] += 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    root = pathlib.Path(args.repo).resolve()
    out = pathlib.Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    origin = provenance.Origin("aionic", root, __file__)
    plan = [
        ("skill", described(root), "skill", "description"),
        ("trigger", triggers(root), "skill", "trigger"),
        ("framework", frameworks(root), "framework", "version"),
        ("definition", definitions(root), "term", "term"),
    ]

    store = SqliteStore(str(out))
    store.memory_init()
    try:
        common.load(store, plan, origin, declined(root))
    finally:
        store.close()
    print(f"\n  store: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
