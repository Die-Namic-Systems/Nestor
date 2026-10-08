"""Big Jim Motors: a refused draft is a refusal, not a traceback.

Two cars whose VINs end in the same KEY_TAIL characters share one key, and
Nestor refuses a second, different draft on a key that already holds one
(``ConflictingDraftError``). The demo must say so in its own voice, keep
Nestor's words, exit non-zero, and leave the first draft where it was.

Run as a subprocess against a temporary ``--home``: the script installs a
process-wide store, and the desk lives wherever ``--home`` points.
"""
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
DEMO = REPO / "demo" / "big_jim.py"

JEEP = ("2009 Jeep Wrangler, black, VIN 1J4FA24189L784210",
        "Lifted, minor rust on the frame")
KIA = ("2013 Kia Soul, white, VIN KNDJT2A54D7784210", "Backup camera, 61,000 miles")


def run(home, *args):
    return subprocess.run([sys.executable, str(DEMO), "--home", str(home), *args],
                          capture_output=True, text=True, cwd=REPO, timeout=120,
                          check=False)


def test_second_car_on_a_held_key_is_refused_cleanly(tmp_path):
    first = run(tmp_path, "draft", *JEEP)
    assert first.returncode == 0, first.stderr

    second = run(tmp_path, "draft", *KIA)
    assert second.returncode == 1
    assert "Traceback" not in second.stderr
    assert "refused" in second.stdout
    assert "'784210'" in second.stdout
    assert "Jeep Wrangler" in second.stdout          # who holds the key
    assert "Two different cars" in second.stdout
    assert "already holds the draft" in second.stdout  # Nestor's own words

    state = run(tmp_path, "state")
    assert "1 row(s)" in state.stdout
    assert "Kia Soul" not in state.stdout


def test_same_car_different_disclosure_is_refused_cleanly(tmp_path):
    assert run(tmp_path, "draft", *JEEP).returncode == 0
    again = run(tmp_path, "draft", JEEP[0], "No rust, never off-road")
    assert again.returncode == 1
    assert "Traceback" not in again.stderr
    assert "Same car, a different disclosure" in again.stdout
    assert "already holds the draft" in again.stdout


def test_same_draft_twice_is_not_a_refusal(tmp_path):
    assert run(tmp_path, "draft", *JEEP).returncode == 0
    repeat = run(tmp_path, "draft", *JEEP)
    assert repeat.returncode == 0, repeat.stdout + repeat.stderr
    assert "refused" not in repeat.stdout
