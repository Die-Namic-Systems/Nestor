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
import shlex
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
# `keys init` creates an empty trust root and is likewise non-minting.
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
#
# Two false positives, one cause: the rule read the whole command as a bag of
# words. `\bsqlite3\b` matched Python's stdlib module name, so a heredoc that
# merely *counted* sealed rows was denied, and with it every read-only audit
# of the seal column — including the unsupported-rows view issue #167 asks
# for, which is by definition a query over sealed rows. Then the narrowed
# version denied `git commit` for a message that *described* the fix. The
# tripwire's own text ends "and reads are fine"; the pattern did not agree.
#
# So the signal is now the command's **executable**, not any mention of it:
# `_invokes_sqlite` walks the pipeline stages and asks whether sqlite3 is the
# program being run. Prose about sqlite3 is prose. This is §6.109's lesson —
# match what a command *does*, not every appearance of the word — applied to
# the one check that was deliberately exempted from it. A write verb is
# required too, so a `SELECT` through the real CLI stays allowed.
_SQLITE_RE = re.compile(r"\bsqlite3\b", re.IGNORECASE)
_SEAL_WRITE_RE = re.compile(r"seal_sig|status\s*=?\s*['\"]?sealed|['\"]sealed['\"]",
                            re.IGNORECASE)
#: SQL that changes rows. A seal is written by one of these or it is not
#: written; `REPLACE`/`ATTACH` are in because each is a route to the same row.
#: A read has none of them.
_SQL_WRITE_VERB_RE = re.compile(
    r"\b(insert|update|replace|delete|attach|drop|"
    r"create\s+table|alter\s+table)\b", re.IGNORECASE)
# A quoted span in the command line. Blanked before the *structural* mint
# checks below, so a mint pattern matches the command's own tokens and not a
# phrase quoted as an argument — e.g. the read-only decision-store consult the
# seat tells every agent to run before proposing, which used to be denied when
# its question text quoted the mint phrase (docs/agent-log.md §6.109). The
# sqlite seal-write check deliberately keeps the raw command: its signal
# (`status='sealed'`) legitimately lives *inside* the SQL string, so blanking
# quotes there would defeat the guard rather than fix a false positive.
_QUOTED_RE = re.compile(r"'[^']*'|\"[^\"]*\"")


def _unquoted(command: str) -> str:
    """``command`` with quoted spans blanked to spaces (see ``_QUOTED_RE``)."""
    return _QUOTED_RE.sub(" ", command)


#: Wrappers that run another program; the real executable is the token after.
_WRAPPERS = frozenset({
    "sudo", "env", "command", "builtin", "exec", "nohup", "time", "xargs",
    "nice", "ionice", "stdbuf", "timeout", "doas",
})
#: Tokens that separate one pipeline stage from the next.
_STAGE_SEPS = frozenset({";", "&", "&&", "|", "||", "(", ")", "\n"})


def _invokes_sqlite(command: str) -> bool:
    """Is ``sqlite3`` the program this command actually runs?

    The seal-write check needs to look inside quotes — a hand-written seal
    lives in the SQL string — so it cannot use ``_unquoted``. That left it
    matching any *mention* of sqlite3, which denied Python heredocs importing
    the stdlib module and git commits describing this very guard.

    Splitting into pipeline stages and reading each stage's executable
    separates "runs sqlite3" from "says sqlite3". Wrappers (``sudo``, ``env``,
    ``timeout`` …) and leading ``NAME=value`` assignments are stepped over so
    ``sudo sqlite3 store.db …`` still counts. Unparseable input (an unbalanced
    quote) falls back to the old substring test: a guard that cannot read a
    command must assume the worst about it, not the best.
    """
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>()")
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return bool(_SQLITE_RE.search(command))

    stage: list[str] = []
    stages: list[list[str]] = []
    for tok in tokens:
        if tok in _STAGE_SEPS:
            if stage:
                stages.append(stage)
            stage = []
        else:
            stage.append(tok)
    if stage:
        stages.append(stage)

    for st in stages:
        for i, tok in enumerate(st):
            base = tok.rsplit("/", 1)[-1]
            if base == "sqlite3":
                return True
            # Step over everything that can sit left of the executable:
            # wrappers, their flags and numeric arguments (`timeout 5 …`), and
            # `NAME=value` assignments — which `env` accepts at any position,
            # not just the first. Anything else is the executable, and it is
            # not sqlite3, so this stage is done.
            if base in _WRAPPERS or tok.startswith("-") or tok.isdigit():
                continue
            if "=" in tok and not tok.startswith("="):
                continue
            break
    return False

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
    # The three structural mints are identified by the command's own tokens
    # (an enrol subcommand, an env assignment, an import with a chosen
    # verifier) — never by a phrase inside a quoted argument. Match them
    # against the quote-blanked command so a consult that merely *names* one
    # in its question text is not denied (§6.109).
    structural = _unquoted(command)
    if _KEYS_ADD_RE.search(structural) and not _PUBLIC_RE.search(structural):
        return _deny()
    if _ENV_ASSIGN_RE.search(structural):
        return _deny()
    if _IMPORT_APPLY_RE.search(structural) and _APPLY_RE.search(structural) and _VERIFIER_RE.search(structural):
        return _deny()
    # The raw command on purpose: a hand-written seal lives *inside* the SQL
    # string, so this is the one check whose signal is quoted content. Three
    # things must hold together — sqlite3 is what the stage actually *runs*,
    # a seal is being written, and a write verb carries it — because any two
    # of them alone describe honest work (see _invokes_sqlite).
    if (_invokes_sqlite(command) and _SEAL_WRITE_RE.search(command)
            and _SQL_WRITE_VERB_RE.search(command)):
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
