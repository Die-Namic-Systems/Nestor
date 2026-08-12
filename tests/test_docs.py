"""The documentation makes checkable claims. These check them.

`IDEAS.md` §4.5 is a README that had outgrown itself — a test count quoted in
three places while pytest reported a different number, and a refusal promised
more strongly than the code delivered. The lesson was not "be careful with the
README"; it was that a claim nobody executes is a claim nobody maintains.

So the mechanical ones run here: the file list, the anchors, the commands, the
environment variables, each document's own stated contract, and the quick-start
example — which is executed and compared against the output printed beneath it,
because the first thing anyone runs is the worst thing to have wrong.

Prose is not checked and cannot be. These pin the parts that rot silently.
"""
from __future__ import annotations

import os

import io
import pathlib
import re
import warnings
from contextlib import redirect_stdout

import pytest

ROOT = pathlib.Path(__file__).parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")
#: Root-level markdown, plus the nested docs that carry operating rules rather
#: than prose. `docs/agent-guide.md` is here because 263 lines moved out of
#: `CLAUDE.md` into it, and a corpus built from `ROOT.glob("*.md")` alone
#: silently stopped link-checking every one of them. Measured before the fix:
#: the same broken link appended to `docs/agent-guide.md` left the suite green,
#: and appended to `AGENTS.md` failed. The move also rewrote every relative link
#: to `../`, so the change most likely to break a path was the one that left
#: coverage.
DOCS = {p.name: p.read_text(encoding="utf-8")
        for p in ROOT.glob("*.md")} | {
    rel: (ROOT / rel).read_text(encoding="utf-8")
    for rel in ("bench/README.md", "docs/agent-guide.md")}


def slugify(heading: str) -> str:
    """GitHub's anchor rule: lowercase, drop punctuation, spaces to hyphens.

    An em dash is *removed*, not replaced, so "The curator — seeing" leaves two
    spaces and therefore two hyphens. Getting that wrong makes this test flag
    every working link in the file, which is how it was found.
    """
    kept = "".join(c for c in heading.strip().lower() if c.isalnum() or c in " -_")
    return kept.replace(" ", "-")


def fenced(text: str, language: str) -> list[str]:
    return re.findall(r"```" + language + r"\n(.*?)```", text, re.S)


# --- the file list ---------------------------------------------------------

def test_the_project_layout_lists_every_module_and_no_ghosts():
    """A layout diagram is a promise about what is in the package."""
    block = README.split("## Project layout", 1)[1].split("```")[1].split("bench/")[0]
    listed = set(re.findall(r"([a-z_]+\.py)", block))
    actual = {p.name for p in (ROOT / "nestor").glob("*.py")}
    assert listed == actual, (
        f"undocumented: {sorted(actual - listed)}; documented but absent: "
        f"{sorted(listed - actual)}")


def test_the_project_layout_lists_every_doc_and_no_ghosts():
    """The docs/ tree drifts where the package tree cannot: a doc absent from the
    layout reads as nonexistent to anyone grepping it for what to read next.

    `FINDINGS-2026-08-05-docs-standup.md` §8 named this class; five days later
    `FINDINGS-2026-08-10-docs-refresh.md` found it had recurred — seven docs and a
    new demo missing from the tree. The package tree has had a gate since IDEAS
    §4.5 and stayed clean; the docs listing had none and drifted. So it gets the
    same gate, over the whole layout block rather than the `nestor/` slice.
    """
    block = README.split("## Project layout", 1)[1].split("```")[1]
    listed = set(re.findall(r"docs/([a-z-]+\.md)", block))
    actual = {p.name for p in (ROOT / "docs").glob("*.md")}
    assert listed == actual, (
        f"undocumented docs: {sorted(actual - listed)}; documented but absent: "
        f"{sorted(listed - actual)}")


# --- the links -------------------------------------------------------------

def test_every_in_page_link_resolves():
    headings = re.findall(r"^#{1,6} (.+)$", README, re.M)
    slugs = {slugify(h) for h in headings}
    broken = sorted(a for a in set(re.findall(r"\]\(#([\w\-]+)\)", README)) if a not in slugs)
    assert not broken, f"anchors pointing at nothing: {broken}"


@pytest.mark.parametrize("name", sorted(DOCS))
def test_every_linked_file_exists(name):
    text = DOCS[name]
    base = (ROOT / name).parent
    missing = [ref for ref in set(re.findall(r"\]\(([\w./-]+\.(?:md|toml|py|json))\)", text))
               if not (base / ref).exists()]
    assert not missing, f"{name} links to files that do not exist: {missing}"


# --- the commands ----------------------------------------------------------

def test_every_documented_subcommand_exists():
    from nestor.cli import build_parser

    known = set(build_parser()._subparsers._group_actions[0].choices)
    documented = set()
    for text in DOCS.values():
        for block in fenced(text, "bash"):
            documented |= set(re.findall(r"^\s*nestor ([a-z-]+)", block, re.M))
    unknown = sorted(c for c in documented if c not in known)
    assert not unknown, f"documented but not a subcommand: {unknown} (have {sorted(known)})"


def test_every_documented_flag_is_accepted():
    """A flag in a README is a promise the parser has to keep."""
    from nestor.cli import build_parser
    from nestor.serve import build_parser as serve_parser
    from nestor.ui import build_parser as ui_parser

    flags = {"nestor": build_parser(), "nestor ui": ui_parser(), "nestor serve": serve_parser()}
    known = {name: {opt for action in p._actions for opt in action.option_strings}
             for name, p in flags.items()}
    # Subcommand flags live on the subparsers, so fold those in for `nestor`.
    for sub in build_parser()._subparsers._group_actions[0].choices.values():
        known["nestor"] |= {opt for action in sub._actions for opt in action.option_strings}

    missing = []
    for text in DOCS.values():
        for block in fenced(text, "bash"):
            for line in block.splitlines():
                line = line.split("#")[0]
                match = re.match(r"\s*(nestor ui|nestor serve|nestor-ui|nestor)\b(.*)", line)
                if not match:
                    continue
                program = "nestor ui" if match.group(1) == "nestor-ui" else match.group(1)
                for flag in re.findall(r"(?<![\w-])(--[a-z][a-z-]*)", match.group(2)):
                    if flag not in known[program]:
                        missing.append(f"{program} {flag}")
    assert not missing, f"documented flags the parser does not accept: {sorted(set(missing))}"


# --- the environment -------------------------------------------------------

def _env_names_in_code() -> set[str]:
    """Every environment variable the code reads.

    ``tests/_fleet_paths.py`` is in scope alongside the package because it is
    the only other place that reads a knob a *document* is entitled to name:
    the sibling-checkout overrides (`JELES_REPO`, `WILLOW_CHARTER_REPO`, …)
    that decide whether eight tests run or skip. Scanning `nestor/` alone made
    this gate narrower than its own docstring — it fired on
    `FINDINGS-2026-08-12-agent-friction.md` for naming two variables that exist,
    work, and are read on every run, which is the false positive that sends a
    writer to delete a true sentence.
    """
    paths = [*(ROOT / "nestor").glob("*.py"), ROOT / "tests" / "_fleet_paths.py"]
    source = "\n".join(p.read_text(encoding="utf-8") for p in paths)
    # `[A-Z0-9_]`, not `[A-Z_]`: the old class stopped at the first digit, so
    # `WILLOW_20_REPO` was captured as `WILLOW_` — a prefix that appears in
    # several documents, so it satisfied the reverse gate by accident and that
    # variable was covered in neither direction. Found by widening the scan
    # above and then checking which names it had actually gained.
    return set(re.findall(r"environ\.get\(\s*[\"']([A-Z][A-Z0-9_]+)", source))


def test_documented_environment_variables_exist():
    """Every knob the docs name must be one the code reads.

    TODO.md is exempt in this direction and only this one: it exists to describe
    work that is *not* in the tree yet — including a variable on an unmerged
    branch — so requiring its identifiers to resolve would invert its purpose.
    The reverse check below still covers it, so a real variable can be documented
    there and nowhere else without slipping past.
    """
    documented = set()
    for name, text in DOCS.items():
        if name == "TODO.md":
            continue
        documented |= set(re.findall(r"`(NESTOR_[A-Z_]+|WILLOW_[A-Z_]+)`", text))
    unknown = sorted(documented - _env_names_in_code())
    assert not unknown, f"documented but read nowhere: {unknown}"


def test_every_environment_variable_is_documented():
    """The other direction, which is the one that rots: a knob nobody wrote down."""
    # Named anywhere in the prose counts — the README writes some as
    # `NESTOR_REQUIRE_SEAL_KEY=1`, which is documentation by any standard.
    undocumented = sorted(v for v in _env_names_in_code()
                          if v.startswith(("NESTOR_", "WILLOW_"))
                          and not any(v in text for text in DOCS.values()))
    assert not undocumented, f"read by the code, documented nowhere: {undocumented}"


# --- each document's own contract ------------------------------------------

def test_every_ideas_entry_carries_a_status():
    """IDEAS.md's first table promises one, and the status is the whole point.

    An entry without one reads as fact when it may be a hypothesis — precisely
    the confusion the vocabulary exists to prevent.
    """
    ideas = DOCS["IDEAS.md"]
    known = ("measured", "verified", "hypothesis", "open", "shipped", "partly",
             "falsified", "mitigated", "addressed")
    bare = [h for h in re.findall(r"^### (.+)$", ideas, re.M)
            if not any(k in h.lower() for k in known)]
    assert not bare, f"IDEAS entries with no status: {bare}"


def test_every_question_carries_a_status():
    questions = DOCS["QUESTIONS.md"]
    headings = re.findall(r"^### (\d+)\. (.+)$", questions, re.M)
    assert len(headings) >= 17, f"only {len(headings)} questions found"
    bare = [h for _, h in headings if "**" not in h]
    assert not bare, f"questions with no status: {bare}"
    numbers = [int(n) for n, _ in headings]
    assert numbers == list(range(1, len(numbers) + 1)), f"numbering skips: {numbers}"


def test_the_readme_still_refuses_to_hardcode_counts_that_drift():
    """Kept from IDEAS 4.5, widened: pair and domain counts drift like test counts."""
    stale = re.findall(r"\b\d{2,4}\s+(?:tests?|pairs? in the memory)\b", README)
    assert not stale, f"README hardcodes a count that will drift: {stale}"


# --- the example everyone runs first ---------------------------------------

def runnable_examples() -> list[tuple[str, str, str]]:
    """Every ``Save this as `x.py`\u200b`` example, with the output printed below it.

    The convention is the promise: if the README tells you to save and run it,
    this runs it. Snippets *without* that introduction are illustrative — the
    rejection and curator sections show transcripts built from earlier state —
    and executing those would be testing a fiction.
    """
    out = []
    for name, rest in re.findall(r"Save this as `([\w.]+)`(.*?)(?=Save this as `|\Z)",
                                 README, re.S):
        found = re.search(r"```python\n(.*?)```.*?```\n(.*?)```", rest, re.S)
        if found:
            out.append((name, found.group(1), found.group(2)))
    return out


@pytest.mark.parametrize("name,demo,expected",
                         runnable_examples(),
                         ids=[e[0] for e in runnable_examples()])
def test_the_readme_examples_print_what_the_readme_says_they_print(
        name, demo, expected, tmp_path, seal_key):
    """Executed, not read. They are the first things anyone runs.

    The ledger lands under the working directory, so this runs in a temp one —
    a doc test that wrote into the repo would be its own kind of wrong.
    """
    prev_cwd = os.getcwd()
    os.chdir(tmp_path)
    os.environ.pop("NESTOR_SEAL_KEY", None)
    import nestor.storage as storage_module
    saved = storage_module._store
    printed = io.StringIO()
    try:
        with warnings.catch_warnings():
            # The README documents this warning in the paragraph below the block.
            warnings.simplefilter("ignore", RuntimeWarning)
            with redirect_stdout(printed):
                exec(compile(demo, "README quick start", "exec"), {"__name__": "__main__"})
    finally:
        storage_module._store = saved
        os.chdir(prev_cwd)

    assert printed.getvalue() == expected, (
        f"{name} prints:\n{printed.getvalue()}\nthe README claims:\n{expected}")


def test_the_readme_documents_the_warning_the_quick_start_emits():
    """It does emit one, and a demo that warns without warning you is a trap."""
    assert "RuntimeWarning" in README and "NESTOR_SEAL_KEY" in README


def test_the_readme_quotes_the_servers_refusal_verbatim():
    """It is printed as a transcript, so it has to be one.

    A quoted refusal that drifts from the real message is the same failure as a
    stale test count, with worse consequences: this is the sentence that tells a
    reader what the server will not do.
    """
    from nestor.serve import Server

    server = Server(store=None)
    try:
        server.call("nestor_seal", {})
    except PermissionError as exc:
        actual = " ".join(str(exc).split())
    quoted = " ".join(README.split("PermissionError:", 1)[1].split("```", 1)[0].split())
    assert quoted == actual, f"README quotes:\n{quoted}\nthe server says:\n{actual}"
