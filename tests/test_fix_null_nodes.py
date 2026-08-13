"""Issue #94: detailPanel() must not stringify null children into the card.

``detailPanel`` in ``nestor/ui_page.py`` assembled its provenance card with
native ``card.append(...)``, passing two arguments that are ``null`` for an
ordinary row:

* ``commitmentPanel(p)`` returns ``null`` for a non-draft row, or a draft with
  no commitment choices, and
* the context panel ``(p.reason || …) ? … : null`` returns ``null`` when the
  row carries no reason.

Native DOM ``append()`` stringifies ``null`` to a text node (``"null"``),
unlike the page's ``h()`` helper, whose kid loop drops ``null``/``undefined``/
``false``. So a plain draft/imported row with no commitment choices and no
reason rendered the literal string ``nullnull`` as two direct child text nodes
of the ``.card``.

This test drives the ACTUAL served page in a real Chromium tab (same harness
as ``tests/test_client_signed_seals_browser.py``), installs such a row as
``S.detail``, calls the page's own ``detailPanel()``, and asserts the card has
no ``"null"`` text among its direct children. Against the pre-fix code the
direct-child text nodes are ``['null', 'null']`` and this test fails; after the
fix they are empty and it passes.

Guarded exactly like the browser signer test: ``importorskip("playwright")``
first, then a collection-time skip if no Chromium binary is reachable, so a
checkout without the optional browser dependency still runs everything else.
"""
from __future__ import annotations

import pathlib
import threading

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright  # noqa: E402

from nestor import cascade, keyring, storage, ui  # noqa: E402
from nestor.sqlite_store import SqliteStore  # noqa: E402


def _chromium_missing_reason() -> str:
    """Cheap collection-time check for a reachable Chromium binary; reads
    metadata only, never launches a browser (mirrors the browser signer
    test)."""
    try:
        with sync_playwright() as p:
            exe = p.chromium.executable_path
    except Exception as exc:                                  # noqa: BLE001
        return f"Playwright could not report a Chromium path: {exc}"
    if not pathlib.Path(exe).exists():
        return f"no Chromium binary at {exe} (PLAYWRIGHT_BROWSERS_PATH not populated)"
    return ""


_SKIP_REASON = _chromium_missing_reason()
pytestmark = pytest.mark.skipif(bool(_SKIP_REASON), reason=_SKIP_REASON)


@pytest.fixture()
def app(tmp_path):
    """A real, running nestor.ui server on loopback — same shape as the browser
    signer test's fixture, minus the keyring choreography this test does not
    need."""
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    store = SqliteStore(str(tmp_path / "nestor.db"))
    store.init_db()
    store.memory_init()
    storage.set_store(store)
    keyring.set_keyring(keyring.Keyring())
    a = ui.App(store=store, source_lang="en", target_lang="es",
               db_path=str(tmp_path / "nestor.db"))
    httpd = ui.serve(a, "127.0.0.1", 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    a.base_url = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        yield a
    finally:
        httpd.shutdown()
        httpd.server_close()


# An ordinary draft row: no commitment choices in target_text (no `A) …` lines,
# no `---seal---` block, so commitmentPanel returns null) and no reason (so the
# context panel is null). Exactly the pair the bug renders as "nullnull".
_ORDINARY_ROW = {
    "status": "draft",
    "source_text": "hello world",
    "target_text": "hola mundo",
    "reason": "",
    "origin": "",
    "signature_valid": False,
    "servable": False,
    "verifier": "",
    "created_at": "",
    "id": "abcdef0123456789",
    "rejection_count": 0,
    "rejections": [],
}


def _card_direct_text(page, row):
    """Render detailPanel() for `row` in the live page and return the trimmed
    text of the card's DIRECT child text nodes (nodeType === 3). These are the
    nodes native append() would fill with the string 'null'."""
    return page.evaluate(
        """(row) => {
            // Force ordinary (non fleet-gap) detail mode and a resolvable
            // read_only lookup, then render the page's own detailPanel.
            S.filters.source_lang = "";
            S.filters.target_lang = "";
            S.state = { read_only: false };
            S.detail = row;
            const card = detailPanel();
            return [...card.childNodes]
                .filter((n) => n.nodeType === Node.TEXT_NODE)
                .map((n) => n.textContent.trim())
                .filter((t) => t.length);
        }""",
        row,
    )


def test_ordinary_row_detail_card_has_no_null_text_nodes(app):
    """The provenance card for a plain draft row (no commitment choices, no
    reason) must not contain the literal string 'null' among its direct
    children. Pre-fix this list is ['null', 'null']; post-fix it is empty."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        try:
            page.goto(app.base_url + "/")
            page.wait_for_selector("nav#tabs button")

            direct_text = _card_direct_text(page, _ORDINARY_ROW)

            # Sanity: the card actually rendered (its <h2> is present), so an
            # empty text list means "no stray text", not "nothing rendered".
            heading = page.evaluate(
                """(row) => {
                    S.state = { read_only: false };
                    S.detail = row;
                    const card = detailPanel();
                    const h2 = card.querySelector("h2");
                    return h2 ? h2.textContent : null;
                }""",
                _ORDINARY_ROW,
            )
        finally:
            browser.close()

    assert not errors, f"the page threw: {errors}"
    assert heading == "Provenance", f"card did not render as expected: {heading!r}"
    assert "null" not in direct_text, (
        "detailPanel stringified null child(ren) into the card: "
        f"direct-child text nodes were {direct_text!r} (issue #94)"
    )
    assert direct_text == [], (
        f"unexpected stray text among the card's direct children: {direct_text!r}"
    )
