#!/usr/bin/env bash
# Explicit test lanes: installing an optional dependency must not enlarge a run.
set -euo pipefail
cd "$(dirname "$0")/.."

lane="${1:-core}"
if [[ $# -gt 0 ]]; then
  shift
fi

case "$lane" in
  core)
    unset NESTOR_BROWSER_TEST NESTOR_SEMANTIC_TEST NESTOR_OLLAMA_TEST NESTOR_EXTERNAL_TEST
    python -m pytest -q -n auto --dist loadgroup \
      -m "not slow and not browser and not semantic and not ollama and not external" \
      "$@"
    ;;
  full)
    # Full local/CI contract. Live services and adjacent repositories remain
    # opt-in even here; their dedicated lanes below make that dependency clear.
    unset NESTOR_BROWSER_TEST NESTOR_SEMANTIC_TEST NESTOR_OLLAMA_TEST NESTOR_EXTERNAL_TEST
    python -m pytest -q -n auto --dist loadgroup "$@"
    ;;
  slow)
    unset NESTOR_BROWSER_TEST NESTOR_SEMANTIC_TEST NESTOR_OLLAMA_TEST NESTOR_EXTERNAL_TEST
    python -m pytest -q -n auto --dist loadgroup -m slow "$@"
    ;;
  performance)
    unset NESTOR_BROWSER_TEST NESTOR_SEMANTIC_TEST NESTOR_OLLAMA_TEST NESTOR_EXTERNAL_TEST
    python -m pytest -q -m performance "$@"
    ;;
  browser)
    unset NESTOR_SEMANTIC_TEST NESTOR_OLLAMA_TEST NESTOR_EXTERNAL_TEST
    export NESTOR_BROWSER_TEST=1
    python -m pytest -q -m browser "$@"
    ;;
  semantic)
    unset NESTOR_BROWSER_TEST NESTOR_OLLAMA_TEST NESTOR_EXTERNAL_TEST
    export NESTOR_SEMANTIC_TEST=1
    python -m pytest -q -m semantic "$@"
    ;;
  ollama)
    unset NESTOR_BROWSER_TEST NESTOR_SEMANTIC_TEST NESTOR_EXTERNAL_TEST
    export NESTOR_OLLAMA_TEST=1
    python -m pytest -q -m ollama "$@"
    ;;
  external)
    unset NESTOR_BROWSER_TEST NESTOR_SEMANTIC_TEST NESTOR_OLLAMA_TEST
    export NESTOR_EXTERNAL_TEST=1
    python -m pytest -q -m external "$@"
    ;;
  *)
    echo "usage: scripts/ci-test.sh {core|full|slow|performance|browser|semantic|ollama|external} [pytest args...]" >&2
    exit 2
    ;;
esac
