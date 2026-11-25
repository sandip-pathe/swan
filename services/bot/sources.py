"""Bounded attributed event feeds and verified-session daily index history."""

import asyncio
import hashlib
import html
import ipaddress
import json
import re
import socket
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from services.bot.engine import make_idea
from services.core.contracts import IST
from services.market.angelone import CANDLES, AngelOneClient
from services.market.calendar import SessionCalendar
from services.market.settings import ProviderError

ROOT = Path(__file__).resolve().parents[2]
HOSTS = {
    "www.rbi.org.in",
    "rbi.org.in",
    "www.nseindia.com",
    "nsearchives.nseindia.com",
    "www.bseindia.com",
}


async def headlines() -> dict:
    config = json.loads((ROOT / "config/bot-sources.json").read_text())
    items: dict[str, dict] = {}
    statuses = []
    async with httpx.AsyncClient(timeout=10, follow_redirects=False, trust_env=False) as client:
        for source in config["sources"][:4]:
            url = urlsplit(source["url"])
            if (
                url.scheme != "https"
                or url.hostname not in HOSTS
                or url.username
                or url.port not in (None, 443)
            ):
                raise ProviderError("SOURCE_NOT_ALLOWLISTED")
            try:
                addresses = await asyncio.get_running_loop().getaddrinfo(
                    url.hostname, 443, type=socket.SOCK_STREAM
                )
                if not addresses or any(
                    not ipaddress.ip_address(row[4][0]).is_global for row in addresses
                ):
                    raise ProviderError("SOURCE_ADDRESS_NOT_PUBLIC")
                content = bytearray()
                async with client.stream("GET", source["url"]) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > 250000:
                            raise ProviderError("FEED_TOO_LARGE")
                if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
                    raise ProviderError("FEED_ENTITIES_REJECTED")
                tree = ET.fromstring(content)
                count = 0
                for row in tree.findall(".//item")[:80]:
                    title = " ".join((row.findtext("title") or "").split())[:500]
                    link = row.findtext("link") or ""
                    published = row.findtext("pubDate")
                    if not title or not published or urlsplit(link).scheme != "https":
                        continue
                    try:
                        stamp = parsedate_to_datetime(published)
                        now = datetime.now(UTC)
                        if stamp.tzinfo is None or not timedelta(0) <= now - stamp <= timedelta(
                            days=7
                        ):
                            continue
                    except (ValueError, TypeError, OverflowError):
                        continue
                    ident = hashlib.sha256(
                        f"{source['name']}:{link}:{stamp.isoformat()}".encode()
                    ).hexdigest()
                    excerpt = re.sub(
                        r"<[^>]*>", " ", html.unescape(row.findtext("description") or "")
                    )
                    relevant = bool(
                        re.search(
                            r"\b(monetary|repo|inflation|gdp|liquidity|fiscal|sensex|interest rate|crude|policy rate|rate decision)\b",
                            title + " " + excerpt,
                            re.I,
                        )
                    )
                    items[ident] = {
                        "id": ident,
                        "title": title,
                        "url": link[:2000],
                        "source": source["name"],
                        "published_at": stamp.isoformat(),
                        "received_at": now.isoformat(),
                        "excerpt": " ".join(excerpt.split())[:1600],
                        "content_kind": "feed_excerpt",
                        "market_relevant": relevant,
                        "fresh_catalyst": relevant and now - stamp <= timedelta(minutes=15),
                    }
                    count += 1
                statuses.append(
                    {
                        "source": source["name"],
                        "status": "available" if count else "empty",
                        "items": count,
                    }
                )
            except (httpx.HTTPError, ProviderError, OSError, ValueError, ET.ParseError):
                statuses.append({"source": source["name"], "status": "unavailable"})
    return {
        "checked_at": datetime.now(UTC).isoformat(),
        "sources": statuses,
        "items": sorted(items.values(), key=lambda row: row["published_at"], reverse=True)[:30],
    }


async def weekly(
    client: AngelOneClient, calendar: SessionCalendar, now: datetime
) -> tuple[dict, list[dict]]:
    # Only explicitly verified completed sessions participate; no guessed weekdays.
    verified = []
    for offset in range(30, -1, -1):
        day = now.astimezone(IST).date() - timedelta(days=offset)
        session = calendar.get("BFO", day)
        if session and datetime.combine(day, time(15, 30), IST) < now:
            verified.append(session)
    if len(verified) < 5:
        return {
            "status": "insufficient",
            "reason": "Five verified completed sessions required.",
        }, []
    sessions = verified[-5:]
    body = {
        "exchange": "BSE",
        "symboltoken": client.settings.sensex_index_token,
        "interval": "ONE_DAY",
        "fromdate": sessions[0].opens_at.strftime("%Y-%m-%d %H:%M"),
        "todate": sessions[-1].closes_at.strftime("%Y-%m-%d %H:%M"),
    }
    raw = await asyncio.wait_for(client._post(CANDLES, body, await client.session()), 15)
    if not isinstance(raw, list) or len(raw) > 35:
        raise ProviderError("DAILY_RESPONSE_INVALID")
    bars: dict = {}
    allowed = {session.key for session in sessions}
    for row in raw:
        if not isinstance(row, list) or len(row) != 6:
            raise ProviderError("DAILY_BAR_INVALID")
        stamp = datetime.fromisoformat(row[0])
        if stamp.tzinfo is None:
            raise ProviderError("DAILY_TIMEZONE_MISSING")
        day = stamp.astimezone(IST).date()
        if day not in allowed:
            continue
        values = [Decimal(str(v)) for v in row[1:5]]
        opening, high, low, close = values
        if (
            not all(v.is_finite() and v > 0 for v in values)
            or not low <= min(opening, close) <= max(opening, close) <= high
        ):
            raise ProviderError("DAILY_OHLC_INVALID")
        if day in bars and bars[day] != values:
            raise ProviderError("DAILY_CONFLICT")
        bars[day] = values
    if set(bars) != allowed:
        return {"status": "insufficient", "reason": "Daily source coverage is incomplete."}, []
    ordered = [bars[session.key] for session in sessions]
    prior_high = max(row[1] for row in ordered[:-1])
    prior_low = min(row[2] for row in ordered[:-1])
    last = ordered[-1][3]
    as_of = datetime.combine(sessions[-1].key, time(15, 30), IST)
    digest = hashlib.sha256(json.dumps(raw, default=str).encode()).hexdigest()
    context = {
        "status": "historical",
        "horizon": "weekly",
        "as_of": as_of.isoformat(),
        "last_close": str(last),
        "prior_four_session_high": str(prior_high),
        "prior_four_session_low": str(prior_low),
        "rule": "five-session-break-v1",
        "source": "angelone-historical:ONE_DAY",
        "evidence": [digest],
        "sessions": [str(session.key) for session in sessions],
        "raw_bars": raw,
        "reason": "Daily structure is research context, not live option pricing.",
    }
    ideas = []
    if last > prior_high or last < prior_low:
        direction = "CALL" if last > prior_high else "PUT"
        width = max((prior_high - prior_low) / 4, Decimal("0.01"))
        trigger = prior_high if direction == "CALL" else prior_low
        invalidation = trigger - width if direction == "CALL" else trigger + width
        idea = make_idea(
            "five-session-break-v1",
            direction,
            trigger,
            invalidation,
            now,
            context,
            "watch",
            "weekly",
        )
        idea["trigger"] = (
            "Fresh next-session confirmation of the completed daily breakout; option checks required."
        )
        ideas.append(idea)
    return context, ideas
