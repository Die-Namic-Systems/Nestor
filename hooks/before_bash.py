"""Gate: refuse a destructive shell command or a secret read before it runs.

The write gate (:mod:`hooks.before_write`) stops an agent editing behaviour it
has not asked the desk about; this one stops a `Bash` call that would delete a
tree, overwrite a disk, or read a key off disk. Same seat, same shape — a
`PreToolUse` evaluator returning ``(allow, user_message, agent_message)``, wired
the same way ``before_write`` is, emitting the same deny spelling.

Clean-room provenance
---------------------
The **taxonomy** — which command shapes are dangerous, and that secret-reads are
their own family — is the idea behind the MIT-licensed ``cc-safety-net``. Nothing
here is copied from it: the rules, the normalizer, the messages and the tests are
written against this repo's own conventions and this repo's own secrets
(``NESTOR_SEAL_KEY`` keystores, ``~/.nestor``). The debt is the *shape of the
problem*, not any line of text.

Why normalize before matching
------------------------------
A guard that greps the raw string is defeated by the first quote or flag swap:
``rm  -f  -r  /`` is ``rm -rf /``, ``sh -c "rm -rf /"`` hides the verb one level
down, and ``c""at .env`` is ``cat .env``. So every command is lexed (quotes
removed, ``\\rm`` de-escaped), split on the control operators ``;`` ``&&`` ``||``
``&``, split again on pipes, unwrapped through ``sh -c`` / ``bash -c``, and each
stage checked on its own. Flags are parsed into a set, so order does not matter.
Each rule below carries a comment naming exactly what it catches.

False-negatives are worse than false-positives here, but only just: a guard that
fires on ``rm -rf .worktrees/tmp`` or ``git push --force-with-lease`` is a guard
people disable, so the broad-path and force-push rules are deliberately narrow.

Fail closed on its subject, open on its own bugs
------------------------------------------------
A matched dangerous command is denied — that is the point. An exception *inside
this evaluator* allows the command, because a guard that wedges the session when
its own parsing trips is a guard everyone deletes. The two failure modes get
opposite defaults on purpose, exactly as ``before_write`` does.
"""
from __future__ import annotations

import pathlib
import re
import shlex
from typing import Any

#: Control operators that separate independent commands. Split here first.
_CONTROL_OPS = {";", "&&", "||", "&", "\n"}

#: Shells whose ``-c`` argument hides a nested command we must re-scan.
_SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "ash"}

#: Leading tokens that wrap the real command without changing what it does.
_WRAPPERS = {"sudo", "doas", "nohup", "time", "command", "env",
             "nice", "ionice", "stdbuf", "then", "do", "exec"}

#: Fetchers that, piped into a shell, run remote code (``curl … | sh``).
_FETCHERS = {"curl", "wget", "fetch"}

#: Commands that read file contents — the delivery vehicles for a secret read.
_READERS = {"cat", "less", "more", "tac", "nl", "head", "tail",
            "cp", "scp", "rsync", "sftp", "base64", "base32", "xxd", "od",
            "hexdump", "strings", "cut", "awk", "sed", "grep", "egrep",
            "fgrep", "sort", "uniq", "vi", "vim", "view", "nano", "dd",
            "curl", "wget", "openssl", "gpg"}

#: Writing to these ``/dev`` nodes is ordinary; anything else is a disk write.
_SAFE_DEVICES = {"/dev/null", "/dev/zero", "/dev/stdin", "/dev/stdout",
                 "/dev/stderr", "/dev/tty", "/dev/random", "/dev/urandom",
                 "/dev/full"}

#: Top-level directories a recursive delete/chmod must never be pointed at.
_SYSTEM_TOP = {"etc", "usr", "bin", "sbin", "lib", "lib64", "var", "boot",
               "dev", "sys", "proc", "root", "home", "users", "opt", "srv",
               "mnt", "media"}

#: Explicit broad delete targets (root, cwd, home, glob).
_BROAD_LITERALS = {"/", ".", "./", "..", "../", "~", "~/", "*", "/*",
                   "$HOME", "${HOME}", "$HOME/", "${HOME}/"}


def extract_command(payload: dict[str, Any]) -> str:
    """The command string, read the way the CLI passes a Bash PreToolUse."""
    tool_input = payload.get("tool_input") or payload.get("arguments") or {}
    if isinstance(tool_input, dict):
        cmd = tool_input.get("command")
        if isinstance(cmd, str):
            return cmd
    cmd = payload.get("command")
    return cmd if isinstance(cmd, str) else ""


def _lex(command: str) -> list[str]:
    """Tokenize respecting quotes, de-escaping ``\\rm`` and stripping quotes.

    ``punctuation_chars`` makes the operators (``;`` ``&`` ``|`` ``<`` ``>``)
    their own tokens so we can split on them; a run of the same char groups, so
    ``&&`` and ``||`` survive as single tokens.
    """
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>()")
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        # Unbalanced quote etc. — fall back to a crude split rather than raise.
        return command.replace('"', " ").replace("'", " ").split()


def _split(tokens: list[str], seps: set[str]) -> list[list[str]]:
    """Break a token list into runs delimited by any token in ``seps``."""
    out: list[list[str]] = []
    cur: list[str] = []
    for tok in tokens:
        if tok in seps:
            if cur:
                out.append(cur)
                cur = []
        else:
            cur.append(tok)
    if cur:
        out.append(cur)
    return out


def _base(token: str) -> str:
    """Command basename, so ``/bin/rm`` and ``rm`` compare equal."""
    return token.rsplit("/", 1)[-1]


def _dissect(stage: list[str]) -> tuple[str, list[str], list[str]]:
    """Strip wrappers/assignments; return (command, args, full-stage-tokens).

    Skips ``sudo``/``env``-style wrappers and leading ``VAR=val`` assignments so
    ``sudo rm -rf /`` and ``FOO=1 cat .env`` are seen for what they are.
    """
    i = 0
    while i < len(stage):
        tok = stage[i]
        if tok in _WRAPPERS:
            i += 1
            continue
        if "=" in tok and tok.split("=", 1)[0].replace("_", "a").isalnum() \
                and not tok.startswith("-") and "/" not in tok.split("=", 1)[0]:
            i += 1  # leading environment assignment
            continue
        break
    if i >= len(stage):
        return "", [], stage
    return stage[i], stage[i + 1:], stage


def _parse_flags(args: list[str]) -> tuple[set[str], set[str], list[str]]:
    """Split args into (short-flag letters, long flags, operands).

    Flag *order* is erased into a set, so ``-rf`` and ``-f -r`` and ``-r -f``
    all yield ``{'r', 'f'}`` — the core of not being fooled by reordering.
    """
    short: set[str] = set()
    longs: set[str] = set()
    operands: list[str] = []
    seen_ddash = False
    for arg in args:
        if seen_ddash:
            operands.append(arg)
        elif arg == "--":
            seen_ddash = True
        elif arg.startswith("--"):
            longs.add(arg)
        elif arg.startswith("-") and len(arg) > 1 and not arg[1].isdigit():
            short.update(arg[1:])
        else:
            operands.append(arg)
    return short, longs, operands


def _is_broad_target(token: str) -> bool:
    """True for a delete/chmod target broad enough to be catastrophic.

    Root, cwd, home, a bare glob, or a shallow absolute path (``/``, ``/etc``,
    ``/home/user``). A deep project path (``/home/user/Nestor/.worktrees/x``)
    or a relative one (``.worktrees/tmp``) is NOT broad — those are safe work.
    """
    if token in _BROAD_LITERALS:
        return True
    if token.startswith("~") or token in {"$HOME", "${HOME}"}:
        return True
    if token.startswith("/"):
        parts = [p for p in token.split("/") if p and p != "."]
        if len(parts) <= 1:                       # '/' or '/etc'
            return True
        if parts[0] in _SYSTEM_TOP and len(parts) <= 2:   # '/home/user'
            return True
    return False


def _secret_candidates(token: str) -> list[str]:
    """Forms of a token that might name a secret (strip ``@``, ``key=`` etc.)."""
    cands = [token, token.lstrip("@")]
    if "=" in token:
        cands.append(token.split("=", 1)[1])
    return [c for c in cands if c]


def _is_secret_path(token: str) -> bool:
    """True if the token names a credential this fleet must not read out.

    ``.env`` / ``.env.*``, SSH private keys and ``.ssh/``, ``.aws/credentials``,
    ``.config/gcloud``, a ``NESTOR_SEAL_KEY`` keystore, and the household roots
    ``~/.nestor`` and ``~/.homestead``. Both roots stay guarded: Nestor's own
    root replaced homestead's as the *default* (``docs/home-paths.md``), but a
    host that pinned ``NESTOR_HOME`` at the old location still keeps live keep
    state there, and dropping a secret-path rule to tidy a rename is how a
    guard quietly narrows.
    """
    for cand in _secret_candidates(token):
        low = cand.lower()
        base = low.rsplit("/", 1)[-1]
        if base == ".env" or base.startswith(".env."):
            return True
        if base in {"id_rsa", "id_ed25519", "id_dsa", "id_ecdsa"}:
            return True
        if ".ssh/" in low or low.endswith("/.ssh") or low == ".ssh" \
                or low.startswith(".ssh/"):
            return True
        if ".aws/credentials" in low or ".config/gcloud" in low:
            return True
        if ".homestead" in low or ".nestor" in low:
            return True
        if "seal_key" in low or "seal-key" in low or "nestor_seal_key" in low:
            return True
    return False


#: ``<<WORD`` / ``<<-'WORD'`` — the opening of a heredoc. ``<<<`` (a here-string)
#: does not match: after ``<<`` the next character must begin a delimiter word.
_HEREDOC_OPEN = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def _strip_heredocs(command: str) -> tuple[str, list[str]]:
    """Separate a command from the heredoc bodies it carries.

    A heredoc body is **data**, not arguments, and the scanner treated it as
    both and neither. Lexed whole, the body's words were flattened into the last
    pipeline stage — so a commit message that merely *names* a secret in prose
    was refused as "reading a secret via tail", the raw-substring-inside-longer-
    text failure of agent-log §6.38 applied to something that was never an
    argument. Meanwhile nothing scanned the body as *code*, so a shell fed by one
    ran unread.

    Returning the two separately lets :func:`_scan` do the right thing with each:
    scan the command without its data, and the data only where something runs it.
    """
    lines = command.split("\n")
    kept: list[str] = []
    bodies: list[str] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        kept.append(line)
        idx += 1
        # One command line may open several heredocs; bash consumes them in order.
        for match in _HEREDOC_OPEN.finditer(line):
            delimiter = match.group(2)
            body: list[str] = []
            while idx < len(lines) and lines[idx].strip() != delimiter:
                body.append(lines[idx])
                idx += 1
            idx += 1                      # drop the terminator line itself
            bodies.append("\n".join(body))
    return "\n".join(kept), bodies


def _shell_reads_stdin(stage: list[str]) -> str:
    """Rule X3: a shell taking its script from stdin, where we cannot read it.

    ``sh -c '…'`` stays allowed — the command is right there in the argument, and
    :func:`_scan` already re-scans it. These forms are not readable at all:
    ``bash < payload.sh`` runs a file that may not exist yet. Refusing them keeps
    the guard's guarantee honest; without this it reported on the visible half of
    a command while the executed half went unread.

    A heredoc into a shell is *not* refused here — its body is in the payload, so
    :func:`_scan` re-scans it rather than guessing.
    """
    if _base(_dissect(stage)[0]) not in _SHELLS:
        return ""
    for pos, tok in enumerate(stage):
        if tok == "<" and pos + 1 < len(stage):
            return (f"a shell running a script from stdin ({stage[0]} < "
                    f"{stage[pos + 1]}) — its contents cannot be scanned")
    return ""


def _pipeline_fetch_to_shell(stages: list[list[str]]) -> str:
    """Rule X1: anything piped into a shell runs text the guard never scanned."""
    fetched = False
    for position, stage in enumerate(stages):
        cmd, _args, _tokens = _dissect(stage)
        base = _base(cmd)
        if base in _SHELLS and fetched:
            return "a fetched script piped straight into a shell (curl … | sh)"
        if base in _SHELLS and position > 0:
            # The same hole without a fetcher: whatever the left-hand side prints
            # becomes the script. `echo '…' | sh` walked past the fetch-only form.
            return ("a shell on the receiving end of a pipe — it runs whatever "
                    "the left-hand side prints, which is not scannable")
        if base in _FETCHERS:
            fetched = True
    return ""


def _redirect_to_device(stage: list[str]) -> str:
    """Rule X2: ``>``/``>>`` onto a raw disk node (``> /dev/sda``)."""
    for idx, tok in enumerate(stage):
        if tok in {">", ">>"} and idx + 1 < len(stage):
            target = stage[idx + 1]
            if target.startswith("/dev/") and target not in _SAFE_DEVICES:
                return f"a redirect onto a raw device node ({target})"
    return ""


def _check_command(cmd: str, args: list[str], stage: list[str]) -> str:
    """Per-command rules. Returns a reason string, or '' if the stage is fine."""
    base = _base(cmd)
    short, longs, operands = _parse_flags(args)

    # Rule R1 — recursive delete pointed at a broad path (rm -rf /, ~, ., *).
    if base == "rm":
        recursive = "r" in short or "R" in short or "--recursive" in longs
        if recursive and any(_is_broad_target(op) for op in operands):
            return "rm -r targeting a broad path (/, ~, ., * or a system dir)"

    # Rule R2 — dd writing to a raw disk node (dd of=/dev/sda).
    if base == "dd":
        for op in args:
            if op.startswith("of=") and op[3:].startswith("/dev/") \
                    and op[3:] not in _SAFE_DEVICES:
                return f"dd writing to a raw device node ({op[3:]})"

    # Rule R3 — filesystem creation over a device (mkfs, mkfs.ext4, …).
    if base.startswith("mkfs"):
        return "mkfs — creating a filesystem destroys whatever is on the device"

    # Rule R4 — shred irreversibly overwrites file contents.
    if base == "shred":
        return "shred — irreversible overwrite of file contents"

    # Rule R5 — chmod -R on a broad path (chmod -R 777 /).
    if base == "chmod":
        recursive = "R" in short or "--recursive" in longs
        if recursive and any(_is_broad_target(op) for op in operands):
            return "chmod -R over a broad path — resets permissions system-wide"

    # Rule G-family — git verbs that discard committed or working state.
    if base == "git":
        if "reset" in operands and "--hard" in args:
            return "git reset --hard — discards uncommitted work irrecoverably"
        if "clean" in operands and (
                "--force" in longs or any("f" in s for s in short if s)
                or any(a.startswith("-") and not a.startswith("--") and "f" in a
                       for a in args)):
            return "git clean -f — deletes untracked files with no undo"
        if "stash" in operands and "clear" in operands:
            return "git stash clear — drops every stashed change"
        # Rule G4 — bare force-push. --force-with-lease is what Nestor uses and
        # is ALLOWED; only an unguarded --force / -f is denied.
        if "push" in operands:
            lease = any(a.startswith(("--force-with-lease", "--force-if-includes"))
                        for a in args)
            bare_force = "--force" in args or any(
                a.startswith("-") and not a.startswith("--") and "f" in a[1:]
                for a in args)
            if bare_force and not lease:
                return ("git push --force without --force-with-lease — "
                        "use --force-with-lease")

    # Rule S1 — a reader/exfil command touching a known secret path.
    if base in _READERS:
        for tok in stage:
            if tok in {">", ">>", "<", "|"}:
                continue
            if _is_secret_path(tok):
                return f"reading a secret via {base} ({tok})"

    return ""


def _scan(command: str, depth: int) -> str:
    """Return the reason the command is dangerous, or '' if it is allowed."""
    if depth > 4:
        return ""
    command, heredocs = _strip_heredocs(command)
    tokens = _lex(command)
    for segment in _split(tokens, _CONTROL_OPS):
        stages = _split(segment, {"|"})
        reason = _pipeline_fetch_to_shell(stages)
        if reason:
            return reason
        for stage in stages:
            reason = _redirect_to_device(stage)
            if reason:
                return reason
            reason = _shell_reads_stdin(stage)
            if reason:
                return reason
            cmd, args, full = _dissect(stage)
            # A shell fed by a heredoc runs the body. The body is in the payload,
            # so scan it rather than refuse it — this is what closes
            # `bash <<'EOF' … EOF`, which reached no rule at all before.
            if _base(cmd) in _SHELLS and "<<" in full:
                for body in heredocs:
                    reason = _scan(body, depth + 1)
                    if reason:
                        return reason
            # Unwrap sh -c "…" / bash -c '…' and re-scan the hidden command.
            if _base(cmd) in _SHELLS and "-c" in args:
                idx = args.index("-c")
                if idx + 1 < len(args):
                    reason = _scan(args[idx + 1], depth + 1)
                    if reason:
                        return reason
                continue
            if not cmd:
                continue
            reason = _check_command(cmd, args, full)
            if reason:
                return reason
    return ""


def evaluate_bash(payload: dict[str, Any], root: pathlib.Path) -> tuple[bool, str, str]:
    """``(allow, user_message, agent_message)`` for one Bash attempt.

    ``root`` is accepted for parity with :func:`hooks.before_write.evaluate_write`
    (this guard's rules are repo-independent). Fails OPEN on any internal
    exception — a parsing bug must not wedge the session.
    """
    try:
        command = extract_command(payload)
        if not command.strip():
            return True, "", ""
        reason = _scan(command, 0)
        if not reason:
            return True, "", ""
        user = f"Blocked a dangerous command: {reason}."
        agent = (
            f"BLOCKED — this Bash command was refused by hooks/before_bash.py: "
            f"{reason}.\n"
            f"This is a hard safety guard, not the review desk — there is no "
            f"receipt that clears it. If the action is genuinely intended, a "
            f"human runs it by hand outside the agent; do not rewrite it to slip "
            f"past the guard (quoting, sh -c, flag reordering are all caught). "
            f"See hooks/before_bash.py for the rule that matched."
        )
        return False, user, agent
    except Exception:          # noqa: BLE001 — fail OPEN on our own bugs
        return True, "", ""
