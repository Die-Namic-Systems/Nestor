"""`demo/desks.py` — the scaffolding, held to the thing it exists to prevent.

The module's claim is that several Nestor deployments can share one interpreter
without silently becoming one deployment. That is a claim about three process
globals — the ledger path, the store and the matcher — so these tests check that
switching desks moves all three, and that a desk's own matcher survives a seal
made at the human surface.

Asserted on **files and served answers**, not on the package's private globals:
`cascade._ledger_path` is private, and a test that read it would be checking the
scaffolding agrees with itself rather than that decisions landed where the desk
said they would.

One thing worth knowing before reading these: a **draft appends nothing to the
chain**. A proposal is not a decision, so every test here that wants a ledger
line has to seal something first — which the first draft of this file did not,
and it spent four failures finding out.

The last test reproduces the failure the module was written after: two desks,
one chain, and a count that is a true number about the wrong desk. It sets the
globals directly, the way a fixture that had never heard of `Desk` would.
"""
import os
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from demo import desks as D
from nestor import cascade, memory


class SerialMatcher:
    """A two-method matcher whose key is nothing like StringMatcher's.

    Its normalize returns only the digits, so "is this desk's matcher actually
    installed" is answerable by looking at one stored key.
    """

    def normalize(self, value) -> str:
        return "".join(c for c in str(value) if c.isdigit()) or "NONE"

    def similarity(self, a_norm: str, b_norm: str) -> float:
        return 1.0 if a_norm == b_norm else 0.0


@pytest.fixture()
def workspace(tmp_path, seal_key):
    os.environ["NESTOR_SEAL_KEY"] = "test-key"
    with D.Workspace(keep=str(tmp_path / "desks")) as w:
        yield w
    D.FAILURES.clear()


def _seal(desk, source, target, verifier):
    """Propose, then seal at the surface — the only route a fixture may take."""
    draft = desk.propose(source, target)
    status, body = desk.seal_draft(draft["id"], verifier=verifier)
    assert status == 200, body
    return draft, body["pair"]


def test_two_desks_keep_separate_stores_and_chains(workspace):
    intake = workspace.desk("intake", "incident", "incident", origin="test")
    review = workspace.desk("review", "defect", "defect", origin="test")

    _seal(intake, "a report", "an adjudication", "ines")
    _seal(review, "a defect", "a patch", "ruaridh")

    assert intake.db != review.db
    assert intake.chain() and review.chain(), "both desks must have written"
    assert intake.chain() != review.chain(), "the desks must not share one chain"
    assert "incident" in "".join(intake.chain())
    assert "incident" not in "".join(review.chain()), \
        "one desk's domain must not appear in the other's chain"


def test_switching_desks_moves_the_matcher(workspace):
    intake = workspace.desk("intake", "incident", "incident",
                            matcher=SerialMatcher(), origin="test")
    review = workspace.desk("review", "defect", "defect", origin="test")

    intake.activate()
    assert isinstance(memory.get_matcher(), SerialMatcher)
    review.activate()
    assert not isinstance(memory.get_matcher(), SerialMatcher), \
        "switching desks must uninstall the previous desk's matcher"


def test_switching_desks_moves_the_chain(workspace):
    """A decision lands in the chain of whichever desk made it."""
    intake = workspace.desk("intake", "incident", "incident", origin="test")
    review = workspace.desk("review", "defect", "defect", origin="test")

    _seal(review, "a defect", "a patch", "ruaridh")
    before = len(intake.chain())
    _seal(intake, "a report", "an adjudication", "ines")

    assert len(intake.chain()) > before, "the intake seal must be in intake's chain"
    assert "a report" not in "".join(review.chain()) and \
        "incident" not in "".join(review.chain()), \
        "and must not have leaked into the desk that was active before it"


def test_a_desk_with_its_own_matcher_keys_rows_its_own_way(workspace):
    """The matcher is installed, so the UI's writes use it too.

    This is why `Desk` installs process-wide rather than only passing
    `matcher=`: `nestor.ui` has no matcher of its own and no field for one, so a
    seal made at the surface is keyed by whatever is installed at the time.
    """
    intake = workspace.desk("intake", "incident", "incident",
                            matcher=SerialMatcher(), origin="test")
    draft, sealed = _seal(intake, "Pump 4471 over-delivered", "confirmed free-flow",
                          "ines")

    assert draft["source_norm"] == "4471"
    assert sealed["id"] == draft["id"], \
        "the seal must upgrade the draft, not insert a second row"
    assert sealed["source_norm"] == "4471", \
        "the desk's matcher must survive a seal made at the human surface"
    # No other digits in the restatement: this matcher keeps every digit it
    # finds, so "ward 6" would key to 44716 and the miss would be the test's
    # fault rather than the desk's.
    assert intake.best_sealed("free-flow reported against 4471") is not None, \
        "a restatement keying to the same serial must reach the seal"


def test_a_fixture_may_propose_and_may_not_confirm(workspace):
    intake = workspace.desk("intake", "incident", "incident", origin="test")
    row = intake.propose("a report", "an adjudication")
    assert row["status"] == "draft"
    assert not row.get("verifier"), "a proposed row must not name a verifier"
    with pytest.raises(TypeError):
        intake.propose("another", "one", status="sealed")


def test_the_failure_this_module_exists_to_prevent(tmp_path, seal_key):
    """Two desks, set up the naive way, silently become one chain.

    Written the way a fixture that had never heard of `Desk` would write it: set
    the ledger path once, stand two stores up, seal into both, and count. The
    count is a true number about the wrong thing, which is the shape that is
    hard to catch in review — nothing errors and nothing looks wrong on screen.
    """
    os.environ["NESTOR_SEAL_KEY"] = "test-key"
    from nestor.sqlite_store import SqliteStore

    a_root, b_root = tmp_path / "a", tmp_path / "b"
    a_root.mkdir()
    b_root.mkdir()

    cascade.set_ledger_path(str(a_root / "ledger.jsonl"))   # set ONCE
    memory.set_matcher(D.DEFAULT_MATCHER)
    for root, domain in ((a_root, "incident"), (b_root, "defect")):
        store = SqliteStore(str(root / "nestor.db"))
        store.init_db()
        store.memory_init()
        memory.add_pair(f"a {domain} source", "a target", domain, domain,
                        status="sealed", verifier="someone", origin="test",
                        store=store)

    a_chain = (a_root / "ledger.jsonl").read_text(encoding="utf-8")
    assert not (b_root / "ledger.jsonl").exists(), \
        "the naive arrangement writes no chain for the second desk at all"
    assert "incident" in a_chain and "defect" in a_chain, \
        "both desks' decisions land in one chain — what Desk.activate prevents"

    # The same two desks through the module get it right.
    D.FAILURES.clear()
    with D.Workspace(keep=str(tmp_path / "fixed")) as w:
        one = w.desk("a", "incident", "incident", origin="test")
        two = w.desk("b", "defect", "defect", origin="test")
        _seal(one, "a incident source", "a target", "someone")
        _seal(two, "a defect source", "a target", "someone")
        assert "defect" not in "".join(one.chain())
        assert "incident" not in "".join(two.chain())
