# Match .github/workflows/tests.yml — run before push (local or cloud).
set -euo pipefail
cd "$(dirname "$0")/.."
python -m ruff check nestor tests hooks
python -m bandit -r nestor -ll -q
# Type gate (IDEAS §7.5) — pragmatic baseline, `nestor` only; see [tool.mypy]
# in pyproject.toml for what that does and does not cover.
python -m mypy nestor
# Secret scan — never commit the trust root. Shared with the workflow's own
# Secret scan step so the exclusion list cannot drift between local and CI
# (agent-log §6.111); the list and its rationale live in scripts/secret-scan.sh.
bash "$(dirname "$0")/secret-scan.sh"
