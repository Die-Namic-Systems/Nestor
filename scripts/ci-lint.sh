# Match .github/workflows/tests.yml — run before push (local or cloud).
set -euo pipefail
cd "$(dirname "$0")/.."
python -m ruff check nestor tests hooks
python -m bandit -r nestor -ll -q
# Type gate (IDEAS §7.5) — pragmatic baseline, `nestor` only; see [tool.mypy]
# in pyproject.toml for what that does and does not cover.
python -m mypy nestor
# Secret scan — never commit the trust root. New findings not in
# .secrets.baseline fail. Derived/binary artifacts carry high-entropy hashes but
# no source secret, so they are excluded (the store bundles, the rebuilt
# decisions bundle, the binary store, bench output, the captured demo
# recording — its ledger-verify transcript prints real sha256 chain hashes,
# regenerated on every capture, not a secret).
git ls-files \
  | grep -vE '(^docs/dogfood/nestor\.db$|^docs/dogfood/decisions\.json$|\.bundle\.json$|^bench/results/|^demo/recordings/)' \
  | xargs python -m detect_secrets.pre_commit_hook --baseline .secrets.baseline
