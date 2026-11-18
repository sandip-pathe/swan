"""Back up and apply a supported paper-ledger migration to the local database."""

import argparse
import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import Connection, make_url

from services.core.database import database_url, make_engine

ROOT = Path(__file__).resolve().parents[1]
TARGET = "95d7e32c10ab"
PARENTS = {
    "84c6d21b09fa": {"31fa5ac4735a"},
    "95d7e32c10ab": {"31fa5ac4735a", "84c6d21b09fa"},
}


def financial_digest(connection: Connection) -> str:
    queries = {
        "accounts": "id, cash, config, session_opening_equity",
        "paper_orders": "id, account_id, decision_id, instrument_id, side, quantity, reason, timestamp",
        "paper_fills": "id, order_id, snapshot_id, quantity, price, fees, fee_breakdown, config_version, cost_version",
        "paper_positions": "id, account_id, instrument_id, entry_order_id, exit_order_id, quantity, average_price, entry_fees, stop_loss, target, planned_risk, opened_at, closed_at, realized_pnl, config",
        "ledger_entries": "id, account_id, fill_id, category, amount, timestamp",
    }
    digest = hashlib.sha256()
    for table, fields in queries.items():
        rows = connection.execute(text(f"SELECT {fields} FROM {table} ORDER BY id")).mappings()
        digest.update(table.encode())
        for row in rows:
            digest.update(json.dumps(dict(row), sort_keys=True, default=str).encode())
    return digest.hexdigest()


def upgrade_local(target: str = TARGET) -> None:
    if target not in PARENTS:
        raise ValueError("Unsupported local migration target")
    url = make_url(database_url())
    if url.host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("This migration helper is restricted to the local database")
    engine = make_engine()
    try:
        with engine.connect() as connection:
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
            if revision == target:
                print("Requested paper-ledger schema is already installed.")
                return
            if revision not in PARENTS[target]:
                raise RuntimeError("Unexpected schema revision; review the migration chain")
            running = connection.scalar(
                text("""
                SELECT COUNT(*) FROM runtime_controls
                WHERE heartbeat >= :cutoff
            """),
                {"cutoff": datetime.now(UTC) - timedelta(seconds=60)},
            )
            enabled = connection.scalar(text("SELECT COUNT(*) FROM accounts WHERE enabled = true"))
            if running or enabled:
                raise RuntimeError("Stop the worker and pause all accounts before migrating")
        backup_dir = ROOT / ".local" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        backup = backup_dir / f"before-{target}-{stamp}.dump"
        env = dict(os.environ)
        env["PGPASSWORD"] = url.password or ""
        result = subprocess.run(
            [
                str(ROOT / ".tools" / "pgsql" / "bin" / "pg_dump.exe"),
                "--host",
                url.host or "127.0.0.1",
                "--port",
                str(url.port or 5432),
                "--username",
                url.username or "",
                "--dbname",
                url.database or "",
                "--format=custom",
                "--file",
                str(backup),
                "--no-password",
            ],
            env=env,
            capture_output=True,
            timeout=120,
            check=False,
        )
        if result.returncode or not backup.is_file() or not backup.stat().st_size:
            raise RuntimeError("Private database backup failed; migration was not attempted")
        with engine.begin() as connection:
            before = financial_digest(connection)
            cfg = Config(str(ROOT / "alembic.ini"))
            cfg.set_main_option("script_location", str(ROOT / "migrations"))
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, target)
            if before != financial_digest(connection):
                raise RuntimeError("Historical financial data changed; migration rolled back")
        print(f"Local schema upgraded to {target}; historical financial data preserved.")
        print(f"Private backup: .local/backups/{backup.name}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=tuple(PARENTS), default=TARGET)
    args = parser.parse_args()
    try:
        upgrade_local(args.target)
    except Exception as error:
        # Do not print DB URLs, pg_dump output, credentials or arbitrary exception bodies.
        raise SystemExit(f"Local migration did not complete ({type(error).__name__}).") from None
