"""Export a flat local paper account for migration without exposing credentials."""

import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    sys.path.insert(0, str(ROOT))
    from sqlalchemy import func, select
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import Session

    from services.core.database import database_url, make_engine
    from services.core.models import Account, PaperOrder, PaperPosition, PaperValidation

    engine = make_engine()
    try:
        with Session(engine) as db:
            opened = db.scalar(
                select(func.count())
                .select_from(PaperPosition)
                .where(
                    PaperPosition.closed_at.is_(None),
                )
            )
            active = db.scalar(
                select(func.count())
                .select_from(PaperValidation)
                .where(
                    PaperValidation.status.in_(("ACTIVE", "STOPPING")),
                )
            )
            if opened or active:
                raise SystemExit("Export blocked: close exposure and stop validation first.")
            counts = {
                name: db.scalar(select(func.count()).select_from(model))
                for name, model in (
                    ("accounts", Account),
                    ("orders", PaperOrder),
                    ("positions", PaperPosition),
                )
            }
        url = make_url(database_url())
        dump = ROOT / ".tools/pgsql/bin/pg_dump.exe" if os.name == "nt" else Path("pg_dump")
        environment = {**os.environ, "PGPASSWORD": url.password or ""}
        target_dir = ROOT / ".local/release"
        target_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        target = target_dir / f"swan-database-{stamp}.dump"
        subprocess.run(
            [
                str(dump),
                "--host",
                url.host or "localhost",
                "--port",
                str(url.port or 5432),
                "--username",
                url.username or "swan",
                "--dbname",
                url.database or "swan_trade",
                "--format=custom",
                "--no-owner",
                "--no-acl",
                "--file",
                str(target),
            ],
            env=environment,
            check=True,
            capture_output=True,
        )
        restore = dump.with_name("pg_restore.exe") if os.name == "nt" else Path("pg_restore")
        subprocess.run([str(restore), "--list", str(target)], check=True, capture_output=True)
        target.with_suffix(".manifest.json").write_text(
            json.dumps(
                {
                    "created_at": datetime.now(UTC).isoformat(),
                    "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                    "counts_before_snapshot": counts,
                    "cutover": "Preparation snapshot only. Stop local writers before final migration.",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"Private database backup: {target}")
        print("Restore catalog verified; repeat after stopping local writers for final cutover.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
