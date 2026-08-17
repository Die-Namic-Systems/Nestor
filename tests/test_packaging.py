"""The wheel ships what the served page needs to render its Graph tab.

nestor/ui_page.py reads nestor/vendor/cytoscape.min.js off disk at import time
and inlines it into the page it serves (nestor/vendor/README.md). That read
has to resolve inside an installed package, not just this checkout — a wheel
built without the vendored file is one `pip install` away from a Graph tab
whose inline <script> is empty and a RuntimeError on the very first import of
nestor.ui_page (see _read_vendor_script there).

This builds a REAL wheel with the project's own build backend (hatchling, via
`pip wheel`) rather than asserting anything about pyproject.toml's config —
config can say the right thing and still not do it (a typo'd force-include
key, a glob that does not match). Building is checked, not assumed.
"""
from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def built_wheel(tmp_path_factory):
    """One real wheel, built once for every test in this module.

    `pip wheel` needs to fetch the build backend (hatchling, hatch-vcs) the
    first time it runs in an environment that has never built this project —
    the same network dependency `pip install -e .` already has. A genuine
    network outage is reported as a skip (an environment limitation, not a
    finding about this project's packaging); any other failure — a bad
    pyproject.toml, a missing vendor file, an sdist that does not build at
    all — fails the test, loudly.
    """
    out_dir = tmp_path_factory.mktemp("wheel")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(out_dir), str(ROOT)],
            capture_output=True, text=True, timeout=180, check=False)
    except subprocess.TimeoutExpired as exc:
        pytest.skip(f"pip wheel did not finish in time (likely no network to fetch "
                    f"the build backend): {exc}")
    if result.returncode != 0:
        low = (result.stderr or "").lower()
        if any(s in low for s in ("could not find a version", "temporary failure",
                                  "connection", "network", "resolve host")):
            pytest.skip(f"pip wheel could not reach the package index to fetch its "
                        f"build backend — an environment limitation, not a packaging "
                        f"defect:\n{result.stderr[-2000:]}")
        pytest.fail(f"pip wheel failed to build nestor-meaning:\n{result.stdout[-2000:]}\n"
                   f"{result.stderr[-2000:]}")
    wheels = list(out_dir.glob("*.whl"))
    assert len(wheels) == 1, f"expected exactly one wheel, found {wheels}"
    return wheels[0]


def test_the_vendored_cytoscape_library_and_its_license_ship_in_the_wheel(built_wheel):
    with zipfile.ZipFile(built_wheel) as z:
        names = set(z.namelist())
        assert "nestor/vendor/cytoscape.min.js" in names
        assert "nestor/vendor/cytoscape.LICENSE" in names
        # Not just present — the real bytes, not an empty placeholder a glob
        # match could satisfy without actually shipping the library.
        shipped = z.read("nestor/vendor/cytoscape.min.js")
        on_disk = (ROOT / "nestor" / "vendor" / "cytoscape.min.js").read_bytes()
        assert shipped == on_disk
        assert len(shipped) > 100_000    # a real ~425 KB bundle, not a stub


def test_an_installed_wheel_can_actually_build_the_served_page(tmp_path, built_wheel):
    """The point of the packaging test: import ui_page from a wheel install,
    not from this checkout, and confirm PAGE actually contains the library.

    Installed into an isolated venv rather than this test's own interpreter —
    installing into a running interpreter's site-packages mid-suite is the
    kind of action-at-a-distance this project's own tests avoid elsewhere.
    """
    venv_dir = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)],
                   check=True, capture_output=True, text=True, timeout=60)
    venv_python = venv_dir / "bin" / "python"
    install = subprocess.run(
        [str(venv_python), "-m", "pip", "install", "--no-deps", "-q", str(built_wheel)],
        capture_output=True, text=True, timeout=120)
    if install.returncode != 0:
        pytest.fail(f"installing the built wheel failed:\n{install.stderr[-2000:]}")
    check = subprocess.run(
        [str(venv_python), "-c",
         "from nestor.ui_page import PAGE; "
         "assert 'cytoscape' in PAGE and 'version=\"3.34.1\"' in PAGE; "
         "print('OK')"],
        capture_output=True, text=True, timeout=30)
    assert check.returncode == 0 and "OK" in check.stdout, (
        f"stdout={check.stdout!r} stderr={check.stderr!r}")
