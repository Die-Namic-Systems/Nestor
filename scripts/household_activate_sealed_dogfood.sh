#!/usr/bin/env bash
# Import a sealed Nestor bundle into ~/.nestor (household trust root).
#
# Git dogfood (docs/dogfood/nestor.db) stays all-draft by covenant — do not
# point this at the committed store. Seal in the household UI (or export from a
# throwaway copy), then import that bundle here.
#
# Usage:
#   ./scripts/household_activate_sealed_dogfood.sh --from-db /path/to/sealed.db
#   ./scripts/household_activate_sealed_dogfood.sh --bundle /path/to/export.bundle.json
#
# See docs/local-agent-prototype.md for the standing household paths.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source .venv/bin/activate

FROM_DB=""
BUNDLE=""

usage() {
  sed -n '2,12p' "$0"
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from-db) FROM_DB="${2:-}"; shift 2 ;;
    --bundle) BUNDLE="${2:-}"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "unknown argument: $1" >&2; usage ;;
  esac
done

if [[ -n "$FROM_DB" && -n "$BUNDLE" ]]; then
  echo "pass only one of --from-db or --bundle" >&2
  exit 2
fi
if [[ -z "$FROM_DB" && -z "$BUNDLE" ]]; then
  echo "required: --from-db PATH or --bundle PATH" >&2
  usage
fi

export NESTOR_HOME="${NESTOR_HOME:-$HOME/.nestor}"
KEEP="$NESTOR_HOME/keep"
export NESTOR_DB="$KEEP/nestor.db"
export NESTOR_LEDGER="$KEEP/ledger.jsonl"
export NESTOR_KEYRING="$KEEP/verifiers.json"
export NESTOR_CORPUS_DIR="${NESTOR_CORPUS_DIR:-$ROOT/data/corpus}"

STAMP="$(date +%Y%m%d-%H%M%S)"

if [[ -n "$FROM_DB" ]]; then
  FROM_DB="$(readlink -f "$FROM_DB")"
  if [[ ! -f "$FROM_DB" ]]; then
    echo "sealed source db not found: $FROM_DB" >&2
    exit 1
  fi
  if [[ "$FROM_DB" == "$(readlink -f docs/dogfood/nestor.db)" ]]; then
    echo "refusing docs/dogfood/nestor.db — the committed store must stay all-draft." >&2
    echo "Seal at ~/.nestor with nestor ui, or export from a throwaway copy." >&2
    exit 1
  fi
  SEALED="$(sqlite3 "$FROM_DB" "SELECT COUNT(*) FROM tm_pairs WHERE status='sealed'")"
  if [[ "$SEALED" == "0" ]]; then
    echo "source db has no sealed rows: $FROM_DB" >&2
    exit 1
  fi
  BUNDLE="/tmp/nestor-household-import-$STAMP.bundle.json"
  echo "==> export $SEALED sealed pair(s) from $FROM_DB"
  nestor --db "$FROM_DB" export --out "$BUNDLE" --format json
fi

if [[ ! -f "$BUNDLE" ]]; then
  echo "bundle not found: $BUNDLE" >&2
  exit 1
fi

mkdir -p "$KEEP"
if [[ -f "$NESTOR_DB" ]]; then
  cp -a "$NESTOR_DB" "$NESTOR_DB.pre-import-$STAMP"
fi
if [[ -f "$NESTOR_LEDGER" ]]; then
  cp -a "$NESTOR_LEDGER" "$NESTOR_LEDGER.pre-import-$STAMP"
fi

echo "==> dry-run import into household ($NESTOR_DB)"
nestor --db "$NESTOR_DB" --ledger "$NESTOR_LEDGER" import "$BUNDLE"

echo "==> apply import"
nestor --db "$NESTOR_DB" --ledger "$NESTOR_LEDGER" import "$BUNDLE" --apply

echo "==> corpus sync"
nestor --db "$NESTOR_DB" corpus sync --source-dir "$NESTOR_CORPUS_DIR"

echo "==> household stats"
nestor --db "$NESTOR_DB" stats
nestor --db "$NESTOR_DB" --ledger "$NESTOR_LEDGER" ledger verify

echo
echo "Done. Restart Cursor MCP (reload window) so nestor serve picks up the household store."
echo "Bundle kept at: $BUNDLE"
