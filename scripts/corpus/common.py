"""Markdown reading and draft loading, shared by the per-repo extractors.

The per-repo files declare *shapes* — the structures a particular repository
actually repeats. Everything mechanical lives here: walking the documents,
splitting tables, and the load loop.

Two behaviours in that loop are not incidental and should not be simplified
away:

**A refused row is reported with both origins.** `ConflictingDraftError` means
one key has two answers. §6.52 measured why that is not automatically a finding
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


def docs(root: pathlib.Path, only: set | None = None) -> list[pathlib.Path]:
    """Markdown under ``root``, optionally narrowed to ``only``.

    ``only`` exists for forks. A fork's tree is its upstream author's work, so
    the standard shapes are run over just the files the operator's own commits
    touched — see `docs/corpus-order.md`.
    """
    found = sorted(p for p in root.rglob("*.md") if ".git" not in p.parts)
    if only is None:
        return found
    return [p for p in found if p.resolve() in only]


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
    pending: str | None = None
    folded: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if pending is not None:
            # A block scalar's body is indented; anything at column 0 ends it.
            if line.startswith((" ", "\t")) and line.strip():
                folded.append(line.strip())
                continue
            out[pending] = " ".join(folded)
            pending, folded = None, []
        m = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", line)
        if not m:
            continue
        key, value = m.group(1).lower(), m.group(2).strip()
        if value in (">", ">-", "|", "|-"):
            # Folded/literal block scalar. Skipping these cost rung 17 every
            # skill it had: the value is a plain string, just written across
            # lines, and refusing it is not the same caution as refusing a list.
            pending, folded = key, []
        elif value:
            out[key] = value.strip("\"'")
    if pending is not None and folded:
        out[pending] = " ".join(folded)
    return out


def cells(line: str) -> list[str]:
    return [c.strip().strip("*").strip() for c in line.strip().strip("|").split("|")]


def is_rule(line: str) -> bool:
    """The ``|---|---|`` separator, which is layout rather than data."""
    return set(line.replace("|", "")) <= set("-: ")


def tables(root: pathlib.Path, only: set | None = None) -> Iterator[tuple[pathlib.Path, str, list[str], list[str]]]:
    """``(path, heading, header, row)`` for every data row of every table."""
    for path in docs(root, only):
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


def findings(root: pathlib.Path, only: set | None = None) -> list[tuple]:
    """``### P1: XX-YY-01 — title`` with a recommended fix.

    Shared rather than per-repository: this shape has now appeared in three
    checkouts unchanged, which makes it a convention of the author rather than
    a feature of any one repository.
    """
    rows = []
    for path in docs(root, only):
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


def constraints(root: pathlib.Path, only: set | None = None) -> list[tuple]:
    """``HS-*`` / ``GOV-*`` blocks: the constraint, and what happens on trigger.

    Rung 1's shape, met again at rung 35 in an archive that carries copies of the
    governance documents. Two repositories makes it the author's convention, the
    same argument that moved `findings` at rung 5 and `rubric` at rung 6.
    """
    rows = []
    for path in docs(root, only):
        for heading, block in sections(path.read_text(encoding="utf-8")):
            ident = heading.split(":")[0].strip()
            if not ident.startswith(("HS-", "GOV-")):
                continue
            constraint = field(block, "Constraint")
            # A stop states its commitment as a Response, or as Rules where the
            # commitment is a list.
            target = field(block, "Response") or field(block, "Rules")
            if not (constraint and target):
                continue
            trigger = field(block, "Trigger")
            rows.append((f"{ident} — {constraint}", target,
                         f"Trigger: {trigger}" if trigger else "", path, ident))
    return rows


def rubric(root: pathlib.Path, only: set | None = None) -> list[tuple]:
    """``# | Check | Status | Notes`` — a check and the verdict it got.

    Declined as noise through rungs 3 and 4, fifteen rows in each, and visible
    only because the declined rows were printed by header. It is the author's
    standing security rubric, so the check is the claim and the status is the
    answer. The two earlier rungs undercount by those rows; their entries state
    what was measured at the time and their stores can be rebuilt from here.
    """
    rows = []
    for path, heading, header, row in tables(root, only):
        if header[:2] != ["#", "check"] or len(row) < 3:
            continue
        notes = row[3] if len(row) > 3 else ""
        rows.append((row[1], row[2], f"{row[0]}: {notes}"[:400], path, heading))
    return rows


def docstrings(root: pathlib.Path, only: set | None = None) -> tuple[list[tuple], int]:
    """``path::symbol → its docstring``, and how many definitions there were.

    A docstring is a declaration, not an inference: the author wrote what the
    thing is for, beside the thing. The second return value is the denominator,
    because a docstring corpus without its coverage says nothing — see §6.55.

    **The key is qualified by file, and that is not cosmetic.** Keyed on the bare
    symbol, rung 6 raised 54 collisions, nearly all of them two unrelated
    functions that happen to share a name — §6.52's lesson arriving in a second
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
        if only is not None and path.resolve() not in only:
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


def labelled(root: pathlib.Path, label: str, minimum: int = 12,
             only: set | None = None) -> list[tuple]:
    """``(document title -> **label:** value)`` wherever the label appears.

    The plan schema — ``Goal`` / ``Architecture`` / ``Tech Stack`` / ``Success``
    — first met in rung 6 and again in rung 14. Two repositories sharing a
    schema makes it the author's convention rather than one repository's
    feature, the same argument that moved ``findings`` here at rung 5.
    """
    rows = []
    for path in docs(root, only):
        text = path.read_text(encoding="utf-8")
        value = field(text, label)
        if len(value) < minimum:
            continue
        why = " | ".join(x for x in (
            f"Architecture: {field(text, 'Architecture')[:200]}"
            if field(text, "Architecture") else "",
            f"Tech Stack: {field(text, 'Tech Stack')[:120]}"
            if field(text, "Tech Stack") else "",
        ) if x)
        m = re.search(r"^#\s+(.+)$", text, re.M)
        title = " ".join(m.group(1).split()) if m else path.stem
        rows.append((title, value[:600], why, path, label.lower()))
    return rows


DEFAULT_DEFN_KEYS = ("term", "concept", "field", "name", "command", "tool",
                     "env var", "option", "key", "module", "file", "idiom",
                     "pattern", "skill", "table", "column", "path")


def definitions(root: pathlib.Path, defn_keys=DEFAULT_DEFN_KEYS, only: set | None = None) -> list[tuple]:
    """Tables whose first column is named as a term."""
    rows = []
    for path, heading, header, row in tables(root, only):
        if header[0] not in defn_keys:
            continue
        target = " · ".join(c for c in row[1:] if c)
        if len(row[0]) < 2 or len(target) < 4:
            continue
        rows.append((row[0], target, f"columns: {' | '.join(header)}", path, heading))
    return rows


def unclaimed(root: pathlib.Path, defn_keys=DEFAULT_DEFN_KEYS, only: set | None = None) -> collections.Counter:
    """Table rows the standard shapes do not take, by header."""
    out: collections.Counter = collections.Counter()
    for _path, _heading, header, row in tables(root, only):
        if header[0] in defn_keys or header[:2] == ["#", "check"]:
            continue
        if len(row[0]) < 2 or len(" · ".join(row[1:])) < 4:
            continue
        out[" | ".join(header)] += 1
    return out


def skills(root: pathlib.Path, only: set | None = None) -> list[tuple]:
    """``SKILL.md`` front matter: the skill's name and what it is for.

    Present in four of the operator's own repositories, which is the bar this
    corpus uses for a shape belonging in `common` rather than in one extractor.
    Rung 3 met 26 of them and got a bespoke reader; rung 17 met four written with
    folded block scalars and got none at all until `frontmatter` learned to read
    those, which is the only reason this is here rather than still repo-specific.
    """
    rows = []
    for path in sorted(root.rglob("SKILL.md")):
        if ".git" in path.parts:
            continue
        if only is not None and path.resolve() not in only:
            continue
        fm = frontmatter(path.read_text(encoding="utf-8"))
        name, desc = fm.get("name"), fm.get("description")
        if not (name and desc and len(desc) > 8):
            continue
        rows.append((name, desc[:600], "SKILL.md front matter", path, name))
    return rows


def standard(root: pathlib.Path, defn_keys=DEFAULT_DEFN_KEYS, only: set | None = None):
    """The four shapes every repository in this corpus has turned out to carry.

    Docstrings, the security rubric, identified findings, definitional tables.
    Written after rung 7 needed byte-for-byte what rung 5 needed: two
    repositories wanting the same extractor is the evidence, and a third copy of
    the same file would have been the kind of duplication this whole exercise
    exists to notice.

    Returns ``(plan, declined, symbols, defined)`` so a caller can prepend its
    own repository-specific shapes and still report both coverage denominators.
    """
    symbols, defined = docstrings(root, only)
    plan = [
        ("docstring", symbols, "symbol", "docstring"),
        ("skill", skills(root, only), "skill", "description"),
        ("rubric", rubric(root, only), "check", "verdict"),
        ("finding", findings(root, only), "finding", "fix"),
        ("definition", definitions(root, defn_keys, only), "term", "term"),
    ]
    return plan, unclaimed(root, defn_keys, only), symbols, defined


def normalize_key(source: str, source_lang: str, target_lang: str) -> tuple:
    """How the store itself keys a row, for counting distinct rows honestly."""
    return (memory.get_matcher().normalize(source), source_lang, target_lang)


def load(store, plan, origin, declined: collections.Counter | None = None,
         root: pathlib.Path | None = None) -> dict:
    """Add every row as a draft. Returns ``memory.stats``; prints as it goes.

    ``plan`` is a list of ``(shape, rows, source_lang, target_lang)`` where each
    row is ``(source, target, reason, path, anchor)``.

    Pass ``root`` to get a **coverage** report: which documents produced no row
    at all. §6.54 is the reason it exists. Two duplicate skills sat in a
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
        seen: set = set()
        for src, tgt, reason, path, anchor in rows:
            where = origin.of(path, anchor, shape)
            try:
                memory.add_pair(src, tgt, sl, tl, status="draft",
                                reason=reason, origin=where, store=store)
                added += 1
                seen.add(normalize_key(src, sl, tl))
            except memory.ConflictingDraftError:
                hits = memory.lookup(src, sl, tl, limit=1, store=store)
                held = hits[0]["pair"] if hits else {}
                collisions.append((shape, src, held.get("target_text", "?"), tgt,
                                   held.get("origin", "?"), where))
                clashed += 1
        # `added` counts accepted calls; `seen` counts the rows they became.
        # `add_pair` returns the stored row for an exact restatement rather than
        # raising, so the two differ whenever a source repeats a claim verbatim —
        # quiet-corner offers `id -> INTEGER PK` in 32 separate schema tables.
        # Printing only the first number overstates a shape's contribution, and
        # this loop printed it beside the row total for twenty rungs.
        dupes = added - len(seen)
        print(f"  {shape:18} {len(seen):4} row(s)"
              + (f" from {added} add(s)" if dupes else "")
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
