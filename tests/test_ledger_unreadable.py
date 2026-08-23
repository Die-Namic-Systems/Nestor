"""A line in the ledger that will not parse is a thing that cannot happen.

Only writers of JSON append to this file, so a line that will not parse is an
impossible state — a torn write, a truncated copy, an editor, a merge. It
happens anyway, and :func:`nestor.ledger.entries` used to walk straight past
one: a four-line ledger returned three records and said nothing, in every
surface built on it. ``verify()`` caught it, and nothing made anybody call
``verify()`` before believing the list.

These pin the other walk. Run against the revision before the fix: **13 fail, 2
pass**. Most fail on ``AttributeError`` — ``ledger.unreadable`` did not exist —
including the three that read as guards (intact ledger, missing ledger, blank
lines); they exercise the new function, so they are not guards, and calling them
that would have been the flattering half of the truth. The line-numbering test
fails on its own terms, reporting the third line of the file as "line 2".

The two that pass before *and* after are the guards: the CLI stays silent about
an intact ledger (a note on every clean run is a note nobody reads), and this
module leaks nothing into ``os.environ``.
"""
from __future__ import annotations

import json
import os

import pytest

from nestor import cascade, cli, ledger, memory, portable, storage, ui
from nestor.sqlite_store import SqliteStore


def _chain(path, n: int = 4) -> list[str]:
    """``n`` real appends through the only writer there is."""
    cascade.set_ledger_path(path)
    for i in range(n):
        cascade.ledger_append({"kind": "passage", "note": f"entry {i}"})
    return path.read_text(encoding="utf-8").splitlines()


def _tear(path, index: int) -> str:
    """Truncate the ``index``-th (0-based) line so it is no longer valid JSON.

    Returns the 1-based number a human would use to open it.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[index] = lines[index][:20]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return index + 1


@pytest.fixture()
def torn(tmp_path):
    """A four-entry ledger whose third line will not parse."""
    p = tmp_path / "ledger.jsonl"
    _chain(p, 4)
    lineno = _tear(p, 2)
    assert lineno == 3
    return p, lineno


# --- the accounting --------------------------------------------------------

def test_the_two_walks_account_for_every_line(torn):
    """One walk collects what parses, one collects what does not, and nothing
    falls between them. This is the property the old single filtering walk could
    not have: it discarded, and a discard leaves no residue to count."""
    path, lineno = torn
    on_disk = [x for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    parsed = ledger.entries(path=str(path))
    damaged = ledger.unreadable(path=str(path))

    assert len(parsed) == 3
    assert [d["line"] for d in damaged] == [lineno]
    assert len(parsed) + len(damaged) == len(on_disk) == 4


def test_the_reported_line_is_the_line_a_human_would_open(torn):
    """``line`` numbers from 1. It counted from 0, so the third line of the file
    was reported as "line 2" — by ``verify`` too, which is the message an
    operator acts on."""
    path, lineno = torn
    raw = path.read_text(encoding="utf-8").splitlines()

    damaged = ledger.unreadable(path=str(path))
    assert damaged[0]["line"] == lineno
    with pytest.raises(json.JSONDecodeError):
        json.loads(raw[damaged[0]["line"] - 1])

    ok, detail = ledger.verify(path=str(path))
    assert not ok
    assert f"line {lineno}:" in detail


def test_the_error_says_what_is_wrong_with_the_line(torn):
    path, _ = torn
    damaged = ledger.unreadable(path=str(path))
    assert len(damaged) == 1
    assert damaged[0]["error"]           # json's own reason, not a substitute for it
    assert set(damaged[0]) == {"line", "error"}


def test_every_damaged_line_is_reported_not_just_the_first(tmp_path):
    """``verify`` stops at the first break, which is right for a verdict and
    wrong for a repair. This walk does not stop."""
    p = tmp_path / "ledger.jsonl"
    _chain(p, 5)
    _tear(p, 1)
    _tear(p, 3)
    assert [d["line"] for d in ledger.unreadable(path=str(p))] == [2, 4]
    assert "line 2:" in ledger.verify(path=str(p))[1]


# --- guards: these passed before the fix too -------------------------------

def test_an_intact_ledger_reports_no_damage(tmp_path):
    """Guard. A clean chain must not acquire a damage report."""
    p = tmp_path / "ledger.jsonl"
    _chain(p, 3)
    assert ledger.unreadable(path=str(p)) == []
    assert ledger.verify(path=str(p))[0] is True


def test_a_missing_ledger_is_not_a_damaged_one(tmp_path):
    """Guard. Absent is a different answer from broken, and ``verify`` is where
    that distinction is drawn."""
    assert ledger.unreadable(path=str(tmp_path / "nope.jsonl")) == []


def test_blank_lines_are_not_damage(tmp_path):
    """Guard. ``entries`` skips them, so this must too, or the accounting the
    first test pins would be wrong on any file with a trailing newline."""
    p = tmp_path / "ledger.jsonl"
    _chain(p, 2)
    p.write_text(p.read_text(encoding="utf-8") + "\n   \n\n", encoding="utf-8")
    assert ledger.unreadable(path=str(p)) == []
    assert len(ledger.entries(path=str(p))) == 2


# --- the surfaces that show the chain to somebody --------------------------

def test_the_cli_listing_says_what_it_could_not_list(torn, tmp_path, capsys):
    """``nestor ledger entries`` printed three rows of a four-line file with no
    mark. The note goes to stderr so a script parsing stdout is unaffected."""
    path, lineno = torn
    code = cli.main(["--db", str(tmp_path / "nestor.db"), "--ledger", str(path),
                     "ledger", "entries"])
    out, err = capsys.readouterr()

    assert code == cli.EXIT_OK
    assert len(out.strip().splitlines()) == 3
    assert "1 line(s)" in err and f"line {lineno}" in err


def test_the_cli_note_survives_a_kind_filter(torn, tmp_path, capsys):
    """A line that will not parse has no kind, so ``--kind`` cannot filter *for*
    it — and must not be read as having excluded it on purpose."""
    path, lineno = torn
    cli.main(["--db", str(tmp_path / "nestor.db"), "--ledger", str(path),
              "ledger", "entries", "--kind", "passage"])
    assert f"line {lineno}" in capsys.readouterr().err


def test_the_cli_says_nothing_about_an_intact_ledger(tmp_path, capsys):
    """Guard. The note appears because there is damage, not because the command
    ran — a warning on every clean run is a warning nobody reads."""
    p = tmp_path / "ledger.jsonl"
    _chain(p, 2)
    cli.main(["--db", str(tmp_path / "nestor.db"), "--ledger", str(p),
              "ledger", "entries"])
    assert "not valid JSON" not in capsys.readouterr().err


def test_an_export_bundle_carries_the_lines_it_could_not_read(torn, tmp_path):
    """The reader of a bundle is the one party who cannot go and look at the
    file, so a short chain with nothing marking the gap is worst here."""
    path, lineno = torn
    store = SqliteStore(":memory:")
    store.init_db()
    store.memory_init()
    memory.add_pair("the annual invoice", "la factura anual", "en", "es", store=store)

    bundle = portable.export_bundle(store)
    assert [d["line"] for d in bundle["ledger"]["unreadable"]] == [lineno]
    assert len(bundle["ledger"]["entries"]) + len(bundle["ledger"]["unreadable"]) == \
        len([x for x in path.read_text(encoding="utf-8").splitlines() if x.strip()])


def test_the_bundle_digest_does_not_move_because_a_line_tore(tmp_path):
    """The digest is over pairs and rejections. Carrying the damage report must
    not make an untouched memory look like a different one — that is the failure
    ``digest``'s own docstring exists to prevent."""
    p = tmp_path / "ledger.jsonl"
    _chain(p, 2)
    store = SqliteStore(":memory:")
    store.init_db()
    store.memory_init()
    memory.add_pair("the annual invoice", "la factura anual", "en", "es", store=store)

    before = portable.export_bundle(store)["digest"]
    _tear(p, 0)
    after = portable.export_bundle(store)
    assert after["digest"] == before
    assert after["ledger"]["unreadable"]


def test_the_ui_ledger_view_reports_the_damage(torn):
    """The UI already joins ``verify`` and ``entries``. ``verify`` names the
    first bad line and stops; the table shows the rest. Neither answers "how
    many are missing from what I am looking at"."""
    _path, lineno = torn
    store = SqliteStore(":memory:")
    store.init_db()
    store.memory_init()
    storage.set_store(store)
    app = ui.App(store=store, source_lang="en", target_lang="es", db_path=":memory:")

    status, view = ui.dispatch(app, "GET", "/api/ledger", {})
    assert status == 200
    assert view["ok"] is False
    assert [d["line"] for d in view["unreadable"]] == [lineno]
    assert len(view["entries"]) == 3


def test_the_page_renders_the_damage_it_is_given():
    """The field is only worth returning if the page shows it. Pins the two
    halves against each other: ``ui.py`` sends ``unreadable``, and the page's
    ledger view reads that name."""
    from nestor import ui_page
    view = ui_page.PAGE.split("function viewLedger()", 1)[1].split("\n}", 1)[0]
    assert "unreadable" in view
    assert "not valid JSON" in view


def test_os_environ_is_untouched_by_this_module():
    """Guard for the suite, not the fix: these tests set a ledger path through
    ``cascade`` rather than the environment, so nothing here leaks into a test
    that runs after it."""
    assert "NESTOR_LEDGER" not in os.environ
