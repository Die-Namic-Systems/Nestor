"""The version, and the release path that will one day use it.

No `import yaml` anywhere below. CI's test job installs `.[keys] pytest
coverage` and nothing else, so pyyaml is absent there even though bandit drags
it into a lint environment — a gate that imports it would skip in CI, and a
gate that can skip is not a gate. String assertions over the workflow are
cruder and they cannot quietly stop running.
"""

from __future__ import annotations

import pathlib
import re
import tomllib
from importlib.metadata import PackageNotFoundError, version as dist_version

import pytest

import nestor

ROOT = pathlib.Path(__file__).resolve().parents[1]
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
DECLARED = PYPROJECT["project"]["version"]

#: What the package reports when there is no installed distribution to ask.
UNINSTALLED = "0+unknown"


def test_version_is_exported():
    assert "__version__" in nestor.__all__
    assert nestor.__version__


def test_version_is_a_plausible_pep440_string():
    assert re.fullmatch(r"\d+(\.\d+)*([a-z]+\d+)?(\.dev\d+)?(\+[\w.]+)?",
                        nestor.__version__), nestor.__version__


def test_version_agrees_with_the_installed_distribution():
    """Or says plainly that there isn't one. Both are correct; a third answer
    would mean the package invented a number."""
    try:
        installed = dist_version("nestor")
    except PackageNotFoundError:
        assert nestor.__version__ == UNINSTALLED
    else:
        assert nestor.__version__ == installed


def test_the_uninstalled_marker_cannot_be_mistaken_for_a_release():
    """`0+unknown` is a PEP 440 local version, so it parses, and it sorts below
    every real release rather than above one. A host logging it gets a string
    that says nobody installed this."""
    assert UNINSTALLED.startswith("0+")
    assert not re.fullmatch(r"\d+(\.\d+)*", UNINSTALLED)


def test_the_version_is_written_once():
    """The gate this file exists for, and the same one
    `test_engine.py::test_the_rule_is_written_once` makes for the voice rule.

    `pyproject.toml` declares the version. If the package also carried a
    literal, the two would be a pending disagreement that nothing checks — and
    the copy that loses is always the one somebody forgot on release day."""
    init = (ROOT / "nestor" / "__init__.py").read_text(encoding="utf-8")
    assert DECLARED not in init, (
        f"nestor/__init__.py contains the literal {DECLARED!r}; the version is "
        f"declared in pyproject.toml and read through importlib.metadata, and a "
        f"second copy is the defect this test exists to refuse")


# --- the release path ------------------------------------------------------

WORKFLOW = (ROOT / ".github" / "workflows" / "publish.yml").read_text(encoding="utf-8")


def test_the_publish_workflow_exists_and_uploads_only_from_a_tag():
    """Three locks, and this pins the one that lives in the repository.

    A `workflow_dispatch` run must build and stop. Removing this condition is
    the single edit that would turn a dry run anybody can trigger into an
    upload anybody can trigger."""
    publish = WORKFLOW.split("  publish:", 1)[1]
    assert "if: startsWith(github.ref, 'refs/tags/v')" in publish
    assert "needs: build" in publish


def test_the_publish_job_uses_trusted_publishing_not_a_stored_token():
    assert "id-token: write" in WORKFLOW
    assert "pypa/gh-action-pypi-publish" in WORKFLOW
    assert "password:" not in WORKFLOW and "PYPI_API_TOKEN" not in WORKFLOW


def test_the_publish_job_is_gated_on_an_environment():
    """The environment is where a required reviewer lives, which is what makes
    an upload a thing a human approves rather than a thing a tag does."""
    assert re.search(r"environment:\s*\n\s*name: pypi", WORKFLOW)


def test_the_workflow_refuses_a_tag_that_disagrees_with_the_version():
    """A filename on PyPI is permanent — it cannot be renamed, reassigned, or
    deleted and replaced. A tag and a version that disagree therefore produce
    an artifact nobody can correct."""
    assert 'tag="${GITHUB_REF_NAME#v}"' in WORKFLOW
    assert 'if [ "$tag" != "$pkg" ]; then' in WORKFLOW


@pytest.mark.parametrize("promise", [
    "readme", "license", "license-files", "classifiers", "keywords",
])
def test_pyproject_carries_what_pypi_renders(promise):
    assert promise in PYPROJECT["project"], promise


def test_no_license_classifier_beside_a_license_expression():
    """setuptools rejects both together rather than reconciling two sources for
    one fact — the same instinct as the test above it."""
    assert isinstance(PYPROJECT["project"]["license"], str)
    assert not [c for c in PYPROJECT["project"]["classifiers"]
                if c.startswith("License ::")]


def test_the_publish_extra_is_not_folded_into_dev():
    """CI's dev install would otherwise carry a build backend and an upload
    client it never uses."""
    extras = PYPROJECT["project"]["optional-dependencies"]
    assert "publish" in extras
    assert not [d for d in extras["dev"] if d.split(">")[0] in ("build", "twine")]
