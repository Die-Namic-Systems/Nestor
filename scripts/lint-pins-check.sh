#!/usr/bin/env bash
# Refuse to run the lint gate against tool versions CI does not use.
#
# Called by scripts/ci-lint.sh before any check runs. Reads the pins from
# scripts/lint-pins.txt — the same file .github/workflows/tests.yml installs
# from — and compares them to what is actually importable here. Also checks
# that .pre-commit-config.yaml's ruff hook `rev:` agrees with this file's
# ruff==, since that is a third place the same version can be pinned and go
# stale (see the ruff_pin block below).
#
# WHY IT REFUSES RATHER THAN WARNS, and rather than quietly running the pinned
# version out of a throwaway environment: three of these five tools are only
# correct *inside this project's environment*. mypy resolves the project's
# imports, pip-audit audits the very environment it runs in, and detect-secrets
# is invoked as `python -m` by scripts/secret-scan.sh. Running those from an
# isolated `uvx`-style sandbox would answer a question about a different
# environment and print it as though it were about this one. So the only honest
# way for a local run to agree with CI is for the local environment to hold
# CI's versions — and the only honest thing to do when it does not is say so
# and stop. Nestor's standing rule (decision 0127): silence from a check means
# nothing, and neither does a check that ran under something else.
set -euo pipefail
cd "$(dirname "$0")/.."

pins_file="scripts/lint-pins.txt"

# The import name is not always the distribution name: `pip-audit` is imported
# as `pip_audit`, `detect-secrets` as `detect_secrets`. Everything else matches.
module_for() {
  case "$1" in
    pip-audit) echo "pip_audit" ;;
    detect-secrets) echo "detect_secrets" ;;
    *) echo "$1" ;;
  esac
}

mismatched=""
missing=""
ruff_pin=""

while IFS= read -r line; do
  line="${line%%#*}"
  line="$(echo "$line" | tr -d '[:space:]')"
  [ -z "$line" ] && continue
  name="${line%%==*}"
  want="${line##*==}"
  module="$(module_for "$name")"

  # `importlib.metadata` reads the *installed distribution's* version, which is
  # the thing pip pinned. Parsing `--version` output would work for four of the
  # five and differ in format for the fifth, and a version check that is itself
  # five parsers is a fifth place for this to drift.
  got="$(python -c "
import sys
try:
    from importlib.metadata import version
    print(version('$name'))
except Exception:
    sys.exit(1)
" 2>/dev/null || true)"

  if [ -z "$got" ]; then
    missing="$missing  $name==$want  (import name: $module)
"
  elif [ "$got" != "$want" ]; then
    mismatched="$mismatched  $name: this environment has $got, CI pins $want
"
  fi

  [ "$name" = "ruff" ] && ruff_pin="$want"
done < "$pins_file"

# .pre-commit-config.yaml pins ruff a second, independent way — a hook `rev:`,
# not a pip requirement — and nothing kept the two numbers in sync: it sat at
# v0.15.0 while this file and [dev] in pyproject.toml had already moved to
# 0.16.6, so `pre-commit run` and `ci-lint.sh`/CI could report different
# findings for the same push. Checked here because this is the one place that
# already reads lint-pins.txt's ruff pin.
precommit_file=".pre-commit-config.yaml"
if [ -n "$ruff_pin" ] && [ -f "$precommit_file" ]; then
  # Scoped to the block that starts at the ruff-pre-commit repo's own `repo:`
  # line, so a `rev:` belonging to a different hook is never read as ruff's.
  precommit_ruff="$(awk '
    /repo: *https:\/\/github\.com\/astral-sh\/ruff-pre-commit/ { in_block=1; next }
    in_block && /^ *rev:/ { sub(/^ *rev: *v?/, ""); print; exit }
    /^ *-? *repo:/ { in_block=0 }
  ' "$precommit_file")"

  if [ -z "$precommit_ruff" ]; then
    missing="$missing  $precommit_file: no astral-sh/ruff-pre-commit rev found
"
  elif [ "$precommit_ruff" != "$ruff_pin" ]; then
    mismatched="$mismatched  ruff (pre-commit hook): $precommit_file pins v$precommit_ruff, $pins_file pins $ruff_pin
"
  fi
fi

if [ -n "$missing" ] || [ -n "$mismatched" ]; then
  echo "ci-lint: refusing to run — this environment's lint tools are not CI's." >&2
  echo >&2
  [ -n "$mismatched" ] && { echo "Different version than CI runs:" >&2; printf '%s' "$mismatched" >&2; }
  [ -n "$missing" ] && { echo "Not installed:" >&2; printf '%s' "$missing" >&2; }
  echo >&2
  echo "A gate that answers under a different version has not answered about" >&2
  echo "this push. Sync, then re-run:" >&2
  echo >&2
  echo "    pip install -r $pins_file" >&2
  echo >&2
  echo "To move a pin deliberately, edit $pins_file — CI installs from the same" >&2
  echo "file, so both move together (agent-log §6.114)." >&2
  exit 1
fi
