#!/usr/bin/env python3
"""nestor/cloud_seal.py — the cloud-path seam (OPTIONAL; requires willow-gate).

An agent, checked in through willow-gate under its OWN identity and capped at its
EARNED rung, provisionally seals items into a hash-chained custody ledger. This
is the "seal it right here, in the cloud" path — the usability gap Nestor's
human-only-at-the-UI seal leaves open when the human is on the far side of a
cloud box.

Two things it is careful never to conflate:

  * A PROVISIONAL seal is NOT canonical. `seal_through_gate` writes custody
    `file.create` events under the agent's identity — witnessed, tamper-evident,
    session-bound — and nothing more. **Canonical is conferred only by the home
    end's `custody.checkpoint()`**, signed by a human key this end does not hold.
    An agent grading its own work is exactly what Nestor's three states, seal
    signatures, and human-only seal exist to prevent; this does not breach that,
    it sits one tier below it.
  * FAIL-CLOSED ON THE GATE. Importing this module requires willow-gate. No gate
    installed at this end → no cloud path — the rule is the gate must be present
    at BOTH ends (the cloud end binds the agent; the home end verifies and
    confers canonical). Nestor's core stays zero-dependency; this is the opt-in
    `nestor-meaning[gate]` extra, and its absence is the off switch.

What "bound" buys, proven by willow-gate and re-exercised in this module's tests:
  * identity is bound by HMAC (a wrong secret is refused, not trusted),
  * the rung is capped and EARNED (a fresh agent cannot claim write/export),
  * export is gated by that rung (Rookie's session carries `exports=0`),
  * every seal carries the authenticated `session_id`.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from dataclasses import dataclass, field
from typing import Iterable, Sequence

try:  # FAIL-CLOSED ON THE GATE — no willow-gate at this end means no cloud path.
    from willow_gate import GateError, canonical_header_bytes  # noqa: F401
    from willow_gate.custody import CustodyLedger, file_create, verify_lineage
except ImportError as e:  # pragma: no cover - exercised by the extra's absence
    raise ImportError(
        "nestor.cloud_seal is the OPTIONAL cloud path and requires willow-gate "
        "installed at THIS end — the gate must be present at both ends. "
        "Install it (`pip install nestor-meaning[gate]`, or the willow-gate sibling)."
    ) from e


def content_fingerprint(text: str) -> str:
    """The stable content hash a custody event stamps. Not a secret — custody's
    redactor deliberately does not flag hashes, which is why a hex digest is the
    right shape here."""
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sign(secret: bytes, header: dict) -> str:
    """HMAC-SHA256 over willow-gate's own canonical header encoding — reuse the
    fleet's one signing encoding, never hand-roll a second."""
    return hmac.new(secret, canonical_header_bytes(header), hashlib.sha256).hexdigest()


def signed_header(agent_id: str, secret: bytes, *, trust_level: int,
                  tools: Sequence[str], agent_name: str = "", drift: int = 20,
                  nonce: str | None = None, state_hash: str | None = None,
                  timestamp: int | None = None, last_gate: str = "G0",
                  pass_count: int = 0, fail_count: int = 0,
                  reserved: int = 0) -> dict:
    """Build and HMAC-sign a valid 13-field willow-gate crossing header. `nonce`
    is fresh per crossing unless echoed (check-out must echo the entry nonce);
    `timestamp` defaults to now (check-out must be strictly after check-in)."""
    header = {
        "agent_id": agent_id,
        "agent_name": agent_name or agent_id,
        "last_gate": last_gate,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "drift": drift,
        "nonce": nonce or os.urandom(16).hex(),
        "trust_level": trust_level,
        "timestamp": timestamp if timestamp is not None else int(time.time() * 1000),
        "tools": list(tools),
        "state_hash": state_hash or ("0" * 64),
        "signature": "0" * 64,
        "reserved": reserved,
    }
    header["signature"] = _sign(secret, header)
    return header


@dataclass
class ProvisionalSealResult:
    """The outcome of a bound provisional seal. `canonical` is always False here —
    canonical is the home end's `checkpoint()`, never this tier."""
    session_id: str
    actor: str
    sealed: list[str] = field(default_factory=list)
    writable: bool = False
    export_allowed: bool = False
    custody_verifies: bool = False
    canonical: bool = False


def seal_through_gate(
    gate,
    agent_id: str,
    secret: bytes,
    items: Iterable[tuple[str, str]],
    *,
    custody: "CustodyLedger",
    trust_level: int = 1,
    tools: Sequence[str] = ("read",),
    agent_name: str = "",
    drift: int = 20,
) -> ProvisionalSealResult:
    """Cross the gate, provisionally seal each `(lineage_id, content)` item into
    `custody` under `agent_id`, then close the crossing.

    Raises `willow_gate.GateError` if identity fails (wrong secret) or the claimed
    rung is not held/earned — the seal never happens for an unauthenticated or
    over-reaching agent. Every seal that does happen is tied to the authenticated
    `session_id` and is PROVISIONAL: no `checkpoint()` is written here.
    """
    entry = signed_header(agent_id, secret, trust_level=trust_level,
                          tools=tools, agent_name=agent_name, drift=drift)
    _ok, _msg, session = gate.check_in(entry)  # raises GateError on bad identity/rung
    sid = session["nonce"]

    sealed: list[str] = []
    for lineage_id, content in items:
        file_create(custody, lineage_id, agent_id, content_fingerprint(content),
                    session_id=sid, path=f"seal/{lineage_id[:8]}")
        sealed.append(lineage_id)

    # Close the crossing: exit echoes the entry nonce, declares no gate-tool use
    # (the seals are custody writes, not gate-authorized tool calls), and carries
    # a timestamp strictly after entry (a fast crossing can otherwise share the
    # entry millisecond and be refused).
    exit_ts = max(int(time.time() * 1000), int(session["entry_ms"]) + 1)
    exit_header = signed_header(agent_id, secret, trust_level=trust_level, tools=[],
                               agent_name=agent_name, drift=drift,
                               nonce=session["nonce"], state_hash="1" * 64,
                               timestamp=exit_ts)
    gate.check_out(session, exit_header)

    custody_verifies = (all(verify_lineage(custody, s).ok for s in sealed)
                        and custody.verify().ok)
    return ProvisionalSealResult(
        session_id=sid,
        actor=agent_id,
        sealed=sealed,
        writable=bool(session.get("writable")),
        export_allowed=bool(session.get("writable")) and int(session.get("exports", 0)) > 0,
        custody_verifies=custody_verifies,
        canonical=False,
    )
