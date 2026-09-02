"""The domain a read actually queries, preferring one the store holds.

The rule lives here, once, because three surfaces run it: the UI (JS,
``askDomain()`` in ``nestor/ui_page.py``, landed in #159), the CLI (issue #167
piece 2, decision 0184 extended it from ``ask`` to ``match``), and the MCP
server (issue #203, decision 0187's follow-up).

The rule, unchanged from the CLI half:

* the *configured* domain (default ``decision → decision``) wins when the store
  actually holds rows in it, or when either flag was named explicitly — an
  explicit flag is the human typing a domain directly, and is used as-is rather
  than second-guessed;
* otherwise the largest domain present wins, because that is the one being
  asked about;
* an empty store keeps the configured default — there is nothing yet to
  prefer instead.

The CLI's ``cli._ask_domain`` is now a thin alias for
:func:`resolve_domain`; existing tests that import it keep working.
"""
from __future__ import annotations

from . import memory
from .storage import Storage

#: The pair a read opens on when neither the caller nor the store's largest
#: domain says otherwise. Nestor's primary store is human-verified decisions;
#: translation memory (``en → es``) remains a domain operators can name
#: explicitly or seed — not the silent default every surface assumes.
DEFAULT_SOURCE_LANG, DEFAULT_TARGET_LANG = "decision", "decision"


def resolve_domain(
    store: Storage,
    source_lang: str | None,
    target_lang: str | None,
) -> tuple[str, str]:
    """Pick the domain a read should actually query on this store.

    ``None`` for either flag means *not specified* — the store-aware fallback
    engages only when both are ``None``. A non-``None`` value is honoured
    verbatim; a caller that names a domain the store does not hold gets that
    domain (and, correctly, no answer), not a different one.
    """
    configured = (source_lang or DEFAULT_SOURCE_LANG,
                  target_lang or DEFAULT_TARGET_LANG)
    if source_lang is not None or target_lang is not None:
        return configured
    held = memory.stats(store=store).get("lang_pairs", [])  # ORDER BY count DESC
    if not held:
        return configured
    if any((sl, tl) == configured for sl, tl, _ in held):
        return configured
    biggest_sl, biggest_tl, _ = held[0]
    return (biggest_sl, biggest_tl)
