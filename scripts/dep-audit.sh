#!/usr/bin/env bash
# Single source of truth for the dependency-vulnerability gate (IDEAS §7.5),
# called by BOTH scripts/ci-lint.sh and .github/workflows/tests.yml — mirrors
# the scripts/secret-scan.sh pattern so the invocation cannot drift between
# local and CI the way the secret-scan exclusion list once did (agent-log
# §6.111): one script, two callers, neither keeps its own copy.
#
# INVOCATION: `python -m pip_audit --skip-editable`, no `-r`/`--requirement`
# and no bare `pyproject.toml` project-path scan. `dependencies = []` at the
# top of pyproject.toml — Nestor's core is stdlib-only — so scanning the
# *declared* dependency list would audit nothing at all. What actually gets
# installed and run is the `[dev]` extra (ruff, bandit, mypy, detect-secrets,
# pip-audit itself, pytest where installed) plus their transitive deps, so
# auditing the resolved environment pip-audit runs in is the only invocation
# that reliably sees the real dependency set — local dev venv or CI's lint
# job, whichever this is running in. `--skip-editable` excludes the local
# nestor-meaning editable install from the scan: it is this project, not a
# dependency, and it is never published to PyPI under its dev version string,
# so leaving it in would report a permanent, meaningless "not found on PyPI"
# skip on every run.
#
# OFFLINE HANDLING (Nestor's standing rule: silence from a check means
# nothing — decision 0127): pip-audit queries a live vulnerability database
# on every run and keeps no committed baseline to fall back on the way
# detect-secrets has .secrets.baseline. Measured directly (see the commit
# this file landed in): when the database is genuinely unreachable, pip-audit
# does NOT report "no known vulnerabilities" — it exits non-zero with a
# connection error. That is exactly the behavior this gate needs, so this
# script trusts and forwards that exit code rather than reinterpreting it;
# the grep below only exists to turn pip-audit's raw traceback into a
# one-line diagnosis (network vs. a genuine finding) without changing whether
# the gate passes or fails. A found vulnerability and an unreachable database
# both fail the gate — neither is silence, so neither is a pass.
#
# A second silent-gap this script also closes: pip-audit can *skip* a
# dependency it fails to resolve (metadata error, private index, etc.)
# without that skip affecting its exit code, which is the same "unaudited
# but reported clean" shape as the network case. `--strict` does not fit
# here — it turns the expected, permanent nestor-meaning editable-skip into a
# hard failure too — so this script instead greps the skip table itself and
# fails loud on any skip that is not the one expected one.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! python -m pip_audit --version >/dev/null 2>&1; then
  echo "dep-audit: pip-audit not installed — run 'pip install -e \".[dev]\"' (or 'pip install pip-audit')." >&2
  exit 1
fi

out="$(mktemp)"
trap 'rm -f "$out"' EXIT

set +e
python -m pip_audit --skip-editable >"$out" 2>&1
status=$?
set -e

cat "$out"

if [ "$status" -ne 0 ]; then
  if grep -qiE 'ConnectionError|NameResolutionError|Max retries exceeded|ConnectTimeout|gaierror|Failed to establish a new connection|Temporary failure in name resolution' "$out"; then
    echo
    echo "dep-audit: UNKNOWN — could not reach the vulnerability database (network unreachable)." >&2
    echo "dep-audit: treating UNKNOWN as a FAIL, not a pass (decision 0127: silence from a check means nothing)." >&2
    echo "dep-audit: retry with network access; this is not a finding you can ignore your way past." >&2
  else
    echo
    echo "dep-audit: known vulnerabilities found in the resolved dependency set (see above) — gate fails." >&2
  fi
  exit "$status"
fi

# pip-audit exits 0 even when it skipped a package it could not resolve
# (distinct from --skip-editable's deliberate, expected skip of this
# project's own editable install) — treat any other skip as an unaudited
# dependency and fail loud rather than pass on partial coverage.
unexpected_skips="$(awk '
  found && /^-+ / { next }
  found && NF == 0 { found = 0; next }
  found { print }
  /^Name +Skip Reason/ { found = 1 }
' "$out" | grep -v '^nestor-meaning ' || true)"

if [ -n "$unexpected_skips" ]; then
  echo
  echo "dep-audit: dependency(ies) skipped by pip-audit without being cleared — unaudited, not clean:" >&2
  echo "$unexpected_skips" >&2
  exit 1
fi

echo "dep-audit: no known vulnerabilities found."
