"""What produced a row, in the one field a pair has for saying so.

`origin` already carried where the *text* came from — a file and an anchor.
IDEAS §6.41 recorded what it did not carry: which extractor, at which revision,
reading which revision of which repository. Without that, two rows disagreeing
cannot be sorted into "the corpus contradicts itself" and "the parser changed",
and §6.42 measured exactly how much that distinction is worth — sixty-three
collisions that turned out to be the parser.

So an origin built here names four things:

    willow@cf1040a:CONSTITUTION.md#Identity Authority [decision/a1b2c3d]
    └─repo  └─commit └─path        └─anchor            └─shape └─toolchain

**The toolchain digest is over the extractor *and* this module**, because a
change to either changes what the rows mean. It is a content hash, not a
version string, so it cannot be bumped by hand and cannot go stale.

**Reproducible by construction.** Nothing here reads a clock or a run counter.
The same extractor over the same commit yields byte-identical origins, which is
what makes a re-run a comparison rather than a new set of facts. That is the
same property `scripts/dogfood_store.py` relies on and for the same reason.

**It only means something because these files are committed.** A digest of a
script in a temporary directory names a thing nobody can fetch, which is the
failure this project exists to refuse. That is why the extractors live in the
repository rather than beside the store they write.
"""
from __future__ import annotations

import hashlib
import pathlib
import subprocess

DIGEST_CHARS = 7


def toolchain(extractor: str | pathlib.Path) -> str:
    """Content digest over the extractor and this module, together."""
    here = pathlib.Path(__file__).resolve()
    files = sorted({pathlib.Path(extractor).resolve(), here})
    h = hashlib.sha256()
    for path in files:
        h.update(path.read_bytes())
    return h.hexdigest()[:DIGEST_CHARS]


def commit(repo_root: str | pathlib.Path) -> str:
    """The source repository's HEAD, short. ``unknown`` if it is not a checkout.

    Not an error: a corpus may one day be read from an export rather than a
    clone, and a row that says ``unknown`` is honest where a row that omits the
    field is merely quiet.
    """
    try:
        out = subprocess.run(["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=30, check=True)
        return out.stdout.strip() or "unknown"
    except (subprocess.SubprocessError, OSError):
        return "unknown"


class Origin:
    """Builds origins for one extractor run over one repository checkout."""

    def __init__(self, repo: str, root: str | pathlib.Path, extractor: str | pathlib.Path):
        self.repo = repo
        self.root = pathlib.Path(root)
        self.commit = commit(root)
        self.toolchain = toolchain(extractor)

    def of(self, path: pathlib.Path, anchor: str, shape: str) -> str:
        rel = pathlib.Path(path).resolve().relative_to(self.root.resolve())
        anchor = " ".join(str(anchor).split())
        return (f"{self.repo}@{self.commit}:{rel}"
                f"{'#' + anchor if anchor else ''} [{shape}/{self.toolchain}]")

    def banner(self) -> str:
        return f"{self.repo}@{self.commit}  toolchain {self.toolchain}"
