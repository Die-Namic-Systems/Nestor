"""``import nestor`` is dependency-light, and this is the test that makes that
a guarantee rather than a docstring promise.

``nestor/__init__.py`` states it: the library surface is imported eagerly, but
the transports (``ui`` / ``cli`` / ``serve``) are pulled *on demand* "since a
library import should not pull in an HTTP server," and ``pyproject.toml`` keeps
core ``dependencies = []``. Two fleet consumers depend on that being true, not
merely intended: ``UTETY`` forbids network egress in its core (its own
``test_no_egress.py``) and ``terpsi-music`` forbids non-local inference on
student data — both need to vendor or pin Nestor's seal/ledger organ *knowing*
a bare import reaches nothing third-party and opens no socket. Jeles ships the
same guard (``test_import_purity.py``); this is Nestor's.

The check runs in a **fresh subprocess** so the assertion is about what
``import nestor`` itself pulls in, not what some earlier test in this session
already imported into ``sys.modules``.
"""
from __future__ import annotations

import subprocess
import sys

#: Transports and cloud seams that are reached on demand, never by a bare
#: ``import nestor``. ``serve``/``ui``/``ui_page``/``cli`` are the HTTP/terminal
#: surfaces the package docstring says stay lazy; ``cloud_seal`` hard-imports
#: ``willow_gate`` (the optional ``[gate]`` extra) and must not be dragged in
#: either. If any of these appears after a plain import, the laziness regressed.
FORBIDDEN_SUBMODULES = (
    "nestor.serve",
    "nestor.ui",
    "nestor.ui_page",
    "nestor.cli",
    "nestor.cloud_seal",
)

#: HTTP-server / socket-server stdlib modules. These are stdlib, so they would
#: not trip the third-party check below, but a library import pulling one in is
#: exactly the "should not pull in an HTTP server" regression, so name them.
FORBIDDEN_SERVERS = ("http.server", "socketserver")

_PROBE = r"""
import sys
before = set(sys.modules)
import nestor
after = set(sys.modules)
new = after - before
tops = sorted({m.split(".")[0] for m in new})
third_party = [m for m in tops if m not in sys.stdlib_module_names and m != "nestor"]
eager = sorted(m for m in sys.modules if m in %r or m in %r)
print("VERSION", nestor.__version__)
print("THIRD_PARTY", ",".join(third_party))
print("EAGER", ",".join(eager))
""" % (FORBIDDEN_SUBMODULES, FORBIDDEN_SERVERS)


def _probe() -> dict:
    """Import nestor in a clean interpreter and report what it pulled in."""
    done = subprocess.run([sys.executable, "-c", _PROBE],
                          capture_output=True, text=True)
    assert done.returncode == 0, (
        f"`import nestor` failed in a clean interpreter:\n{done.stderr}")
    out = {}
    for line in done.stdout.splitlines():
        key, _, val = line.partition(" ")
        out[key] = val
    return out


def test_a_bare_import_pulls_in_nothing_third_party():
    """`import nestor` reaches only the standard library — the property that
    lets a zero-egress host vendor it without auditing a dependency tree."""
    result = _probe()
    third_party = [m for m in result["THIRD_PARTY"].split(",") if m]
    assert third_party == [], (
        "`import nestor` pulled in third-party module(s) "
        f"{third_party}; core is meant to be pure stdlib (pyproject core "
        "dependencies = []). A new eager import in nestor/__init__.py's import "
        "block, or in something it imports, broke the guarantee.")


def test_a_bare_import_opens_no_transport_or_server():
    """The ui/cli/serve transports and the cloud_seal gate seam stay lazy — a
    library import opens no HTTP server and drags in no willow-gate."""
    result = _probe()
    eager = [m for m in result["EAGER"].split(",") if m]
    assert eager == [], (
        f"`import nestor` eagerly imported {eager}; these are on-demand "
        "surfaces (nestor/__init__.py: 'a library import should not pull in an "
        "HTTP server'). Import them where they are used, not at package top.")


def test_the_probe_would_notice_a_regression():
    """The guard can fail: importing a forbidden submodule directly makes the
    eager-transport assertion catch it. A test that cannot fail is not a gate."""
    probe = _PROBE.replace("import nestor\n", "import nestor\nimport nestor.serve\n")
    done = subprocess.run([sys.executable, "-c", probe],
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    eager_line = [ln for ln in done.stdout.splitlines() if ln.startswith("EAGER")][0]
    assert "nestor.serve" in eager_line, (
        "the probe did not observe an eagerly-imported nestor.serve even when "
        "it was imported outright — the purity check is not actually watching "
        "sys.modules and would not catch a real regression.")
