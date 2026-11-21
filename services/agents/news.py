"""Attributed news from configured feeds or the NewsData.io free API."""

import asyncio
import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import httpx
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, SecretStr

from services.market.settings import ProviderError


class NewsSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    url: HttpUrl
    license_reference: str = Field(min_length=1, max_length=1000)
    automation_and_storage_permitted: bool


class NewsConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["rss", "newsdata_free"] = "rss"
    sources: list[NewsSource] = Field(default_factory=list, max_length=8)


class Headline(BaseModel):
    id: str
    title: str
    url: str
    source: str
    published_at: AwareDatetime
    fetched_at: AwareDatetime
    provider_delay_seconds: int = 0
    provider_name: str | None = None


class NewsReader:
    def __init__(self, config: str, api_key: SecretStr = SecretStr("")):
        self.config = Path(config)
        self.api_key = api_key
        self._cached: list[Headline] = []
        self._cached_at: datetime | None = None

    async def read(self) -> list[Headline]:
        try:
            config = NewsConfiguration.model_validate_json(self.config.read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError, TypeError):
            raise ProviderError("NEWS_CONFIGURATION_INVALID") from None
        if config.provider == "newsdata_free":
            return await self.read_newsdata()
        sources = config.sources
        if not sources:
            raise ProviderError("NEWS_NOT_CONFIGURED")
        if len(sources) > 8:
            raise ProviderError("NEWS_SOURCE_LIMIT")
        if any(
            not row.automation_and_storage_permitted
            or row.url.scheme != "https"
            or row.url.username
            or row.url.password
            for row in sources
        ):
            raise ProviderError("NEWS_LICENSE_OR_URL_INVALID")
        try:
            async with httpx.AsyncClient(
                timeout=10, follow_redirects=False, trust_env=False
            ) as client:
                batches = await asyncio.gather(*(self.fetch(client, row) for row in sources))
            items = {item.id: item for batch in batches for item in batch}
            if not items:
                raise ProviderError("NEWS_NO_CURRENT_HEADLINES")
            return sorted(items.values(), key=lambda row: row.published_at, reverse=True)[:30]
        except (httpx.HTTPError, ValueError, ET.ParseError):
            raise ProviderError("NEWS_UNAVAILABLE") from None

    async def read_newsdata(self) -> list[Headline]:
        if not self.api_key.get_secret_value():
            raise ProviderError("NEWS_API_KEY_MISSING")
        now = datetime.now(UTC)
        if self._cached_at and timedelta(0) <= now - self._cached_at < timedelta(minutes=15):
            current = [
                h for h in self._cached if now - timedelta(hours=24) <= h.published_at <= now
            ]
            if current:
                return current
        # One free endpoint request, no pagination or article-body retrieval.
        # Header authentication keeps the key out of URLs and request logs.
        try:
            async with httpx.AsyncClient(
                timeout=10, follow_redirects=False, trust_env=False
            ) as client:
                content = bytearray()
                async with client.stream(
                    "GET",
                    "https://newsdata.io/api/1/market",
                    headers={"X-ACCESS-KEY": self.api_key.get_secret_value()},
                    params={"country": "in", "language": "en"},
                ) as response:
                    if response.status_code in {401, 403}:
                        raise ProviderError("NEWS_AUTH_OR_PLAN_REJECTED")
                    if response.status_code == 429:
                        raise ProviderError("NEWS_QUOTA_OR_RATE_LIMIT")
                    if response.status_code != 200:
                        raise ProviderError("NEWS_HTTP_ERROR")
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > 1000000:
                            raise ProviderError("NEWS_RESPONSE_TOO_LARGE")
            data = json.loads(content)
            if (
                not isinstance(data, dict)
                or data.get("status") != "success"
                or not isinstance(data.get("results"), list)
            ):
                raise ProviderError("NEWS_RESPONSE_INVALID")
            items: dict[str, Headline] = {}
            for row in data["results"][:200]:
                if not isinstance(row, dict):
                    continue
                try:
                    # NewsData pubDate is UTC; retain publication time, never use
                    # retrieval time to make delayed free-tier articles look live.
                    stamp = datetime.fromisoformat(row["pubDate"].replace("Z", "+00:00"))
                    if stamp.tzinfo is None:
                        if row.get("pubDateTZ", "UTC") != "UTC":
                            continue
                        stamp = stamp.replace(tzinfo=UTC)
                    link = HttpUrl(row["link"])
                    title = " ".join(row["title"].split())[:500]
                    source = row.get("source_name") or row["source_id"]
                    if (
                        not title
                        or not isinstance(source, str)
                        or not source
                        or link.scheme != "https"
                        or link.username
                        or link.password
                    ):
                        continue
                    if not now - timedelta(hours=24) <= stamp <= now:
                        continue
                    ident = hashlib.sha256(
                        (source + str(link) + stamp.isoformat()).encode()
                    ).hexdigest()
                    items[ident] = Headline(
                        id=ident,
                        title=title,
                        url=str(link)[:2000],
                        source=source[:100],
                        published_at=stamp,
                        fetched_at=now,
                        provider_delay_seconds=43200,
                        provider_name="NewsData.io",
                    )
                except (ValueError, KeyError, TypeError, AttributeError, OverflowError):
                    continue
            if not items:
                raise ProviderError("NEWS_NO_CURRENT_HEADLINES")
            self._cached = sorted(items.values(), key=lambda h: h.published_at, reverse=True)[:30]
            self._cached_at = now
            return self._cached
        except (httpx.HTTPError, ValueError, TypeError):
            raise ProviderError("NEWS_UNAVAILABLE") from None

    async def fetch(self, client: httpx.AsyncClient, source: NewsSource) -> list[Headline]:
        content = bytearray()
        async with client.stream("GET", str(source.url)) as response:
            if response.status_code != 200:
                raise ProviderError("NEWS_HTTP_ERROR")
            async for chunk in response.aiter_bytes():
                content.extend(chunk)
                if len(content) > 1000000:
                    raise ProviderError("NEWS_RESPONSE_TOO_LARGE")
        if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
            raise ProviderError("NEWS_XML_UNSAFE")
        root = ET.fromstring(content)
        atom = "{http://www.w3.org/2005/Atom}"
        entries = root.findall("./channel/item") + root.findall(atom + "entry")
        now = datetime.now(UTC)
        results = []
        for entry in entries[:200]:
            title = entry.findtext("title") or entry.findtext(atom + "title") or ""
            link = entry.findtext("link")
            if not link:
                link = next(
                    (
                        node.get("href")
                        for node in entry.findall(atom + "link")
                        if node.get("rel", "alternate") == "alternate"
                    ),
                    None,
                )
            date = (
                entry.findtext("pubDate")
                or entry.findtext(atom + "published")
                or entry.findtext(atom + "updated")
            )
            if not title or not link or not date:
                continue
            try:
                try:
                    stamp = datetime.fromisoformat(date.replace("Z", "+00:00"))
                except ValueError:
                    stamp = parsedate_to_datetime(date)
                if stamp.tzinfo is None or not now - timedelta(hours=24) <= stamp <= now:
                    continue
                if urlsplit(link).scheme != "https":
                    continue
                results.append(
                    Headline(
                        id=hashlib.sha256(
                            (source.name + link + stamp.isoformat()).encode()
                        ).hexdigest(),
                        title=" ".join(title.split())[:500],
                        url=link[:2000],
                        source=source.name,
                        published_at=stamp,
                        fetched_at=now,
                    )
                )
            except (ValueError, TypeError, OverflowError):
                continue
        return results
