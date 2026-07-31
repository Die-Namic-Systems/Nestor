#!/usr/bin/env bash
# Create local/fleet-integration branches tracking fleet IDEAS remotes (see docs/local-fleet.md).
set -euo pipefail

GITHUB="${GITHUB:-$HOME/github}"
BRANCH=local/fleet-integration

checkout() {
  local repo="$1" remote_branch="$2"
  local dir="$GITHUB/$repo"
  if [[ ! -d "$dir/.git" ]]; then
    echo "skip $repo (no clone at $dir)"
    return 0
  fi
  echo "==> $repo -> $BRANCH ($remote_branch)"
  git -C "$dir" fetch origin --prune
  git -C "$dir" checkout -B "$BRANCH" "origin/$remote_branch"
}

checkout terpsi-music claude/coat-hat-check-p6obau
checkout safe-app-store-public claude/repo-test-run-a8lt94

# Optional second clone name used on some machines
if [[ -d "$GITHUB/safe-app-store/.git" ]]; then
  checkout safe-app-store claude/repo-test-run-a8lt94
fi

echo "Done. Nestor: pip install -e $GITHUB/nestor && see docs/local-fleet.md"
