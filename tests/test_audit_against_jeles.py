"""The jeles audit — held to its reader, because that is where these go wrong.

`scripts/audit_against_jeles.py` reads another repository's rules by parsing and
then attacks this package with them. Two failure modes, and this repo has now
produced both in one day:

* **the reader misreads, and the audit reports a hole in somebody else's repo.**
  `test_feed_willow_constitution.py` exists because that happened twice.
* **the probe measures a configuration nobody chose, and reports FAILS against
  this package's own subject.** That happened to the constitution audit's
  CONST-0-5 probe this morning and to this file's witness probe this afternoon.

So the gates are on the extractor, on fixtures written here rather than on
jeles — jeles is not a dependency, is not in CI, and a test that skipped without
it would leave the reader ungated in exactly the environment that runs it. Two
tests drive the real checkout when present, marked skip otherwise.
"""
from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys
import textwrap

import pytest

from nestor import keyring as keyring_mod

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import audit_against_jeles as AUDIT

from tests._fleet_paths import jeles_checkout

JELES = jeles_checkout()
SCRIPT = REPO / "scripts" / "audit_against_jeles.py"


def mod(tmp_path, body: str, name: str = "m.py") -> pathlib.Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


# --- reading constants -----------------------------------------------------

def test_a_plain_int_constant(tmp_path):
    assert AUDIT._module_constant(mod(tmp_path, "MIN = 2\n"), "MIN") == 2


def test_a_frozenset_is_a_call_not_a_literal(tmp_path):
    """`ast.literal_eval` refuses a Call, and jeles writes its allow-lists as
    `frozenset({...})`. Without the one-constructor unwrap this reads as None,
    and the audit would report that jeles names nobody as un-witnessable."""
    got = AUDIT._module_constant(
        mod(tmp_path, "_NON_WITNESS = frozenset({'a.com', 'b.com'})\n"), "_NON_WITNESS")
    assert got == {"a.com", "b.com"}


def test_a_dict_of_frozensets(tmp_path):
    got = AUDIT._module_constant(mod(tmp_path, """
        _ALLOWED_ARGS = {
            "put_nugget": frozenset({"question", "answer"}),
            "log_gap": frozenset({"question"}),
        }
        """), "_ALLOWED_ARGS")
    assert got == {"put_nugget": {"question", "answer"}, "log_gap": {"question"}}


def test_an_annotated_assignment_counts(tmp_path):
    got = AUDIT._module_constant(mod(tmp_path, "X: int = 7\n"), "X")
    assert got == 7


def test_a_missing_constant_is_none_not_a_guess(tmp_path):
    assert AUDIT._module_constant(mod(tmp_path, "Y = 1\n"), "X") is None


def test_a_module_that_does_not_parse_is_none(tmp_path):
    assert AUDIT._module_constant(mod(tmp_path, "X = (\n"), "X") is None


# --- reading a default argument --------------------------------------------

def test_a_positional_default(tmp_path):
    """Where one of jeles' rungs actually lives — a default, not a constant."""
    got = AUDIT._default_arg(mod(tmp_path, """
        def put_nugget(question, answer, verification_kind="human"):
            pass
        """), "put_nugget", "verification_kind")
    assert got == "human"


def test_positional_only_args_do_not_shift_the_alignment(tmp_path):
    """`arguments.posonlyargs` is a SEPARATE list from `args`, and `defaults`
    spans both. Reading only `args` mis-aligns every default by the number of
    positional-only parameters, so this would report a neighbour's value.

    jeles' `put_nugget` has no `/`, which is exactly why the run that mattered
    would not have caught it — and why the gate is a fixture, not the checkout.
    """
    got = AUDIT._default_arg(mod(tmp_path, """
        def f(a, b="B", /, c="C", d="D"):
            pass
        """), "f", "c")
    assert got == "C", "posonly parameters must be counted in the alignment"
    assert AUDIT._default_arg(mod(tmp_path, """
        def f(a, b="B", /, c="C", d="D"):
            pass
        """), "f", "b") == "B"


def test_a_keyword_only_default(tmp_path):
    got = AUDIT._default_arg(mod(tmp_path, """
        def f(a, *, kind="machine"):
            pass
        """), "f", "kind")
    assert got == "machine"


def test_an_argument_with_no_default_is_none(tmp_path):
    assert AUDIT._default_arg(mod(tmp_path, "def f(a, b=1):\n    pass\n"), "f", "a") is None


def test_a_missing_function_is_none(tmp_path):
    assert AUDIT._default_arg(mod(tmp_path, "def g(a=1):\n    pass\n"), "f", "a") is None


# --- refusing to look ------------------------------------------------------

def test_a_checkout_without_the_files_reads_none(tmp_path):
    """'I could not look' — never a clean audit against a repo that is not there.

    Measured while mutation-testing: removing the ``exists()`` guard alone leaves
    this green, because ``_module_constant`` returns None for an unreadable path
    and the closing ``if rules["min_sources"] and rules["pinned_rung"]`` catches
    it anyway. Two independent mechanisms, not a vacuous test — remove *both* and
    three tests here go red. Recorded so the next reader does not re-run the
    mutation that survives and conclude the gate is decorative.
    """
    assert AUDIT.read_rules(tmp_path) is None


def test_a_checkout_missing_one_file_reads_none(tmp_path):
    (tmp_path / "jeles").mkdir()
    (tmp_path / "jeles" / "_independence.py").write_text("MIN_INDEPENDENT_SOURCES = 2\n")
    assert AUDIT.read_rules(tmp_path) is None


def test_a_missing_repo_exits_nonzero(tmp_path):
    done = subprocess.run([sys.executable, str(SCRIPT), "--repo", str(tmp_path)],
                          capture_output=True, text=True, timeout=180, check=False)
    assert done.returncode == 1
    assert "could not read" in done.stdout


def test_it_never_imports_the_repo_it_reads():
    """Parsing, not importing — the same architectural pin the feeders carry."""
    src = SCRIPT.read_text(encoding="utf-8")
    body = src.split('"""', 2)[-1]
    for forbidden in ("importlib", "exec(", "runpy", "__import__"):
        assert forbidden not in body, f"the audit must not {forbidden}"
    assert re.search(r"(?<!literal_)\beval\(", body) is None
    assert "ast.parse" in body


# --- IDEAS §6.98: an ambient NESTOR_KEYRING must not produce a false FAILS --

def _fake_jeles_repo(tmp_path) -> pathlib.Path:
    """A minimal, self-contained stand-in for a jeles checkout — just enough
    for :func:`AUDIT.read_rules` to succeed, so the probes run without needing
    the real repository (not a dependency, not in CI, per this file's own
    module docstring)."""
    repo = tmp_path / "jeles"
    (repo / "jeles" / "reactions").mkdir(parents=True)
    (repo / "jeles" / "_independence.py").write_text(
        "MIN_INDEPENDENT_SOURCES = 2\n")
    (repo / "jeles" / "reactions" / "conflict_scan.py").write_text(textwrap.dedent("""\
        PROPOSAL_VERIFICATION_KIND = "human"
        _NON_WITNESS = frozenset({"a-search-engine.example"})
        _ALLOWED_ARGS = {"put_nugget": frozenset({"question", "answer"})}
        """))
    (repo / "jeles" / "corpus.py").write_text(textwrap.dedent("""\
        def put_nugget(question, answer, verification_kind="human"):
            pass
        """))
    return repo


def test_an_ambient_keyring_does_not_produce_a_false_fails(tmp_path):
    """The exact second false verdict IDEAS §6.98 records: JELES-INDEPENDENCE
    seals as ``verifier="one-person"`` in-process. With a real ``NESTOR_KEYRING``
    exported — correct for a real deployment — that name is not registered
    anywhere, ``memory.add_pair`` used to raise ``UnknownVerifierError``, the
    probe caught its own failure, and the audit published 'jeles fails an
    independence clause' from a fault that was the harness's, not jeles'.

    Run against the unfixed script this reports the clause FAILING with 'the
    probe itself raised UnknownVerifierError'. Fixed, it reads 'differently'
    regardless of what the calling shell has exported.
    """
    ring = keyring_mod.Keyring(path=str(tmp_path / "keys.json"))
    ring.add("rita")                        # a real person; not a probe's name
    ring.save()
    env = {**os.environ, "NESTOR_KEYRING": str(ring.path)}
    env.pop("NESTOR_SEAL_KEY", None)

    done = subprocess.run([sys.executable, str(SCRIPT), "--repo",
                           str(_fake_jeles_repo(tmp_path))],
                          capture_output=True, text=True, timeout=180, env=env,
                          check=False)
    out = re.sub(r"\x1b\[[0-9;]*m", "", done.stdout + done.stderr)
    assert "the probe itself raised" not in out, (
        "a probe died and the audit reported it as an ordinary verdict: " + out)
    # JELES-WITNESS legitimately prints "UnknownVerifierError" — its "keyring"
    # branch installs its own explicit keyring and *expects* an unregistered
    # witness to be refused. The bug this guards is specific to
    # JELES-INDEPENDENCE, which never touches a keyring on purpose.
    tail = out.split("JELES-INDEPENDENCE", 1)[-1].split("JELES-DEFAULT")[0]
    assert "FAILS" not in tail, out
    assert "UnknownVerifierError" not in tail, out
    assert "differently" in tail, out
    assert "0 failing" in out, out
    assert done.returncode == 0, out


# --- against the real checkout ---------------------------------------------

@pytest.mark.skipif(not JELES.exists(), reason="no jeles checkout present")
def test_the_real_rules_are_all_readable():
    rules = AUDIT.read_rules(JELES)
    assert rules is not None
    assert isinstance(rules["min_sources"], int) and rules["min_sources"] >= 1
    assert rules["pinned_rung"], "conflict_scan pins a rung"
    assert rules["non_witness"], "jeles names parties that cannot witness"
    assert rules["allowed_args"], "the proposal allow-list must be readable"
    assert rules["put_nugget_rung"], (
        "put_nugget's rung is a default argument — if this is None, check the "
        "parser before reporting that jeles pins nothing")


@pytest.mark.skipif(not JELES.exists(), reason="no jeles checkout present")
def test_the_witness_probe_runs_both_signing_configurations():
    """The correction. Its first version measured only the single-key mode and
    returned FAILS against this package's own subject; under a keyring the same
    call is refused before the store is touched. A verdict of FAILS here means
    the probe found an unnamed verifier accepted in *both* modes."""
    done = subprocess.run([sys.executable, str(SCRIPT), "--repo", str(JELES)],
                          capture_output=True, text=True, timeout=600, check=False)
    out = re.sub(r"\x1b\[[0-9;]*m", "", done.stdout)
    assert "single shared key:" in out and "keyring:" in out, (
        "both configurations must be reported, or the verdict is about whichever "
        "one the script happened to be running in")
    assert "0 failing" in out
    assert done.returncode == 0
