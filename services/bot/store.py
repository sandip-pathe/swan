"""Separate bot storage: short transactions, WAL and bounded history."""

import json
import sqlite3
from contextlib import contextmanager
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
            db.execute("DELETE FROM insights WHERE id NOT IN "
                       "(SELECT id FROM insights ORDER BY created_at DESC, id DESC LIMIT 300)")
            db.execute("DELETE FROM evidence WHERE insight_id NOT IN (SELECT id FROM insights)")
        return bool(inserted)

    def evidence(self, insight_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM evidence WHERE insight_id=?", (insight_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def insights(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM insights ORDER BY created_at DESC, id DESC "
                              "LIMIT 30").fetchall()
        return [json.loads(row[0]) for row in rows]
