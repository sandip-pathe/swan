"""Provider contract tests use an isolated HTTP transport, never real API credits."""

import asyncio
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import SecretStr

from services.agents.news import NewsReader
from services.core.setup import NewsPolicy
from services.market.settings import ProviderError


def reader(tmp_path, monkeypatch, handler):
    path = tmp_path / "news.json"
    path.write_text('{"provider":"newsdata_free"}', encoding="utf-8")
    original = httpx.AsyncClient
    monkeypatch.setattr(
        "services.agents.news.httpx.AsyncClient",
        lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(handler)),
    )
    return NewsReader(str(path), SecretStr("test-private-key"))


def article(hours=13, **overrides):
    return {
        "title": " An attributed headline ",
        "link": "https://publisher.example/story",
        "source_name": "Publisher",
        "pubDate": (datetime.now(UTC) - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S"),
        "pubDateTZ": "UTC",
        **overrides,
    }


def test_newsdata_header_auth_freshness_attribution_and_cache(tmp_path, monkeypatch):
    calls = []

    def respond(request):
        calls.append(request)
        assert "apikey" not in request.url.params
        assert "test-private-key" not in str(request.url)
        assert request.headers["X-ACCESS-KEY"] == "test-private-key"
        assert request.url.path == "/api/1/market"
        assert dict(request.url.params) == {
            "country": "in",
            "language": "en",
        }
        row = article()
        return httpx.Response(
            200,
            json={
                "status": "success",
                "nextPage": "do-not-follow",
                "results": [
                    row,
                    row,
                    article(25),
                    article(-1),
                    article(link="http://unsafe.example"),
                    article(pubDate="bad"),
                    article(title=None),
                ],
            },
        )

    news = reader(tmp_path, monkeypatch, respond)

    async def check():
        first = await news.read()
        second = await news.read()
        assert len(first) == 1
        assert first == second
        item = first[0]
        assert item.title == "An attributed headline"
        assert item.source == "Publisher"
        assert item.provider_delay_seconds == 43200
        assert item.fetched_at - item.published_at > timedelta(hours=12)
        assert len(calls) == 1
        assert "test-private-key" not in item.model_dump_json()

    asyncio.run(check())


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "NEWS_AUTH_OR_PLAN_REJECTED"),
        (403, "NEWS_AUTH_OR_PLAN_REJECTED"),
        (429, "NEWS_QUOTA_OR_RATE_LIMIT"),
        (500, "NEWS_HTTP_ERROR"),
    ],
)
def test_provider_errors_are_sanitized(tmp_path, monkeypatch, status, code):
    news = reader(
        tmp_path, monkeypatch, lambda request: httpx.Response(status, text="private response")
    )
    with pytest.raises(ProviderError, match=code):
        asyncio.run(news.read())


@pytest.mark.parametrize(
    "data,code",
    [
        ({"status": "error", "results": {"message": "private"}}, "NEWS_RESPONSE_INVALID"),
        ({"status": "success", "results": []}, "NEWS_NO_CURRENT_HEADLINES"),
    ],
)
def test_empty_or_invalid_payload_fails_closed(tmp_path, monkeypatch, data, code):
    news = reader(tmp_path, monkeypatch, lambda request: httpx.Response(200, json=data))
    with pytest.raises(ProviderError, match=code):
        asyncio.run(news.read())


def test_missing_key_does_not_contact_provider(tmp_path, monkeypatch):
    def unexpected(request):
        pytest.fail("must not contact provider")

    news = reader(tmp_path, monkeypatch, unexpected)
    news.api_key = SecretStr("")
    with pytest.raises(ProviderError, match="NEWS_API_KEY_MISSING"):
        asyncio.run(news.read())


def test_news_policy_supports_existing_rss_and_free_api():
    assert NewsPolicy.model_validate({"sources": []}).provider == "rss"
    policy = NewsPolicy.model_validate({"provider": "newsdata_free"})
    assert "key" not in json.dumps(policy.model_dump())
    with pytest.raises(ValueError):
        NewsPolicy.model_validate({"provider": "invented"})
