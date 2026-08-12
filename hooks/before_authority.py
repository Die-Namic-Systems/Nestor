"""Self-grant tripwire — the one authority in Nestor is the power to seal.

Nestor's covenant is narrower than a permission system: an agent may **propose**
and may not **confirm**. There is exactly one thing to protect — the power to
write a ``status="sealed"`` row, or a ``verifier=`` a serving path will honour —
because minting it lets the machine forge a human's ratification. This guard
denies the acts that mint that power and allows the ones that give it up or only
read it, the same shape as ``before_mcp``/``before_write``.

**It is a tripwire, not a boundary.** A PreToolUse hook lives in the agent's own
harness; on a single-uid host nothing stops an agent that ignores it (and Claude
Code's ``permissions.deny`` is not even applied to Edit/Write — anthropics/
claude-code#11226). The durable control is the cryptographic covenant (an
ed25519 keyring whose private half never touches the instance, a human signing in
``nestor ui``) and, for the host, the managed-settings layer
(``/etc/claude-code/managed-settings.json``, ``allowManagedHooksOnly``). This
guard's job is the willow-mcp sudo-invariant's job: make a minting attempt
**loud and unsealed at the moment it happens**, so "the command looked ordinary"
stops being a defense. Say enforcement or ledger — this is a ledger with a siren.

The idea is willow-mcp's self-grant guard and the honesty framing is
dwarvesf/claude-guardrails' ("a catch-net, not a security boundary", MIT); no
text was copied.
"""
from __future__ import annotations

import pathlib
import re
from typing import Any

#: Env vars that ARE seal-key material. Pinned to what the modules actually read
#: (``signing._key``/``cache_key``, ``keyring.keyring_path``) by a test, so a new
#: ``NESTOR_*_KEY`` can't be added to the code and skip the guard — the drift
#: willow-mcp's ``test_net_capabilities_cover_every_gate_flag`` exists to catch.
SEAL_ENV = ("NESTOR_SEAL_KEY", "NESTOR_KEYRING", "NESTOR_CACHE_KEY")

_WRITE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")

# `nestor keys add <name>` mints a signing entry (default HMAC = a symmetric key
# that signs AS that name; --rotate replaces a human's key). `--public` is
# exempt: registering a peer's PUBLIC key confers verify-only, never signing.
_KEYS_ADD_RE = re.compile(r"\bnestor\b[^\n|;&]*\bkeys\s+add\b", re.IGNORECASE)
_PUBLIC_RE = re.compile(r"--public\b", re.IGNORECASE)
# Assigning a seal-key env var (export or inline `VAR=val nestor …`). A read
# (`$NESTOR_SEAL_KEY`, `echo`, `grep`) has no `NAME=` and does not match.
_ENV_ASSIGN_RE = re.compile(r"\b(" + "|".join(SEAL_ENV) + r")\s*=", re.IGNORECASE)
# `nestor import … --apply … --verifier <human>` applies rows under a chosen
# verifier — the self-attribution move. Order-independent.
_IMPORT_APPLY_RE = re.compile(r"\bnestor\b[^\n|;&]*\bimport\b", re.IGNORECASE)
_APPLY_RE = re.compile(r"--apply\b", re.IGNORECASE)
_VERIFIER_RE = re.compile(r"--verifier\b", re.IGNORECASE)
# A raw sqlite write that sets a seal — `sqlite3 store.db "… status='sealed' …"`.
_SQLITE_RE = re.compile(r"\bsqlite3\b", re.IGNORECASE)
_SEAL_WRITE_RE = re.compile(r"seal_sig|status\s*=?\s*['\"]?sealed|['\"]sealed['\"]",
                            re.IGNORECASE)

_USER = ("Minting sealing authority is disabled in this seat. You may propose, "
         "not confirm.")
_AGENT = ("Self-grant tripwire: this act would mint the power to seal (forge a "
          "human's ratification). Record the decision as `draft` instead; a human "
          "seals it in `nestor ui`. Registering a peer's --public key, `keys "
          "list`/`revoke`, and reads are fine. See docs/agent-guide.md, "
          "hooks/seat.md §Governance. (A tripwire, not a boundary — the crypto "
          "covenant and managed-settings are the real controls.)")


def _deny() -> tuple[bool, str, str]:
    return False, _USER, _AGENT


def _keyring_basenames() -> set[str]:
    """Filenames that ARE the signing keyring — a write to one is minting."""
    import os
    names = {"keyring.json"}
    env = os.environ.get("NESTOR_KEYRING")
    if env:
        names.add(pathlib.Path(env).name)
    return names


def _check_command(command: str) -> tuple[bool, str, str]:
    if not command:
        return True, "", ""
    if _KEYS_ADD_RE.search(command) and not _PUBLIC_RE.search(command):
        return _deny()
    if _ENV_ASSIGN_RE.search(command):
        return _deny()
    if _IMPORT_APPLY_RE.search(command) and _APPLY_RE.search(command) and _VERIFIER_RE.search(command):
        return _deny()
    if _SQLITE_RE.search(command) and _SEAL_WRITE_RE.search(command):
        return _deny()
    return True, "", ""


def _check_write(file_path: str, content: str) -> tuple[bool, str, str]:
    name = pathlib.Path(file_path).name if file_path else ""
    # A write to the signing keyring is minting, whatever the content.
    if name and (name in _keyring_basenames()
                 or ("keyring" in name.lower() and name.lower().endswith(".json"))):
        return _deny()
    # A hand-written seal into a store file.
    if file_path.endswith(".db") and _SEAL_WRITE_RE.search(content or ""):
        return _deny()
    return True, "", ""


def evaluate_authority(payload: dict[str, Any], root: pathlib.Path) -> tuple[bool, str, str]:
    """``(allow, user_message, agent_message)`` for one authority-touching act.

    Denies the seal-minting acts; allows de-escalation and reads. ``root`` is
    accepted for parity with the other gates; the rules are repo-independent.
    Raises only on a genuine bug — the runner fails OPEN on that, closed on a
    real minting act (the ``before_write`` split: closed on subject, open on our
    own fault).
    """
    tool = str(payload.get("tool_name") or payload.get("toolName") or "")
    ti = payload.get("tool_input") or payload.get("arguments") or {}
    if not isinstance(ti, dict):
        ti = {}
    if tool in _WRITE_TOOLS:
        content = ti.get("content") or ti.get("new_string") or ti.get("new_str") or ""
        return _check_write(str(ti.get("file_path") or ti.get("path") or ""), str(content))
    command = ti.get("command") or payload.get("command") or ""
    return _check_command(str(command))
