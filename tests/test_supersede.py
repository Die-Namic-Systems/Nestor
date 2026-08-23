"""Lineage (docs/decision-memory.md, build-order steps 1-2).

The cases here were proven first in the SAFE store's playground build
(apps/aristarchus, its test_decision_memory.py) and ported to Nestor's API —
supersede keeps the predecessor, one-live-row stays a database constraint, a
failed supersede restores the store, and reopen_when tells never from
not-yet. Plus the migration case aristarchus never needed: a database
written before lineage existed must come up to date without losing a row.
"""
from __future__ import annotations

import sqlite3

import pytest

from nestor import cascade, memory, storage
from nestor.sqlite_store import SqliteStore
from nestor.storage import supports_lineage


@pytest.fixture()
def store(tmp_path, seal_key):
    cascade.set_ledger_path(tmp_path / "ledger.jsonl")
    s = SqliteStore(":memory:")
    s.init_db()
    s.memory_init()
    storage.set_store(s)
    yield s
    s.close()


def _seal(store, src="the catalog lives at the root", tgt="root catalog.json",
          verifier="rita", reason=""):
    return memory.add_pair(src, tgt, "en", "es", status="sealed",
                           verifier=verifier, reason=reason, store=store)


# -- the capability -------------------------------------------------------

class TestCapability:
    def test_sqlite_store_supports_lineage(self, store):
        assert supports_lineage(store)

    def test_partial_support_counts_as_none(self, store):
        class Partial:
            memory_mark_superseded = staticmethod(lambda *a: None)
        assert not supports_lineage(Partial())

    def test_supersede_refuses_without_capability(self, store, monkeypatch):
        _seal(store)
        monkeypatch.delattr(SqliteStore, "memory_lineage")
        with pytest.raises(RuntimeError, match="lineage"):
            memory.supersede_pair("the catalog lives at the root",
                                  "elsewhere", "en", "es",
                                  verifier="loki", store=store)


# -- modified: supersede keeps the lineage --------------------------------

class TestSupersede:
    def test_supersede_keeps_the_predecessor(self, store):
        old = _seal(store, reason="simplest thing that works")
        new = memory.supersede_pair(
            "the catalog lives at the root", ".willow/store/catalog.json",
            "en", "es", verifier="loki",
            reason="rule 9: the catalog lives in .willow/store/", store=store)
        # The live row is the successor...
        live = store.memory_find(old["source_norm"], "en", "es")
        assert live["id"] == new["id"]
        assert live["reason"].startswith("rule 9")
        # ...and the predecessor is intact history, reason and verifier and
        # signature included, pointing at what replaced it.
        chain = store.memory_lineage(new["id"])
        assert [r["id"] for r in chain] == [old["id"]]
        assert chain[0]["target_text"] == "root catalog.json"
        assert chain[0]["reason"] == "simplest thing that works"
        assert chain[0]["verifier"] == "rita"
        assert chain[0]["seal_sig"] == old["seal_sig"]
        assert chain[0]["superseded_by"] == new["id"]

    def test_chain_of_three(self, store):
        a = _seal(store, src="threshold", tgt="0.80", reason="first guess")
        b = memory.supersede_pair("threshold", "0.92", "en", "es",
                                  verifier="rita", reason="benched",
                                  store=store)
        c = memory.supersede_pair("threshold", "0.90", "en", "es",
                                  verifier="rita", reason="recall fell",
                                  store=store)
        chain = store.memory_lineage(c["id"])
        assert [r["id"] for r in chain] == [b["id"], a["id"]]

    def test_lookup_serves_successor_never_history(self, store):
        _seal(store, src="hello", tgt="hola")
        new = memory.supersede_pair("hello", "buenos dias", "en", "es",
                                    verifier="loki", store=store)
        got = memory.lookup("hello", "en", "es", store=store)
        assert got, "lookup returned nothing"
        pairs = [m["pair"] for m in got]
        assert pairs[0]["id"] == new["id"]
        assert pairs[0]["target_text"] == "buenos dias"
        # History is not even a lower-ranked candidate — it is absent.
        assert all(p["id"] != "old" and not p.get("superseded_by")
                   for p in pairs)

    def test_one_live_row_is_still_a_database_constraint(self, store):
        _seal(store, src="hello", tgt="hola")
        memory.supersede_pair("hello", "buenos dias", "en", "es",
                              verifier="loki", store=store)
        # History shares the key; a THIRD live row is refused by the partial
        # index itself, guards or no guards.
        row = {"id": "x", "source_text": "hello",
               "source_norm": memory._norm("hello"), "source_lang": "en",
               "target_text": "another", "target_lang": "es", "status": "sealed",
               "verifier": "", "weight": 1.0, "origin": "", "created_at": "now",
               "seal_sig": ""}
        with pytest.raises(sqlite3.IntegrityError):
            store.memory_insert(row)

    def test_failed_supersede_restores_the_store(self, store, monkeypatch):
        old = _seal(store, src="hello", tgt="hola")
        monkeypatch.setattr(store, "memory_insert",
                            lambda pair: (_ for _ in ()).throw(
                                sqlite3.OperationalError("disk full")))
        with pytest.raises(sqlite3.OperationalError):
            memory.supersede_pair("hello", "buenos dias", "en", "es",
                                  verifier="loki", store=store)
        monkeypatch.undo()
        live = store.memory_find(old["source_norm"], "en", "es")
        assert live is not None and live["id"] == old["id"]
        assert live["superseded_by"] == ""

    def test_refusals(self, store):
        with pytest.raises(ValueError, match="nothing to supersede"):
            memory.supersede_pair("never sealed", "x", "en", "es",
                                  verifier="loki", store=store)
        _seal(store, src="hello", tgt="hola")
        with pytest.raises(ValueError, match="verifier"):
            memory.supersede_pair("hello", "salut", "en", "es",
                                  verifier="", store=store)
        with pytest.raises(ValueError, match="nothing to supersede"):
            memory.supersede_pair("hello", "hola", "en", "es",
                                  verifier="loki", store=store)
        memory.add_pair("draft source", "draft target", "en", "es",
                        store=store)
        with pytest.raises(ValueError, match="draft"):
            memory.supersede_pair("draft source", "other", "en", "es",
                                  verifier="loki", store=store)
        memory.reject_pair(_seal(store, src="bad", tgt="worse")["id"],
                           verifier="rita", reason="wrong", store=store)
        with pytest.raises(memory.RejectedPairError):
            memory.supersede_pair("bad", "better", "en", "es",
                                  verifier="loki", store=store)

    def test_supersede_is_ledgered(self, store, tmp_path):
        _seal(store, src="hello", tgt="hola")
        memory.supersede_pair("hello", "buenos dias", "en", "es",
                              verifier="loki", reason="corrected",
                              store=store)
        import json
        kinds = [json.loads(ln)["kind"] for ln in
                 (tmp_path / "ledger.jsonl").read_text().splitlines()]
        assert "supersede" in kinds
        entry = next(json.loads(ln) for ln in
                     (tmp_path / "ledger.jsonl").read_text().splitlines()
                     if json.loads(ln)["kind"] == "supersede")
        assert entry["replaced_verifier"] == "rita"
        assert entry["verifier"] == "loki"
        assert entry["same_verifier"] is False


# -- N4: reason-for-yes ---------------------------------------------------

class TestReason:
    def test_reason_stored_on_insert(self, store):
        p = _seal(store, reason="the why behind the yes")
        assert store.memory_find(p["source_norm"], "en", "es")["reason"] == \
            "the why behind the yes"

    def test_reason_survives_draft_upgrade(self, store):
        memory.add_pair("hello", "hola", "en", "es", store=store)  # draft
        memory.add_pair("hello", "hola", "en", "es", status="sealed",
                        verifier="rita", reason="checked against corpus",
                        store=store)
        row = store.memory_find(memory._norm("hello"), "en", "es")
        assert row["status"] == "sealed"
        assert row["reason"] == "checked against corpus"

    def test_store_without_set_reason_refuses_rather_than_drops(self, store,
                                                                monkeypatch):
        memory.add_pair("hello", "hola", "en", "es", store=store)
        monkeypatch.delattr(SqliteStore, "memory_set_reason")
        with pytest.raises(RuntimeError, match="memory_set_reason"):
            memory.add_pair("hello", "hola", "en", "es", status="sealed",
                            verifier="rita", reason="would be lost",
                            store=store)


# -- N5: never vs not-yet -------------------------------------------------

class TestReopenWhen:
    def test_reopen_when_stored_and_read_back(self, store):
        p = _seal(store, src="hello", tgt="hola")
        memory.reject_match("hello", "en", "es", pair_id=p["id"],
                            verifier="rita", reason="wrong register",
                            reopen_when="a formal-register corpus exists",
                            store=store)
        rejs = store.memory_rejections(memory._norm("hello"), "en", "es")
        assert rejs[0]["reopen_when"] == "a formal-register corpus exists"

    def test_default_stays_never(self, store):
        p = _seal(store, src="hello", tgt="hola")
        memory.reject_match("hello", "en", "es", pair_id=p["id"],
                            verifier="rita", reason="just wrong", store=store)
        rejs = store.memory_rejections(memory._norm("hello"), "en", "es")
        assert rejs[0]["reopen_when"] == ""


# -- migration: a pre-lineage database comes up to date -------------------

class TestMigration:
    def _old_schema_db(self, path):
        """A database exactly as the pre-lineage build wrote it: 12-column
        tm_pairs, 10-column tm_rejections, FULL unique index."""
        conn = sqlite3.connect(path)
        conn.executescript("""
            CREATE TABLE tm_pairs (
                id TEXT PRIMARY KEY, source_text TEXT NOT NULL,
                source_norm TEXT NOT NULL, source_lang TEXT NOT NULL,
                target_text TEXT NOT NULL, target_lang TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                verifier TEXT NOT NULL DEFAULT '',
                weight REAL NOT NULL DEFAULT 1.0,
                origin TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
                seal_sig TEXT NOT NULL DEFAULT '');
            CREATE TABLE tm_rejections (
                id TEXT PRIMARY KEY, query_norm TEXT NOT NULL,
                source_lang TEXT NOT NULL, target_lang TEXT NOT NULL,
                pair_id TEXT NOT NULL DEFAULT '',
                target_text TEXT NOT NULL DEFAULT '',
                verifier TEXT NOT NULL DEFAULT '',
                reason TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
                reject_sig TEXT NOT NULL DEFAULT '');
            CREATE UNIQUE INDEX idx_tm_pairs_key
                ON tm_pairs(source_norm, source_lang, target_lang);
            INSERT INTO tm_pairs VALUES ('old-1', 'hello', 'hello', 'en',
                'hola', 'es', 'sealed', 'rita', 1.0, '', 'then', 'sig');
        """)
        conn.commit()
        conn.close()

    def test_pre_lineage_db_migrates_without_losing_rows(self, tmp_path,
                                                         seal_key):
        db = str(tmp_path / "old.db")
        self._old_schema_db(db)
        cascade.set_ledger_path(tmp_path / "ledger.jsonl")
        store = SqliteStore(db)
        store.memory_init()          # the migration
        try:
            row = store.memory_find("hello", "en", "es")
            assert row is not None and row["id"] == "old-1"   # nothing lost
            assert row["reason"] == "" and row["superseded_by"] == ""
            with store._db() as conn:
                names = {r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' "
                    "AND tbl_name='tm_pairs'")}
            assert "idx_tm_pairs_key" not in names      # full index dropped
            assert "idx_tm_pairs_key_live" in names     # partial in place
            # And the migrated row is genuinely supersedable.
            new = memory.supersede_pair("hello", "buenos dias", "en", "es",
                                        verifier="loki", store=store)
            assert [r["id"] for r in store.memory_lineage(new["id"])] == \
                ["old-1"]
        finally:
            store.close()


# -- export: history does not travel --------------------------------------

class TestExport:
    def test_superseded_rows_stay_home(self, store):
        from nestor import portable
        _seal(store, src="hello", tgt="hola")
        new = memory.supersede_pair("hello", "buenos dias", "en", "es",
                                    verifier="loki", store=store)
        bundle = portable.export_bundle(store=store)
        ids = [p["id"] for p in bundle["pairs"]]
        assert new["id"] in ids
        assert len([p for p in bundle["pairs"]
                    if p["source_norm"] == memory._norm("hello")]) == 1
