"""The staleness listing — held to the two things it must never become.

`scripts/due_for_reverification.py` implements §3 of
`docs/seal-staleness-and-quorum.md`: an aged seal keeps serving and additionally
appears as work for a person. The memo's argument is that the *other* design — a
decay curve feeding a score multiplier — is wrong for this package specifically,
because it converts "a human checked this" back into a confidence number and
does it silently, with no decision in the trail to explain why an answer stopped
being served.

So the gates are not mostly about arithmetic:

* **it must not become a multiplier.** No score, no weight, no threshold that any
  serving path consults. Pinned on the source, because the day someone wires this
  into `best_sealed` is the day the memo was written to prevent.
* **it must not read the row's clock.** `signing._message` covers
  `[source_norm, target_text, verifier]` and nothing else, so `created_at` is
  outside the signature and a staleness computed from it is resettable by anyone
  who can write the row. Measured in the fixture below rather than asserted.

The arithmetic is tested too, on hand-built entries, because that is where an
off-by-one hides. One test drives a real chain.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import due_for_reverification as DUE            # noqa: E402

SCRIPT = ROOT / "scripts" / "due_for_reverification.py"
NOW = dt.datetime(2027, 1, 1, tzinfo=dt.timezone.utc)


def at(days_ago: int) -> str:
    return (NOW - dt.timedelta(days=days_ago)).isoformat()


def seal(pair_id: str, who: str, days_ago: int) -> dict:
    return {"kind": "seal", "pair_id": pair_id, "verifier": who, "ts": at(days_ago)}


# --- what it must never become --------------------------------------------

def test_it_carries_no_score_weight_or_multiplier():
    """§3's whole argument. A decay curve feeding a threshold is the design this
    file exists instead of, so the words should not be in it doing that job."""
    body = SCRIPT.read_text(encoding="utf-8").split('"""', 2)[-1]
    for forbidden in ("weight", "multiplier", "SEAL_THRESHOLD", "decay"):
        assert forbidden not in body, (
            f"{forbidden!r} appears in the listing's code — this must stay a "
            f"list, not a number anything serves from")


def test_it_never_writes_and_never_opens_a_store():
    body = SCRIPT.read_text(encoding="utf-8").split('"""', 2)[-1]
    for forbidden in ("add_pair", "set_store", "SqliteStore", "memory_seal",
                      "_ledger_append", "write_text", "open("):
        assert forbidden not in body, f"the listing must not {forbidden}"


def test_it_does_not_read_the_rows_own_clock():
    """Age comes from the chain. `created_at` is outside the signature, so a
    staleness read off it is a number anyone who can write the row can put
    back — see the fixture test below, which moves one and watches the seal
    keep verifying."""
    body = SCRIPT.read_text(encoding="utf-8").split('"""', 2)[-1]
    assert "created_at" not in body


# --- the arithmetic --------------------------------------------------------

def test_the_freshest_decision_per_pair_wins():
    """A re-verification resets the clock — the point of a queue over a curve."""
    rows = DUE.age_seals([seal("p1", "ada", 400),
                          {"kind": "countersign", "pair_id": "p1",
                           "verifier": "bo", "countersigned": "ada", "ts": at(10)}], NOW)
    assert len(rows) == 1 and rows[0]["days"] == 10


def test_a_retired_pair_is_not_overdue():
    """A superseded row is finished, not late. Listing it would be noise in the
    one place noise costs a person time."""
    rows = DUE.age_seals([seal("p1", "ada", 400),
                          {"kind": "supersede", "pair_id": "p1", "ts": at(5)}], NOW)
    assert rows == []


def test_only_the_final_entry_is_marked_unvouched_for():
    """`ledger.verify` documents it: each line is vouched for by the line after
    it. Measured on a real chain in `test_editing_the_tail_timestamp_is_not
    _caught`; here the flag itself is pinned."""
    rows = DUE.age_seals([seal("p1", "ada", 300), seal("p2", "bo", 200)], NOW)
    by_id = {r["pair_id"]: r for r in rows}
    assert by_id["p1"]["tail"] is False
    assert by_id["p2"]["tail"] is True


def test_an_entry_with_no_parseable_timestamp_is_skipped_not_dated_now():
    """Defaulting a missing date to now would report an ancient seal as fresh —
    the one direction of error that hides work rather than inventing it."""
    rows = DUE.age_seals([{"kind": "seal", "pair_id": "p1", "verifier": "ada"},
                          {"kind": "seal", "pair_id": "p2", "verifier": "bo",
                           "ts": "not a date"}], NOW)
    assert rows == []


def test_a_naive_timestamp_is_read_as_utc_not_crashed_on():
    rows = DUE.age_seals([{"kind": "seal", "pair_id": "p1", "verifier": "ada",
                           "ts": "2026-01-01T00:00:00"}], NOW)
    assert len(rows) == 1 and rows[0]["days"] > 300


# --- reading ---------------------------------------------------------------

def test_a_missing_chain_is_none_not_an_empty_list(tmp_path):
    assert DUE.read(tmp_path / "absent.jsonl") is None
    p = tmp_path / "empty.jsonl"
    p.write_text("", encoding="utf-8")
    assert DUE.read(p) == []


def test_a_missing_chain_exits_nonzero_and_says_which_nothing(tmp_path):
    done = subprocess.run([sys.executable, str(SCRIPT), "--ledger",
                           str(tmp_path / "absent.jsonl")],
                          capture_output=True, text=True, timeout=180)
    assert done.returncode == 1
    assert DUE.UNREADABLE in done.stdout
    assert "Not 'nothing is stale'" in done.stdout


# --- against a chain nestor wrote ------------------------------------------

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
for i in range(3):
    memory.add_pair('q%d' % i, 'a%d' % i, 'source', 'serves', status='sealed',
                    verifier='rita', origin='fixture', store=s)
"""


def _chain(tmp_path) -> pathlib.Path:
    done = subprocess.run(
        [sys.executable, "-c", _BUILD.format(root=str(ROOT), work=str(tmp_path))],
        capture_output=True, text=True, timeout=180)
    assert done.returncode == 0, done.stderr[-800:]
    return tmp_path / "ledger.jsonl"


def _run(path, *extra):
    done = subprocess.run([sys.executable, str(SCRIPT), "--ledger", str(path), *extra],
                          capture_output=True, text=True, timeout=180)
    done.stdout = re.sub(r"\x1b\[[0-9;]*m", "", done.stdout)
    return done


def test_the_rows_timestamp_is_outside_the_signature(tmp_path):
    """The measurement §2 rests on, run rather than quoted.

    Move a sealed row's `created_at` back twenty-seven years and the seal still
    verifies — so a staleness derived from that column is a number anyone who
    can write the row can put back. This is why the listing reads the chain.
    """
    _chain(tmp_path)
    probe = f"""
import os, sys, pathlib, sqlite3
sys.path.insert(0, {str(ROOT)!r})
os.environ['NESTOR_SEAL_KEY'] = 'test-fixture-key-not-a-secret'
w = pathlib.Path({str(tmp_path)!r})
from nestor import cascade, memory, storage
from nestor.sqlite_store import SqliteStore
cascade.set_ledger_path(str(w / 'ledger.jsonl'))
s = SqliteStore(str(w / 'n.db')); s.init_db(); s.memory_init(); storage.set_store(s)
db = sqlite3.connect(str(w / 'n.db'))
db.execute("update tm_pairs set created_at='1999-01-01T00:00:00+00:00'")
db.commit(); db.close()
rows = s.memory_candidates('source', 'serves')
print('VERIFIES' if all(memory.is_verified_seal(r) for r in rows) else 'REFUSED')
"""
    done = subprocess.run([sys.executable, "-c", probe], capture_output=True,
                          text=True, timeout=180)
    assert "VERIFIES" in done.stdout, (
        "if this ever prints REFUSED the signature has started covering "
        "created_at, and the listing could read the row's clock after all")


def test_editing_the_tail_timestamp_is_not_caught_but_an_earlier_one_is(tmp_path):
    """Why the listing distinguishes the last entry from the rest.

    Not a defect — `ledger.verify` documents exactly this and ships
    `expected_head` to close it. Pinned because the listing's honesty depends
    on it staying true.
    """
    from nestor import ledger
    path = _chain(tmp_path)
    original = path.read_text(encoding="utf-8")

    def move_ts(index: int) -> bool:
        lines = original.splitlines()
        entry = json.loads(lines[index])
        assert entry.get("ts"), "the entry must have a ts to move"
        entry["ts"] = "1999-01-01T00:00:00+00:00"
        lines[index] = json.dumps(entry)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        ok, _ = ledger.verify(str(path))
        path.write_text(original, encoding="utf-8")
        return ok

    assert move_ts(0) is False, "an early edit must break the chain"
    assert move_ts(2) is True, "the tail is unvouched-for — the reason for the flag"


def test_the_tail_flag_disappears_when_the_head_is_pinned(tmp_path):
    """The bug this caught: the per-row marker ignored `--expected-head`, so
    following the command's own advice did not change what it printed."""
    from nestor import ledger
    path = _chain(tmp_path)
    loose = _run(path, "--older-than", "0")
    assert "unvouched-for" in loose.stdout
    strict = _run(path, "--older-than", "0", "--expected-head", ledger.head(str(path)))
    assert strict.returncode == 0
    assert "unvouched-for" not in strict.stdout, (
        "passing the head it asks for must close the warning it prints")


def test_a_wrong_head_refuses_to_age_anything(tmp_path):
    path = _chain(tmp_path)
    done = _run(path, "--expected-head", "deadbeef" * 8)
    assert done.returncode == 1
    assert DUE.BROKEN in done.stdout


def test_it_says_that_nothing_stopped_being_served(tmp_path):
    """The sentence is the feature. A listing that did not say so would read
    like a change to what the store answers."""
    path = _chain(tmp_path)
    done = _run(path, "--older-than", "0")
    assert done.returncode == 0
    assert "Nothing stopped being served" in done.stdout
    assert "still served, every one" in done.stdout
