# Lightweight docs-only verification gate (IDEAS §6.100).
#
# When a change touches only docs/, IDEAS.md, AGENTS.md, CLAUDE.md, README.md,
# or docs/dogfood/decisions/*.json, the full gate (ci-lint.sh + full pytest)
# costs ~100s for ~46 tests that cannot break. This script runs only the tests
# that docs-only changes can fail (~7s), so an agent in a session with a human
# waiting can verify without the human paying for irrelevant coverage.
#
# What it runs:
#   1. dogfood_store.py --verify  — decision files match the committed store
#   2. test_docs.py              — README layout, module docstrings, docs
#   3. test_open_findings.py     — IDEAS.md §6 tags are well-formed
#   4. test_dogfood_store.py     — store builder's own invariants
#
# What it does NOT run (and why that is safe for docs-only changes):
#   - ruff / bandit / mypy       — no Python source changed
#   - secret-scan / dep-audit    — no new secrets or dependencies possible
#   - the rest of the test suite — nestor/, recipes/, hooks/ untouched
#
# AGENTS.md carries the change-class table that tells an agent when this gate
# is the correct choice vs. the full gate. When in doubt, run full.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "ci-docs: verifying dogfood store matches decision files..."
python scripts/dogfood_store.py --verify

echo "ci-docs: running docs-relevant tests..."
python -m pytest tests/test_docs.py tests/test_open_findings.py tests/test_dogfood_store.py -q

echo "ci-docs: docs-only gate passed."
