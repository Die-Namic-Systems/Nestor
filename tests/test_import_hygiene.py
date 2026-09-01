"""The fifteen hand-corrections that made this suite collectable beside a
sibling repo, held by a check instead of by memory.

`tests/` has no `__init__.py`, so `tests` is a NAMESPACE package, and a
regular package earlier on `sys.path` beats one. With another tree on
PYTHONPATH whose test directory *is* a package — willows-grove, on a fleet
standup — the dotted form resolves to that tree's module and collection dies.
Measured against this repo with a stub package on the path: 2233 collected
with 9 errors, against 2306 clean.

The bare form holds because pytest's prepend import mode puts each test
file's own directory at ``sys.path[0]`` before importing it, so this repo's
helpers win regardless of what else is importable.

Fifteen modules were corrected by hand. Nothing stopped the sixteenth, which
is the shape TODO.md's closing section names: a guarantee enforced by
convention at call sites, with a second path in that never passes it. This is
the one place that cannot be walked around, because it reads every file.
"""
from __future__ import annotations

import pathlib
import re

TESTS = pathlib.Path(__file__).resolve().parent

#: A dotted import of this repo's own test package, at the start of a
#: statement. Anchored with ``^\s*`` rather than matched anywhere, so prose in
#: a docstring that happens to name the pattern is not a finding — only real
#: import statements are.
DOTTED = re.compile(r"^\s*(?:from\s+tests(?:\.|\s+import\b)|import\s+tests\b)",
                    re.MULTILINE)


def offenders(text: str) -> list[str]:
    """Every line in ``text`` that imports through the ``tests`` package."""
    return [line.strip() for line in text.splitlines() if DOTTED.match(line)]


def test_no_module_under_tests_imports_the_tests_package():
    found = {}
    scanned = 0
    for path in sorted(TESTS.rglob("*.py")):
        scanned += 1
        hits = offenders(path.read_text(encoding="utf-8"))
        if hits:
            found[path.relative_to(TESTS.parent).as_posix()] = hits

    assert scanned > 100, (
        f"only {scanned} file(s) scanned — the glob stopped seeing the suite, "
        f"which would make this check pass on an empty set")
    assert not found, (
        "these import through the `tests` package, which breaks collection "
        "when another tree's test package is on PYTHONPATH — use the bare "
        f"module name instead (`from conftest import ...`):\n{found}")


def test_the_check_would_actually_catch_one():
    """A scan that matches nothing passes forever whether or not it works.

    The forbidden forms are assembled from fragments rather than written out,
    so this file does not trip its own scan and need exempting from it — an
    exemption is the second path the check exists to close. Each form is
    asserted on its own line, so a regression names which one stopped being
    caught.
    """
    for form in ("tests.conftest import read_ledger",
                 "tests import conftest",
                 "tests._fleet_paths import jeles_checkout"):
        line = "from " + form
        assert offenders(line) == [line], line
    plain = "import " + "tests.conftest"
    assert offenders(plain) == [plain], plain
    indented = "    from " + "tests.conftest import read_ledger"
    assert offenders(indented) == [indented.strip()], indented


def test_the_check_does_not_fire_on_what_it_should_allow():
    """The bare imports #268 moved to, and mentions that are not imports.

    A guard with false positives gets exempted, and an exemption is how the
    convention got walked around in the first place.
    """
    for line in ("from conftest import read_ledger",
                 "from _fleet_paths import jeles_checkout",
                 "import conftest",
                 "from nestor import memory",
                 "from nestor.sqlite_store import SqliteStore",
                 "# from " + "tests.conftest import x — a comment, not an import",
                 '"""A docstring may name from ' + 'tests.conftest."""'):
        assert offenders(line) == [], line
