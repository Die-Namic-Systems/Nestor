#!/usr/bin/env python3
"""Serve the bench dashboard — the measurements, as charts.

    python bench/serve_ui.py
    python bench/serve_ui.py --open

``bench/results/*.json`` is the record of what was measured: false-seal rate
against paraphrase recall, swept across thresholds and corpus sizes, with the
parameters and git rev of every run. It is also several thousand lines of JSON.
The argument those numbers make — *there is no threshold that is simultaneously
safe and useful* — is a shape, and a shape wants a chart.

**Read-only, and a different thing from ``nestor ui``.** This serves static
files and the committed results. It has no API, no store, and no way to record a
decision. Sealing, rejecting, curating and working the review queue live in
:mod:`nestor.ui`, which does those things properly: CSRF refusal, a
content-security policy, seal signatures, per-verifier sign-in, ``--read-only``.

This dashboard once carried a second review playground beside the charts, on a
weaker surface, drafting through a network API by default. Two ways into the
store, one of them weaker, is the exact shape of the defects this repo keeps
finding in itself (see the note at the end of ``TODO.md``). So there is one
review surface, and this is not it.

It binds 8770 rather than ``nestor ui``'s 8765, so both can run at once.

Open the URL the server prints — ``file://…/index.html`` cannot load the results.
"""
from __future__ import annotations

import argparse
import pathlib
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

BENCH = pathlib.Path(__file__).resolve().parent


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BENCH), **kwargs)

    def end_headers(self) -> None:
        # Results change whenever a bench runs; a cached chart of yesterday's
        # numbers is worse than no chart.
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_GET(self) -> None:                                  # noqa: N802
        if urlparse(self.path).path in ("", "/", "/index.html"):
            self.send_response(302)
            self.send_header("Location", "/ui/")
            self.end_headers()
            return
        super().do_GET()

    def log_message(self, fmt: str, *args) -> None:            # noqa: A003
        if args and str(args[0]).startswith(("GET /ui/", "GET /results/")):
            return
        super().log_message(fmt, *args)


def main() -> None:
    ap = argparse.ArgumentParser(description="Nestor bench dashboard (read-only)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--open", action="store_true", help="open the dashboard in a browser")
    args = ap.parse_args()

    url = f"http://{args.host}:{args.port}/ui/"
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Nestor bench dashboard at {url}")
    print("Read-only: these are the charts over bench/results/*.json. To seal, "
          "reject or curate anything, run `nestor ui`.")
    print("Press Ctrl+C to stop.")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
        server.shutdown()


if __name__ == "__main__":
    main()
