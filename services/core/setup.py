"""Versioned non-secret configuration. Writes require the authenticated owner."""

import hashlib
import json
import os
import tempfile
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from services.agents.news import NewsConfiguration
from services.core.execution import PaperExecutionConfig
from services.market.calendar import CalendarDocument
from services.market.settings import ROOT


class AgentPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    model: str = Field(min_length=1, max_length=150, pattern=r"^[a-zA-Z0-9._:-]+$")
    daily_token_budget: int = Field(gt=0)
    max_output_tokens: int = Field(ge=256, le=8000)
    timeout_seconds: int = Field(ge=5, le=45)


class NewsPolicy(NewsConfiguration):
    @model_validator(mode="after")
    def licensed(self):
        if any(
            not s.automation_and_storage_permitted
            or s.url.scheme != "https"
            or s.url.username
            or s.url.password
            for s in self.sources
        ):
            raise ValueError("NEWS_LICENSE_OR_URL_INVALID")
        if self.provider == "newsdata_free" and self.sources:
            raise ValueError("NEWS_PROVIDER_SOURCES_CONFLICT")
        return self


CONFIG_FILES = {
    "execution": ROOT / "config" / "paper-execution.json",
    "calendar": ROOT / "config" / "exchange-calendar.json",
    "news": ROOT / "config" / "news-sources.json",
    "agents": ROOT / "config" / "agents.json",
}
CONFIG_TYPES: dict[str, type[BaseModel]] = {
    "execution": PaperExecutionConfig,
    "calendar": CalendarDocument,
    "news": NewsPolicy,
    "agents": AgentPolicy,
}


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def document(name: str) -> dict:
    path = CONFIG_FILES[name]
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        raw = ""
    try:
        value = json.loads(raw)
    except ValueError:
        value = None
    return {"name": name, "document": value, "revision": hashlib.sha256(raw.encode()).hexdigest()}


def save_document(name: str, value: dict, expected_revision: str) -> dict:
    path = CONFIG_FILES[name]
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("UNSAFE_CONFIG_DESTINATION")
    parsed = CONFIG_TYPES[name].model_validate(value)
    previous = document(name)
    if previous["revision"] != expected_revision:
        raise ValueError("SETTINGS_CHANGED_REFRESH_REQUIRED")
    serialized = parsed.model_dump_json(indent=2) + "\n"
    atomic_text(path, serialized)
    return previous


def atomic_text(path: Path, serialized: str) -> None:
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as output:
            output.write(serialized)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
