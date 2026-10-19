"""Session seals — a person's one yes to their own session, over its bundle.

A host (willow-bot's one script) runs a whole session with no seal in the
middle of it: an idea is not a decision, so nothing waits on a human while the
work is being done. At the end, the host gathers the session — what the person
did and what came of each, and the pieces it pulled in — compresses it into one
**bundle**, and proposes one draft pair:

    source_text   the person's actions, rendered from the bundle (what they read)
    target_text   ``session:<sha256>`` over the bundle's bytes (what they seal)
    domain        ``session`` (source_lang and target_lang)

The person then does one of two things in ``nestor ui``:

* **Seal** — "yes, these were my actions in this session". Their own signature,
  as for any seal; the machine never makes it.
* **Deny** — :func:`nestor.memory.reject_pair`. The pair and its bundle stay in
  the store and can be read; a rejected pair is never served or offered again.

**What is shown is what is sealed.** :func:`view` re-reads the stored bundle,
checks it still hashes to the pair's target, and checks the rendered actions
are the pair's ``source_text`` exactly. Anything else is ``unverifiable``, with
why, and :func:`nestor.memory.add_pair` refuses to seal a session pair that is
not ``verified`` — on every seal path, the UI's included, because the check is
in the one function that turns a pair into a sealed one.

**Tagged, never excluded.** ``session`` is a domain tag like any other: a
sealed session matches and serves in its domain exactly as any sealed pair
does, so a later session can pull it in when it is close enough. Nothing here
filters it out of anything.

The bundle is the host's: a JSON object with a ``session`` id and a non-empty
``actions`` list, each ``{"did": str, "came_of": [str, ...]}``; every other key (the pieces, the
record's tip, the session id) is carried and hashed, never interpreted here.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, cast

from .errors import NestorError
from .storage import SessionBundleStorage, Storage, get_store, require_capability, supports

#: The domain tag a session pair carries, as both source and target language.
DOMAIN = "session"
#: A session pair's target: the bundle's SHA-256, hex, lower case.
_SUBJECT = re.compile(r"^session:([0-9a-f]{64})$")
#: The bundle is a session's worth of data, compressed by the host; this bounds
#: one row, not a session (a host over it compresses harder or splits nothing).
MAX_BUNDLE = 4 * 1024 * 1024

VERIFIED = "verified"
UNVERIFIABLE = "unverifiable"


class SessionBundleError(NestorError):
    """A session pair that can't be proposed or sealed: its bundle is malformed,
    missing, doesn't hash to the pair's target, or says something other than
    the actions the pair shows."""


def _require(store: Storage) -> None:
    require_capability(
        store, "session_bundles",
        f"{type(store).__name__} does not implement Nestor's session-bundle "
        f"capability (memory_put_session_bundle, memory_get_session_bundle — "
        f"see nestor.storage).", exc_type=SessionBundleError)


def canonical(bundle: dict) -> bytes:
    """The bundle's bytes: sorted keys, compact, UTF-8. One bundle, one byte
    string, so one hash."""
    return json.dumps(bundle, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def subject(data: bytes) -> str:
    """The target a session pair carries for these bytes."""
    return "session:" + hashlib.sha256(data).hexdigest()


def _actions(bundle: Any) -> list[dict]:
    """The bundle's actions, or SessionBundleError saying what is wrong."""
    if not isinstance(bundle, dict):
        raise SessionBundleError("a session bundle is a JSON object")
    sid = bundle.get("session")
    if not (isinstance(sid, str) and sid.strip()):
        raise SessionBundleError("a session bundle needs a non-empty 'session' id")
    acts = bundle.get("actions")
    if not isinstance(acts, list) or not acts:
        raise SessionBundleError("a session bundle needs a non-empty actions list")
    for i, a in enumerate(acts, 1):
        if not (isinstance(a, dict) and isinstance(a.get("did"), str) and a["did"].strip()):
            raise SessionBundleError(f"action {i} needs a non-empty 'did'")
        came = a.get("came_of", [])
        if not (isinstance(came, list) and all(isinstance(c, str) for c in came)):
            raise SessionBundleError(f"action {i}'s 'came_of' is a list of strings")
    return acts


def render(bundle: dict) -> str:
    """The person's actions as the pair's ``source_text``: the session's id,
    then one numbered line per action and an indented ``→`` line for each thing
    that came of it. The id keeps two sessions that did the same things apart."""
    acts = _actions(bundle)
    lines = [f"Session {bundle['session'].strip()}"]
    for i, a in enumerate(acts, 1):
        lines.append(f"{i}. {a['did'].strip()}")
        lines += [f"   → {c.strip()}" for c in a.get("came_of", []) if c.strip()]
    return "\n".join(lines)


def propose(bundle: dict, *, origin: str = "", store: Storage | None = None) -> dict:
    """Store the bundle and propose the session's one draft pair. Confirms
    nothing: the pair is a draft until the person seals or denies it.

    Also attaches a ``construction`` warrant (the bundle's hash is its own
    proof) where the store holds warrants. Returns the pair.
    """
    from . import memory, warrant

    store = get_store(store)
    _require(store)
    text = render(bundle)
    data = canonical(bundle)
    if len(data) > MAX_BUNDLE:
        raise SessionBundleError(
            f"the bundle is {len(data)} bytes; one session row holds {MAX_BUNDLE}")
    subj = subject(data)
    cast(SessionBundleStorage, store).memory_put_session_bundle(
        subj.split(":", 1)[1], data, datetime.now(timezone.utc).isoformat())
    pair = memory.add_pair(text, subj, DOMAIN, DOMAIN, status="draft",
                           origin=origin, store=store)
    if supports(store, "warrants") and pair.get("status") == "draft":
        warrant.attach(
            pair["id"], "construction", "nestor.session_seal",
            "nestor.session_seal.view",
            check="re-read the stored bundle and recompute its SHA-256",
            expected_digest=subj.split(":", 1)[1], attached_by=origin,
            store=store)
    return pair


def check(source_text: str, target_text: str, store: Storage | None = None) -> dict:
    """``{"state", "why", "bundle"}`` for a session pair's two strings: verified
    only when the stored bundle hashes to the target and renders to the source."""
    store = get_store(store)
    if not supports(store, "session_bundles"):
        return {"state": UNVERIFIABLE, "bundle": None,
                "why": f"{type(store).__name__} holds no session bundles"}
    m = _SUBJECT.match(target_text or "")
    if m is None:
        return {"state": UNVERIFIABLE, "bundle": None,
                "why": "the target is not session:<sha256>"}
    data = cast(SessionBundleStorage, store).memory_get_session_bundle(m.group(1))
    if data is None:
        return {"state": UNVERIFIABLE, "bundle": None,
                "why": "the bundle is not in this store"}
    if hashlib.sha256(data).hexdigest() != m.group(1):
        return {"state": UNVERIFIABLE, "bundle": None,
                "why": "the stored bundle doesn't hash to the target"}
    try:
        bundle = json.loads(data.decode("utf-8"))
        shown = render(bundle)
    except (ValueError, SessionBundleError) as e:
        return {"state": UNVERIFIABLE, "bundle": None,
                "why": f"the stored bundle can't be read: {e}"}
    if shown != source_text:
        return {"state": UNVERIFIABLE, "bundle": bundle,
                "why": "the actions shown are not the bundle's actions"}
    return {"state": VERIFIED, "bundle": bundle, "why": ""}


def view(pair_id: str, store: Storage | None = None) -> dict:
    """What the reviewer is shown for one session pair: its actions, its state
    (``verified`` / ``unverifiable`` and why), and its status."""
    store = get_store(store)
    getter = getattr(store, "memory_get", None)
    row = getter(pair_id) if callable(getter) else None
    if row is None:
        raise SessionBundleError(f"no such pair {pair_id!r}")
    if row.get("source_lang") != DOMAIN:
        raise SessionBundleError(f"pair {pair_id!r} is not a session pair")
    got = check(row.get("source_text", ""), row.get("target_text", ""), store)
    bundle = got["bundle"] or {}
    acts = bundle.get("actions", []) if got["state"] == VERIFIED else []
    return {"pair_id": row["id"], "status": row.get("status", ""),
            "subject": row.get("target_text", ""), "state": got["state"],
            "why": got["why"], "actions": acts,
            "keys": sorted(k for k in bundle if k != "actions")}


def require_verified(source_text: str, target_text: str, store: Storage) -> None:
    """Refuse a seal of a session pair that isn't verified. Called from
    :func:`nestor.memory.add_pair` and :func:`nestor.memory.supersede_pair`."""
    got = check(source_text, target_text, store)
    if got["state"] != VERIFIED:
        raise SessionBundleError(f"this session can't be sealed: {got['why']}")
