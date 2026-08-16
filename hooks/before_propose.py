"""Cross-session collision awareness: notice another agent is in the room.

``hooks/before_build.py`` is the anti-rediscovery guard (#105) — it asks *what
already exists* before an agent builds. This is its sibling for the concurrent
present, not the past: it asks *who else is building right now*, before a
decision number is minted or a PR is opened. IDEAS.md §7.5 (last bullet) has
the worked instance this closes: two sessions ran this repo at once, both
minted decision ``0118`` off the same master, both rebuilt the derived store,
and the model read the other open PR's number as an opaque token until the
operator pointed at it. The signal was structural and present the whole time —
another branch on the same base, a duplicate number in flight (the
number-before-PR hazard decision ``0054`` names), the same derived files
rebuilt on a sibling branch — and nothing was surfacing it.

It rides **UserPromptSubmit**, same as ``before_build``, and injects a short
reminder only when the prompt reads as *about to propose/mint a decision or
open a PR* — a status question or an ordinary edit costs nothing.

**What it scans, entirely with local git — no network, no GitHub API:**

* the next decision number this checkout would mint (``docs/dogfood/decisions/``,
  highest ``NNNN-*.json`` plus one), and whether any other locally-known branch
  (``git branch -a``) already claims it;
* other branches that have added a decision file this branch has not yet seen —
  "in flight elsewhere", not necessarily a collision on the *next* number;
* other branches that have touched the derived files (``docs/dogfood/nestor.db``,
  ``docs/dogfood/decisions.json``) this checkout would also rebuild.

**Advisory, best-effort, and it says so.** A hook cannot serialize two agents;
it can only make a visible collision loud. Read ``limits()`` below and in the
emitted text — this is the one guard in the suite whose job is partly to admit
what it cannot see, not just what it found.

Three properties carried over from ``before_build``, on purpose:

* **Advisory, not a boundary.** It warns, it does not block — excluded from
  ``scripts/hook_guard.py``'s blocking-gate proof for that reason, the same as
  ``before_build``.
* **Silent unless it reads as propose/mint/open-a-PR.** Latency and noise on
  every turn is the mistake ``reinject`` avoids; this one costs nothing on a
  status question or a routine edit.
* **Fails CLOSED into silence safely.** If the scan cannot determine collision
  state (no git, no resolvable base, a repo it cannot read), it says
  *UNKNOWN*, not *clear*. A guard that goes quiet and reads as reassurance on
  its own failure is worse than no guard — "silence from the store means
  nothing" is a lesson this repo has already paid for once (decision ``0127``,
  the read-only probe that wasn't).

Clean-room: the UserPromptSubmit-stdout-becomes-context mechanism is the
official Claude Code behaviour (shared with ``reinject`` and ``before_build``);
the git-based collision scan is written fresh against this repo's own decision
numbering and derived-file layout.
"""
from __future__ import annotations

import dataclasses
import pathlib
import re
import subprocess

from hooks.session_start import repo_root

#: The hook event this rides — the same moment `before_build` rides.
EVENT = "UserPromptSubmit"

#: The derived files a decision-store rebuild touches (`scripts/dogfood_store.py
#: --rebuild`). A sibling branch that has also touched these is rebuilding the
#: same derived artifact this checkout would.
DERIVED_FILES = ("docs/dogfood/nestor.db", "docs/dogfood/decisions.json")

#: Local refs tried, in order, as "the shared base" two branches diverged from.
#: Tried locally-known first (no fetch performed, no network required) —
#: `origin/master` if this checkout has ever seen it, then plain `master`/`main`
#: for a repo with no remote configured at all.
_BASES = ("origin/master", "origin/main", "master", "main")

#: One decision file's number, from its path relative to the repo root.
_NUM_RX = re.compile(r"^docs/dogfood/decisions/(\d{4})-")

# --- intent: does this prompt read as "about to mint a number or open a PR" ---

#: Verbs that put a *decision* record into being — deliberately not "decide" on
#: its own (too common, too unrelated: "let's decide on lunch") and not "seal"
#: (that is a human's act at `nestor ui`, not a mint).
_DECISION_VERB = r"\b(?:mint|propose|record|add|write\s+up|file|draft)\b"
_DECISION_NOUN = r"\bdecisions?\b"
_DECISION_RX = (
    rf"{_DECISION_VERB}(?:\W+\w+){{0,4}}\W+{_DECISION_NOUN}"
    rf"|{_DECISION_NOUN}(?:\W+\w+){{0,4}}\W+number"
    r"|\bnext\s+decision\s+number\b"
)
#: Opening a PR — the other half of the worked instance (#111's collision was
#: two PRs, not just two decision numbers).
_PR_RX = (
    r"\b(?:open|raise|create|submit|file)\b(?:\W+\w+){0,3}\W+"
    r"(?:a\s+|the\s+|new\s+)*(?:pr|pull\s*requests?)\b"
)
#: Rebuilding the derived store directly — the other artifact the worked
#: instance collided on.
_REBUILD_RX = r"\brebuild\b(?:\W+\w+){0,3}\W+store\b|\bdogfood_store\b"

_COLLISION_RX = re.compile(
    f"(?:{_DECISION_RX})|(?:{_PR_RX})|(?:{_REBUILD_RX})", re.IGNORECASE)


def is_collision_intent(prompt: str) -> bool:
    """True when the prompt reads as *about to mint a number / open a PR*.

    A named predicate, not an inline regex, for the same reason
    ``before_build.is_build_intent`` is one: the prove-it-can-fail tests pin
    both directions independently of the advisory text around it.
    """
    return bool(prompt) and bool(_COLLISION_RX.search(prompt))


# --- the scan: entirely local git, no network -------------------------------

def _git(root: pathlib.Path, *args: str) -> str | None:
    """Run one git command in ``root``; ``None`` on any failure, not raise.

    Every caller in this module treats ``None`` as *could not determine*, which
    is the honest state to report — never coerced into "found nothing" (that
    would be a false-clear on a git that failed to run).
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def resolve_base(root: pathlib.Path) -> str | None:
    """The first of `_BASES` this checkout actually knows about, or ``None``."""
    for candidate in _BASES:
        if _git(root, "rev-parse", "--verify", "--quiet", candidate) is not None:
            return candidate
    return None


def local_next_number(root: pathlib.Path) -> str | None:
    """The decision number this checkout would mint next, from the working
    tree (not HEAD) — an uncommitted new decision file counts, the same as it
    would for the next agent to look at the directory and pick a number."""
    ddir = root / "docs" / "dogfood" / "decisions"
    if not ddir.is_dir():
        return None
    nums = []
    for path in ddir.glob("*.json"):
        m = re.match(r"^(\d{4})-", path.name)
        if m:
            nums.append(int(m.group(1)))
    if not nums:
        return None
    return f"{max(nums) + 1:04d}"


def _candidate_branches(root: pathlib.Path, base: str) -> list[str] | None:
    """Every locally-known branch with commits not yet in ``base``, minus this
    checkout's own branch and its own remote-tracking counterpart.

    ``git branch -a --no-merged`` is one call, offline (no fetch performed —
    "locally-known" is exactly what a repo with no network can still answer),
    and it is what makes sibling *worktrees* of this very repo visible: they
    share one set of refs, so another agent's worktree branch shows up here
    the moment it has committed anything, with no PR and no push required.
    """
    out = _git(root, "branch", "-a", "--no-merged", base,
               "--format=%(refname:short)")
    if out is None:
        return None
    here = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    here = here.strip() if here else None
    skip = {here, f"origin/{here}"} if here else set()
    return [b.strip() for b in out.splitlines()
            if b.strip() and b.strip() not in skip and not b.strip().endswith("/HEAD")]


@dataclasses.dataclass(frozen=True)
class ScanResult:
    """What one collision scan found — or why it could not look.

    ``ok=False`` means the scan itself did not run to completion (no git, no
    resolvable base, an unreadable repo): every other field is a partial best
    effort and must be presented as *unknown*, not folded into "no collision".
    """
    ok: bool
    base: str | None
    error: str
    next_number: str | None
    #: number -> branches that already have a decision file with that number.
    claimed_numbers: dict[str, list[str]]
    #: branch -> decision numbers it has added that this checkout has not.
    decisions_touched: dict[str, list[str]]
    #: branches that have also touched a derived file.
    derived_touched: list[str]
    checked: int


def scan(root: pathlib.Path) -> ScanResult:
    """One collision scan of ``root``, entirely local, never mutates the repo."""
    base = resolve_base(root)
    next_number = local_next_number(root)
    if base is None:
        return ScanResult(
            ok=False, base=None,
            error="no origin/master, origin/main, master, or main ref known "
                  "locally to diff against",
            next_number=next_number, claimed_numbers={}, decisions_touched={},
            derived_touched=[], checked=0)

    branches = _candidate_branches(root, base)
    if branches is None:
        return ScanResult(
            ok=False, base=base,
            error="`git branch -a --no-merged` failed (not a git repo, or git "
                  "unavailable)",
            next_number=next_number, claimed_numbers={}, decisions_touched={},
            derived_touched=[], checked=0)

    claimed: dict[str, list[str]] = {}
    touched: dict[str, list[str]] = {}
    derived: list[str] = []
    unreadable = []
    for branch in branches:
        diff = _git(root, "diff", "--name-only", f"{base}...{branch}")
        if diff is None:
            unreadable.append(branch)
            continue
        files = [f for f in diff.splitlines() if f]
        nums = sorted({m.group(1) for f in files if (m := _NUM_RX.match(f))})
        if nums:
            touched[branch] = nums
            for n in nums:
                claimed.setdefault(n, []).append(branch)
        if any(f in DERIVED_FILES for f in files):
            derived.append(branch)

    error = (f"{len(unreadable)} branch(es) could not be diffed: "
             f"{', '.join(unreadable[:5])}") if unreadable else ""
    return ScanResult(
        ok=True, base=base, error=error, next_number=next_number,
        claimed_numbers=claimed, decisions_touched=touched,
        derived_touched=derived, checked=len(branches))


def limits() -> str:
    """The honest ceiling on what this guard can see — stated once, quoted by
    both the emitted text and the test that pins it."""
    return (
        "LIMITS (best-effort, advisory only): sees only branches this "
        "checkout already knows about (`git branch -a`) as of the last fetch "
        "— a sibling session's uncommitted work, or a branch pushed since, is "
        "invisible here. It cannot serialize two agents, only make a visible "
        "collision loud. It never calls the GitHub API and it never writes."
    )


def advisory(root: pathlib.Path | None = None) -> str:
    """The before-propose reminder — deterministic, and honest when it cannot
    determine collision state rather than reassuring on a guess."""
    try:
        root = root or repo_root()
        result = scan(root)
    except Exception as exc:  # noqa: BLE001 — a broken scan must not crash a reminder
        return "\n".join([
            "[NESTOR collision] You may not be the only agent in this tree "
            "right now (issue #111, IDEAS §7.5).",
            f"  [collision] scan crashed ({type(exc).__name__}: {exc}) — "
            f"collision state UNKNOWN, not clear. Check by hand: "
            f"`git branch -a --no-merged origin/master`.",
            f"  [collision] {limits()}",
        ])

    lines = [
        "[NESTOR collision] You may not be the only agent in this tree right "
        "now — before minting a decision number or opening a PR, check who "
        "else is building (issue #111, IDEAS §7.5).",
    ]
    if not result.ok:
        lines.append(f"  [collision] scan incomplete ({result.error}) — "
                     f"collision state UNKNOWN here, not clear. Check by hand: "
                     f"`git branch -a --no-merged origin/master`.")
        lines.append(f"  [collision] {limits()}")
        return "\n".join(lines)

    nxt = result.next_number or "(no decisions/ yet)"
    lines.append(f"  [collision] next local decision number would be {nxt} "
                f"(base {result.base}, {result.checked} sibling branch(es) "
                f"checked).")
    if result.next_number and result.next_number in result.claimed_numbers:
        who = ", ".join(sorted(result.claimed_numbers[result.next_number]))
        lines.append(
            f"  [collision] COLLISION: decision {result.next_number} already "
            f"exists on {who} — do not mint it here too. Yield the number, "
            f"the way decision 0120 resolved the worked instance: renumber "
            f"this branch's, or coordinate with whoever is on {who} first.")
    others = {n: bs for n, bs in result.claimed_numbers.items()
              if n != result.next_number}
    if others:
        detail = "; ".join(f"{n} on {', '.join(sorted(bs))}"
                           for n, bs in sorted(others.items()))
        lines.append(f"  [collision] other decisions in flight elsewhere, not "
                    f"yet on this branch: {detail}.")
    if result.derived_touched:
        who = ", ".join(sorted(result.derived_touched))
        lines.append(
            f"  [collision] derived files (nestor.db / decisions.json) also "
            f"touched on: {who} — rebuilding here will conflict with that "
            f"branch's rebuild. Resolve by rebuilding from the union of "
            f"authored decision files, never by hand-merging the derived "
            f"store (decision 0120).")
    if not result.claimed_numbers and not result.derived_touched:
        lines.append(
            "  [collision] no sibling branch touching decisions/ or the "
            "derived store found in local git — quiet, not proof (see "
            "limits below).")
    if result.error:
        lines.append(f"  [collision] partial scan: {result.error}.")
    lines.append(f"  [collision] {limits()}")
    return "\n".join(lines)


def for_prompt(prompt: str, root: pathlib.Path | None = None) -> str:
    """The context to inject for this prompt: the advisory on propose/mint/PR
    intent, the empty string otherwise (which the runner emits as nothing)."""
    return advisory(root) if is_collision_intent(prompt) else ""
