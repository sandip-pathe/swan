"""Check installed backend tooling and a disposable database transaction."""

import sys
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path

import fastapi
import psycopg
import pytest
import sqlalchemy
from dotenv import dotenv_values


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    for package in ("fastapi", "sqlalchemy", "alembic", "psycopg", "pytest", "ruff"):
        print(f"{package}: {version(package)}")
    if not (fastapi.FastAPI and sqlalchemy.create_engine and pytest.main):
        raise RuntimeError("Backend imports failed")

    url = dotenv_values(root / ".env").get("DATABASE_URL")
    if not url:
        raise RuntimeError("Database configuration is missing")
    connection_url = url.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(connection_url, connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            cursor.execute("CREATE TEMP TABLE environment_check (amount NUMERIC(18, 2))")
            cursor.execute(
                "INSERT INTO environment_check (amount) VALUES (%s)",
                (Decimal("100000.01"),),
            )
            cursor.execute("SELECT amount FROM environment_check")
            if cursor.fetchone() != (Decimal("100000.01"),):
                raise RuntimeError("Database decimal round-trip failed")
        connection.rollback()
    print("PASS: authenticated PostgreSQL connection and exact decimal round-trip (rolled back).")


if __name__ == "__main__":
    try:
        main()
    except (psycopg.Error, RuntimeError, OSError, ValueError) as error:
        # Driver exceptions may include connection details: report only the class.
        print(
            f"Environment check failed ({type(error).__name__}); inspect local setup.",
            file=sys.stderr,
        )
        sys.exit(1)
