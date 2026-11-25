"""Separate bot storage: short transactions, WAL and bounded history."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path


class Store:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS documents (
                    key TEXT PRIMARY KEY, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS insights (
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evidence (
                    insight_id TEXT PRIMARY KEY, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS insight_feed (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, insight_id TEXT UNIQUE NOT NULL
                );
                CREATE TABLE IF NOT EXISTS stars (
                    owner TEXT NOT NULL, insight_id TEXT NOT NULL,
                    PRIMARY KEY(owner, insight_id)
                );
                INSERT OR IGNORE INTO insight_feed(insight_id)
                    SELECT id FROM insights WHERE id NOT IN
                        (SELECT insight_id FROM insight_feed) ORDER BY created_at, id;
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=3)
        try:
            with db:
                yield db
        finally:
            db.close()

    def read(self, key: str, default=None):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM documents WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def write(self, key: str, value) -> None:
        with self.connect() as db:
            db.execute("INSERT INTO documents VALUES (?,?) ON CONFLICT(key) DO UPDATE "
                       "SET payload=excluded.payload", (key, json.dumps(value)))

    def publish(self, insight: dict) -> bool:
        value = dict(insight)
        snapshot = value.pop("source_snapshot", None)
        with self.connect() as db:
            inserted = db.execute("INSERT OR IGNORE INTO insights VALUES (?,?,?)",
                                  (value["id"], value["as_of"], json.dumps(value))).rowcount
            if inserted and snapshot:
                db.execute("INSERT INTO evidence VALUES (?,?)", (value["id"], json.dumps(snapshot)))
            if inserted:
                db.execute("INSERT INTO insight_feed(insight_id) VALUES (?)", (value["id"],))
        self.prune()
        return bool(inserted)

    def prune(self) -> None:
        cutoff = (datetime.now(UTC) - timedelta(days=7)).isoformat()
        with self.connect() as db:
            db.execute("DELETE FROM insights WHERE id NOT IN (SELECT insight_id FROM stars) "
                       "AND (julianday(created_at) < julianday(?) OR id NOT IN "
                       "(SELECT id FROM insights ORDER BY created_at DESC, id DESC LIMIT 1000))",
                       (cutoff,))
            db.execute("DELETE FROM evidence WHERE insight_id NOT IN (SELECT id FROM insights)")
            db.execute("DELETE FROM insight_feed WHERE insight_id NOT IN (SELECT id FROM insights)")
            db.execute("DELETE FROM documents WHERE key LIKE 'explanation:%' AND "
                       "json_extract(payload, '$.day') != ?", (datetime.now(UTC).date().isoformat(),))

    def changes(self, after: int) -> dict:
        with self.connect() as db:
            latest = db.execute("SELECT seq FROM sqlite_sequence WHERE name='insight_feed'").fetchone()
            latest = latest[0] if latest else 0
            rows = db.execute("SELECT f.sequence, i.payload FROM insight_feed f JOIN insights i "
                              "ON i.id=f.insight_id WHERE f.sequence>? ORDER BY f.sequence LIMIT 101",
                              (after,)).fetchall()
        page = rows[:100]
        return {"insights": [json.loads(row[1]) for row in page],
                "cursor": page[-1][0] if len(rows) > 100 else latest,
                "has_more": len(rows) > 100,
                "retention_days": 7, "server_reset": after > latest}

    def saved(self, owner: str) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT i.payload FROM insights i JOIN stars s ON i.id=s.insight_id "
                              "WHERE s.owner=? ORDER BY i.created_at DESC", (owner,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def star(self, owner: str, insight_id: str, starred: bool) -> bool:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM insights WHERE id=?", (insight_id,)).fetchone():
                return False
            if starred:
                count = db.execute("SELECT count(*) FROM stars WHERE owner=?", (owner,)).fetchone()[0]
                exists = db.execute("SELECT 1 FROM stars WHERE owner=? AND insight_id=?",
                                    (owner, insight_id)).fetchone()
                if count >= 200 and not exists:
                    raise ValueError("SAVED_INSIGHT_LIMIT")
                db.execute("INSERT OR IGNORE INTO stars VALUES (?,?)", (owner, insight_id))
            else:
                db.execute("DELETE FROM stars WHERE owner=? AND insight_id=?", (owner, insight_id))
        self.prune()
        return True

    def evidence(self, insight_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM evidence WHERE insight_id=?", (insight_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def insights(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM insights ORDER BY created_at DESC, id DESC "
                              "LIMIT 30").fetchall()
        return [json.loads(row[0]) for row in rows]
