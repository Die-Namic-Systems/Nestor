#!/usr/bin/env python3
"""One repository's merged pull requests, as decisions a human already made.

    python scripts/git_decisions/extract.py --repo ~/github/x/y --name owner/y \\
        --email me@example.com --out data/git-decisions/y.db

**The claim each row makes.** Not "this is true" — *this shipped, and a person
put it there*. The merge is the attestation: authored, timestamped, and anchored
to a SHA in a structure that is already a hash chain. Nothing is inferred about
intent; the row quotes what the merge itself says and cites where to check.

**Shape.** A merge commit made by a person reads:

    subject   Merge pull request #3 from owner/claude/soft-nestor-seam
    body      fix: make the Nestor citation seam soft (optional dependency)

The subject carries the PR number and the branch that proposed it; the body's
first line is the pull request's title, which is the commitment. So the pair is
*what was proposed* → *what shipped*, and the evidence is the SHA.

**Every row is a draft.** A merge proves a person chose it; it does not prove
they would choose it again today, and this tool is not entitled to decide that.
Sealing stays a human act — the covenant, unchanged: propose, do not confirm.

**Robot merges are skipped and counted.** A release bot's merge happened; nobody
chose it in the moment. The count is printed rather than dropped, because a tool
that silently discards part of its input is one whose totals cannot be checked.
"""
from __future__ import annotations

import argparse
import pathlib
import sqlite3
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from nestor import memory, storage                                 # noqa: E402
from nestor.sqlite_store import SqliteStore                        # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from inventory import ROBOT_MARKERS, git, repo_name                # noqa: E402

DOMAIN, TARGET = "decision", "commitment"

#: Branch prefixes that name the process, not the subject — `claude/soft-seam`
#: is about the seam, not about Claude.
_PREFIXES = ("claude/", "codex/", "feat/", "fix/", "chore/", "docs/", "test/",
             "refactor/", "release/", "ci/", "build/", "perf/")
#: The disambiguating suffix an agent appends to a branch name (`-ei08dl`).
#: Only stripped from agent-prefixed branches: applied everywhere it eats real
#: words that happen to be the right length — `repin-nestor-to-master` became
#: "repin nestor to", losing the word that said where it was repinned *to*.
_SUFFIX = re.compile(r"-[a-z0-9]{6,8}$")
#: Prefixes that mark a branch an agent named, and so the only ones that carry
#: a random suffix worth removing.
_AGENT_PREFIXES = ("claude/", "codex/")


#: Conventional-commit type, with an optional scope: `feat(propagate):`.
_CC_TYPE = re.compile(
    r"^(feat|fix|chore|docs|test|refactor|perf|build|ci|style|revert)"
    r"(\([^)]*\))?\s*:\s*", re.I)
#: Words too common to count as shared subject matter between a branch and a
#: title. Overlap on "the" is not evidence the branch describes the change.
_STOP = frozenset((
    "a", "an", "and", "the", "to", "of", "for", "in", "on", "with", "from",
    "into", "at", "by", "is", "it", "its", "as", "that", "this", "add", "adds",
    "new", "make", "makes", "use", "uses", "fix", "fixes", "up", "out", "off",
    "over", "under", "not", "no", "so", "or", "but", "be", "do", "does"))
#: How many words of a title make a topic. Long enough to carry the subject,
#: short enough that a short query can still match it.
_TOPIC_WORDS = 8


def words(text: str) -> list[str]:
    """Lowercase word tokens, punctuation and separators dropped."""
    cleaned = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return [w for w in cleaned.split() if w]


def branch_topic(branch: str) -> str:
    """The subject a branch names, as words.

    `claude/soft-nestor-seam-ei08dl` is about a soft nestor seam. Strip the
    process prefix and the agent's random suffix, and turn the separators into
    spaces so the matcher sees words rather than one long token.
    """
    if not branch:
        return ""
    low = branch.lower()
    agent = low.startswith(_AGENT_PREFIXES)
    for prefix in _PREFIXES:
        if low.startswith(prefix):
            branch = branch[len(prefix):]
            break
    if agent:
        branch = _SUFFIX.sub("", branch)
    return branch.replace("-", " ").replace("_", " ").replace("/", " ").strip()


def title_topic(title: str) -> str:
    """A findable subject taken from what the change was called when it landed.

    Drop the conventional-commit type, keep the first clause, and cap the length:
    the source is what a search has to match, and a whole sentence matches a
    short query worse than the phrase it is about.
    """
    if not title:
        return ""
    body = _CC_TYPE.sub("", title.strip())
    body = re.split(r"[,;]| — | -- ", body, maxsplit=1)[0]
    return " ".join(words(body)[:_TOPIC_WORDS])


def topic(branch: str, title: str = "") -> str:
    """The findable half of the pair, from whichever half actually names it.

    A branch name is a good proxy for the subject about three times in four. The
    fourth is a branch named for the session rather than the change —
    `llm-only-joke` carried a hash-chain tamper-evidence port, `struck-shot-smote`
    carried an AGENTS.md propagation — and the row was then filed under a topic
    that says nothing about what was decided. The evidence stayed correct and the
    row became unfindable by its own subject, which is a retrieval failure rather
    than a provenance one.

    So the branch is used only when it shares real vocabulary with the title;
    otherwise the title names the topic. Overlap ignores stopwords, because
    agreeing on "the" is not evidence a branch describes anything.
    """
    from_branch = branch_topic(branch)
    if not title:
        return from_branch
    shared = ({w for w in words(from_branch) if w not in _STOP}
              & {w for w in words(title) if w not in _STOP})
    return from_branch if shared else (title_topic(title) or from_branch)

#: `Merge pull request #3 from owner/branch-name`
_PR = re.compile(r"Merge pull request #(\d+) from \S+?/(\S+)")
#: `Merge branch 'master' into feature` — housekeeping. Pulling the trunk into a
#: branch is not a decision about anything; it is keeping a branch current. These
#: carry no PR, no title and no body, so without this they arrive as rows with an
#: empty question. Counted and set aside, like robot merges.
_BACKMERGE = re.compile(r"^Merge branch '[^']+' into ")
#: Record separator — a commit body may contain anything, including blank lines.
_SEP = "\x1e"


def merges(root: pathlib.Path,
           emails: list[str]) -> tuple[list[dict], int, int]:
    """The operator's own merge commits, oldest first.

    Oldest first matters: a topic decided repeatedly is replayed in the order it
    was decided, so the newest proposal is the one left standing and the earlier
    ones become its history rather than overwriting it.

    Returns ``(rows, robot_merges, housekeeping_merges)``.
    """
    who = [f"--author={e}" for e in emails]
    raw = git(root, "log", "--all", "--merges", *who, "--reverse",
              f"--format=%h{_SEP}%an{_SEP}%ae{_SEP}%ad{_SEP}%s{_SEP}%b\x1d",
              "--date=short")
    rows, robots, housekeeping = [], 0, 0
    for record in raw.split("\x1d"):
        if not record.strip():
            continue
        parts = record.lstrip("\n").split(_SEP)
        if len(parts) < 6:
            continue
        sha, author, email, date, subject, body = parts[:6]
        if any(m in subject.lower() or m in body.lower() for m in ROBOT_MARKERS):
            robots += 1
            continue
        if _BACKMERGE.match(subject):
            housekeeping += 1
            continue
        match = _PR.search(subject)
        title = next((ln.strip() for ln in body.splitlines() if ln.strip()), "")
        rows.append({
            "sha": sha, "author": author, "email": email, "date": date,
            "pr": match.group(1) if match else "",
            "branch": match.group(2) if match else "",
            # The proposal: the PR's own title when the merge carries one, else
            # the branch that proposed it. A merge with neither is skipped below
            # rather than filed under an empty question.
            "title": title,
            "subject": subject,
            "body": body.strip(),
        })
    return rows, robots, housekeeping


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--name", default="", help="owner/name; read from the remote if absent")
    ap.add_argument("--email", nargs="*", default=[])
    ap.add_argument("--out", required=True)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    root = pathlib.Path(args.repo).expanduser()
    if not (root / ".git").is_dir():
        print(f"not a checkout: {root}", file=sys.stderr)
        return 2
    name = args.name or repo_name(root)
    emails = args.email or [git(root, "config", "user.email").strip()]
    emails = [e for e in emails if e]
    if not emails:
        print(f"{name}: no author to attribute to (--email, or set user.email)",
              file=sys.stderr)
        return 2

    rows, robots, housekeeping = merges(root, emails)
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    storage.set_store(SqliteStore(str(out)))

    written, revised, skipped = 0, 0, 0
    for r in rows:
        # The pair is *what it was called while it was being proposed* -> *what
        # it became when it landed*. Both halves are quoted from the merge; the
        # question is not reconstructed, because a merge does not record the
        # question it answered and inventing one would be the tool claiming to
        # know something the evidence does not say.
        #
        # An earlier draft used the title for both halves. That maps X to X:
        # asking the title returns the title, and the store learns nothing it
        # could serve. The branch is what makes the row findable by topic.
        question = topic(r["branch"], r["title"]) or r["title"]
        if not question:
            skipped += 1                      # neither a branch nor a title
            continue
        # What shipped, and where to check it. The body beyond its first line is
        # kept in the reason, not the target: the target is what a search should
        # match, and a long rationale buried in it makes every row look alike.
        commitment = r["title"] or r["subject"]
        pr = f"PR #{r['pr']}" if r["pr"] else "merge"
        reason = (f"merged {r['date']} by {r['author']} <{r['email']}>\n"
                  f"{pr}" + (f" · branch {r['branch']}" if r["branch"] else "")
                  + (f"\n{r['body']}" if r["body"] else ""))
        fields = dict(source_lang=DOMAIN, target_lang=TARGET, reason=reason,
                      origin=f"{name}@{r['sha']}:{pr}")
        try:
            memory.add_pair(question, commitment, DOMAIN, TARGET,
                            status="draft", origin=fields["origin"], reason=reason)
            written += 1
        except memory.ConflictingDraftError:
            # The same topic, decided again. That is not a duplicate to drop or
            # a collision to uniquify away — it is a revision, and the store has
            # a verb for it that keeps the earlier proposal as history with its
            # own reason. One long-running branch here carried eighteen merges;
            # flattening those to one row would lose the sequence, and skipping
            # them would lose every decision after the first.
            memory.revise_draft(question, commitment, DOMAIN, TARGET,
                                reason=reason, origin=fields["origin"])
            revised += 1

    # Count what is in the store, not what we believe we put there. `add_pair`
    # returns the stored draft without inserting when the same source AND target
    # already exist — an identical decision merged twice — so counting calls that
    # did not raise over-reported two repositories here by 55 and 6 rows. For a
    # pipeline whose whole claim is that its gaps are not silent, the number it
    # prints has to be the number on disk.
    def counts() -> tuple[int, int]:
        # A repository with no qualifying merge never writes a row, and the store
        # creates its tables on first write — so "nothing to count" and "the
        # count failed" reach here as the same missing table. Zero is the honest
        # answer, and it is not an error: six of this box's twenty-two rungs are
        # repositories the operator committed to but never merged in.
        try:
            con = sqlite3.connect(out)
            try:
                a = con.execute("SELECT COUNT(*) FROM tm_pairs").fetchone()[0]
                b = con.execute("SELECT COUNT(*) FROM tm_pairs WHERE "
                                "superseded_by IS NULL OR superseded_by = ''"
                                ).fetchone()[0]
                return a, b
            finally:
                con.close()
        except sqlite3.OperationalError:
            return 0, 0

    stored, live = counts()
    duplicates = written - live

    if not args.quiet:
        aside = []
        if stored != live:
            aside.append(f"{stored - live} revision(s) kept as history")
        if robots:
            aside.append(f"{robots} robot merge(s)")
        if housekeeping:
            aside.append(f"{housekeeping} back-merge(s)")
        if duplicates:
            aside.append(f"{duplicates} identical to one already recorded")
        if skipped:
            aside.append(f"{skipped} unnamed")
        print(f"  {name:<34} {live:>4} decision(s)"
              + (f" · {', '.join(aside)}" if aside else ""))
        print(f"  {'':34} all drafts — a merge proves a person chose it once, "
              f"not that they would today")
        print(f"  {'':34} store: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
