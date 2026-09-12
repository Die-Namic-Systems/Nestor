"""G2-conventions-nestor — this tree is held to the fleet's published conventions.

Fleet plan decision 4: every repo carries `tests/test_fleet_conventions.py`
whose rules are **read from the published document**, never restated here.
The document is `reconciler conventions --json` (willow-reconciler, the one
home the fleet's convention set has since its Wave 2 merged). Each rule in it
carries its own `sources` entry — the incident that made it a rule — so a
reader who wants to know *why* opens the document, not this file.

**Vendored, not imported (decision 0237).** `tests/fleet_conventions.json` is
the byte-for-byte output of `reconciler conventions --json` from
willow-reconciler 0.6.0, pinned below by sha256. This repo's dependency
discipline (`scripts/lint-pins.txt`, `dep-audit.sh`, and a CI test job that
installs `.[keys]` plus pytest and nothing else) makes a new test-time
dependency a real decision, and the document is a few hundred bytes of JSON
that changes only when the fleet's conventions do. So: the copy is pinned to
a named source version, a planted edit to it must be caught, and whenever
`reconciler` happens to be importable the live document must equal the
vendored one — a bump upstream shows up here as a failing test, not as a
silently stale copy.

**What is checked on the real tree.** Five rules, each with a plant below
that proves the check fires on a tree that breaks it:

* `release-please.yml` arms auto-merge here (`gh pr merge --auto`), so every
  file in `required_when_release_please_arms_automerge` must exist —
  `pr-title.yml`, the guard that stops a `fix(ci):` title over `ci:` commits
  from cutting a release (willow-mcp v2.1.1).
* the config's hidden changelog set equals the published `hidden_types`, and
  its un-hidden set equals the published `release_cutting_types` — the two
  sets `pr-title.yml` already reads from the same file.
* the config carries every `required_config_comments` key: the reasoning
  beside the setting it explains.
* `CONTRIBUTING.md` names the test command — the one thing the PR template's
  Evidence line can quote.
* a numbered pile exists (`IDEAS.md`), so `required_when_pile_exists` bites:
  `trailers.yml`, which E3-trailers (fleet plan Wave 3) adds. That test is
  `xfail(strict=True)` until it lands — the rule is not weakened, and the day
  the workflow appears the xfail turns into a failure that says so.

`publish.yml` is this repo's release workflow and is never renamed; the
published document does not name `release.yml`, and nothing here does either.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent

#: The vendored document, its source, and the pin. The digest is of the file's
#: bytes exactly as `reconciler conventions --json` printed them (json, indent
#: 2, trailing newline) — a hash, not a secret, which is why the allowlist
#: pragma sits on it: detect-secrets flags any 64-hex string it has not seen.
DOCUMENT = TESTS_DIR / "fleet_conventions.json"
DOCUMENT_SOURCE = "willow-reconciler 0.6.0"
DOCUMENT_SHA256 = "8c2ba122a7100141200d8c76ad086339f984446ab7e90dd9c27a092dbf7f5335"  # pragma: allowlist secret
DOCUMENT_SCHEMA = "willow-fleet-conventions/1"

RULES = json.loads(DOCUMENT.read_text(encoding="utf-8"))

RELEASE_PLEASE = ".github/workflows/release-please.yml"
RELEASE_CONFIG = "release-please-config.json"
CONTRIBUTING = "CONTRIBUTING.md"
#: This repo's numbered pile: `IDEAS.md`, which opens with a CI-gated Map of
#: every subsection and carries the idea ids a trailer would join to.
PILE = "IDEAS.md"
ARMS_AUTOMERGE = "gh pr merge --auto"
#: The gate `AGENTS.md`'s table and `CONTRIBUTING.md`'s table both name for a
#: code change, and the command CI's `test` job runs the same collection under
#: (`pytest -n auto --dist loadgroup`). Held as the script's name so a lane
#: argument (`full`, `core`) after it still counts.
TEST_COMMAND = "bash scripts/ci-test.sh"


# --- the document itself -----------------------------------------------------


def _document_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_the_vendored_document_is_the_published_one_pinned_by_hash():
    """The copy is `reconciler conventions --json` from a named version and
    nothing else: its bytes hash to the pin, and it declares the schema this
    file was written against. Bumping the document means re-running the
    command, re-pinning, and naming the new source version."""
    assert _document_digest(DOCUMENT) == DOCUMENT_SHA256, (
        f"tests/fleet_conventions.json is not the {DOCUMENT_SOURCE} document "
        "this file was pinned to — regenerate it with `reconciler conventions "
        "--json`, re-pin DOCUMENT_SHA256 and name the source version")
    assert RULES["schema"] == DOCUMENT_SCHEMA
    assert set(RULES) >= {
        "hidden_types", "release_cutting_types",
        "required_when_release_please_arms_automerge", "required_config_comments",
        "required_when_pile_exists", "contributing_must_name_test_command",
        "idea_id_trailer", "sources",
    }


def test_the_hash_pin_fires_on_a_planted_edit_to_the_document(tmp_path):
    """Planted: a one-key change to a copy of the document must change the
    digest, or the pin above is decoration."""
    edited = json.loads(DOCUMENT.read_text(encoding="utf-8"))
    edited["hidden_types"] = [t for t in edited["hidden_types"] if t != "ci"]
    planted = tmp_path / "fleet_conventions.json"
    planted.write_text(json.dumps(edited, indent=2) + "\n", encoding="utf-8")
    assert _document_digest(planted) != DOCUMENT_SHA256

    verbatim = tmp_path / "verbatim.json"
    verbatim.write_bytes(DOCUMENT.read_bytes())
    assert _document_digest(verbatim) == DOCUMENT_SHA256, "and an exact copy still matches"


def test_the_vendored_document_matches_the_live_reconciler_when_importable():
    """When willow-reconciler is installed on this seat, the document it
    publishes must equal the vendored copy. Skipped, not passed, where it is
    not importable — the hash pin above is the check that always runs."""
    conventions = pytest.importorskip(
        "reconciler.conventions",
        reason="willow-reconciler not installed here; the sha256 pin is the standing check",
    )
    assert conventions.conventions() == RULES, (
        f"the installed reconciler publishes a different document from the vendored "
        f"{DOCUMENT_SOURCE} copy — re-vendor, re-pin, and name the new version")


# --- the rules, read from the document ---------------------------------------


def _arms_automerge(root: Path) -> bool:
    workflow = root / RELEASE_PLEASE
    return workflow.exists() and ARMS_AUTOMERGE in workflow.read_text(encoding="utf-8")


def _missing_when_armed(root: Path, required: list[str]) -> list[str]:
    if not _arms_automerge(root):
        return []
    return [f for f in required if not (root / f).exists()]


def _config_sections(config_text: str) -> list[dict]:
    return json.loads(config_text)["packages"]["."]["changelog-sections"]


def _config_hidden_types(config_text: str) -> set[str]:
    return {s["type"] for s in _config_sections(config_text) if s.get("hidden")}


def _config_release_cutting_types(config_text: str) -> set[str]:
    return {s["type"] for s in _config_sections(config_text) if not s.get("hidden")}


def _config_missing_comments(config_text: str, required: list[str]) -> list[str]:
    package = json.loads(config_text)["packages"]["."]
    return [c for c in required if c not in package]


def _missing_when_pile_exists(root: Path, required: list[str]) -> list[str]:
    if not (root / PILE).exists():
        return []
    return [f for f in required if not (root / f).exists()]


def _names_test_command(contributing_text: str) -> bool:
    return TEST_COMMAND in contributing_text


def test_pr_title_guard_is_present_wherever_automerge_is_armed():
    assert _arms_automerge(REPO_ROOT), (
        f"{RELEASE_PLEASE} no longer arms auto-merge; if that is deliberate this "
        "rule stops applying and the test should say so, not go quiet")
    assert _missing_when_armed(REPO_ROOT, RULES["required_when_release_please_arms_automerge"]) == []


def test_the_configs_hidden_set_equals_the_published_set():
    text = (REPO_ROOT / RELEASE_CONFIG).read_text(encoding="utf-8")
    assert _config_hidden_types(text) == set(RULES["hidden_types"])


def test_the_configs_release_cutting_set_equals_the_published_set():
    """The other half of the same file: every un-hidden type cuts a release
    on its own (willow-mcp 2.1.5), so the set is closed and published, and
    `pr-title.yml` reads it from here."""
    text = (REPO_ROOT / RELEASE_CONFIG).read_text(encoding="utf-8")
    assert _config_release_cutting_types(text) == set(RULES["release_cutting_types"])


def test_the_config_carries_every_required_reasoning_comment():
    text = (REPO_ROOT / RELEASE_CONFIG).read_text(encoding="utf-8")
    assert _config_missing_comments(text, RULES["required_config_comments"]) == []


def test_contributing_names_the_test_command():
    assert RULES["contributing_must_name_test_command"] is True
    assert _names_test_command((REPO_ROOT / CONTRIBUTING).read_text(encoding="utf-8")), (
        f"{CONTRIBUTING} does not name `{TEST_COMMAND}` — the PR template's Evidence "
        "line has nothing to quote")


@pytest.mark.xfail(strict=True, reason="E3-trailers (fleet plan Wave 3) adds trailers.yml")
def test_trailers_workflow_is_present_because_a_pile_exists():
    """This repo has a numbered pile, so the rule bites today and the file it
    requires does not exist yet. Strict xfail: the rule is not weakened, and
    when E3-trailers lands the unexpected pass fails this test until the
    marker is removed."""
    assert (REPO_ROOT / PILE).exists()
    assert _missing_when_pile_exists(REPO_ROOT, RULES["required_when_pile_exists"]) == []


# --- the plants ---------------------------------------------------------------


def _tree(tmp_path: Path, label: str, *, arms: bool, files: tuple[str, ...] = ()) -> Path:
    root = tmp_path / label
    (root / ".github" / "workflows").mkdir(parents=True)
    body = "jobs:\n  release-please:\n    steps:\n      - run: |\n"
    body += f"          {ARMS_AUTOMERGE} \"$pr\"\n" if arms else "          gh pr list\n"
    (root / RELEASE_PLEASE).write_text(body, encoding="utf-8")
    for f in files:
        (root / f).parent.mkdir(parents=True, exist_ok=True)
        (root / f).write_text("# planted\n", encoding="utf-8")
    return root


def test_the_armed_tree_check_fires_on_a_planted_tree_missing_the_guard(tmp_path):
    required = RULES["required_when_release_please_arms_automerge"]
    assert _missing_when_armed(_tree(tmp_path, "bare", arms=True), required) == required
    assert _missing_when_armed(_tree(tmp_path, "guarded", arms=True, files=tuple(required)), required) == []
    assert _missing_when_armed(_tree(tmp_path, "manual", arms=False), required) == []


def test_the_hidden_set_check_catches_a_planted_config_that_unhides_ci():
    planted = json.dumps({"packages": {".": {"changelog-sections": [
        {"type": "feat", "section": "Added"},
        {"type": "docs", "section": "Docs", "hidden": True},
        {"type": "test", "section": "Tests", "hidden": True},
        {"type": "ci", "section": "CI"},
        {"type": "chore", "section": "Chores", "hidden": True},
    ], "$comment-what-cuts-a-release": "kept"}}})
    assert _config_hidden_types(planted) == {"chore", "docs", "test"}
    assert _config_hidden_types(planted) != set(RULES["hidden_types"])
    assert _config_release_cutting_types(planted) == {"feat", "ci"}, (
        "an un-hidden `ci` is a release-cutting type, which is the whole defect")
    assert _config_missing_comments(planted, RULES["required_config_comments"]) == ["$comment-hidden-rule"]


def test_the_pile_check_fires_on_a_planted_tree_with_a_pile_and_no_verify_gate(tmp_path):
    required = RULES["required_when_pile_exists"]
    with_pile = _tree(tmp_path, "pile", arms=False, files=(PILE,))
    assert _missing_when_pile_exists(with_pile, required) == required
    gated = _tree(tmp_path, "gated", arms=False, files=(PILE, *required))
    assert _missing_when_pile_exists(gated, required) == []
    assert _missing_when_pile_exists(_tree(tmp_path, "nopile", arms=False), required) == [], (
        "a tree with no pile owes nothing under this rule")


def test_the_contributing_check_catches_a_planted_contributing_without_the_command():
    assert not _names_test_command("# Contributing\n\nRun the tests before pushing.\n")
    assert not _names_test_command("```bash\npython -m pytest -q\n```\n"), (
        "a different test command is not the gate this repo names")
    assert _names_test_command(f"```sh\n{TEST_COMMAND} full\n```\n")
