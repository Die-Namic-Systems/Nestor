"""The cross-instance trust boundary, executed rather than argued.

`portable.py` claims a memory can move between deployments without laundering
trust. Unit tests exercise that inside one interpreter, where the store, ledger
override, matcher and keyring are all module globals — so two "instances" are
one instance wearing two hats. `scripts/two_instances.py` is the version with
two of everything and a subprocess per command, and this runs it.

Every assertion here is the script's own; it exits non-zero if one stops
holding. What this file adds is that CI notices. Run as a subprocess for the
same reason the script exists: it installs process-wide state per box, and a
test that imported it would be the very confusion it was written to avoid.
"""
import pathlib
import subprocess
import sys

import pytest

# The demo's first step is `nestor keys add --type ed25519`, which needs the
# [keys] extra (cryptography). Without it every test here is the same crash in
# setup, three steps from the cause — so skip like the other asymmetric suites
# (test_asymmetric_seals, test_client_signed_seals) rather than hard-fail for a
# missing optional dependency. CI installs .[keys], so these run there.
pytest.importorskip("cryptography")

REPO = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "two_instances.py"


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, cwd=REPO, timeout=300)


def test_the_two_boxes_stay_independent_and_the_seal_does_not_cross():
    done = run()
    assert done.returncode == 0, done.stdout + done.stderr
    assert "CLAIM FAILED" not in done.stdout
    # The counts, not the labels. `nestor import` prints "N demoted to draft"
    # whether N is 0 or 1, so asserting the words passes even when the trust
    # check has been removed — measured, by removing it.
    assert "0 sealed, 1 demoted to draft" in done.stdout
    assert "1 sealed, 0 demoted to draft" in done.stdout


def test_it_shows_the_three_things_it_is_for():
    out = run().stdout
    for beat in ("They are actually independent",
                 "A seal does not cross just because a file did",
                 "With the peer's PUBLIC key, it verifies"):
        assert beat in out, f"missing beat: {beat}"
    # The two readings that carry the argument: the same query answered
    # differently by each box, and a peer entry that can verify and not sign.
    assert "'A great big hug' (nieves)" in out and "'With love' (paco)" in out
    assert "{'nieves': True, 'paco': False}" in out


def test_it_cleans_up_after_itself_unless_told_not_to(tmp_path):
    kept = tmp_path / "kept"
    assert run("--keep", str(kept)).returncode == 0
    for box in ("a", "b"):
        assert (kept / box / "nestor.db").exists()
        assert (kept / box / "ledger.jsonl").exists()
        assert (kept / box / "keys.json").exists()
    assert (kept / "from-b.json").exists()

    before = set(pathlib.Path("/tmp").glob("nestor-two-*"))
    assert run().returncode == 0
    assert not (set(pathlib.Path("/tmp").glob("nestor-two-*")) - before), \
        "the default run must not leave two instances behind"


def test_the_boxes_do_not_inherit_the_developers_environment(tmp_path, monkeypatch):
    """The isolation that matters most is the one nobody looks at.

    A box that reads NESTOR_SEAL_KEY or NESTOR_KEYRING from the launching shell
    is not a second instance, and the failure is silent — it would seal with the
    developer's key and the demotion in beat 2 would quietly stop happening.
    """
    monkeypatch.setenv("NESTOR_SEAL_KEY", "the-developers-own-key")
    monkeypatch.setenv("NESTOR_KEYRING", str(tmp_path / "developer-keys.json"))
    done = run()
    assert done.returncode == 0, done.stdout + done.stderr
    assert "demoted to draft" in done.stdout
    assert not (tmp_path / "developer-keys.json").exists(), \
        "a box wrote into the keyring the shell named"
