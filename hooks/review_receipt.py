"""Where the review desk leaves proof it was consulted, and how fresh that is.

Shared by :mod:`hooks.before_write`, which reads it, and
``demo/review_desk.py``, which writes it. Kept out of ``nestor/`` on purpose:
this is seat tooling, not product, and the package has no business knowing an
agent was told to go and read something.

**Never inside the repository.** A receipt is per-machine runtime state, like a
ledger path or a keyring — writing it into the tree would put it in a diff, and
a marker saying "the review happened" that can be committed is a marker somebody
can commit instead of doing the review.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import tempfile
import time

#: How long a consultation counts for, in seconds. Half an hour: long enough to
#: cover one piece of work, short enough that a session which wanders onto a
#: different subsystem has to look again.
DEFAULT_TTL_SEC = 1800

_ENV_PATH = "NESTOR_REVIEW_RECEIPT"
_ENV_TTL = "NESTOR_REVIEW_TTL_SEC"


def ttl_seconds() -> int:
    raw = os.environ.get(_ENV_TTL, "")
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_TTL_SEC


def receipt_path(root: pathlib.Path) -> pathlib.Path:
    """Per-checkout receipt file. Explicit env wins, then homestead, then temp."""
    override = os.environ.get(_ENV_PATH, "")
    if override:
        return pathlib.Path(override)
    try:                                    # PR #52's household root, if present
        from nestor.homestead_paths import home
        base = pathlib.Path(home()) / "nestor-review"
    except Exception:
        base = pathlib.Path(tempfile.gettempdir()) / "nestor-review"
    key = hashlib.sha256(str(pathlib.Path(root).resolve()).encode()).hexdigest()[:16]
    return base / f"{key}.json"


def record(root: pathlib.Path, query: str) -> pathlib.Path:
    """Note that the review desk was consulted, and about what."""
    path = receipt_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    prior: list = []
    if path.exists():
        try:
            prior = json.loads(path.read_text(encoding="utf-8")).get("queries", [])
        except (OSError, json.JSONDecodeError):
            prior = []
    path.write_text(json.dumps({
        "at": time.time(),
        "root": str(pathlib.Path(root).resolve()),
        "queries": ([query] + list(prior))[:20],
    }), encoding="utf-8")
    return path


def is_fresh(root: pathlib.Path) -> tuple[bool, str]:
    """``(fresh, detail)`` — whether a consultation still counts.

    Any unreadable or malformed receipt is treated as **absent** rather than
    valid. This gate fails closed on its own subject matter and open on its own
    bugs; see :mod:`hooks.before_write` for why that split is deliberate.
    """
    path = receipt_path(root)
    if not path.exists():
        return False, "no consultation recorded"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        at = float(data.get("at", 0))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return False, "receipt unreadable"
    age = time.time() - at
    ttl = ttl_seconds()
    if age > ttl:
        return False, f"last consultation was {int(age // 60)}m ago (ttl {ttl // 60}m)"
    last = (data.get("queries") or [""])[0]
    return True, f"consulted {int(age // 60)}m ago: {last!r}"
