"""The quorum measurement — held to the two numbers it exists to keep apart.

`scripts/count_countersignatures.py` answers step 2 of
`docs/seal-staleness-and-quorum.md`. Two things about it can be wrong in ways
that look right, and both are what these gates are for:

* **the count.** A seal is idempotent and a countersignature is not, so the
  entries and the distinct actors differ by every repeat. The memo says so
  before anybody runs it; a test that only checked "it found some" would pass
  on the inflated number.
* **the zero.** A chain with one reviewer *cannot* produce a countersignature,
  so its zero is not evidence about quorum. Reporting that zero the same way as
  a zero from a chain with three reviewers is the `feed_all.py` conflation with
  different nouns, and it is the one this script exists to refuse.

Most of it runs on hand-built entry lists, because `read` and `measure` are pure
and that is where the logic is. One test drives a **real** chain end to end —
built by `memory.add_pair` in a subprocess, so the ledger and store globals are
that process's problem and never this one's — because the entry shapes are
`nestor.memory`'s to change, and a fixture that mirrors them would keep passing
after they moved.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import count_countersignatures as COUNT       # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "count_countersignatures.py"


def seal(pair_id: str, who: str) -> dict:
    return {"kind": "seal", "pair_id": pair_id, "verifier": who}


def counter(pair_id: str, who: str, first: str) -> dict:
    return {"kind": "countersign", "pair_id": pair_id,
            "verifier": who, "countersigned": first}


# --- the count -------------------------------------------------------------

def test_repeat_attestations_do_not_inflate_the_measurement():
    """The memo's warning, as a gate. `grep -c` and step 2 disagree here.

    Three countersignatures by one person on one pair are three entries and one
    *act*. The raw number is the one a UI retry or a flaky client moves.
    """
    got = COUNT.measure([
        seal("p1", "ada"),
        counter("p1", "bo", "ada"),
        counter("p1", "bo", "ada"),
        counter("p1", "bo", "ada"),
    ])
    assert got["countersign_entries"] == 3
    assert got["countersign_acts"] == 1


def test_both_numbers_are_reported_not_just_the_right_one():
    """The gap is the evidence. Keeping only the correct count hides that the
    naive one would have been wrong, which is the thing worth showing."""
    got = COUNT.measure([seal("p1", "ada"), counter("p1", "bo", "ada"),
                         counter("p1", "bo", "ada")])
    assert got["countersign_entries"] != got["countersign_acts"]


def test_two_people_on_one_pair_reach_the_bar_and_one_does_not():
    got = COUNT.measure([
        seal("p1", "ada"), counter("p1", "bo", "ada"),   # two names
        seal("p2", "ada"),                               # one name
    ])
    assert got["pairs_at_quorum"] == 1
    assert got["at_quorum"]["p1"] == {"ada", "bo"}
    assert "p2" not in got["at_quorum"]


def test_a_countersignature_names_both_parties_by_itself():
    """`countersigned` carries the first sealer, so a chain written with
    ``audit=False`` on the seal path — where no `seal` entry exists — still
    identifies both people. Without reading that field the pair would show one
    attester and the actor count would be short by everyone who sealed quietly.
    """
    got = COUNT.measure([counter("p1", "bo", "ada")])
    assert got["seals"] == 0
    assert got["actors"] == ["ada", "bo"]
    assert got["pairs_at_quorum"] == 1


# --- the zero --------------------------------------------------------------

def test_one_reviewer_is_no_opportunity_not_a_measurement():
    """The discriminator. `add_pair` logs a countersignature only when
    ``first and verifier and first != verifier``, so this chain could not have
    produced one however its reviewers felt about quorum."""
    got = COUNT.measure([seal("p1", "solo"), seal("p2", "solo")])
    assert got["countersign_acts"] == 0
    assert COUNT.verdict(got) == COUNT.NO_OPPORTUNITY


def test_two_reviewers_and_no_countersignature_is_a_measurement():
    """The other half, and the one that makes the first half mean something. A
    zero here IS data: the opportunity existed and went unused."""
    got = COUNT.measure([seal("p1", "ada"), seal("p2", "bo")])
    assert got["countersign_acts"] == 0
    assert COUNT.verdict(got) == COUNT.MEASURED


def test_an_actor_counts_whatever_kind_of_decision_they_made():
    """Deliberately not a per-kind allow-list — that would be a second copy of
    `cascade.LEDGER_KINDS` to keep in step, and a kind missing from it would
    under-count the population that decides whether a zero means anything."""
    got = COUNT.measure([seal("p1", "ada"),
                         {"kind": "reject_pair", "pair_id": "p2", "verifier": "bo"}])
    assert COUNT.verdict(got) == COUNT.MEASURED
    assert got["actors"] == ["ada", "bo"]


def test_an_unnamed_decider_is_not_an_actor():
    """An empty or missing verifier is nobody. Counting it would manufacture a
    second reviewer out of an anonymous write — the same wrong polarity
    `add_pair` avoids by requiring both sides to name themselves."""
    got = COUNT.measure([seal("p1", "ada"), {"kind": "seal", "pair_id": "p2",
                                             "verifier": "  "},
                         {"kind": "seal", "pair_id": "p3"}])
    assert got["actors"] == ["ada"]
    assert COUNT.verdict(got) == COUNT.NO_OPPORTUNITY


# --- reading ---------------------------------------------------------------

def test_a_missing_chain_is_none_and_an_empty_one_is_a_list(tmp_path):
    """`None` is 'I could not look'; `[]` is 'the chain is empty'. Different
    facts, and the reason `scripts/feed_all.py` exists at all."""
    assert COUNT.read(tmp_path / "absent.jsonl") is None
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    assert COUNT.read(empty) == []


def test_a_line_that_is_not_json_makes_the_whole_chain_unreadable(tmp_path):
    """Not 'skip the bad line'. A chain with a line nobody can parse is a chain
    whose contents are unknown, and counting the rest would report a number over
    an unknown denominator."""
    p = tmp_path / "l.jsonl"
    p.write_text(json.dumps(seal("p1", "ada")) + "\nnot json\n", encoding="utf-8")
    assert COUNT.read(p) is None


def test_a_json_line_that_is_not_an_object_is_unreadable(tmp_path):
    p = tmp_path / "l.jsonl"
    p.write_text("[1, 2, 3]\n", encoding="utf-8")
    assert COUNT.read(p) is None


# --- end to end, against a chain nestor actually wrote ----------------------

_BUILD = """
import os, sys, pathlib
sys.path.insert(0, {root!r})
os.environ['NESTOR_SEAL_KEY'] = 'test-fixture-key-not-a-secret'
w = pathlib.Path({work!r})
from nestor import cascade, memory, storage
from nestor.sqlite_store import SqliteStore
cascade.set_ledger_path(str(w / 'ledger.jsonl'))
s = SqliteStore(str(w / 'n.db')); s.init_db(); s.memory_init()
storage.set_store(s)
def seal(a, b, v):
    memory.add_pair(a, b, 'd', 't', status='sealed', verifier=v,
                    origin='fixture', store=s)
seal('q0', 'a0', 'reviewer-ada')
for _ in range(3):
    seal('q0', 'a0', 'reviewer-bo')
"""


def _real_chain(tmp_path) -> pathlib.Path:
    """A chain written by `memory.add_pair`, in its own interpreter.

    A subprocess because `set_ledger_path` and `set_store` are process-wide —
    installing a fixture chain in the test process is how a suite ends up with
    one test's ledger under another's feet.
    """
    done = subprocess.run(
        [sys.executable, "-c", _BUILD.format(root=str(ROOT), work=str(tmp_path))],
        capture_output=True, text=True, timeout=180)
    assert done.returncode == 0, f"fixture chain failed: {done.stderr[-800:]}"
    return tmp_path / "ledger.jsonl"


def test_the_asymmetry_is_real_and_not_just_described(tmp_path):
    """Seal idempotent, countersignature not — measured on a chain nestor wrote.

    The rest of this file asserts against entry dicts written here, which pins
    the arithmetic and nothing about `memory`. This is the one that would notice
    if a re-seal stopped producing a `countersign` entry, or started producing a
    second `seal`.
    """
    entries = COUNT.read(_real_chain(tmp_path))
    assert entries is not None
    got = COUNT.measure(entries)
    assert got["seals"] == 1, "three re-seals by the same target must add no seal"
    assert got["countersign_entries"] == 3, "each countersignature is its own event"
    assert got["countersign_acts"] == 1, "by one person, on one pair"
    assert got["pairs_at_quorum"] == 1


def test_it_refuses_to_count_over_a_tampered_chain(tmp_path):
    """A tally on a broken trail reads as a measurement, which is worse than
    none. Exit 1 and say the chain is the problem."""
    path = _real_chain(tmp_path)
    lines = path.read_text(encoding="utf-8").splitlines()
    victim = lines[0]
    assert '"verifier": "reviewer-ada"' in victim, (
        "the tamper must edit a field the entry has, or it proves nothing")
    lines[0] = victim.replace('"verifier": "reviewer-ada"', '"verifier": "reviewer-eve"')
    assert lines[0] != victim
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    done = subprocess.run([sys.executable, str(SCRIPT), "--ledger", str(path)],
                          capture_output=True, text=True, timeout=180)
    assert done.returncode == 1
    assert COUNT.BROKEN in done.stdout


def test_a_missing_ledger_exits_nonzero_and_says_which_kind_of_nothing(tmp_path):
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--ledger", str(tmp_path / "absent.jsonl")],
        capture_output=True, text=True, timeout=180)
    assert done.returncode == 1
    assert COUNT.UNREADABLE in done.stdout
    assert "Not 'nobody countersigns'" in done.stdout


def test_it_writes_nothing_to_the_chain_it_reads(tmp_path):
    """A measurement that appends to the trail it measures is not a
    measurement. Pinned on the bytes, not on the absence of a write call."""
    path = _real_chain(tmp_path)
    before = path.read_bytes()
    subprocess.run([sys.executable, str(SCRIPT), "--ledger", str(path)],
                   capture_output=True, text=True, timeout=180)
    assert path.read_bytes() == before
