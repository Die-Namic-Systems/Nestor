#!/usr/bin/env bash
# Single source of truth for the secret scan, called by BOTH
# scripts/ci-lint.sh and .github/workflows/tests.yml. It used to be copied into
# each, and the two drifted: the demo/recordings exclusion reached ci-lint.sh
# but not the workflow step, so a local `ci-lint.sh` passed while CI flagged the
# captured demo transcript's sha256 chain hashes (agent-log §6.111). One list
# lives here now; neither caller keeps its own copy, so they cannot disagree.
#
# New findings not in .secrets.baseline fail. Derived/binary artifacts carry
# high-entropy hashes but no source secret, so they are excluded: the binary
# store, the rebuilt decisions bundle, portable `.bundle.json` exports, bench
# output, the captured demo recording (its ledger-verify transcript prints
# real sha256 chain hashes, regenerated on every capture — not a secret), and
# nestor/vendor/ (a minified third-party .js bundle — Cytoscape.js, pinned and
# checksummed in nestor/vendor/README.md — whose minified identifiers read as
# high-entropy strings to detect-secrets but carry no secret of ours; the scan
# still covers every line Nestor's own contributors write).
set -euo pipefail
cd "$(dirname "$0")/.."
git ls-files \
  | grep -vE '(^docs/dogfood/nestor\.db$|^docs/dogfood/decisions\.json$|\.bundle\.json$|^bench/results/|^demo/recordings/|^nestor/vendor/)' \
  | xargs python -m detect_secrets.pre_commit_hook --baseline .secrets.baseline
