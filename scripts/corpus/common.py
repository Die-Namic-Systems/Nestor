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

import ast
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


def frontmatter(text: str) -> dict[str, str]:
    """Scalar keys of a leading ``---`` block. ``{}`` when there is none.

    Deliberately not a YAML parser: nested and list values are skipped rather
    than half-read, so a caller can trust that a key present here had a scalar
    on one line. The corpus is full of documents whose front matter is
    hand-written and only mostly valid.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    out: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        m = re.match(r"^([A-Za-z][\w-]*):\s*(\S.*)$", line)
        if m:
            out[m.group(1).lower()] = m.group(2).strip().strip("\"'")
    return out


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


def findings(root: pathlib.Path) -> list[tuple]:
    """``### P1: XX-YY-01 — title`` with a recommended fix.

    Shared rather than per-repository: this shape has now appeared in three
    checkouts unchanged, which makes it a convention of the author rather than
    a feature of any one repository.
    """
    rows = []
    for path in docs(root):
        for heading, block in sections(path.read_text(encoding="utf-8")):
            m = re.match(r"^(P\d):\s*([A-Z][A-Z0-9]*-[A-Z]+-\d+)\s*[—-]\s*(.+)$", heading)
            if not m:
                continue
            severity, ident, title = m.groups()
            fix = field(block, "Recommended fix")
            if not fix:
                continue
            status = field(block, "Status")
            rows.append((f"{ident} — {title}", fix,
                         f"severity {severity}" + (f", status {status}" if status else ""),
                         path, ident))
    return rows


def rubric(root: pathlib.Path) -> list[tuple]:
    """``# | Check | Status | Notes`` — a check and the verdict it got.

    Declined as noise through rungs 3 and 4, fifteen rows in each, and visible
    only because the declined rows were printed by header. It is the author's
    standing security rubric, so the check is the claim and the status is the
    answer. The two earlier rungs undercount by those rows; their entries state
    what was measured at the time and their stores can be rebuilt from here.
    """
    rows = []
    for path, heading, header, row in tables(root):
        if header[:2] != ["#", "check"] or len(row) < 3:
            continue
        notes = row[3] if len(row) > 3 else ""
        rows.append((row[1], row[2], f"{row[0]}: {notes}"[:400], path, heading))
    return rows


def docstrings(root: pathlib.Path) -> tuple[list[tuple], int]:
    """``path::symbol → its docstring``, and how many definitions there were.

    A docstring is a declaration, not an inference: the author wrote what the
    thing is for, beside the thing. The second return value is the denominator,
    because a docstring corpus without its coverage says nothing — see §6.45.

    **The key is qualified by file, and that is not cosmetic.** Keyed on the bare
    symbol, rung 6 raised 54 collisions, nearly all of them two unrelated
    functions that happen to share a name — §6.42's lesson arriving in a second
    domain: a collision is evidence about the key before it is evidence about
    the corpus. Qualifying the key removes the false ones and leaves the real
    question (two implementations of one interface that disagree) to be asked
    deliberately rather than as a parser artefact.
    """
    rows: list[tuple] = []
    total = 0
    for path in sorted(root.rglob("*.py")):
        if ".git" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        rel = path.relative_to(root)
        module_doc = ast.get_docstring(tree)
        total += 1
        if module_doc:
            rows.append((str(rel), " ".join(module_doc.split())[:600],
                         "module docstring", path, path.stem))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            total += 1
            doc = ast.get_docstring(node)
            if not doc:
                continue
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            rows.append((f"{rel}::{node.name}", " ".join(doc.split())[:600],
                         f"{kind} docstring", path, node.name))
    return rows, total


def load(store, plan, origin, declined: collections.Counter | None = None,
         root: pathlib.Path | None = None) -> dict:
    """Add every row as a draft. Returns ``memory.stats``; prints as it goes.

    ``plan`` is a list of ``(shape, rows, source_lang, target_lang)`` where each
    row is ``(source, target, reason, path, anchor)``.

    Pass ``root`` to get a **coverage** report: which documents produced no row
    at all. §6.44 is the reason it exists. Two duplicate skills sat in a
    repository, one of them empty, and the store raised no collision — not
    because they agreed but because neither ever reached it. A silent store
    cannot distinguish "consistent" from "absent", so any claim about corpus
    consistency needs the coverage number printed beside it or it cannot be
    falsified.
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

    if root is not None:
        touched = {pathlib.Path(r[3]).resolve()
                   for _shape, rows, _sl, _tl in plan for r in rows}
        every = [p.resolve() for p in docs(root)]
        silent = [p for p in every if p not in touched]
        print(f"\n  coverage: {len(every) - len(silent)}/{len(every)} document(s) "
              f"produced at least one row")
        for p in silent[:10]:
            print(f"    silent  {p.relative_to(root.resolve())}")
        if len(silent) > 10:
            print(f"    … and {len(silent) - 10} more")

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
