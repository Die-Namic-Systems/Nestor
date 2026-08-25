"""#97 / §6.105 — the decision-record ↔ corpus-extractor boundary is a gate.

The corpus extractors in ``scripts/corpus/`` read external checkouts; the
dogfood store built by ``scripts/dogfood_store.py`` reads *this* repository's
``docs/dogfood/decisions/*.json``. The two stores are deliberately separate —
mixing them would let a corpus import carry a decision that never went
through a PR, which is the thing the decision store's remote-to-local rule
exists to prevent.

The boundary was already documented in the module docstring of
``scripts/corpus/common.py`` (cites ``docs/two-stores.md``). This file makes
the same boundary a *gate*: option (b) of the issue's acceptance criterion —
*"a test asserting the boundary, so the separation is a declared decision
rather than an accident a reader has to reconstruct."*

Two assertions, one for each side of drift:

* **No extractor reads the decision record.** Grep every
  ``scripts/corpus/extract_*.py`` (and the shared ``common.py`` /
  ``provenance.py``) for the path ``docs/dogfood/decisions``. A hit would
  mean an extractor has quietly started routing decision-store rows into a
  corpus store — the exact mix the boundary refuses.
* **The docstring boundary still names it.** A reader looking at
  ``scripts/corpus/common.py`` must find the sentence that says the
  omission is deliberate. If someone deletes or reflows the docstring, this
  test breaks and points them at the file that carries the rule.
"""
from __future__ import annotations

import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
CORPUS = REPO_ROOT / "scripts" / "corpus"


def _extractor_and_shared_files() -> list[pathlib.Path]:
    """Every corpus extractor plus the modules they all import.

    The path of the finding is any of these files quietly gaining a reader
    for ``docs/dogfood/decisions/``; the assertion covers the whole surface,
    not only the ``extract_*`` entrypoints — a helper in ``common.py`` that
    read the decision record would show up as *no* extractor touching it and
    yet the corpus stores carrying its rows.
    """
    files = sorted(CORPUS.glob("extract_*.py"))
    files += [CORPUS / "common.py", CORPUS / "provenance.py"]
    return [p for p in files if p.exists()]


def test_no_corpus_extractor_reads_the_decision_record():
    offenders = []
    for path in _extractor_and_shared_files():
        text = path.read_text(encoding="utf-8")
        # Look for the path in code, not in prose that mentions it as an
        # example of what NOT to do — a comment or docstring saying
        # "docs/dogfood/decisions" is fine, an open() or Path() on it is not.
        # Simplest defensible check: a bare occurrence of the path outside a
        # comment / docstring is a hit. Docstrings and comments are stripped
        # by a coarse regex first, then we grep the remainder.
        stripped = _strip_comments_and_docstrings(text)
        if "docs/dogfood/decisions" in stripped:
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, (
        f"corpus extractor(s) touched the decision record: {offenders}. "
        f"The dogfood store (scripts/dogfood_store.py) is the only reader of "
        f"docs/dogfood/decisions/*.json by design — see the module docstring "
        f"of scripts/corpus/common.py and docs/two-stores.md.")


def test_the_module_docstring_still_names_the_boundary():
    """The doc-gate half. If someone rewrites ``scripts/corpus/common.py``'s
    docstring and drops the boundary sentence, a reader loses the *reason*
    the extractor set omits the decision record — and the omission stops
    being a declared decision and starts being an accident.
    """
    text = (CORPUS / "common.py").read_text(encoding="utf-8")
    docstring = _module_docstring(text)
    assert docstring, "scripts/corpus/common.py has no module docstring"
    lowered = docstring.lower()
    # Two anchors, both from the current sentence:
    assert "decision" in lowered, (
        "scripts/corpus/common.py docstring no longer mentions the "
        "decision record — the boundary against docs/dogfood/decisions/ "
        "is undocumented (issue #97 / §6.105).")
    assert "dogfood" in lowered or "two-stores" in lowered, (
        "scripts/corpus/common.py docstring names 'decision' but no longer "
        "cites the dogfood store or docs/two-stores.md — the reason for "
        "the boundary is lost (issue #97 / §6.105).")


# --- helpers ---------------------------------------------------------------


_COMMENT_RE = re.compile(r"(?m)^\s*#.*$")
_TRIPLE_STRING_RE = re.compile(r'"""(?:.|\n)*?"""|\'\'\'(?:.|\n)*?\'\'\'')


def _strip_comments_and_docstrings(source: str) -> str:
    """Remove ``#`` comments and triple-quoted strings.

    Coarse on purpose: a triple-quoted string that is not a docstring (e.g. a
    heredoc-style constant) is also removed, which for these files' style
    (docstrings only) is close enough. The alternative — walking the AST to
    tell docstrings from other triple-quoted literals — is more machinery
    than the boundary check earns.
    """
    without_strings = _TRIPLE_STRING_RE.sub("", source)
    return _COMMENT_RE.sub("", without_strings)


def _module_docstring(source: str) -> str:
    m = _TRIPLE_STRING_RE.match(source.lstrip())
    return m.group(0) if m else ""
