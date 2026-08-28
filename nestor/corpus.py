"""One non-authoritative corpus lane inside the household Nestor database.

Source stores are extractor outputs, not verified memory.  They are opened
strictly read-only, consolidated without touching ``tm_pairs``, and exposed only
as attributed, authority-free drafting context.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .matcher import StringMatcher

_REQUIRED_SOURCE_COLUMNS = {
    "id",
    "source_text",
    "source_norm",
    "source_lang",
    "target_text",
    "target_lang",
    "status",
    "origin",
    "created_at",
}
_STOPWORDS = {
    "a", "about", "after", "again", "against", "all", "already", "also", "am",
    "an", "and", "any", "are", "as", "at", "be", "because", "been", "before",
    "being", "between", "both", "but", "by", "can", "cannot", "could", "did",
    "do", "does", "each", "explain", "for", "from", "further", "had", "has",
    "have", "having", "he", "her", "here", "hers", "herself", "him", "himself",
    "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just",
    "may", "me", "more", "most", "my", "myself", "no", "nor", "not", "now", "of",
    "off", "on", "once", "one", "only", "or", "other", "our", "ours",
    "ourselves", "out", "over", "own", "same", "she", "should", "so", "some",
    "such", "than", "that", "the", "their", "theirs", "them", "themselves",
    "then", "there", "these", "they", "this", "those", "through", "to", "too",
    "under", "until", "up", "very", "was", "we", "were", "what", "when",
    "where", "which", "while", "who", "why", "will", "with", "without", "would",
    "you", "your", "yours", "yourself", "yourselves",
}
_CORPUS_SCHEMA = """
CREATE TABLE IF NOT EXISTS corpus_snapshots (
    snapshot_sha256 TEXT PRIMARY KEY,
    source_count INTEGER NOT NULL,
    claim_count INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS corpus_claims (
    id TEXT PRIMARY KEY,
    repository TEXT NOT NULL,
    source_pair_id TEXT NOT NULL,
    source_text TEXT NOT NULL,
    source_norm TEXT NOT NULL,
    source_lang TEXT NOT NULL,
    target_text TEXT NOT NULL,
    target_lang TEXT NOT NULL,
    source_status TEXT NOT NULL,
    origin TEXT NOT NULL,
    source_created_at TEXT NOT NULL,
    row_sha256 TEXT NOT NULL,
    comparison_labels TEXT NOT NULL DEFAULT '[]',
    snapshot_sha256 TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_corpus_claims_key
    ON corpus_claims(source_norm, source_lang, target_lang);
CREATE INDEX IF NOT EXISTS idx_corpus_claims_repository
    ON corpus_claims(repository);
CREATE VIRTUAL TABLE IF NOT EXISTS corpus_claims_fts USING fts5(
    claim_id UNINDEXED,
    source_text,
    target_text,
    origin,
    tokenize='unicode61 remove_diacritics 2'
);
"""


class CorpusError(RuntimeError):
    """A corpus source or snapshot could not be read completely and safely."""


@dataclass(frozen=True)
class CorpusClaim:
    id: str
    repository: str
    source_pair_id: str
    source_text: str
    source_norm: str
    source_lang: str
    target_text: str
    target_lang: str
    source_status: str
    origin: str
    row_sha256: str
    comparison_labels: tuple[str, ...]
    matched_terms: tuple[str, ...]
    query_coverage: float
    authority: str = "none"
    score: float = 0.0
    rank: int = 0


@dataclass(frozen=True)
class CorpusSyncReport:
    sources: int
    claims: int
    shared_keys: int
    drift_keys: int
    two_kind_keys: int
    restated_keys: int
    snapshot_sha256: str
    changed: bool


@dataclass(frozen=True)
class CorpusSearchResult:
    mode: str
    query_sha256: str
    snapshot_sha256: str
    candidate_count: int
    eligible_count: int
    claims: tuple[CorpusClaim, ...]
    semantic_error: str = ""


@dataclass(frozen=True)
class CorpusRepository:
    repository: str
    claims: int
    source_langs: tuple[str, ...]
    target_langs: tuple[str, ...]


@dataclass(frozen=True)
class CorpusMap:
    snapshot_sha256: str
    consolidated_at: str
    sources_total: int
    claims_total: int
    repositories: tuple[CorpusRepository, ...]


def _canonical_row(row: dict) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _lexical_tokens(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(
        token for token in re.findall(r"[\w-]+", text.casefold())
        if len(token) > 1 and token not in _STOPWORDS
    ))


def _canonical_term(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and token.endswith(("ches", "shes", "sses", "xes", "zes")):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith(
        ("ss", "us", "is", "ias", "ews")
    ):
        return token[:-1]
    return token


def meaningful_tokens(text: str) -> tuple[str, ...]:
    """Distinct lexical terms useful for retrieval rather than sentence glue."""
    return tuple(dict.fromkeys(_canonical_term(token) for token in _lexical_tokens(text)))


def _read_source(path: Path) -> list[dict]:
    wal = path.with_name(path.name + "-wal")
    if wal.exists() and wal.stat().st_size:
        raise CorpusError(
            f"{path.name}: source has an active WAL; checkpoint/close its writer "
            "before taking an immutable snapshot"
        )
    try:
        conn = sqlite3.connect(
            f"{path.resolve().as_uri()}?mode=ro&immutable=1", uri=True
        )
    except sqlite3.Error as exc:
        raise CorpusError(f"{path.name}: could not open read-only: {exc}") from exc
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only=ON")
        columns = {
            str(row["name"]) for row in conn.execute("PRAGMA table_info(tm_pairs)")
        }
        missing = sorted(_REQUIRED_SOURCE_COLUMNS - columns)
        if missing:
            raise CorpusError(
                f"{path.name}: tm_pairs is missing required columns: {', '.join(missing)}"
            )
        if "superseded_by" in columns:
            rows = conn.execute(
                "SELECT created_at, id, origin, source_lang, source_norm, "
                "source_text, status, target_lang, target_text FROM tm_pairs "
                "WHERE superseded_by = ''"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT created_at, id, origin, source_lang, source_norm, "
                "source_text, status, target_lang, target_text FROM tm_pairs"
            ).fetchall()
        repository = path.stem
        out = []
        for raw in rows:
            source = {key: str(raw[key] or "") for key in _REQUIRED_SOURCE_COLUMNS}
            row_sha = _digest(_canonical_row(source))
            claim_id = _digest(f"{repository}\0{source['id']}")
            out.append({
                "id": claim_id,
                "repository": repository,
                "source_pair_id": source["id"],
                "source_text": source["source_text"],
                "source_norm": source["source_norm"],
                "source_lang": source["source_lang"],
                "target_text": source["target_text"],
                "target_lang": source["target_lang"],
                "source_status": source["status"],
                "origin": source["origin"],
                "source_created_at": source["created_at"],
                "row_sha256": row_sha,
            })
        return out
    except sqlite3.DatabaseError as exc:
        raise CorpusError(f"{path.name}: unreadable corpus database: {exc}") from exc
    finally:
        conn.close()


def _comparison_labels(claims: list[dict]) -> tuple[dict[str, set[str]], dict[str, int]]:
    matcher = StringMatcher()
    by_key: dict[str, list[dict]] = defaultdict(list)
    for claim in claims:
        key = matcher.normalize(claim["source_text"])
        claim["source_norm"] = key
        by_key[key].append(claim)

    labels: dict[str, set[str]] = defaultdict(set)
    counts = {"shared": 0, "drift": 0, "two kinds": 0, "restated": 0}
    for group in by_key.values():
        if len({claim["repository"] for claim in group}) < 2:
            continue
        counts["shared"] += 1
        by_kind: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for claim in group:
            by_kind[(claim["source_lang"], claim["target_lang"])].append(claim)
        if len(by_kind) > 1:
            counts["two kinds"] += 1
            for claim in group:
                labels[claim["id"]].add("two kinds")
        for same_kind in by_kind.values():
            if len({claim["repository"] for claim in same_kind}) < 2:
                continue
            targets = {matcher.normalize(claim["target_text"]) for claim in same_kind}
            label = "drift" if len(targets) > 1 else "restated"
            counts[label] += 1
            for claim in same_kind:
                labels[claim["id"]].add(label)
    return labels, counts


def sync(source_dir: str | Path, household_db: str | Path) -> CorpusSyncReport:
    """Consolidate every source DB into one inert corpus snapshot transactionally."""
    source_dir = Path(source_dir).expanduser().resolve()
    household_db = Path(household_db).expanduser().resolve()
    if not source_dir.is_dir():
        raise CorpusError(f"{source_dir}: corpus source directory is missing")
    paths = sorted(
        path for path in source_dir.glob("*.db")
        if path.resolve() != household_db
    )
    if not paths:
        raise CorpusError(f"{source_dir}: no corpus source databases")

    claims: list[dict] = []
    seen_ids: set[str] = set()
    for path in paths:
        for claim in _read_source(path):
            if claim["id"] in seen_ids:
                raise CorpusError(
                    f"{path.name}: duplicate corpus claim identity {claim['id']}"
                )
            seen_ids.add(claim["id"])
            claims.append(claim)
    labels, counts = _comparison_labels(claims)
    ordered = sorted(claims, key=lambda claim: claim["id"])
    snapshot = _digest(_canonical_row({"sources": [p.name for p in paths], "claims": ordered}))

    def report(changed: bool) -> CorpusSyncReport:
        return CorpusSyncReport(
            sources=len(paths),
            claims=len(ordered),
            shared_keys=counts["shared"],
            drift_keys=counts["drift"],
            two_kind_keys=counts["two kinds"],
            restated_keys=counts["restated"],
            snapshot_sha256=snapshot,
            changed=changed,
        )

    household_db.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = sqlite3.connect(household_db)
        conn.execute("PRAGMA busy_timeout=5000")
        conn.executescript(_CORPUS_SCHEMA)
        current = conn.execute(
            "SELECT snapshot_sha256 FROM corpus_snapshots LIMIT 1"
        ).fetchone()
        if current is not None and str(current[0]) == snapshot:
            return report(False)
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM corpus_claims_fts")
        conn.execute("DELETE FROM corpus_claims")
        conn.execute("DELETE FROM corpus_snapshots")
        conn.execute(
            "INSERT INTO corpus_snapshots(snapshot_sha256, source_count, claim_count) "
            "VALUES (?, ?, ?)",
            (snapshot, len(paths), len(ordered)),
        )
        for claim in ordered:
            comparison = json.dumps(sorted(labels.get(claim["id"], set())))
            conn.execute(
                "INSERT INTO corpus_claims("
                "id, repository, source_pair_id, source_text, source_norm, "
                "source_lang, target_text, target_lang, source_status, origin, "
                "source_created_at, row_sha256, comparison_labels, snapshot_sha256"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    claim["id"], claim["repository"], claim["source_pair_id"],
                    claim["source_text"], claim["source_norm"], claim["source_lang"],
                    claim["target_text"], claim["target_lang"], claim["source_status"],
                    claim["origin"], claim["source_created_at"], claim["row_sha256"],
                    comparison, snapshot,
                ),
            )
            conn.execute(
                "INSERT INTO corpus_claims_fts("
                "claim_id, source_text, target_text, origin) VALUES (?, ?, ?, ?)",
                (
                    claim["id"], claim["source_text"], claim["target_text"],
                    claim["origin"],
                ),
            )
        conn.commit()
    except sqlite3.DatabaseError as exc:
        if "conn" in locals():
            conn.rollback()
        raise CorpusError(f"{household_db}: could not install corpus snapshot: {exc}") from exc
    finally:
        if "conn" in locals():
            conn.close()

    return report(True)


class CorpusRetriever:
    """Read-only ranked access to the consolidated corpus lane."""

    def __init__(
        self,
        household_db: str | Path,
        *,
        semantic: bool = False,
        embedder: Callable[[str], tuple[float, ...]] | None = None,
    ):
        self.path = Path(household_db).expanduser().resolve()
        self.semantic = semantic
        self._embedder = embedder
        self._embedding_cache: dict[str, tuple[float, ...]] = {}

    def _connect(self) -> sqlite3.Connection:
        try:
            conn = sqlite3.connect(f"{self.path.as_uri()}?mode=ro", uri=True)
        except sqlite3.Error as exc:
            raise CorpusError(f"{self.path}: corpus snapshot is unavailable: {exc}") from exc
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        return conn

    def count(self) -> int:
        try:
            with self._connect() as conn:
                return int(conn.execute("SELECT COUNT(*) FROM corpus_claims").fetchone()[0])
        except sqlite3.DatabaseError as exc:
            raise CorpusError(f"{self.path}: no consolidated corpus: {exc}") from exc

    def repositories(self) -> CorpusMap:
        """Per-repository counts and language sets, plus the snapshot row.

        The taxonomy `nestor_corpus_search`'s `repository` argument is checked
        against. Names come from the same ``corpus_claims.repository`` column
        the retriever reads, so a name published here is a name the store will
        accept — and one absent here is refused with the whole list, not a
        silent zero.
        """
        try:
            with self._connect() as conn:
                snapshot_row = conn.execute(
                    "SELECT snapshot_sha256, source_count, claim_count, created_at "
                    "FROM corpus_snapshots ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
                count_rows = conn.execute(
                    "SELECT repository, COUNT(*) AS claims "
                    "FROM corpus_claims GROUP BY repository ORDER BY repository"
                ).fetchall()
                # Fetch (repository, source_lang, target_lang) tuples and
                # dedupe in Python rather than GROUP_CONCAT-then-split-on-
                # comma. A source_lang value that ever contained a comma
                # would fracture into bogus tokens with no error under the
                # split approach; this path is faithful to whatever the
                # extractor wrote, and the row count is bounded by the
                # cross product of repositories and language tags — trivial.
                lang_rows = conn.execute(
                    "SELECT DISTINCT repository, source_lang, target_lang "
                    "FROM corpus_claims"
                ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise CorpusError(f"{self.path}: no consolidated corpus: {exc}") from exc
        if snapshot_row is None:
            raise CorpusError(f"{self.path}: no consolidated corpus snapshot")
        source_langs_by_repo: dict[str, set[str]] = defaultdict(set)
        target_langs_by_repo: dict[str, set[str]] = defaultdict(set)
        for lang_row in lang_rows:
            source_langs_by_repo[str(lang_row["repository"])].add(
                str(lang_row["source_lang"]))
            target_langs_by_repo[str(lang_row["repository"])].add(
                str(lang_row["target_lang"]))
        repositories = tuple(
            CorpusRepository(
                repository=str(row["repository"]),
                claims=int(row["claims"]),
                source_langs=tuple(sorted(source_langs_by_repo[str(row["repository"])])),
                target_langs=tuple(sorted(target_langs_by_repo[str(row["repository"])])),
            )
            for row in count_rows
        )
        return CorpusMap(
            snapshot_sha256=str(snapshot_row["snapshot_sha256"]),
            consolidated_at=str(snapshot_row["created_at"]),
            sources_total=int(snapshot_row["source_count"]),
            claims_total=int(snapshot_row["claim_count"]),
            repositories=repositories,
        )

    @staticmethod
    def _tokens(text: str) -> tuple[str, ...]:
        return meaningful_tokens(text)

    @classmethod
    def _query(cls, text: str) -> str:
        return " OR ".join(
            f'"{token.replace(chr(34), chr(34) * 2)}"'
            for token in _lexical_tokens(text)
        )

    @staticmethod
    def _public_origin(origin: str, repository: str) -> str:
        normalized = origin.replace("\\", "/")
        if normalized.startswith("/") or re.search(
            r"(?:^|/)(?:home|Users)/[^/]+/", normalized
        ):
            return f"{repository}:{normalized.rsplit('/', 1)[-1]}"
        return origin

    @staticmethod
    def _claim(
        row: sqlite3.Row,
        *,
        score: float,
        rank: int,
        matched_terms: tuple[str, ...],
        query_token_count: int,
    ) -> CorpusClaim:
        return CorpusClaim(
            id=str(row["id"]),
            repository=str(row["repository"]),
            source_pair_id=str(row["source_pair_id"]),
            source_text=str(row["source_text"]),
            source_norm=str(row["source_norm"]),
            source_lang=str(row["source_lang"]),
            target_text=str(row["target_text"]),
            target_lang=str(row["target_lang"]),
            source_status=str(row["source_status"]),
            origin=CorpusRetriever._public_origin(
                str(row["origin"]), str(row["repository"])
            ),
            row_sha256=str(row["row_sha256"]),
            comparison_labels=tuple(json.loads(row["comparison_labels"])),
            matched_terms=matched_terms,
            query_coverage=round(len(matched_terms) / query_token_count, 4),
            score=score,
            rank=rank,
        )

    @staticmethod
    def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = sum(value * value for value in left) ** 0.5
        right_norm = sum(value * value for value in right) ** 0.5
        if not left_norm or not right_norm:
            return 0.0
        return dot / (left_norm * right_norm)

    def _embed(self, text: str) -> tuple[float, ...]:
        key = _digest(text)
        if key not in self._embedding_cache:
            if self._embedder is None:
                from .ollama_embed import embed_one

                self._embedder = embed_one
            self._embedding_cache[key] = tuple(self._embedder(text))
        return self._embedding_cache[key]

    def search(self, task: str, *, limit: int = 8, shortlist: int = 50,
               repository: str | None = None) -> CorpusSearchResult:
        query = self._query(str(task))
        query_sha = _digest(str(task))
        if not query or limit <= 0:
            return CorpusSearchResult("fts", query_sha, "", 0, 0, ())
        # A repository filter narrows the FTS-join in SQL rather than trimming
        # after: the shortlist could otherwise be dominated by other repos and
        # drop rows the caller asked for. It also skips the per-repo cap below,
        # since the caller already scoped and the cap is a diversifier.
        sql = (
            "SELECT c.*, bm25(corpus_claims_fts, 0.0, 5.0, 2.0, 0.5) AS rank_score "
            "FROM corpus_claims_fts "
            "JOIN corpus_claims c ON c.id = corpus_claims_fts.claim_id "
            "WHERE corpus_claims_fts MATCH ?"
        )
        params: list[object] = [query]
        if repository:
            sql += " AND c.repository = ?"
            params.append(repository)
        sql += " ORDER BY rank_score, c.repository, c.id LIMIT ?"
        params.append(max(limit, shortlist))
        try:
            with self._connect() as conn:
                snapshot_row = conn.execute(
                    "SELECT snapshot_sha256 FROM corpus_snapshots LIMIT 1"
                ).fetchone()
                if snapshot_row is None:
                    raise CorpusError(f"{self.path}: no consolidated corpus snapshot")
                rows = conn.execute(sql, tuple(params)).fetchall()
        except sqlite3.DatabaseError as exc:
            raise CorpusError(f"{self.path}: corpus retrieval failed: {exc}") from exc

        query_tokens = set(self._tokens(str(task)))
        minimum_matches = 2 if len(query_tokens) >= 4 else 1
        eligible = []
        for row in rows:
            candidate_tokens = set(self._tokens(
                f"{row['source_text']} {row['target_text']} {row['origin']}"
            ))
            matched_terms = tuple(sorted(query_tokens & candidate_tokens))
            if len(matched_terms) >= minimum_matches:
                eligible.append((row, matched_terms))

        mode = "fts"
        semantic_error = ""
        ranked = [
            (row, matched_terms, -float(row["rank_score"]))
            for row, matched_terms in eligible
        ]
        ranked.sort(
            key=lambda item: (
                -len(item[1]),
                -item[2],
                item[0]["repository"],
                item[0]["id"],
            )
        )
        if self.semantic and ranked:
            try:
                query_vector = self._embed(str(task))
                ranked = [
                    (
                        row,
                        matched_terms,
                        self._cosine(
                            query_vector,
                            self._embed(
                                f"{row['source_text']}\n{row['target_text']}"
                            ),
                        ),
                    )
                    for row, matched_terms, _lexical_score in ranked
                ]
                ranked.sort(
                    key=lambda item: (
                        -len(item[1]),
                        -item[2],
                        item[0]["repository"],
                        item[0]["id"],
                    )
                )
                mode = "fts+semantic"
            except (OSError, RuntimeError, ValueError) as exc:
                semantic_error = f"{type(exc).__name__}: {exc}"

        selected: list[CorpusClaim] = []
        seen: set[tuple[str, str, str, str]] = set()
        per_repo: dict[str, int] = defaultdict(int)
        matcher = StringMatcher()
        # The per-repo cap is a diversifier for the cross-corpus search; when
        # the caller has scoped to one repository it becomes an arbitrary cap
        # of 2 on that one repo, which is not what a scoped call asked for.
        per_repo_cap = None if repository else 2
        for row, matched_terms, score in ranked:
            key = (
                str(row["source_norm"]),
                matcher.normalize(str(row["target_text"])),
                str(row["source_lang"]),
                str(row["target_lang"]),
            )
            row_repository = str(row["repository"])
            if key in seen:
                continue
            if per_repo_cap is not None and per_repo[row_repository] >= per_repo_cap:
                continue
            seen.add(key)
            per_repo[row_repository] += 1
            selected.append(
                self._claim(row, score=round(score, 6),
                            rank=len(selected) + 1,
                            matched_terms=matched_terms,
                            query_token_count=len(query_tokens))
            )
            if len(selected) >= limit:
                break
        return CorpusSearchResult(
            mode=mode,
            query_sha256=query_sha,
            snapshot_sha256=str(snapshot_row["snapshot_sha256"]),
            candidate_count=len(rows),
            eligible_count=len(eligible),
            claims=tuple(selected),
            semantic_error=semantic_error,
        )
