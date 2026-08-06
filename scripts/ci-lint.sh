# Match .github/workflows/tests.yml — run before push (local or cloud).
set -euo pipefail
cd "$(dirname "$0")/.."
python -m ruff check nestor tests hooks
python -m bandit -r nestor -ll -q
