# Dogfood smoke corpus (pinned for CI)

Real decision JSON files — not invented rows — copied from the active and archived
corpora. The O(n²) slow tests and ``demo/the_dogfooding.py`` (via ``--smoke``)
measure this subset instead of the full active queue so CI time stays bounded as
the audit corpus grows.

| File | Role |
|------|------|
| [`manifest.txt`](manifest.txt) | Which decision files belong in the fixture |
| [`decisions/`](decisions/) | Copied JSON (regenerate with ``python scripts/build_dogfood_smoke_fixture.py``) |

The full active store still verifies against every file in ``docs/dogfood/decisions/``.
