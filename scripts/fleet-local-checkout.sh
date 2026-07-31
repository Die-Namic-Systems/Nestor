#!/usr/bin/env bash
# Track fleet IDEAS remotes on local/fleet-integration (see docs/local-fleet.md).
set -euo pipefail

GITHUB="${GITHUB:-$HOME/github}"
BRANCH=local/fleet-integration

remote_for() {
  case "$1" in
    terpsi-music) echo "claude/coat-hat-check-p6obau" ;;
    safe-app-store-public|safe-app-store) echo "claude/repo-test-run-a8lt94" ;;
    *) echo "" ;;
  esac
}

checkout() {
  local repo="$1"
  local remote_branch
  remote_branch="$(remote_for "$repo")"
  local dir="$GITHUB/$repo"
  if [[ -z "$remote_branch" ]]; then
    return 0
  fi
  if [[ ! -d "$dir/.git" ]]; then
    echo "skip $repo (no clone at $dir)"
    return 0
  fi
  echo "==> $repo -> $BRANCH"
  git -C "$dir" fetch origin --prune
  if ! git -C "$dir" show-ref --verify --quiet "refs/remotes/origin/$remote_branch"; then
    echo "    origin/$remote_branch is gone (merged?); leaving $(git -C "$dir" branch --show-current) as-is"
    return 0
  fi
  local prev
  prev="$(git -C "$dir" branch --show-current)"
  if git -C "$dir" show-ref --verify --quiet "refs/heads/$BRANCH"; then
    git -C "$dir" checkout "$BRANCH"
    if ! git -C "$dir" merge --ff-only "origin/$remote_branch"; then
      echo "    could not fast-forward $BRANCH — resolve locally or delete the branch to recreate"
    fi
  else
    git -C "$dir" checkout -b "$BRANCH" "origin/$remote_branch"
  fi
  if [[ "$prev" != "$BRANCH" ]]; then
    echo "    (was on $prev; switch back with: git -C $dir checkout $prev)"
  fi
}

for repo in terpsi-music safe-app-store-public safe-app-store; do
  checkout "$repo"
done

echo "Done. Nestor: pip install -e $GITHUB/nestor && see docs/local-fleet.md"
