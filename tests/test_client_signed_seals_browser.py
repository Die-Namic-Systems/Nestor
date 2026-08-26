"""Nestor#17's browser signer, proved against a REAL browser (decision 0078).

``tests/test_client_signed_seals.py`` proves the server-side seam with a
Python stand-in for a client signer — a real ``cryptography`` keypair signing
``signing._message``'s bytes directly. That is the right test for the server,
and it is not, and cannot be, proof that ``nestor/ui_page.py``'s JavaScript
produces the same bytes: nothing in that file ever calls the page's JS. This
file is the other half. It launches a real ``nestor.ui`` server (in-process,
same pattern as ``tests/test_ui.py::test_a_real_request_over_loopback``),
drives the actual served page in a real Chromium tab via Playwright,
GENERATES an Ed25519 identity in the browser with WebCrypto (never touching
``nestor.keyring`` to do it), reads the exported public key back out of the
DOM exactly as a human would, enrolls it into the keyring this server checks
against (mirroring the literal ``nestor keys add NAME --type ed25519
--public HEX`` shape the page prints, in-process rather than shelled out to
— the CLI itself is covered by ``tests/test_cli.py``), and drives a real seal
through the page's own "Ask" view: fill text, ask, type a verified target,
click Seal, read the confirmation dialog, click Sign & seal. The server
recording a sealed row that :func:`nestor.signing.seal_is_valid` accepts is
the only genuine proof that the page's JS reproduces the frozen
``signing._message`` wire contract byte-for-byte against a live browser
rather than merely reads as though it would.

Guarded the same way the ``[keys]`` extra is guarded elsewhere in this suite
(``pytest.importorskip("cryptography")``): ``pytest.importorskip("playwright")``
first, then a collection-time skip if Playwright cannot find a Chromium
binary, so a checkout without the optional browser dependency still runs
every other test. ``PLAYWRIGHT_BROWSERS_PATH`` is expected to already point at
a downloaded Chromium — this file never calls ``playwright install``.
"""
from __future__ import annotations

import pathlib
import re
import threading

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright

from nestor import cascade, keyring, memory, signing, storage, ui
from nestor.sqlite_store import SqliteStore


def _chromium_missing_reason() -> str:
    """Cheap collection-time check: does Playwright know where a Chromium
    binary lives, and does that path exist? Reads metadata only — this never
    launches a browser, so importing this module costs nothing extra when
    Playwright is not installed or has no browser downloaded."""
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
    """A real, running nestor.ui server on loopback, backed by a keyring that
    starts EMPTY -- exactly the state a fresh deployment is in before its
    first verifier enrolls. ``keyring.set_keyring`` is process-wide and the
    injected form is read live (no caching, unlike the ``NESTOR_KEYRING``
    env-var path) -- see :func:`nestor.keyring.get_keyring` -- so updating it
    from the test body, mid-test, takes effect on the SERVER THREAD's very
    next request with no restart needed.
    """
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    store = SqliteStore(str(tmp_path / "nestor.db"))
    store.init_db()
    store.memory_init()
    storage.set_store(store)
    ring = keyring.Keyring()
    keyring.set_keyring(ring)
    a = ui.App(store=store, source_lang="en", target_lang="es",
              db_path=str(tmp_path / "nestor.db"))
    httpd = ui.serve(a, "127.0.0.1", 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    a.base_url = f"http://127.0.0.1:{httpd.server_address[1]}"
    a.ring = ring
    try:
        yield a
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_browser_generates_enrolls_and_seals_and_the_server_verifies_it(app):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        try:
            page.goto(app.base_url + "/")
            page.wait_for_selector("nav#tabs button")

            # -- generate an identity entirely in the browser -----------------
            page.click("text=Browser key…")
            page.wait_for_selector("#key-dialog[open]")
            page.click("text=Generate a new identity")
            page.fill("#gen-name", "sean campbell")
            page.click("#key-dialog-body button:text-is('Generate')")
            page.wait_for_selector("#gen-result .mono")
            public_hex = page.eval_on_selector("#gen-result .mono", "el => el.textContent")
            assert re.fullmatch(r"[0-9a-f]{64}", public_hex), \
                f"expected a raw 32-byte hex public key, got {public_hex!r}"

            # The exact command the page prints, for a human to run out of
            # band -- read it back, and confirm it is the shape the mandate
            # requires (public key only, `--public`, nothing that looks like
            # a private key). Two `.mono` paragraphs are shown (the raw
            # public key, then the command); take the second.
            mono_lines = page.eval_on_selector_all(
                "#gen-result p.mono", "els => els.map(e => e.textContent)")
            assert len(mono_lines) == 2, mono_lines
            enroll_cmd = mono_lines[1]
            assert enroll_cmd == (
                "nestor keys add 'sean campbell' --type ed25519 "
                f"--public {public_hex}"
            )

            # -- enroll it: exactly what that command does, in-process -------
            # (the CLI itself is exercised by tests/test_cli.py; this proves
            # the public key that came OUT of the browser is one the server's
            # own enrollment path accepts, not a hand-picked stand-in for it).
            app.ring.add("sean campbell", key=bytes.fromhex(public_hex),
                         kind="ed25519")
            entry = app.ring.get("sean campbell")
            assert entry is not None and entry.kind == "ed25519" and not entry.private, (
                "the server must hold ONLY sean campbell's public half -- the entire "
                "property this feature exists to prove")

            page.click("#key-dialog >> text=Close")

            # -- drive a real seal through the page's own Ask -> Translate ---
            source_text = "héllo world"                    # non-ASCII, on purpose
            target_text = 'a target with a "quote" in it'  # an embedded quote
            page.click("nav#tabs button:text-is('Ask')")
            page.wait_for_selector("#ask-text")
            page.fill("#ask-text", source_text)
            page.click("#view button.primary:text-is('Ask')")
            page.wait_for_selector("#ask-seal-target")
            page.fill("#ask-seal-target", target_text)
            page.click("#view button:has-text('Seal this answer')")

            # -- the human sees what is about to be signed before it is ------
            page.wait_for_selector("#sign-dialog[open]")
            shown = page.eval_on_selector("#sign-dialog-body .context-panel",
                                          "el => el.textContent")
            expected_norm = memory.get_matcher(None).normalize(source_text)
            assert expected_norm in shown
            assert target_text in shown
            assert "sean campbell" in shown

            with page.expect_response(
                    lambda r: r.url.endswith("/api/seal") and r.request.method == "POST"
            ) as resp_info:
                page.locator("#sign-dialog button", has_text="Sign & seal").click()
            response = resp_info.value
            seal_status = response.status
            seal_body = response.json()
        finally:
            browser.close()

    assert not errors, f"the page threw: {errors}"
    assert seal_status == 200, seal_body

    # -- the server's own record, checked with the SAME function every seal
    #    on this instance is checked with -- not a special-cased assertion.
    row = app.store.memory_find(expected_norm, "en", "es")
    assert row is not None
    assert row["status"] == "sealed"
    assert row["verifier"] == "sean campbell"
    assert row["source_text"] == source_text
    assert row["target_text"] == target_text
    assert signing.seal_is_valid(
        expected_norm, target_text, "sean campbell", row["seal_sig"]
    ), (
        "the signature the BROWSER produced does not verify -- the page's JS "
        "did not reproduce signing._message byte-for-byte")


def test_empty_memory_still_offers_the_human_seal_form(app):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(app.base_url + "/")
            page.click("nav#tabs button:text-is('Memory')")
            page.wait_for_selector("text=No pairs match.")
            assert page.get_by_text("Seal a pair by hand").is_visible()
        finally:
            browser.close()


def test_a_public_only_verifier_cannot_seal_without_a_browser_key(app):
    """The negative space the positive test above needs to be meaningful:
    the SAME public-only verifier, reached the OLD way (typed name, no
    seal_sig), is still refused -- proving the browser key was actually
    necessary above, not incidental."""
    app.ring.add("bob", key=b"\x00" * 32, kind="ed25519")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(app.base_url + "/")
        page.wait_for_selector("nav#tabs button")
        status = page.evaluate(
            """async (base) => {
                const res = await fetch(base + "/api/seal", {
                    method: "POST",
                    headers: {"Content-Type": "application/json", "X-Nestor-UI": "1"},
                    body: JSON.stringify({source: "no key here", target: "sin llave",
                                          source_lang: "en", target_lang: "es",
                                          verifier: "bob"}),
                });
                return res.status;
            }""",
            app.base_url,
        )
        browser.close()
    assert status in (400, 401, 403)
    assert app.store.memory_find("no key here", "en", "es") is None
