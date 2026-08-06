"""Markdown reading and draft loading, shared by the per-repo extractors.

The per-repo files declare *shapes* — the structures a particular repository
actually repeats. Everything mechanical lives here: walking the documents,
splitting tables, and the load loop.

Two behaviours in that loop are not incidental and should not be simplified
away:

**A refused row is reported with both origins.** `ConflictingDraftError` means
one key has two answers. §6.42 measured why that is not automatically a finding
about the corpus: with a coarse key it is a finding about the parser, and the
only thing that separates the two cases is whether the held row and the new one
came from the same document. So the loop asks the store what it is holding and
prints both provenances, rather than printing a count.

**A declined row is counted, by header.** An extractor that silently ignores
78% of the candidate rows reads exactly like one that found nothing there.
"""
from __future__ import annotations

import collections
import pathlib
import re
from typing import Iterator

from nestor import memory

FIELD = r"\*\*{}:\*\*\s*(.+?)(?=\n\n|\n\*\*|\n#|\n---|\Z)"


def docs(root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(p for p in root.rglob("*.md") if ".git" not in p.parts)


def field(block: str, name: str) -> str:
    """A ``**Label:** value`` field, whitespace collapsed. ``""`` if absent."""
    m = re.search(FIELD.format(re.escape(name)), block, re.S)
    return " ".join(m.group(1).split()) if m else ""


def sections(text: str, depth: str = "{2,4}") -> Iterator[tuple[str, str]]:
    """``(heading, block)`` for each heading at the given depth."""
    for block in re.split(rf"^#{depth} ", text, flags=re.M)[1:]:
        yield block.splitlines()[0].strip(), block


def cells(line: str) -> list[str]:
    return [c.strip().strip("*").strip() for c in line.strip().strip("|").split("|")]


def is_rule(line: str) -> bool:
    """The ``|---|---|`` separator, which is layout rather than data."""
    return set(line.replace("|", "")) <= set("-: ")


def tables(root: pathlib.Path) -> Iterator[tuple[pathlib.Path, str, list[str], list[str]]]:
    """``(path, heading, header, row)`` for every data row of every table."""
    for path in docs(root):
        heading: str = ""
        header: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("#"):
                heading, header = line.lstrip("# ").strip(), []
                continue
            if not line.strip().startswith("|"):
                header = []
                continue
            row = cells(line)
            if not header:
                header = [c.lower() for c in row]
                continue
            if is_rule(line) or len(row) < 2:
                continue
            yield path, heading, header, row


def load(store, plan, origin, declined: collections.Counter | None = None) -> dict:
    """Add every row as a draft. Returns ``memory.stats``; prints as it goes.

    ``plan`` is a list of ``(shape, rows, source_lang, target_lang)`` where each
    row is ``(source, target, reason, path, anchor)``.
    """
    print(origin.banner())
    collisions: list[tuple] = []

    for shape, rows, sl, tl in plan:
        added = clashed = 0
        for src, tgt, reason, path, anchor in rows:
            where = origin.of(path, anchor, shape)
            try:
                memory.add_pair(src, tgt, sl, tl, status="draft",
                                reason=reason, origin=where, store=store)
                added += 1
            except memory.ConflictingDraftError:
                hits = memory.lookup(src, sl, tl, limit=1, store=store)
                held = hits[0]["pair"] if hits else {}
                collisions.append((shape, src, held.get("target_text", "?"), tgt,
                                   held.get("origin", "?"), where))
                clashed += 1
        print(f"  {shape:18} {added:4} draft(s)"
              + (f"   {clashed} collision(s)" if clashed else ""))

    stats = memory.stats(store=store)
    print(f"\n  {stats['total']} pair(s): {stats['draft']} draft, "
          f"{stats['sealed']} sealed")

    if declined:
        print(f"\n  not extracted: {sum(declined.values())} row(s) under "
              f"{len(declined)} header(s) no shape claims — top 6:")
        for header, n in declined.most_common(6):
            print(f"    {n:4}  {header[:78]}")

    if collisions:
        def doc(o: str) -> str:
            return o.split("#")[0]

        cross = [c for c in collisions if doc(c[4]) != doc(c[5])]
        print(f"\n  {len(collisions)} collision(s): {len(cross)} across documents, "
              f"{len(collisions) - len(cross)} within one")
        for shape, src, held, mine, ho, mo in cross[:8]:
            print(f"\n    [{shape}] {src[:66]}")
            print(f"      {doc(ho)}\n        {held[:92]}")
            print(f"      {doc(mo)}\n        {mine[:92]}")
    return stats
