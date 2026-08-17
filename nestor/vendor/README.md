# Vendored: Cytoscape.js

Nestor's read-only decision-graph view (`nestor ui`'s Graph tab) renders with
[Cytoscape.js](https://js.cytoscape.org/), vendored here rather than pulled
from a CDN — the served page's CSP is `script-src 'unsafe-inline'` with no
`'self'` and no allowed host, so a `<script src="...">` of any kind, local or
remote, would be blocked by the browser. `nestor/ui_page.py` reads
`cytoscape.min.js` off disk at serve time and inlines its bytes into a
`<script>` tag already in the page — see `_read_vendor_script` there.

Only Cytoscape itself is vendored. No layout is: the view uses Cytoscape's
built-in `breadthfirst` layout (a directed decision graph is closer to a DAG
than to a force-directed cloud), so nothing else needed pulling in — in
particular, **not** `elkjs` (copyleft, off-limits for this project) and not
`cytoscape-dagre` (MIT, would have been allowed, wasn't needed).

## Pinned version

| | |
|---|---|
| Package | `cytoscape` |
| Version | **3.34.1** |
| File | `dist/cytoscape.min.js` (the UMD build — a single global, no module loader required) |
| Source | `https://registry.npmjs.org/cytoscape/-/cytoscape-3.34.1.tgz` |
| npm shasum (sha1, from registry metadata) | `364923bb9598f5bc1ed1c849a1273671198275fc` |
| sha256 of the vendored `cytoscape.min.js` | `5141892eb19898946e5af8300e14cec15a63a22186a4ca56d76819a91e2a3fe6` |
| Size | 435,503 bytes (~425 KiB) |

Fetched via `curl` from the npm registry tarball (unpkg and the GitHub
releases API were both blocked by this session's egress policy; the npm
registry tarball was reachable and its sha1 was checked against the shasum
the registry itself reports for that exact version before anything was
copied in). Re-verify with:

```
sha256sum nestor/vendor/cytoscape.min.js
# expect 5141892eb19898946e5af8300e14cec15a63a22186a4ca56d76819a91e2a3fe6
```

To pick up a newer release, repeat the same steps: download the tarball for
the target version from `https://registry.npmjs.org/cytoscape/-/cytoscape-<version>.tgz`,
check its sha1 against `dist-tags` metadata, copy `dist/cytoscape.min.js` and
`LICENSE` in over these files, and update every value in this table
(including the sha256 above — it changes with the file).

## License

Cytoscape.js is MIT-licensed. `cytoscape.LICENSE` here is copied verbatim
from the package's own `LICENSE` file — Copyright (c) 2016-2026, The
Cytoscape Consortium. Its header is also kept intact inside
`cytoscape.min.js` itself (the first ~15 lines of the minified file are the
license comment, unminified, exactly as npm ships it). See also `NOTICE` at
the repository root for the project-level attribution this vendoring adds
alongside Nestor's own Apache-2.0 license.

## Why this file is excluded from a few gates

- **`scripts/secret-scan.sh`** excludes `nestor/vendor/` — a minified ~425 KB
  bundle is exactly the high-entropy shape detect-secrets flags, and it is a
  well-known, checksummed, third-party artifact, not project source that
  could carry a real credential. See the exclusion's comment in that script
  for the same reasoning already applied to other binary/high-entropy paths.
- **ruff / mypy** are scoped to `nestor`, `tests`, `hooks` as Python source;
  `nestor/vendor/*.js` is not Python and is excluded from both configs in
  `pyproject.toml`, documented at the exclusion.
- **Packaging**: `nestor/vendor/*.js` and `nestor/vendor/*.LICENSE` are
  force-included into the wheel in `pyproject.toml`
  (`[tool.hatch.build.targets.wheel.force-include]`) as an explicit contract
  that survives a future change to hatchling's own default packaging —
  verified (not assumed) that hatchling's current default already ships them
  too, by building a wheel with the block removed and inspecting its
  contents. `tests/test_packaging.py` builds a real wheel and asserts both
  files land inside it, which is the actual guard either way.
