#!/bin/bash
# SessionStart hook for Claude Code on the web: make the documented commands
# work before the first prompt is typed. A cold clone is a trap here — the
# package imports from the repo root without any install, so half the README
# appears to work while `nestor`, `python -m pytest` and the lint gates do not.
#
# The install goes into the repo's own .venv, not system python: this
# container carries a Debian-packaged cryptography on sys.path that is broken
# for this interpreter (no _cffi_backend), and satisfies pip's `[keys]`
# requirement without actually importing. A venv is the documented convention
# and the only layout that cannot be half-satisfied by system site-packages.
set -euo pipefail

# Resolve the repo root from THIS SCRIPT's own path — <root>/.claude/hooks/
# session-start.sh, so two levels up — not from $PWD or CLAUDE_PROJECT_DIR. In a
# multi-repo web checkout the session is rooted ABOVE the repo, so $PWD is the
# parent and a bare CLAUDE_PROJECT_DIR is unset; trusting either is what let the
# whole boot no-op (IDEAS §6.108). Decision 0054 removed a bare
# `cd "$CLAUDE_PROJECT_DIR"` here but left the root still coming from the
# environment. NESTOR_PROJECT_ROOT still wins as an explicit override for tests.
SELF="$(readlink -f -- "${BASH_SOURCE[0]}" 2>/dev/null || echo "${BASH_SOURCE[0]}")"
SELF_ROOT="$(cd -- "$(dirname -- "$SELF")/../.." && pwd -P)"
ROOT="${NESTOR_PROJECT_ROOT:-$SELF_ROOT}"
cd "$ROOT"

# Local sessions manage their own .venv (docs/agent-guide.md — Environment). Say
# so on stderr rather than exiting silently: a setup step that declines to run is
# a different thing from one that ran, and a silent `exit 0` here was
# indistinguishable from success — the trap this script exists to prevent
# (FINDINGS-2026-08-12 §1.1).
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  echo "[session-start] CLAUDE_CODE_REMOTE != 'true' — skipping venv bootstrap in $ROOT; local sessions manage their own .venv" >&2
  exit 0
fi

if [ ! -x .venv/bin/python ]; then
  python -m venv .venv
fi

# [dev] = pytest, ruff==0.15.0, bandit; [keys] = cryptography for the
# asymmetric suite. [semantic] is deliberately absent — installing it
# un-skips model-downloading tests and diverges from the CI baseline.
.venv/bin/pip install -e ".[dev,keys]" --quiet

# Loud on the one outcome that matters: did the bootstrap actually land? A
# missing interpreter here is the cold-clone trap, and it must not read as
# success. The caller (maybe_bootstrap_claude_venv) uses check=False so this
# exit does not abort SessionStart — but it names the failure where a silent
# `exit 0` used to hide it, and the injected `[check] pytest:` line reports it
# to the agent independently.
if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "[session-start] venv bootstrap FAILED: no interpreter at $ROOT/.venv/bin/python" >&2
  exit 1
fi

# Put the venv on the session's PATH so bare `python`, `pytest`, `ruff`,
# `bandit` and `nestor` are the installed ones in every later shell. This
# depends on CLAUDE_ENV_FILE being set by the runtime; when it is not, the venv
# is built but not exported, so say so rather than leave the next shell to
# discover a venv that exists but is not on PATH.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  {
    echo "export VIRTUAL_ENV=\"$ROOT/.venv\""
    echo "export PATH=\"$ROOT/.venv/bin:\$PATH\""
  } >> "$CLAUDE_ENV_FILE"
  echo "[session-start] venv ready and exported to PATH: $ROOT/.venv" >&2
else
  echo "[session-start] venv ready at $ROOT/.venv but CLAUDE_ENV_FILE is unset — not on PATH; activate with: source $ROOT/.venv/bin/activate" >&2
fi
