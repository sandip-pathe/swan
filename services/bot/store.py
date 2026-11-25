"""Separate bot storage: short transactions, WAL and bounded history."""

import json
import os
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
                CREATE TABLE IF NOT EXISTS idea_revisions (
                    idea_id TEXT NOT NULL, revision INTEGER NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(idea_id, revision)
                );
                CREATE TABLE IF NOT EXISTS research_jobs (
                    id TEXT PRIMARY KEY, idea_id TEXT NOT NULL, revision INTEGER NOT NULL,
                    state TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS research_pending ON research_jobs(state, created_at);
                CREATE TABLE IF NOT EXISTS reported_entries (
                    owner TEXT NOT NULL, idea_id TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(owner, idea_id)
                );
                CREATE TABLE IF NOT EXISTS evaluations (
                    idea_id TEXT PRIMARY KEY, payload TEXT NOT NULL
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
            db.execute(
                "INSERT INTO documents VALUES (?,?) ON CONFLICT(key) DO UPDATE "
                "SET payload=excluded.payload",
                (key, json.dumps(value)),
            )

    def publish(self, insight: dict) -> bool:
        value = dict(insight)
        snapshot = value.pop("source_snapshot", None)
        with self.connect() as db:
            inserted = db.execute(
                "INSERT OR IGNORE INTO insights VALUES (?,?,?)",
                (value["id"], value["as_of"], json.dumps(value)),
            ).rowcount
            if inserted and snapshot:
                db.execute("INSERT INTO evidence VALUES (?,?)", (value["id"], json.dumps(snapshot)))
            if inserted:
                db.execute("INSERT INTO insight_feed(insight_id) VALUES (?)", (value["id"],))
        self.prune()
        return bool(inserted)

    def idea(self, identifier: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM insights WHERE id=?", (identifier,)).fetchone()
        return json.loads(row[0]) if row else None

    def ideas(self, limit: int = 100) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT payload FROM insights WHERE json_extract(payload,'$.kind')='idea' "
                "ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def revise(self, value: dict, expected: int, snapshot: dict | None = None) -> bool:
        from services.bot.contracts import Idea

        idea = Idea.model_validate(value).model_dump(mode="json")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT payload FROM insights WHERE id=?", (idea["id"],)).fetchone()
            revision = json.loads(prior[0]).get("revision", 0) if prior else 0
            if revision != expected or idea["revision"] != expected + 1:
                return False
            db.execute(
                "INSERT INTO insights VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET "
                "payload=excluded.payload",
                (idea["id"], idea["as_of"], json.dumps(idea)),
            )
            db.execute(
                "INSERT INTO idea_revisions VALUES (?,?,?)",
                (idea["id"], idea["revision"], json.dumps(idea)),
            )
            prior_state = json.loads(prior[0]).get("state") if prior else None
            if idea["state"] in {"eligible", "invalidated"} and prior_state != idea["state"]:
                db.execute(
                    "INSERT INTO documents VALUES (?,?) ON CONFLICT(key) DO UPDATE SET payload=excluded.payload",
                    ("notification:" + idea["id"], json.dumps(idea)),
                )
            # Reinsert into the monotonic feed atomically: existing clients receive revisions.
            db.execute("DELETE FROM insight_feed WHERE insight_id=?", (idea["id"],))
            db.execute("INSERT INTO insight_feed(insight_id) VALUES (?)", (idea["id"],))
            if snapshot:
                db.execute(
                    "INSERT INTO evidence VALUES (?,?) ON CONFLICT(insight_id) DO UPDATE "
                    "SET payload=excluded.payload",
                    (idea["id"], json.dumps(snapshot)),
                )
            db.execute(
                "DELETE FROM idea_revisions WHERE idea_id=? AND revision < ?",
                (idea["id"], max(1, idea["revision"] - 19)),
            )
        return True

    def enqueue(self, idea: dict) -> None:
        ident = f"{idea['id']}:{idea['revision']}"
        with self.connect() as db:
            db.execute(
                "UPDATE research_jobs SET state='superseded' WHERE idea_id=? AND state='queued' AND id != ?",
                (idea["id"], ident),
            )
            count = db.execute(
                "SELECT count(*) FROM research_jobs WHERE state='queued'"
            ).fetchone()[0]
            if count < 16:
                db.execute(
                    "INSERT OR IGNORE INTO research_jobs VALUES (?,?,?,'queued',?,?)",
                    (ident, idea["id"], idea["revision"], idea["published_at"], json.dumps(idea)),
                )

    def claim_job(self) -> dict | None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT id,payload FROM research_jobs WHERE state='queued' "
                "ORDER BY created_at LIMIT 1"
            ).fetchone()
            if not row:
                return None
            db.execute("UPDATE research_jobs SET state='running' WHERE id=?", (row[0],))
        return {"job_id": row[0], "idea": json.loads(row[1])}

    def finish_job(self, identifier: str, state: str) -> None:
        with self.connect() as db:
            db.execute("UPDATE research_jobs SET state=? WHERE id=?", (state, identifier))

    def report_entry(self, owner: str, identifier: str, value: dict) -> None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM insights WHERE id=?", (identifier,)).fetchone()
            if not row or json.loads(row[0]).get("revision") != value["expected_revision"]:
                raise ValueError("IDEA_REVISION_CHANGED")
            if (
                db.execute("SELECT count(*) FROM stars WHERE owner=?", (owner,)).fetchone()[0]
                >= 200
            ):
                if not db.execute(
                    "SELECT 1 FROM stars WHERE owner=? AND insight_id=?", (owner, identifier)
                ).fetchone():
                    raise ValueError("SAVED_INSIGHT_LIMIT")
            db.execute("INSERT OR IGNORE INTO stars VALUES (?,?)", (owner, identifier))
            db.execute(
                "INSERT INTO reported_entries VALUES (?,?,?) ON CONFLICT(owner,idea_id) "
                "DO UPDATE SET payload=excluded.payload",
                (owner, identifier, json.dumps(value)),
            )

    def entries(self, owner: str) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT idea_id,payload FROM reported_entries WHERE owner=?", (owner,)
            ).fetchall()
        return [{"idea_id": row[0], **json.loads(row[1])} for row in rows]

    def backup(self) -> str:
        target = self.path + ".backup"
        temporary = target + ".tmp"
        with self.connect() as source, sqlite3.connect(temporary) as destination:
            source.backup(destination, pages=128, sleep=0.01)
            if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise OSError("BACKUP_INTEGRITY_FAILED")
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
        return target

    def prune(self) -> None:
        cutoff = (datetime.now(UTC) - timedelta(days=7)).isoformat()
        with self.connect() as db:
            db.execute(
                "DELETE FROM insights WHERE id NOT IN (SELECT insight_id FROM stars) "
                "AND (julianday(created_at) < julianday(?) OR id NOT IN "
                "(SELECT id FROM insights ORDER BY created_at DESC, id DESC LIMIT 1000))",
                (cutoff,),
            )
            db.execute(
                "DELETE FROM documents WHERE key LIKE 'scenario:%' AND substr(key,10) NOT IN (SELECT id FROM insights)"
            )
            db.execute("DELETE FROM evidence WHERE insight_id NOT IN (SELECT id FROM insights)")
            db.execute("DELETE FROM insight_feed WHERE insight_id NOT IN (SELECT id FROM insights)")
            db.execute("DELETE FROM idea_revisions WHERE idea_id NOT IN (SELECT id FROM insights)")
            db.execute(
                "DELETE FROM research_jobs WHERE state != 'running' AND "
                "julianday(created_at)<julianday(?)",
                (cutoff,),
            )
            db.execute(
                "DELETE FROM documents WHERE key LIKE 'explanation:%' AND "
                "json_extract(payload, '$.day') != ?",
                (datetime.now(UTC).date().isoformat(),),
            )

    def changes(self, after: int) -> dict:
        with self.connect() as db:
            latest = db.execute(
                "SELECT seq FROM sqlite_sequence WHERE name='insight_feed'"
            ).fetchone()
            latest = latest[0] if latest else 0
            rows = db.execute(
                "SELECT f.sequence, i.payload FROM insight_feed f JOIN insights i "
                "ON i.id=f.insight_id WHERE f.sequence>? ORDER BY f.sequence LIMIT 101",
                (after,),
            ).fetchall()
        page = rows[:100]
        return {
            "insights": [json.loads(row[1]) for row in page],
            "cursor": page[-1][0] if len(rows) > 100 else latest,
            "has_more": len(rows) > 100,
            "retention_days": 7,
            "server_reset": after > latest,
        }

    def saved(self, owner: str) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT i.payload FROM insights i JOIN stars s ON i.id=s.insight_id "
                "WHERE s.owner=? ORDER BY i.created_at DESC",
                (owner,),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def star(self, owner: str, insight_id: str, starred: bool) -> bool:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM insights WHERE id=?", (insight_id,)).fetchone():
                return False
            if starred:
                count = db.execute("SELECT count(*) FROM stars WHERE owner=?", (owner,)).fetchone()[
                    0
                ]
                exists = db.execute(
                    "SELECT 1 FROM stars WHERE owner=? AND insight_id=?", (owner, insight_id)
                ).fetchone()
                if count >= 200 and not exists:
                    raise ValueError("SAVED_INSIGHT_LIMIT")
                db.execute("INSERT OR IGNORE INTO stars VALUES (?,?)", (owner, insight_id))
            else:
                db.execute("DELETE FROM stars WHERE owner=? AND insight_id=?", (owner, insight_id))
        self.prune()
        return True

    def evidence(self, insight_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute(
                "SELECT payload FROM evidence WHERE insight_id=?", (insight_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def insights(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT payload FROM insights ORDER BY created_at DESC, id DESC LIMIT 30"
            ).fetchall()
        return [json.loads(row[0]) for row in rows]
