"""G2-meta-scans-nestor — the meta-scan: every AST/grep-guard helper this suite
carries has been shown to catch something, by a test that *calls it*.

*A scan that has never fired has not been shown to check anything* is a rule
this repo already states in its own words — `tests/test_import_hygiene.py`'s
"a scan that matches nothing passes forever whether or not it works",
`tests/test_version.py`'s planted `SERVER_VERSION = "0.1.0"` (#292), and the
`--verify` gate's "silence from a check means nothing" (decision 0127). This
file is that rule turned into a test that reads the *other* test files: it
finds every module-level helper in ``tests/`` that is shaped like a
violation-scanner and asserts that some planted-violation test in the *same
file* runs that helper — directly, or through another helper it calls.

This file is not a fresh design: it is homestead-ledger's
`tests/test_scans_fire.py` (itself the sibling drift sweeps' meta-scan),
copied for its shape and re-grounded against this repo's own 170-odd test
files. The discovery rule and the plant rule below are theirs, verified here
rather than re-derived, because a meta-scan that disagreed between repos
about what counts as "planted" would be exactly the kind of drift the fleet
loop exists to close. Where a rule reported a helper of this repo's, the
helper got a plant; the rule was not narrowed to excuse it (decision 0236).

**Discovery is structural, not a naming convention.** A rule that only
matched a leading underscore or a stem list would miss a public
`check_payload_reach(...)` (an AST-walking scan spelled the way a helper
meant to be imported is spelled) and a grep-shaped `forbidden_word_hits(path)`
that reads a file and asks `"payload" in text` with no `ast` and no matching
stem at all — both are planted below, alongside the real thing. So the rule
is what a scan *does*:

* it parses or walks source (`ast.parse`, `ast.walk`), **or**
* it matches text with a pattern (`re.search`/`findall`/`finditer`/`match`/
  `fullmatch`/`compile`, or a module-level compiled pattern's `.search(…)`),
  **or**
* it reads a file's text (`.read_text()`/`.read_bytes()`) *and* asks a
  membership question of it (`x in text`, `x not in parts`) — the grep shape
  with no regex in it, which `tests/test_prompt_advisories_are_reachable.py`'s
  `_prompt_advisory_modules` is, **or**
* it walks a **module-level list of forbidden words** and asks membership of
  each — `[phrase for phrase in FORBIDDEN_PHRASES if phrase in checked]`. The
  rule is narrow on purpose — the iteration must be over a module-level
  *collection* constant and the body must ask an `in` question — because
  "references a constant and says `in` somewhere" reports ordinary
  behaviour tests, and a meta-scan that cries wolf gets an allowlist bolted
  to it and stops meaning anything, **or**
* it filters the *caller's* terms by membership of the loop variable itself
  (`[term for term in terms if term in haystack]`), the same grep with the
  list hoisted to the caller.

The name stems and the `_is_` prefix are kept on top of that, not instead of
it: they still catch helpers that hand their work to a caller
(`tests/test_decision_check_matcher.py::_run_decision_check` runs the real
CLI and is found by its stem). Discovery is a union, so it is strictly wider
than either half alone.

**Having a plant means a plant test calls the scan.** A test called
`test_the_guard_can_fail` that never touches the guard has not fired it — the
word in a test's name is not the evidence, and this repo shipped exactly
that shape in `tests/test_prompt_advisories_are_reachable.py` until this
bite rewrote it. A helper counts as planted only when a `test_*` function
whose name carries `plant`, `fires` or `catches`, or whose docstring carries
`plant`, reaches it — through the module's own helpers as well as directly,
so a plant that calls a wrapper has exercised the parser underneath it too.

**Honest about what it still cannot see.** A helper that reaches `ast.parse`
through an alias (`from ast import parse as p`), one that shells out to
`grep`, or one whose whole check is a comparison of two already-read strings
with no membership test and no pattern, is outside the rule above. Closing
those needs an interpreter, not a reader; this scan is the AST-grep half, not
a promise that it sees everything a scan could be shaped like. Scans written
inline in a test body are the second half of this file, held to a
shrink-only ledger rather than to zero — see `INLINE_SCAN_LEDGER`.
"""
from __future__ import annotations

import ast
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent

#: Word-stems the repo's own scan helpers already use, split on "_" so
#: `_version_literal_hits`-style and `_run_decision_check`-style names both
#: match without over-firing on unrelated names.
_NAME_TOKENS = frozenset(
    {"scan", "scans", "reads", "calls", "offenders", "uses", "check", "checks",
     "guard", "guards"}
)

#: The convention this repo actually uses for "this scan was shown to fire on
#: a planted violation" — read off the real test names
#: (`test_the_hidden_version_literal_scan_actually_fires`,
#: `test_a_stale_precommit_rev_is_refused`'s "Planted:" docstring), not
#: guessed. The word is necessary; calling the scan is what makes it count.
_PLANT_NAME_WORDS = ("plant", "fires", "catches")

#: In a *docstring*, only "plant" counts. "fires" and "catches" are ordinary
#: prose about the thing under test — this repo's docstrings say "the guard
#: fires" and "nothing catches it" about hooks and ledgers, not about a plant
#: — and a word that common in a repo's own subject matter cannot also be
#: its evidence of a plant.
_PLANT_DOC_WORDS = ("plant",)

#: Pattern-matching methods. Matched on the attribute name alone, so both
#: `re.search(...)` and a module-level `_VERSION_LITERAL.findall(...)` count —
#: a compiled pattern is the same scan with the compile hoisted.
_MATCH_CALLS = frozenset(
    {"search", "findall", "finditer", "match", "fullmatch", "compile"}
)

#: Reading a file's text through `pathlib`. The grep half of a grep-shaped
#: scan, in the spelling this suite reaches for first.
_TEXT_READS = frozenset({"read_text", "read_bytes"})

#: The same read through an already-open handle — `open(p).read()` and the
#: `with open(p) as f: f.read()` spelling of it.
_HANDLE_READS = frozenset({"read", "readlines", "readline"})

#: Wrappers a read may be decoded or normalised through before the
#: membership question is asked — `p.read_bytes().decode()` is the same read
#: of the same file, and the text it yields is the text actually read.
_TEXT_WRAPPERS = frozenset({"decode", "strip", "lower", "upper", "casefold"})

#: Reading a module's source without naming a path. `inspect.getsource(obj)`
#: returns the real file's text; `tests/test_prompt_advisories_are_reachable.py`
#: reads the joiner that way.
_SOURCE_READS = frozenset({"getsource", "getsourcelines"})


def _is_open_call(expr: ast.AST) -> bool:
    """A builtin `open(...)`, however its mode and encoding are spelled."""
    return (
        isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Name)
        and expr.func.id == "open"
    )


def _open_handles(node: ast.AST) -> frozenset[str]:
    """Every local name bound to an `open(...)` — `with open(p) as f` and
    `f = open(p)` alike — so `f.read()` is recognised as the file read it
    is."""
    names: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.withitem) and _is_open_call(sub.context_expr):
            if isinstance(sub.optional_vars, ast.Name):
                names.add(sub.optional_vars.id)
        elif isinstance(sub, ast.Assign) and _is_open_call(sub.value):
            names.update(t.id for t in sub.targets if isinstance(t, ast.Name))
    return frozenset(names)


def _is_read_call(expr: ast.AST, handles: frozenset[str] = frozenset()) -> bool:
    """True if `expr` itself reads a real file's text — `.read_text()`/
    `.read_bytes()`, `open(...).read()` or an open handle's `.read()`, or
    `inspect.getsource(...)` — through any number of decoding wrappers."""
    if not isinstance(expr, ast.Call) or not isinstance(expr.func, ast.Attribute):
        return False
    attr = expr.func.attr
    if attr in _TEXT_READS or attr in _SOURCE_READS:
        return True
    if attr in _HANDLE_READS:
        return _is_open_call(expr.func.value) or (
            isinstance(expr.func.value, ast.Name) and expr.func.value.id in handles
        )
    if attr in _TEXT_WRAPPERS:
        return _is_read_call(expr.func.value, handles)
    return False


def _calls_in(node: ast.AST):
    """Every `Call` anywhere inside `node`."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            yield sub


def _walks_source(node: ast.AST) -> bool:
    """True if the body calls `ast.parse(...)` or `ast.walk(...)` — the shape
    of a scan that reads source rather than trusting an already-parsed tree."""
    return any(
        isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "ast"
        and call.func.attr in ("parse", "walk")
        for call in _calls_in(node)
    )


def _matches_text(node: ast.AST) -> bool:
    """True if the body runs a pattern over text — `re.search(...)`, a
    compiled pattern's `.finditer(...)`, or a bare `compile(...)`."""
    for call in _calls_in(node):
        if isinstance(call.func, ast.Attribute) and call.func.attr in _MATCH_CALLS:
            return True
        if isinstance(call.func, ast.Name) and call.func.id == "compile":
            return True
    return False


def _reads_file_text(node: ast.AST) -> bool:
    """True if the body reads a file's text itself, in any of the spellings
    `_is_read_call` knows."""
    handles = _open_handles(node)
    return any(_is_read_call(call, handles) for call in _calls_in(node))


def _tests_membership(node: ast.AST) -> bool:
    """True if the body asks `x in y` / `x not in y` anywhere — the grep
    question, once the text is in hand."""
    return any(
        isinstance(sub, ast.Compare)
        and any(isinstance(op, (ast.In, ast.NotIn)) for op in sub.ops)
        for sub in ast.walk(node)
    )


def _module_collection_constants(tree: ast.Module) -> frozenset[str]:
    """Every module-level `ALL_CAPS` name bound to a collection literal (or to
    `frozenset(...)`/`set(...)`/`tuple(...)`/`list(...)`) — the shape a
    forbidden-word list is written in, in this repo and its siblings."""
    found: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not (isinstance(target, ast.Name) and target.id.isupper()):
                continue
            value = node.value
            if isinstance(value, (ast.Set, ast.List, ast.Tuple)) or (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name)
                and value.func.id in ("frozenset", "set", "tuple", "list")
            ):
                found.add(target.id)
    return frozenset(found)


def _scans_a_word_list(node: ast.AST, constants: frozenset[str]) -> bool:
    """True if the body iterates one of `constants` and asks a membership
    question inside that iteration — the forbidden-word-list scan."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.For):
            iterables, body = [sub.iter], sub.body
        elif isinstance(sub, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            iterables, body = [g.iter for g in sub.generators], [sub]
        else:
            continue
        if not any(
            isinstance(it, ast.Name) and it.id in constants for it in iterables
        ):
            continue
        if any(_tests_membership(part) for part in body):
            return True
    return False


def _decorator_name(dec: ast.AST) -> str:
    """A decorator's own terminal name: `pytest.fixture` -> "fixture",
    `pytest.mark.usefixtures(...)` -> "usefixtures"."""
    if isinstance(dec, ast.Call):
        dec = dec.func
    if isinstance(dec, ast.Attribute):
        return dec.attr
    if isinstance(dec, ast.Name):
        return dec.id
    return ""


def _filters_by_membership(node: ast.AST) -> bool:
    """True if the body loops over something and keeps the items that are
    (or are not) *in* something else — `[term for term in terms if term in
    haystack]`.

    `_scans_a_word_list` above wants the iterable to be a module-level
    constant, which is right for a helper owning its own forbidden list. A
    helper handed the terms as an argument is the same grep with the list
    hoisted to the caller. Narrow the same way: the membership question must
    be asked *of the loop variable itself*, so iterating a table and
    asserting something about a result is still not a scan.
    """
    for sub in ast.walk(node):
        if isinstance(sub, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
            targets = {
                gen.target.id for gen in sub.generators
                if isinstance(gen.target, ast.Name)
            }
            conditions = [cond for gen in sub.generators for cond in gen.ifs]
        elif isinstance(sub, ast.For) and isinstance(sub.target, ast.Name):
            targets, conditions = {sub.target.id}, list(sub.body)
        else:
            continue
        for condition in conditions:
            for inner in ast.walk(condition):
                if (
                    isinstance(inner, ast.Compare)
                    and any(isinstance(op, (ast.In, ast.NotIn)) for op in inner.ops)
                    and isinstance(inner.left, ast.Name)
                    and inner.left.id in targets
                ):
                    return True
    return False


def _is_fixture(node: ast.FunctionDef) -> bool:
    """`@pytest.fixture` — setup, not a scan, whatever it reads.

    Matched on the decorator's *own terminal name*, not on the word
    "fixture" appearing anywhere in its dump: `@pytest.mark.usefixtures(...)`
    carries that word and is not a fixture, and reading it as one would
    silently exempt the whole decorated test from both halves of this file.
    """
    return any(_decorator_name(dec) == "fixture" for dec in node.decorator_list)


def _is_scan_helper(
    node: ast.FunctionDef, constants: frozenset[str] = frozenset()
) -> bool:
    """A module-level helper counts as a scan/guard if it is shaped like one
    (walks source, matches a pattern, reads a file and asks a membership
    question of it, walks a module-level word list asking membership of
    each, or filters the caller's terms by membership) or its name carries
    one of the repo's own stems.

    Deliberately *not* conditioned on a leading underscore: a public
    `offenders(text)` (`tests/test_import_hygiene.py`) is the same scan with
    a different name.
    """
    name = node.name
    if name.startswith(("test_", "__")):
        return False
    if _is_fixture(node):
        return False
    if name.startswith("_is_"):
        return True
    if _NAME_TOKENS & set(name.strip("_").split("_")):
        return True
    return (
        _walks_source(node)
        or _matches_text(node)
        or (_reads_file_text(node) and _tests_membership(node))
        or _scans_a_word_list(node, constants)
        or _filters_by_membership(node)
    )


def _is_plant_test(node: ast.FunctionDef) -> bool:
    """True if `node` is a planted-violation test by this repo's convention:
    a plant word in its name, or the narrower "plant" in its docstring."""
    name = node.name.lower()
    doc = (ast.get_docstring(node) or "").lower()
    return any(word in name for word in _PLANT_NAME_WORDS) or any(
        word in doc for word in _PLANT_DOC_WORDS
    )


def _module_helpers(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    """Every module-level, non-test function in one tests module, by name."""
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("test_")
    }


def _scan_helpers(source: str) -> list[str]:
    """Every module-level scan-helper function name in one tests module."""
    tree = ast.parse(source)
    constants = _module_collection_constants(tree)
    return sorted(
        name
        for name, node in _module_helpers(tree).items()
        if _is_scan_helper(node, constants)
    )


def _direct_calls(node: ast.AST, known: dict[str, ast.FunctionDef]) -> set[str]:
    """The module's own helpers this node calls by bare name."""
    return {
        call.func.id
        for call in _calls_in(node)
        if isinstance(call.func, ast.Name) and call.func.id in known
    }


def _helpers_the_plants_exercise(source: str) -> set[str]:
    """Every helper reachable from a planted-violation test in this module.

    A test counts as a plant test when its **name** carries one of
    `_PLANT_NAME_WORDS`, or its docstring carries one of the narrower
    `_PLANT_DOC_WORDS`; from there the reach is transitive through the
    module's own helpers, because a plant that calls a wrapper has exercised
    the helper underneath it just as surely as if it had called it by hand.
    """
    tree = ast.parse(source)
    helpers = _module_helpers(tree)
    reached: set[str] = set()
    for node in tree.body:
        if not (isinstance(node, ast.FunctionDef) and node.name.startswith("test_")):
            continue
        if not _is_plant_test(node):
            continue
        pending = list(_direct_calls(node, helpers))
        while pending:
            name = pending.pop()
            if name in reached:
                continue
            reached.add(name)
            pending.extend(_direct_calls(helpers[name], helpers))
    return reached


def _unplanted_scan_helpers(source: str) -> list[str]:
    """The scan helpers in one tests module that no planted-violation test in
    the same module ever calls."""
    exercised = _helpers_the_plants_exercise(source)
    return [name for name in _scan_helpers(source) if name not in exercised]


#: A shared scan module, if this repo ever grows one. Not a `test_*.py` file,
#: so it would hold no plant tests of its own and the same-file rule above
#: could not reach it; its helpers are swept against plants anywhere in
#: `tests/` instead. This repo has none today — `tests/conftest.py` is
#: fixtures and a session hook, `tests/_fleet_paths.py` resolves sibling
#: checkouts and defines no scan-shaped helper — so the sweep is proven on a
#: planted module below rather than on a real one.
SHARED_SCANS = TESTS_DIR / "_scans.py"


def _import_aliases(tree: ast.Module) -> dict[str, str]:
    """`from _scans import terms_found as tf` -> `{"tf": "terms_found"}`,
    for imports anywhere in the module, function bodies included."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.asname:
                    aliases[alias.asname] = alias.name
    return aliases


def _called_names(node: ast.AST, aliases: dict[str, str]) -> set[str]:
    """Every name `node` calls: bare (resolved through `aliases`) or through
    an attribute — `helper(...)`, `tf(...)`, `module.helper(...)` are one
    delegation by three routes."""
    names: set[str] = set()
    for call in _calls_in(node):
        if isinstance(call.func, ast.Name):
            names.add(aliases.get(call.func.id, call.func.id))
        elif isinstance(call.func, ast.Attribute):
            names.add(call.func.attr)
    return names


def _names_the_plants_call(source: str) -> frozenset[str]:
    """Every name a planted-violation test in this module calls — directly,
    or through the module's own helpers, whichever module actually defines
    the name it calls."""
    tree = ast.parse(source)
    helpers = _module_helpers(tree)
    aliases = _import_aliases(tree)
    called: set[str] = set()
    walked: set[str] = set()
    for node in tree.body:
        if not (isinstance(node, ast.FunctionDef) and node.name.startswith("test_")):
            continue
        if not _is_plant_test(node):
            continue
        called |= _called_names(node, aliases)
        pending = list(_direct_calls(node, helpers))
        while pending:
            name = pending.pop()
            if name in walked:
                continue
            walked.add(name)
            called |= _called_names(helpers[name], aliases)
            pending.extend(_direct_calls(helpers[name], helpers))
    return frozenset(called)


def _unplanted_shared_scan_helpers(
    shared: Path = SHARED_SCANS, tests_dir: Path = TESTS_DIR
) -> list[str]:
    """The scan helpers in a shared module that no planted-violation test
    anywhere in `tests_dir` ever calls. Cross-module by construction: the
    shared module has no plant tests of its own, and the plant that proves a
    shared helper belongs with the caller that relies on it."""
    if not shared.exists():
        return []
    exercised: set[str] = set()
    for path in sorted(tests_dir.glob("test_*.py")):
        if path.name == "test_scans_fire.py":
            continue
        exercised |= _names_the_plants_call(path.read_text(encoding="utf-8"))
    return [
        name
        for name in _scan_helpers(shared.read_text(encoding="utf-8"))
        if name not in exercised
    ]


def _offenders() -> list[str]:
    """Every tests/*.py file that defines a scan helper no plant test in the
    same file calls — and the shared scan module, if there is one, whose
    helpers are held to a plant anywhere in `tests/`."""
    offenders = []
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        if path.name == "test_scans_fire.py":
            continue  # this file's own helpers are proven below, not here
        unplanted = _unplanted_scan_helpers(path.read_text(encoding="utf-8"))
        if unplanted:
            offenders.append(f"{path.name}: {unplanted}")
    shared_unplanted = _unplanted_shared_scan_helpers()
    if shared_unplanted:
        offenders.append(f"{SHARED_SCANS.name}: {shared_unplanted}")
    return offenders


def test_every_scan_helper_has_a_planted_violation_test():
    """The house rule, run for real: no `tests/*.py` file may carry an
    AST/grep-guard helper that no planted-violation test in the same file
    actually runs. On the day this file landed it reported eleven helpers in
    seven files; each got a plant in its own file rather than an exemption
    here."""
    offenders = _offenders()
    assert not offenders, (
        "these test files define a scan helper (it walks source, matches a "
        "pattern, or reads a file and asks a membership question of it — or "
        f"its name carries one of {sorted(_NAME_TOKENS)}) that no test naming "
        "plant/fires/catches ever calls — a scan that has never fired has not "
        f"been shown to check anything: {offenders}"
    )


# ── the discovery half, planted: AST-shaped, grep-shaped, regex-shaped ──────


def _write(tmp_path: Path, name: str, body: str) -> str:
    """A fake tests module on disk, read back the way `_offenders()` reads a
    real one."""
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path.read_text(encoding="utf-8")


def test_the_meta_scan_finds_an_ast_shaped_scan_whatever_it_is_named(tmp_path):
    """Planted: a scan that walks `ast` under a **public** name. A rule that
    required a leading underscore would miss `check_payload_reach` — the same
    scan, spelled the way a helper meant to be imported is spelled — and its
    missing plant would go unreported."""
    source = _write(
        tmp_path,
        "test_planted_ast_shaped_scan.py",
        "import ast\n"
        "\n"
        "def check_payload_reach(source):\n"
        "    return [n for n in ast.walk(ast.parse(source))\n"
        "            if isinstance(n, ast.Attribute) and n.attr == 'payload']\n"
        "\n"
        "def test_nothing_reaches_a_payload():\n"
        "    assert not check_payload_reach('x = 1\\n')\n",
    )

    assert _scan_helpers(source) == ["check_payload_reach"], (
        "an ast.parse/ast.walk scan must be found under any name, public or "
        f"private; got {_scan_helpers(source)}"
    )
    assert _unplanted_scan_helpers(source) == ["check_payload_reach"], (
        "and with no planted-violation test in the file it must be reported"
    )


def test_the_meta_scan_finds_a_grep_shaped_scan(tmp_path):
    """Planted: a scan with no `ast` in it at all — `path.read_text()` and an
    `in`. The repo has this shape already
    (`test_prompt_advisories_are_reachable.py::_prompt_advisory_modules`), and
    a discovery rule that only knew about `ast` would clear a file whose only
    guard is this shape."""
    source = _write(
        tmp_path,
        "test_planted_grep_shaped_scan.py",
        "def forbidden_word_hits(path):\n"
        "    return 'payload' in path.read_text(encoding='utf-8')\n"
        "\n"
        "def test_no_module_says_payload(tmp_path):\n"
        "    probe = tmp_path / 'm.py'\n"
        "    probe.write_text('x = 1\\n', encoding='utf-8')\n"
        "    assert not forbidden_word_hits(probe)\n",
    )

    assert _scan_helpers(source) == ["forbidden_word_hits"], (
        "a read_text()+`in` scan is a scan; the name carries none of the "
        f"repo's stems, which is the point. Got {_scan_helpers(source)}"
    )
    assert _unplanted_scan_helpers(source) == ["forbidden_word_hits"]


def test_the_meta_scan_finds_a_regex_shaped_scan(tmp_path):
    """Planted: a scan whose whole body is a module-level compiled pattern
    run over text — no `ast`, no `read_text`, and a name carrying none of the
    repo's stems. `tests/test_version.py::_version_literal_hits` is this
    shape."""
    source = _write(
        tmp_path,
        "test_planted_regex_shaped_scan.py",
        "import re\n"
        "\n"
        "_BANNED = re.compile(r'innerHTML')\n"
        "\n"
        "def banned_spellings(page):\n"
        "    return _BANNED.findall(page)\n"
        "\n"
        "def test_the_page_builds_no_markup():\n"
        "    assert not banned_spellings('x')\n",
    )

    assert _scan_helpers(source) == ["banned_spellings"], (
        f"a compiled-pattern scan is a scan; got {_scan_helpers(source)}"
    )
    assert _unplanted_scan_helpers(source) == ["banned_spellings"]


def test_the_meta_scan_finds_a_forbidden_word_list_scan(tmp_path):
    """Planted: the word-list shape. A helper that walks a module-level
    constant asking membership of text its caller hands it reads no file,
    compiles no pattern and parses no source, so the first three rules all
    clear it."""
    source = _write(
        tmp_path,
        "test_planted_word_list_scan.py",
        "FORBIDDEN_PHRASES = ('official form', 'you should file')\n"
        "\n"
        "def phrase_hits(text):\n"
        "    return [p for p in FORBIDDEN_PHRASES if p in text]\n"
        "\n"
        "def test_the_package_says_none_of_them():\n"
        "    assert not phrase_hits('a household keeps its own books')\n",
    )

    assert _scan_helpers(source) == ["phrase_hits"], (
        "a scan that walks a module-level word list asking membership of each "
        f"is a scan; got {_scan_helpers(source)}"
    )
    assert _unplanted_scan_helpers(source) == ["phrase_hits"]


def test_the_word_list_rule_does_not_fire_on_ordinary_constant_use(tmp_path):
    """The control the narrow rule exists for. A behaviour test that iterates
    a module-level table and asserts membership of a *result* is not a scan,
    and a rule loose enough to call it one gets itself allowlisted into
    silence."""
    source = _write(
        tmp_path,
        "test_planted_ordinary_constant_use.py",
        "CADENCES = ('monthly', 'weekly')\n"
        "\n"
        "def detect(rows):\n"
        "    return rows[0]\n"
        "\n"
        "def test_every_cadence_round_trips():\n"
        "    for c in CADENCES:\n"
        "        assert c in ('monthly', 'weekly', 'yearly')\n",
    )
    assert _scan_helpers(source) == []


def test_the_meta_scan_finds_a_scan_handed_its_word_list_by_the_caller(tmp_path):
    """Planted: the fifth shape. `terms_found(haystack, terms)` walks the
    *caller's* list asking membership of each — no module-level constant, no
    regex, no read, no stem in its name — so all four earlier rules clear
    it."""
    source = _write(
        tmp_path,
        "test_planted_caller_word_list.py",
        "def terms_found(haystack, terms):\n"
        "    return [term for term in terms if term in haystack]\n"
        "\n"
        "def test_the_log_carries_none_of_them():\n"
        "    assert not terms_found('a reference only', ('1234',))\n",
    )
    assert _scan_helpers(source) == ["terms_found"], (
        "a helper that filters the caller's terms by membership is a scan; "
        f"got {_scan_helpers(source)}"
    )
    assert _unplanted_scan_helpers(source) == ["terms_found"]


def test_the_caller_word_list_rule_does_not_fire_on_an_ordinary_filter(tmp_path):
    """The control the narrow half exists for: the membership question must
    be asked *of the loop variable itself*. A helper that filters rows by a
    field is ordinary code."""
    source = _write(
        tmp_path,
        "test_planted_ordinary_filter.py",
        "KNOWN = ('checking', 'savings')\n"
        "\n"
        "def due_rows(rows):\n"
        "    return [row for row in rows if row[1] in KNOWN]\n"
        "\n"
        "def test_it():\n"
        "    assert due_rows([]) == []\n",
    )
    assert _scan_helpers(source) == []


def test_a_fixture_is_not_mistaken_for_a_scan(tmp_path):
    """The other side of the same honesty: `@pytest.fixture` setup that reads
    a file must not be reported, or the meta-scan cries wolf on every suite
    that stages a tmp store."""
    source = _write(
        tmp_path,
        "test_planted_fixture_only.py",
        "import pytest\n"
        "\n"
        "@pytest.fixture\n"
        "def household(tmp_path):\n"
        "    (tmp_path / 'seed').write_text('x', encoding='utf-8')\n"
        "    return 'seed' in (tmp_path / 'seed').read_text(encoding='utf-8')\n"
        "\n"
        "def test_it(household):\n"
        "    assert household\n",
    )
    assert _scan_helpers(source) == []


# ── the plant half: naming a test "fires" is not having fired ────────────────


def test_the_plant_check_requires_the_plant_test_to_call_the_scan(tmp_path):
    """The counter-example, planted. A file whose only "plant" is a test
    *named* `test_the_scan_fires` and whose body never touches the scan must
    still be reported — a plant word in a name is not a plant. This repo
    shipped exactly this: `test_the_guard_can_fail` in
    `test_prompt_advisories_are_reachable.py` asserted a set literal and never
    called `_invoked_actions`."""
    source = _write(
        tmp_path,
        "test_planted_name_only_plant.py",
        "import ast\n"
        "\n"
        "def _payload_reaches(tree):\n"
        "    return [n for n in ast.walk(tree)\n"
        "            if isinstance(n, ast.Attribute) and n.attr == 'payload']\n"
        "\n"
        "def test_the_scan_fires_on_a_planted_violation():\n"
        "    '''Says it plants. Plants nothing.'''\n"
        "    assert True\n",
    )

    assert _scan_helpers(source) == ["_payload_reaches"]
    assert _unplanted_scan_helpers(source) == ["_payload_reaches"], (
        "a plant test that never calls the scan has not fired it; the word in "
        "the test's name is not the evidence"
    )


def test_a_plant_that_calls_the_scan_through_a_helper_clears_it(tmp_path):
    """And not over-strict: a real plant might call a wrapper rather than the
    parser underneath it. Reaching a helper through another helper is having
    exercised it, so neither may be reported."""
    source = _write(
        tmp_path,
        "test_planted_indirect_plant.py",
        "import ast\n"
        "\n"
        "def _payload_reaches(tree):\n"
        "    return [n for n in ast.walk(tree)\n"
        "            if isinstance(n, ast.Attribute) and n.attr == 'payload']\n"
        "\n"
        "def _offenders_in(source):\n"
        "    return _payload_reaches(ast.parse(source))\n"
        "\n"
        "def test_the_scan_catches_a_planted_reach():\n"
        "    assert _offenders_in('y = r.payload\\n')\n",
    )

    assert _scan_helpers(source) == ["_offenders_in", "_payload_reaches"]
    assert _unplanted_scan_helpers(source) == [], (
        "both the wrapper and the helper it calls were exercised by the plant"
    )


def test_a_docstring_saying_fires_about_something_else_does_not_clear_a_scan(tmp_path):
    """Planted: a test whose docstring says "the guard fires" — prose about the
    thing under test, not about a plant — must not clear a scan. Only "plant"
    counts in a docstring; "fires" and "catches" count in a test's name, where
    they are deliberate."""
    source = _write(
        tmp_path,
        "test_planted_prose_fires.py",
        "import ast\n"
        "\n"
        "def _reaches(tree):\n"
        "    return [n for n in ast.walk(tree) if isinstance(n, ast.Attribute)]\n"
        "\n"
        "def test_the_workflow_publishes():\n"
        "    '''No tag workflow fires, so nothing publishes and nothing catches it.'''\n"
        "    assert _reaches(ast.parse('a.b\\n'))\n",
    )

    assert _scan_helpers(source) == ["_reaches"]
    assert _unplanted_scan_helpers(source) == ["_reaches"], (
        "prose using the word 'fires' is not a plant; the scan is still "
        "unproven and must still be reported"
    )


def test_a_docstring_that_says_planted_does_clear_the_scan(tmp_path):
    """And the other side, so the tightening cannot be a blanket refusal: a
    test whose name carries no plant word but whose docstring says it plants,
    and which calls the scan, has fired it — this is how
    `test_import_hygiene.py::test_the_check_would_actually_catch_one` and
    `test_lint_pins_check.py::test_a_stale_precommit_rev_is_refused` count."""
    source = _write(
        tmp_path,
        "test_planted_docstring_plant.py",
        "import ast\n"
        "\n"
        "def _reaches(tree):\n"
        "    return [n for n in ast.walk(tree) if isinstance(n, ast.Attribute)]\n"
        "\n"
        "def test_a_reach_is_reported():\n"
        "    '''Planted: a module that does reach an attribute.'''\n"
        "    assert _reaches(ast.parse('a.b\\n'))\n",
    )
    assert _scan_helpers(source) == ["_reaches"]
    assert _unplanted_scan_helpers(source) == []


def test_the_plant_check_does_not_fire_on_a_real_guarded_file():
    """The whole thing against a real file of this repo's:
    `tests/test_version.py` defines `_version_literal_hits` (#292) and plants
    it in `test_the_hidden_version_literal_scan_actually_fires`, so the
    meta-scan must clear it — or it would be crying wolf on the very files it
    exists to clear."""
    source = (TESTS_DIR / "test_version.py").read_text(encoding="utf-8")
    assert "_version_literal_hits" in _scan_helpers(source), (
        "test_version.py is expected to define the version-literal scan")
    assert _unplanted_scan_helpers(source) == []


def test_the_shared_scan_sweep_holds_a_planted_shared_module_to_a_plant_anywhere(tmp_path):
    """Planted: a shared scan module with no tests of its own, swept against
    plants in the rest of the directory — reached through an import alias
    and through `module.helper(...)`, the routes a cross-module call actually
    takes. This repo has no `tests/_scans.py` today, so the sweep is proven
    here on a fake one rather than passing vacuously on an absent file."""
    shared = tmp_path / "_scans.py"
    shared.write_text(
        "def terms_found(haystack, terms):\n"
        "    return [term for term in terms if term in haystack]\n"
        "\n"
        "def other_helper(path):\n"
        "    return 'banned' in path.read_text(encoding='utf-8')\n",
        encoding="utf-8",
    )
    assert _unplanted_shared_scan_helpers(shared, tmp_path) == [
        "other_helper", "terms_found"
    ], "with no plant anywhere, every shared scan helper is reported"

    _write(
        tmp_path,
        "test_planted_aliased_plant.py",
        "from _scans import terms_found as tf\n"
        "import _scans\n"
        "\n"
        "def test_the_shared_scan_catches_a_planted_leak():\n"
        "    assert tf('a line naming 1234', ('1234',)) == ['1234']\n"
        "    assert _scans.other_helper('banned word')\n",
    )
    assert _unplanted_shared_scan_helpers(shared, tmp_path) == [], (
        "an aliased call and a `module.helper(...)` call are both calls")

    _write(
        tmp_path,
        "test_planted_aliased_plant.py",
        "from _scans import terms_found as tf\n"
        "\n"
        "def test_the_shared_scan_catches_a_planted_leak():\n"
        "    assert True\n",
    )
    assert _unplanted_shared_scan_helpers(shared, tmp_path) == [
        "other_helper", "terms_found"
    ], "importing a helper is not calling it; the plant word in the name is not the evidence"

    assert not SHARED_SCANS.exists(), (
        "tests/_scans.py appeared; the sweep above now runs against it for "
        "real in _offenders(), and this assertion should be retired")


# ── the inline half: a scan written directly in a test's own body ───────────
#
# Everything above reads *module-level helpers*. A guard written inline, in a
# test's own body, with nothing to name and nothing to plant, is invisible to
# it. This half walks every `test_*` function's own body for the same shapes
# the module-helper half already knows, holds it to the same "reads a file,
# not a string it built" requirement, and clears a test that delegates to a
# scan helper already defined (and already required to be planted) somewhere
# in `tests/` — recognised by name, whichever module actually owns it.
#
# "Reads a membership question of it" is held to the text actually read, not
# to anything built from it: a name bound directly to a `.read_text()`/
# `.read_bytes()` call (one level, no chain through `json.loads` or the
# like) counts; a dict key several steps removed does not. Loosening that
# would also catch `"x" in pyproject["project"]` and similar ordinary
# assertions that have nothing to do with scanning a tree.


#: String operations that narrow text without turning it into something
#: else: `source.split("def _route_post")[1]` is still the file's own text,
#: and a membership question of it is still a question of the tree.
_TEXT_SLICERS = _TEXT_WRAPPERS | frozenset(
    {"split", "rsplit", "splitlines", "partition", "rpartition", "replace",
     "lstrip", "rstrip", "removeprefix", "removesuffix"}
)


def _text_root(expr: ast.AST) -> ast.AST:
    """Peel subscripts and `_TEXT_SLICERS` calls off `expr` and return what
    the text ultimately came from."""
    while True:
        if isinstance(expr, ast.Subscript):
            expr = expr.value
        elif (
            isinstance(expr, ast.Call)
            and isinstance(expr.func, ast.Attribute)
            and expr.func.attr in _TEXT_SLICERS
        ):
            expr = expr.func.value
        else:
            return expr


def _direct_text_names(func: ast.FunctionDef) -> frozenset[str]:
    """Local names holding the text of a file this function read — bound
    straight from the read, or from a slice of one such name through
    `_TEXT_SLICERS` alone. Nothing that turns the text into another kind of
    object (`json.loads`, `tomllib.loads`) is traced."""
    handles = _open_handles(func)
    names: set[str] = set()
    assigns = [
        (
            [t.id for t in node.targets if isinstance(t, ast.Name)],
            _text_root(node.value),
        )
        for node in ast.walk(func)
        if isinstance(node, ast.Assign)
    ]
    for _ in range(len(assigns) + 1):  # to a fixed point; each pass adds ≥1 or stops
        grew = False
        for targets, root in assigns:
            if not targets or set(targets) <= names:
                continue
            if _is_read_call(root, handles) or (
                isinstance(root, ast.Name) and root.id in names
            ):
                names.update(targets)
                grew = True
        if not grew:
            break
    return frozenset(names)


def _is_text_source(
    expr: ast.AST, direct_names: frozenset[str], handles: frozenset[str]
) -> bool:
    root = _text_root(expr)
    return _is_read_call(root, handles) or (
        isinstance(root, ast.Name) and root.id in direct_names
    )


def _membership_on_read_text(node: ast.FunctionDef) -> bool:
    """A membership test whose text side is a file read — directly, or
    through a name `_direct_text_names` traces back to one."""
    direct_names = _direct_text_names(node)
    handles = _open_handles(node)
    for sub in ast.walk(node):
        if (
            isinstance(sub, ast.Compare)
            and any(isinstance(op, (ast.In, ast.NotIn)) for op in sub.ops)
            and any(
                _is_text_source(operand, direct_names, handles)
                for operand in (sub.left, *sub.comparators)
            )
        ):
            return True
    return False


def _isinstance_against_ast_type(node: ast.AST) -> bool:
    """True if the body itself calls `isinstance(x, ast.SomeType)` (or a
    tuple containing one) — the direct judgment of a source walk, as against
    a test that merely calls `ast.parse()` and hands the tree to a scan
    helper already defined (and already planted) elsewhere."""
    for call in _calls_in(node):
        if isinstance(call.func, ast.Name) and call.func.id == "isinstance" and len(call.args) == 2:
            type_arg = call.args[1]
            candidates = type_arg.elts if isinstance(type_arg, ast.Tuple) else [type_arg]
            for candidate in candidates:
                if (
                    isinstance(candidate, ast.Attribute)
                    and isinstance(candidate.value, ast.Name)
                    and candidate.value.id == "ast"
                ):
                    return True
    return False


def _global_scan_helper_names() -> frozenset[str]:
    """Every scan-helper name defined anywhere in `tests/` — every
    `test_*.py` file (this one excluded — its own helpers are proven above,
    not by this rule) plus the shared scan module, if there is one. A test
    that calls one of these by name — bare, or through `module.helper(...)`
    — is delegating to a helper the module-helper half already holds to its
    own plant, wherever that helper actually lives."""
    names: set[str] = set()
    paths = sorted(TESTS_DIR.glob("test_*.py"))
    if SHARED_SCANS.exists():
        paths.append(SHARED_SCANS)
    for path in paths:
        if path.name == "test_scans_fire.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        constants = _module_collection_constants(tree)
        for name, fn in _module_helpers(tree).items():
            if _is_scan_helper(fn, constants):
                names.add(name)
    return frozenset(names)


def _imported_names(tree: ast.Module) -> frozenset[str]:
    """Every name this module binds with `from ... import name` (or `as`),
    anywhere — function-body imports included."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
    return frozenset(names)


def _calls_any_by_name(
    node: ast.AST, bare: frozenset[str], attrs: frozenset[str] | None = None
) -> bool:
    """True if `node` delegates to a known scan helper: a bare call to one of
    `bare`, or `module.helper(...)` for one of `attrs`.

    The two sets differ on purpose. An attribute call names the module it
    comes from, so matching the attribute alone is safe. A *bare* name is
    only that helper if this module actually has it — imported, or defined
    here — otherwise a local function that happens to share a name with some
    other module's scan helper would clear every inline scan beside it.
    """
    attrs = bare if attrs is None else attrs
    for call in _calls_in(node):
        if isinstance(call.func, ast.Name) and call.func.id in bare:
            return True
        if isinstance(call.func, ast.Attribute) and call.func.attr in attrs:
            return True
    return False


def _resolvable_helpers(source: str, global_helpers: frozenset[str]) -> frozenset[str]:
    """The known scan helpers this module can reach by a *bare* name: the
    ones it imports, and the ones it defines itself."""
    tree = ast.parse(source)
    return global_helpers & (
        _imported_names(tree) | frozenset(_scan_helpers(source))
    )


def _is_inline_scan(
    node: ast.AST,
    global_helpers: frozenset[str],
    bare_helpers: frozenset[str] | None = None,
) -> bool:
    """A test body counts as an inline scan when it reads a real file and,
    in its own body — not by calling a scan helper `tests/` already defines
    somewhere — walks source and judges it directly (`ast.parse`/`ast.walk`
    plus an `isinstance` against an `ast.*` type), matches a pattern, or asks
    a membership question of the text it read.

    **Delegation clears the whole test, deliberately.** A test that calls a
    known scan helper is not reported even if it also asks its own `in`
    question of the text it read, because that second question is usually
    the fixture precondition of the first ("the file really does carry the
    thing I am about to change"). The cost is real and named: an unplanted
    inline `in` hidden behind a delegated call is not seen. The alternative
    pushes those preconditions out of sight, which is worse.
    """
    if not (
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    ):
        return False
    if _is_fixture(node):
        return False
    if not _reads_file_text(node):
        return False  # not reading a real file — a string the test built
    bare = global_helpers if bare_helpers is None else bare_helpers
    if _calls_any_by_name(node, bare, global_helpers):
        return False  # delegates to a helper already held to its own plant
    return (
        (_walks_source(node) and _isinstance_against_ast_type(node))
        or _matches_text(node)
        or _membership_on_read_text(node)
    )


def _test_functions(tree: ast.Module):
    """Every test function in a module, by the name a failure would report
    it as: module-level `def test_*`/`async def test_*`, and the methods of
    a `class Test*` — `tests/test_persona.py` and `tests/test_preferences.py`
    write classes of them, and a rule that read only `tree.body` could never
    see a scan in one."""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node.name, node
        elif isinstance(node, ast.ClassDef):
            for method in node.body:
                if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield f"{node.name}::{method.name}", method


def _inline_scan_tests(source: str, global_helpers: frozenset[str]) -> list[str]:
    """Every test function in one tests module whose own body is itself a
    scan by the rule above."""
    tree = ast.parse(source)
    bare = _resolvable_helpers(source, global_helpers)
    return sorted(
        name
        for name, node in _test_functions(tree)
        if _is_inline_scan(node, global_helpers, bare)
    )


def _inline_scan_offenders() -> list[str]:
    """Every `file::test_name` in `tests/*.py` whose own body is itself an
    unfactored scan."""
    global_helpers = _global_scan_helper_names()
    offenders = []
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        if path.name == "test_scans_fire.py":
            continue
        for name in _inline_scan_tests(path.read_text(encoding="utf-8"), global_helpers):
            offenders.append(f"{path.name}::{name}")
    return offenders


#: The inline scans this suite carried on the day the meta-scan landed —
#: fifty-five test bodies that read a real file and judge it in place, with
#: no helper to name and so no plant to prove them. Factoring each out is
#: its own bite (the PR that landed this file names them as its follow-up);
#: until then this ledger is held **shrink-only**: a new inline scan anywhere
#: in `tests/` fails the test below today, and an entry that stops offending
#: must be struck or the same test fails — so the list can neither grow nor
#: go stale. That is what separates it from an allowlist (which only ever
#: grows and excuses whatever is on it): nothing on this list is excused
#: from the rule, it is named as owing a plant, and the day it is empty the
#: test below collapses to `assert not offenders`.
INLINE_SCAN_LEDGER = frozenset({
    "test_audit_against_constitution.py::test_a_probe_that_raises_is_a_failure_not_a_pass",
    "test_audit_against_constitution.py::test_it_does_not_paraphrase_the_clauses",
    "test_audit_against_constitution.py::test_the_tamper_probe_asserts_it_tampered",
    "test_audit_against_constitution.py::test_the_verdict_vocabulary_is_four_states",
    "test_audit_against_jeles.py::test_it_never_imports_the_repo_it_reads",
    "test_before_authority.py::test_every_keys_verb_is_classified",
    "test_before_authority.py::test_seal_env_covers_every_key_material_env_the_modules_read",
    "test_bench_dashboard.py::test_the_dashboard_cannot_record_a_decision",
    "test_bench_dashboard.py::test_the_dashboard_is_self_contained",
    "test_ci_venv.py::test_pythonpath_is_pinned_so_the_invocation_cannot_matter",
    "test_count_countersignatures.py::test_it_refuses_to_count_over_a_tampered_chain",
    "test_desks.py::test_the_failure_this_module_exists_to_prevent",
    "test_dogfood_store.py::test_the_standing_rule_is_written_where_somebody_will_meet_it",
    "test_dogfood_store.py::test_the_thin_pointer_still_points",
    "test_due_for_reverification.py::test_it_carries_no_score_weight_or_multiplier",
    "test_due_for_reverification.py::test_it_does_not_read_the_rows_own_clock",
    "test_due_for_reverification.py::test_it_never_writes_and_never_opens_a_store",
    "test_engine.py::test_no_module_hands_a_model_a_prompt_built_elsewhere",
    "test_feed_all.py::test_it_runs_feeders_as_subprocesses",
    "test_feed_jeles_sources.py::test_it_never_imports_the_repo_it_reads",
    "test_feed_jeles_sources.py::test_it_separates_what_it_measured_from_what_it_only_asked",
    "test_feed_jeles_sources.py::test_the_two_corrected_hypotheses_still_carry_their_verdicts",
    "test_feed_willow_constitution.py::test_it_never_imports_the_repo_it_reads",
    "test_filing_cabinet.py::test_it_says_it_is_fiction_before_it_says_anything_else",
    "test_findings_2026_07_30.py::test_readme_does_not_state_a_stale_test_count",
    "test_fix_null_nodes.py::test_detail_panel_source_routes_through_append_kids",
    "test_issue_probe.py::test_report_covers_every_prompt_and_corpus",
    "test_ledger.py::test_the_checkpoint_does_not_replace_the_walk",
    "test_ledger_kinds.py::test_every_source_literal_kind_is_pinned",
    "test_lint_pins_check.py::test_the_committed_precommit_config_agrees_with_lint_pins",
    "test_persona.py::TestTheEngineCannotReachThePersona::test_no_persona_reaches_a_system_prompt",
    "test_preferences.py::TestNeverSeals::test_module_does_not_import_seal_machinery",
    "test_process_lens.py::test_propose_has_no_path_to_sealed",
    "test_record_demo.py::test_a_failing_beat_propagates_a_nonzero_exit",
    "test_record_demo.py::test_it_captures_the_fast_run_and_every_beat_is_in_the_transcript",
    "test_rejection_needs_no_session.py::test_every_rejection_endpoint_uses_the_rejection_verifier",
    "test_rejection_needs_no_session.py::test_no_seal_endpoint_uses_the_rejection_verifier",
    "test_seal_replacement.py::test_targets_are_digested_not_copied",
    "test_session_start.py::test_the_boot_check_covers_every_gate_ci_lint_runs",
    "test_session_start.py::test_the_boot_check_probes_every_pin_ci_installs",
    "test_session_start.py::test_the_two_places_a_lint_version_is_pinned_agree",
    "test_shoebox.py::test_it_says_it_is_fiction_before_it_says_anything_else",
    "test_test_lanes.py::test_lane_runner_names_every_expensive_integration",
    "test_the_verification.py::test_the_demo_never_seals_anything",
    "test_two_desks.py::test_it_says_it_is_fiction_before_it_says_anything_else",
    "test_two_desks.py::test_the_two_desks_keep_separate_chains",
    "test_ui_edge_seal.py::test_nothing_in_ui_ever_signs_an_edge",
    "test_version.py::test_dev_installs_every_gate_ci_lint_runs",
    "test_version.py::test_shipped_install_hints_name_the_distribution_that_exists",
    "test_version.py::test_the_pr_title_gate_reads_the_types_from_the_config",
    "test_version.py::test_the_version_is_written_once",
    "test_walk_through_covenant.py::test_beat_1_sealed_serve",
    "test_walk_through_covenant.py::test_beat_2_the_draft_row_is_pending",
    "test_walk_through_covenant.py::test_beat_3_rewrite_is_below_the_bar",
    "test_walk_through_covenant.py::test_doc_names_the_bench_that_gates_it",
})


def test_no_new_test_body_is_itself_a_scan_and_the_ledger_only_shrinks():
    """The inline half of the house rule, held to a shrink-only ledger. A
    guard written directly in a test's body, with no helper to name and
    plant, is invisible to the module-helper scan and can never be shown to
    fire. Every `tests/*.py` test must either not be a scan by the shapes
    above, delegate to a scan helper `tests/` already defines and plants, or
    already be named in `INLINE_SCAN_LEDGER` as owing that refactor — and an
    entry that has been refactored must be struck, so the ledger records the
    debt exactly and never a stale excuse."""
    offenders = set(_inline_scan_offenders())
    new = sorted(offenders - INLINE_SCAN_LEDGER)
    assert not new, (
        "these tests are themselves a scan (reads a real file, then walks "
        "its source and judges it, matches a pattern, or asks a membership "
        "question of the text) with no scan helper behind them anywhere in "
        "tests/, so the scan has never been planted — factor the scan into a "
        f"module-level helper and plant it in the same file: {new}"
    )
    struck = sorted(INLINE_SCAN_LEDGER - offenders)
    assert not struck, (
        "these INLINE_SCAN_LEDGER entries no longer offend (refactored, "
        "renamed, or removed) — strike them from the ledger so it only ever "
        f"shrinks: {struck}"
    )


def test_the_inline_scan_check_finds_a_scan_written_directly_in_a_test_body(tmp_path):
    """Planted: a test file whose only guard is written inline — `ast.parse`
    plus a direct `isinstance` walk, on a file the test actually reads (via
    `tmp_path`, not a string built in place). No helper exists anywhere for
    it to delegate to, so it must be reported."""
    target = tmp_path / "target.py"
    target.write_text("import banned\n", encoding="utf-8")
    source = _write(
        tmp_path,
        "test_planted_inline_scan.py",
        "import ast\n"
        "from pathlib import Path\n"
        f"TARGET = Path({str(target)!r})\n"
        "\n"
        "def test_no_banned_import_at_module_scope():\n"
        "    tree = ast.parse(TARGET.read_text('utf-8'))\n"
        "    for node in tree.body:\n"
        "        if isinstance(node, ast.Import):\n"
        "            assert 'banned' not in {a.name for a in node.names}\n",
    )
    assert _inline_scan_tests(source, frozenset()) == ["test_no_banned_import_at_module_scope"]


def test_the_inline_scan_check_knows_every_spelling_of_reading_a_real_file(tmp_path):
    """Planted, one per spelling: the same scan written with the builtin
    `open`, with a `with` block, through `read_bytes().decode()`, or through
    `inspect.getsource` is still reading a real file."""
    spellings = {
        "open_chain": "    text = open('x', encoding='utf-8').read()\n",
        "open_with": (
            "    with open('x', encoding='utf-8') as handle:\n"
            "        text = handle.read()\n"
        ),
        "read_bytes_decode": "    text = Path('x').read_bytes().decode()\n",
        "getsource": "    text = inspect.getsource(Path)\n",
    }
    for label, read in spellings.items():
        source = _write(
            tmp_path,
            f"test_planted_read_{label}.py",
            "import inspect\n"
            "from pathlib import Path\n"
            "\n"
            "def test_no_banned_word():\n"
            f"{read}"
            "    assert 'banned' not in text\n",
        )
        assert _inline_scan_tests(source, frozenset()) == ["test_no_banned_word"], (
            f"reading a real file via {label} is reading a real file"
        )


def test_the_inline_scan_check_follows_a_slice_of_the_text_but_not_a_parse_of_it(tmp_path):
    """The boundary the one-level rule draws, planted both ways. A `.split()`
    of the text read is still that text, but a dict `json.loads` built from
    it is another kind of object, and asking membership of *that* is the
    ordinary assertion this rule must not cry wolf on."""
    sliced = _write(
        tmp_path,
        "test_planted_sliced_text.py",
        "from pathlib import Path\n"
        "\n"
        "def test_the_post_router_names_no_export():\n"
        "    source = Path('x').read_text(encoding='utf-8')\n"
        "    block = source.split('def _route_post')[1].split('def _field')[0]\n"
        "    assert 'export' not in block\n",
    )
    assert _inline_scan_tests(sliced, frozenset()) == ["test_the_post_router_names_no_export"]

    parsed = _write(
        tmp_path,
        "test_planted_parsed_text.py",
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        "def test_the_document_declares_a_version():\n"
        "    loaded = json.loads(Path('x').read_text(encoding='utf-8'))\n"
        "    assert 'version' in loaded['project']\n",
    )
    assert _inline_scan_tests(parsed, frozenset()) == [], (
        "a dict parsed out of the text is not the text; a rule that reported "
        "this gets an allow-list bolted to it and stops meaning anything"
    )


def test_the_inline_scan_check_does_not_fire_on_a_string_the_test_built(tmp_path):
    """Planted: a test that matches a pattern, but only against a string
    literal it built itself — no `.read_text()`/`.read_bytes()` anywhere.
    Not a scan of the tree, so it must not be reported."""
    source = _write(
        tmp_path,
        "test_planted_string_literal_match.py",
        "import re\n"
        "\n"
        "def test_the_greeting_has_no_banned_word():\n"
        "    assert not re.search(r'banned', 'a household keeps its own books')\n",
    )
    assert _inline_scan_tests(source, frozenset()) == []


def test_a_usefixtures_marker_does_not_exempt_a_test_from_either_half(tmp_path):
    """Planted: `@pytest.mark.usefixtures` carries the word "fixture", and a
    rule that looked for that word anywhere in the decorator would clear
    every test wearing it. The marker must not exempt; a real
    `@pytest.fixture` beside it still must."""
    marked = _write(
        tmp_path,
        "test_planted_usefixtures.py",
        "import pytest\n"
        "from pathlib import Path\n"
        "\n"
        "@pytest.mark.usefixtures('_home')\n"
        "def test_no_banned_word():\n"
        "    text = Path('x').read_text(encoding='utf-8')\n"
        "    assert 'banned' not in text\n",
    )
    assert _inline_scan_tests(marked, frozenset()) == ["test_no_banned_word"], (
        "a usefixtures marker is not a fixture and must not exempt the test"
    )

    real = _write(
        tmp_path,
        "test_planted_real_fixture.py",
        "import pytest\n"
        "from pathlib import Path\n"
        "\n"
        "@pytest.fixture(autouse=True)\n"
        "def staged():\n"
        "    return 'banned' in Path('x').read_text(encoding='utf-8')\n",
    )
    assert _scan_helpers(real) == [], "a real @pytest.fixture is still setup"
    assert _inline_scan_tests(real, frozenset()) == []


def test_the_inline_scan_check_clears_a_test_that_delegates_to_a_known_helper(tmp_path):
    """And not over-strict: a test that reads a real file and calls a scan
    helper already known to `tests/` (wherever it actually lives — bare name
    or `module.helper(...)`) is delegating, not scanning inline, so it must
    not be reported even though it still reads a real file and still asks a
    membership question of the result."""
    target = tmp_path / "target.py"
    target.write_text("from tests import conftest\n", encoding="utf-8")
    source = _write(
        tmp_path,
        "test_planted_delegating_test.py",
        "from pathlib import Path\n"
        f"TARGET = Path({str(target)!r})\n"
        "\n"
        "from test_import_hygiene import offenders\n"
        "\n"
        "def test_the_module_does_not_import_through_tests():\n"
        "    hits = offenders(TARGET.read_text(encoding='utf-8'))\n"
        "    assert 'tests' not in hits\n",
    )
    assert _inline_scan_tests(source, frozenset({"offenders"})) == []


def test_the_inline_scan_check_reads_class_methods_and_async_tests_too(tmp_path):
    """Planted: the two shapes a `tree.body`-only walk cannot see. This suite
    writes test classes (`test_persona.py`, `test_preferences.py`), so a scan
    in a method must be reportable; an `async def test_*` would be the same
    blind spot the day one is written."""
    in_a_class = _write(
        tmp_path,
        "test_planted_class_scan.py",
        "from pathlib import Path\n"
        "\n"
        "class TestTheTree:\n"
        "    def test_no_banned_word(self):\n"
        "        text = Path('x').read_text(encoding='utf-8')\n"
        "        assert 'banned' not in text\n",
    )
    assert _inline_scan_tests(in_a_class, frozenset()) == [
        "TestTheTree::test_no_banned_word"
    ], "a scan in a test class's method is still a scan, and is named as one"

    awaited = _write(
        tmp_path,
        "test_planted_async_scan.py",
        "from pathlib import Path\n"
        "\n"
        "async def test_no_banned_word():\n"
        "    text = Path('x').read_text(encoding='utf-8')\n"
        "    assert 'banned' not in text\n",
    )
    assert _inline_scan_tests(awaited, frozenset()) == ["test_no_banned_word"]


def test_delegating_clears_a_test_that_also_asks_its_own_question(tmp_path):
    """The boundary this rule draws, pinned rather than left to be
    rediscovered: a test that calls a known scan helper is cleared *whole*,
    including an `in` of its own on the same text — the `in` beside the
    delegated call is the precondition that keeps the plant honest."""
    source = _write(
        tmp_path,
        "test_planted_delegate_and_check.py",
        "from pathlib import Path\n"
        "from test_version import _version_literal_hits\n"
        "\n"
        "def test_the_planted_literal_is_reported():\n"
        "    source = Path('x').read_text(encoding='utf-8')\n"
        "    assert 'SERVER_VERSION' in source\n"
        "    assert _version_literal_hits(Path('x').parent)\n",
    )
    assert _inline_scan_tests(source, frozenset({"_version_literal_hits"})) == []
    assert _inline_scan_tests(source, frozenset()) == [
        "test_the_planted_literal_is_reported"
    ], "and with no helper behind it, the same body is an inline scan"


def test_a_local_function_sharing_a_helpers_name_does_not_clear_a_scan(tmp_path):
    """Planted: the shadow. Delegation is recognised by *name*, across the
    whole of `tests/`, so a module with a local function that happens to
    share a scan helper's name would have every inline scan beside it
    cleared by a call to something else entirely. A bare name only counts
    when this module imports it or defines it."""
    shadow = _write(
        tmp_path,
        "test_planted_shadowed_helper.py",
        "from pathlib import Path\n"
        "\n"
        "def _sections(text):\n"
        "    return text\n"
        "\n"
        "def test_no_banned_word():\n"
        "    text = Path('x').read_text(encoding='utf-8')\n"
        "    assert _sections(text)\n"
        "    assert 'banned' not in text\n",
    )
    assert _inline_scan_tests(shadow, frozenset({"_sections"})) == [
        "test_no_banned_word"
    ], "a local `_sections` is not another module's `_sections`"

    imported = _write(
        tmp_path,
        "test_planted_imported_helper.py",
        "from pathlib import Path\n"
        "from test_docs import _sections\n"
        "\n"
        "def test_no_banned_word():\n"
        "    text = Path('x').read_text(encoding='utf-8')\n"
        "    assert _sections(text)\n"
        "    assert 'banned' not in text\n",
    )
    assert _inline_scan_tests(imported, frozenset({"_sections"})) == [], (
        "and the same call, of the helper this module really imported, is "
        "the delegation it looks like"
    )


def test_the_inline_scan_check_does_not_fire_on_a_real_delegating_file():
    """The whole thing against a real file of this repo's:
    `tests/test_import_hygiene.py` reads every file under `tests/` and
    delegates the judgment to its own `offenders`, planted in the same file
    — so the check must clear it, or it would be crying wolf on the very
    shape it exists to require."""
    global_helpers = _global_scan_helper_names()
    assert "offenders" in global_helpers
    source = (TESTS_DIR / "test_import_hygiene.py").read_text(encoding="utf-8")
    assert _inline_scan_tests(source, global_helpers) == []


def test_the_ledger_names_only_real_offenders():
    """The ledger is a list of test ids, and a test id can be misspelled. Every
    entry must parse as `file::name` (or `file::Class::name`) for a file that
    exists, so a typo cannot sit in the ledger looking like a debt."""
    for entry in sorted(INLINE_SCAN_LEDGER):
        file_name, _, rest = entry.partition("::")
        assert file_name.startswith("test_") and file_name.endswith(".py"), entry
        assert (TESTS_DIR / file_name).exists(), f"{entry}: no such test file"
        assert rest and all(part for part in rest.split("::")), entry
