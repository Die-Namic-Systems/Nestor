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

IDEAS §6.97 reopened this after the #94 fix above shipped, because that fix
filtered nulls at the ONE call site (``card.append(...[...].filter(...))``)
instead of fixing the mechanism — the same mixed idiom (``h()`` for some
children, native ``.append()`` for others) is used in several panels, so the
next null-returning helper would reintroduce the bug elsewhere. The
mechanism-level fix extracts ``h()``'s null-skipping kid loop into a shared
``appendKids(el, ...kids)`` helper that both ``h()`` and ``detailPanel``'s
card assembly now route through, in place of the per-call-site filter.
``test_detail_panel_source_routes_through_append_kids`` locks that shape
directly (no Chromium needed) and ``test_append_kids_skips_null_generically``
proves the helper's null-skipping behaves correctly for ANY caller, not just
the two known-null values in an ordinary row.
"""
from __future__ import annotations

import pathlib
import threading

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright

from nestor import cascade, keyring, storage, ui
from nestor.sqlite_store import SqliteStore


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


def test_detail_panel_source_routes_through_append_kids():
    """Locks the SHAPE of the mechanism-level fix (IDEAS §6.97), independent
    of Chromium: ``detailPanel``'s card assembly must call the shared
    ``appendKids`` helper — the same null-skip rule ``h()`` applies to its own
    children — instead of re-deriving the predicate as a bespoke
    ``.filter(...)`` at this one call site, which is the shape that regresses
    the moment another panel mixes ``h()`` output with a native ``.append()``
    of a nullable expression.

    Runs against the pre-mechanism-fix code (the #94 fix that shipped in
    ``ea316ee``/``0f7d1a1``) and fails: that code has no ``appendKids`` at all,
    and assembles the card with
    ``card.append(...[...].filter((kid) => kid !== null ...))``.
    """
    src = pathlib.Path(__file__).resolve().parents[1].joinpath("nestor", "ui_page.py").read_text()

    assert "function appendKids(" in src, (
        "no shared appendKids helper defined — the null-skip rule is not "
        "factored out of h() into something other call sites can reuse"
    )

    start = src.index("\nfunction detailPanel()")
    end = src.index("\nfunction ", start + 10)
    body = src[start:end]

    assert "appendKids(card" in body, (
        "detailPanel does not route its card assembly through the shared "
        "appendKids helper"
    )
    assert ".filter((kid)" not in body and ".filter(kid " not in body, (
        "detailPanel is back to filtering nulls at this one call site instead "
        "of using the shared appendKids helper — the per-call-site shape "
        "IDEAS §6.97 warned would regress"
    )


def test_append_kids_skips_null_generically(app):
    """The mechanism, not just the symptom: call the shared ``appendKids``
    helper directly with null/undefined/false interleaved among real
    children, the way any FUTURE panel might, and confirm none of them leave
    a stray text node. This is what makes the fix mechanism-level rather than
    a fix for detailPanel's two specific null cases — it protects the next
    null-returning helper too, wherever it is added.

    Fails on the pre-mechanism-fix code with a ReferenceError (``appendKids``
    does not exist yet).
    """
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        try:
            page.goto(app.base_url + "/")
            page.wait_for_selector("nav#tabs button")
            result = page.evaluate(
                """() => {
                    const el = document.createElement("div");
                    appendKids(el, "a", null, "b", undefined, false, "c",
                               h("span", { text: "d" }));
                    return {
                        text: [...el.childNodes]
                            .filter((n) => n.nodeType === Node.TEXT_NODE)
                            .map((n) => n.textContent).join(""),
                        childCount: el.childNodes.length,
                        spanText: el.querySelector("span") ? el.querySelector("span").textContent : null,
                    };
                }"""
            )
        finally:
            browser.close()

    assert not errors, f"the page threw: {errors}"
    assert result["text"] == "abc", (
        f"appendKids let a null/undefined/false argument leak into a text "
        f"node: {result!r}"
    )
    assert result["childCount"] == 4, (
        f"expected exactly 4 child nodes (3 text + 1 span), got {result!r}"
    )
    assert result["spanText"] == "d", f"real element child was dropped: {result!r}"
