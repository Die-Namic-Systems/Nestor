# Match .github/workflows/tests.yml — run before push (local or cloud).
set -euo pipefail
cd "$(dirname "$0")/.."
python -m ruff check nestor tests hooks
python -m bandit -r nestor -ll -q
# Secret scan — never commit the trust root. New findings not in
# .secrets.baseline fail. Derived/binary artifacts carry high-entropy hashes but
# no source secret, so they are excluded (the store bundles, the rebuilt
# decisions bundle, the binary store, bench output).
git ls-files \
  | grep -vE '(^docs/dogfood/nestor\.db$|^docs/dogfood/decisions\.json$|\.bundle\.json$|^bench/results/)' \
  | xargs python -m detect_secrets.pre_commit_hook --baseline .secrets.baseline
