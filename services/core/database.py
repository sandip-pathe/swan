"""Local configuration and transaction-capable PostgreSQL connections."""

import os
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from sqlalchemy import Engine, create_engine


def database_url() -> str:
    root = Path(__file__).resolve().parents[2]
    value = os.environ.get("DATABASE_URL") or dotenv_values(root / ".env").get("DATABASE_URL")
    if not value:
        raise RuntimeError("DATABASE_URL is not configured")
    return value


def make_engine(url: str | None = None, **kwargs: Any) -> Engine:
    connect_args = {"connect_timeout": 5, **kwargs.pop("connect_args", {})}
    return create_engine(
        url or database_url(),
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args=connect_args,
        **kwargs,
    )
