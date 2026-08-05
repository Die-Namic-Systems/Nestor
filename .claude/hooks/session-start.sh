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

# Local sessions manage their own .venv (see CLAUDE.md — Environment).
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

if [ ! -x .venv/bin/python ]; then
  python -m venv .venv
fi

# [dev] = pytest, ruff==0.15.0, bandit; [keys] = cryptography for the
# asymmetric suite. [semantic] is deliberately absent — installing it
# un-skips model-downloading tests and diverges from the CI baseline.
.venv/bin/pip install -e ".[dev,keys]" --quiet

# Put the venv on the session's PATH so bare `python`, `pytest`, `ruff`,
# `bandit` and `nestor` are the installed ones in every later shell.
{
  echo "export VIRTUAL_ENV=\"$CLAUDE_PROJECT_DIR/.venv\""
  echo "export PATH=\"$CLAUDE_PROJECT_DIR/.venv/bin:\$PATH\""
} >> "${CLAUDE_ENV_FILE:-/dev/null}"
