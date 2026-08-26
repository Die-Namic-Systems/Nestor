"""The audit — and the probe that has to actually do the thing it names.

`scripts/audit_against_constitution.py` attacks this package with the charter's
five Trace-ID clause cards. The test that matters is the tamper probe's, because that one
produced a **false FAIL against this package's headline claim**: it replaced the
target text `"a0"` in a ledger line, the chain never stores target text (it
keeps a `source_sha` digest), the replace was a no-op, `verify()` correctly
returned True on an unmodified file — and the audit reported CONST-0-5 as
failing. A probe that does not create the condition it names proves nothing, and
here it proved something false about the tamper-evidence this whole package
rests on.

So: the probe asserts it changed the line before drawing any conclusion, and
these pin that it still does.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import textwrap

import pytest

from nestor import keyring as keyring_mod
from tests._fleet_paths import constitution_cases

REPO = pathlib.Path(__file__).resolve().parent.parent
AUDIT = REPO / "scripts" / "audit_against_constitution.py"
CASES = constitution_cases()


def run(*args, env=None):
    return subprocess.run([sys.executable, str(AUDIT), *args],
                          capture_output=True, text=True, cwd=REPO, timeout=300,
                          env=env, check=False)


def test_it_refuses_a_constitution_it_cannot_read(tmp_path):
    done = run("--repo", str(tmp_path / "nope"))
    assert done.returncode == 1
    assert "could not look" in done.stdout, \
        "an unreadable constitution must not report a clean audit"


def test_the_tamper_probe_asserts_it_tampered():
    """The guard against the false FAIL. Pinned on the source, because the
    property is that the probe refuses to conclude from an unchanged file."""
    src = AUDIT.read_text()
    assert "the tamper must actually change the line" in src
    assert "the probe must edit a field the entry actually has" in src
    assert '"verifier": "someone"' in src, \
        "it must edit a field the ledger really writes, not one it digests"


def test_it_does_not_paraphrase_the_clauses():
    """Clause text comes from the checkout. A summary of somebody else's rule,
    written by the party being audited, is the least trustworthy sentence
    available — so the script must read, not restate."""
    src = AUDIT.read_text()
    assert "from feed_willow_constitution import extract" in src
    for invented in ("CLAUSE = ", "CLAUSES = {"):
        assert invented not in src, "the audit must not carry its own clause text"


def test_the_verdict_vocabulary_is_four_states():
    src = AUDIT.read_text()
    for verdict in ("satisfied", "differently", "not applicable", "FAILS"):
        assert f'"{verdict}"' in src or f"'{verdict}'" in src


def test_a_probe_that_raises_is_a_failure_not_a_pass():
    """A probe that dies proves nothing, and must never read as satisfied."""
    src = AUDIT.read_text()
    assert "the probe itself raised" in src
    assert "except Exception as exc:" in src


@pytest.mark.external
@pytest.mark.skipif(
    os.environ.get("NESTOR_EXTERNAL_TEST", "").strip().lower()
    not in {"1", "true", "yes", "on"},
    reason="set NESTOR_EXTERNAL_TEST=1 to audit an adjacent charter checkout",
)
@pytest.mark.skipif(not CASES.exists() or not any(CASES.glob("const_*.py")),
                    reason="no charter constitution cases present")
def test_against_the_real_constitution():
    done = run("--cases", str(CASES))
    assert done.returncode == 0, done.stdout + done.stderr
    assert "0 failing" in done.stdout
    # The two that are honestly not clean passes must stay visible as such.
    assert "differently" in done.stdout
    assert "CONST-0-5" in done.stdout and "CONST-0-2" in done.stdout


# --- IDEAS §6.98: an ambient NESTOR_KEYRING must not produce a false FAILS --

def _fixture_cases(tmp_path) -> pathlib.Path:
    """Two minimal ``const_*.py`` cards, naming the two clauses whose probes
    seal under a synthetic verifier in-process (``probe_ratify``,
    ``probe_ledger``) — no subprocess of their own, so nothing else about the
    environment they run under can explain a pass or a fail."""
    cases = tmp_path / "cases"
    cases.mkdir()
    (cases / "const_0_2_ratify.py").write_text(textwrap.dedent('''\
        """CONST-0-2 — self-ratification.

        The forbidden act, in one line: *this package's own machinery promoting
        its own claim to verified.*
        """

        TRACE_ID = "CONST-0-2"
        CLAUSE = "A claim may not ratify itself."
        '''))
    (cases / "const_0_5_ledger.py").write_text(textwrap.dedent('''\
        """CONST-0-5 — tamper-evidence.

        The forbidden act, in one line: *rewriting a past entry without the
        chain noticing.*
        """

        TRACE_ID = "CONST-0-5"
        CLAUSE = "The ledger must detect tampering with a past entry."
        '''))
    return cases


def test_an_ambient_keyring_does_not_produce_a_false_fails(tmp_path):
    """The exact regression IDEAS §6.98 measured: with a real ``NESTOR_KEYRING``
    exported — the correct configuration for a real deployment — the audit used
    to report clauses FAILING because its own probes seal as ``"someone"`` and
    ``"a-machine-with-the-key"``, names deliberately not in any real keyring.

    Run against the unfixed script this reports 2 failing (CONST-0-2,
    CONST-0-5), each with 'the probe itself raised UnknownVerifierError' —
    proving the failure was the harness reading ambient config, not the
    clause. Fixed, the same run reports 0 failing regardless of what the
    calling shell has exported.
    """
    ring = keyring_mod.Keyring(path=str(tmp_path / "keys.json"))
    ring.add("rita")                        # a real person; not a probe's name
    ring.save()
    env = {**os.environ, "NESTOR_KEYRING": str(ring.path)}
    env.pop("NESTOR_SEAL_KEY", None)

    done = run("--cases", str(_fixture_cases(tmp_path)), env=env)
    out = done.stdout + done.stderr
    assert done.returncode == 0, out
    assert "0 failing" in out, out
    assert "the probe itself raised" not in out, (
        "a probe died and the audit reported it as an ordinary verdict: " + out)
    assert "UnknownVerifierError" not in out, out


@pytest.mark.skipif(not CASES.exists() or not any(CASES.glob("const_*.py")),
                    reason="no charter constitution cases present")
def test_the_ledger_clause_is_satisfied_by_a_probe_that_really_tampers():
    """Not just 'satisfied' — satisfied with evidence of a broken chain."""
    out = run("--cases", str(CASES)).stdout
    tail = out.split("CONST-0-5", 1)[-1]
    assert "broken chain" in tail, (
        "the ledger verdict must cite the chain breaking, not merely assert it — "
        "the first version reported a verdict from a file it had not changed")
