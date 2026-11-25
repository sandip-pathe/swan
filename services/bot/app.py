"""Only bot reads and chat are exposed; no legacy routers or account writes."""

import asyncio
import hashlib
import json
import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from services.api.auth import settings, verified_claims
from services.bot.contracts import ReportedEntry
from services.bot.feasibility import assess, personalize
from services.bot.session import market_context
from services.bot.store import Store
from services.core.contracts import Instrument, Quote
from services.market.calendar import SessionCalendar
from services.market.settings import MarketSettings, ProviderError


def owner(token: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False))) -> UUID:
    if token is None or len(token.credentials) > 10000:
        raise HTTPException(401, "SIGN_IN_REQUIRED")
    claims = verified_claims(token.credentials)
    account = settings().swan_account_bindings.get(claims["sub"])
    if account is None:
        raise HTTPException(403, "ACCOUNT_NOT_AUTHORIZED")
    return account


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.store = Store(os.environ.get("BOT_DB_PATH", ".local/bot/bot.sqlite3"))
    app.state.chat_lock = asyncio.Lock()
    yield


app = FastAPI(
    title="SWAN market bot", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings().swan_web_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(sqlite3.Error)
async def storage_unavailable(request, error):
    return JSONResponse(status_code=503, content={"detail": "SAVED_DATA_UNAVAILABLE"})


@app.middleware("http")
async def private_responses(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/health")
def health():
    with app.state.store.connect() as db:
        db.execute("SELECT 1")
    return {"service": "swan-bot", "database": "connected"}


def idea_view(
    store: Store, idea: dict, now: datetime, market_open: bool, owner_id: str | None
) -> dict:
    if idea.get("kind") != "idea":
        return idea
    value = dict(idea)
    market = store.read("option_market", {})
    contract = value.get("contract")
    if contract and value["state"] not in {"invalidated", "expired"}:
        raw = market.get("quotes", {}).get(contract["id"])
        economics, reasons = assess(
            Instrument.model_validate(contract),
            Quote.model_validate(raw) if raw else None,
            now,
            market.get("noise", {}).get(contract["id"], {}),
            (store.read("scenario:" + idea["id"]) or {}).get("economics"),
        )
        value["economics"] = economics
        if reasons and value["state"] == "eligible":
            value.update(state="suspended", reasons=list(dict.fromkeys(value["reasons"] + reasons)))
    preferences = store.read(f"preferences:{owner_id}", {}) if owner_id else {}
    return personalize(
        value,
        Decimal(preferences.get("position_budget", "0")),
        now,
        market_open and market.get("connected", False),
    )


def evaluation_summary(store: Store) -> dict:
    with store.connect() as db:
        rows = db.execute("SELECT payload FROM evaluations LIMIT 2000").fetchall()
    records = [json.loads(row[0]) for row in rows]
    closed = [row for row in records if row.get("outcome")]
    priced = [row for row in closed if row.get("net_estimate") is not None]
    return {
        "hypothetical": True,
        "sample_count": len(records),
        "closed_count": len(closed),
        "priced_count": len(priced),
        "unpriced_count": len(closed) - len(priced),
        "net_estimate_total": str(
            sum((Decimal(row["net_estimate"]) for row in priced), Decimal(0))
        ),
        "edge_status": "not_established",
        "retention_limit": 2000,
        "limitation": "Prospective quote scenarios, not actual fills or a validated win probability. Missing exits remain unpriced.",
    }


def context(
    store: Store, now: datetime, include_insights: bool = True, owner_id: str | None = None
) -> dict:
    try:
        source_calendar = SessionCalendar(MarketSettings().calendar_file)
        calendars = {
            name: market_context(source_calendar, now, venue)
            for name, venue in (("SENSEX", "BFO"), ("NIFTY", "NFO"))
        }
    except ProviderError:
        calendars = {name: {"state": "unknown"} for name in ("SENSEX", "NIFTY")}
    calendar = calendars["SENSEX"]
    worker = store.read("worker", {"status": "not_started"})
    heartbeat = worker.get("heartbeat")
    worker = {
        **worker,
        "heartbeat_current": bool(
            heartbeat
            and timedelta(0) <= now - datetime.fromisoformat(heartbeat) <= timedelta(minutes=3)
        ),
    }
    quotes = []
    for underlying in ("NIFTY", "SENSEX"):
        quote = store.read(f"quote:{underlying}")
        age = (now - datetime.fromisoformat(quote["timestamp"])).total_seconds() if quote else None
        quotes.append(
            {
                "underlying": underlying,
                "quote": quote,
                "age_seconds": age,
                "status": "unavailable"
                if quote is None
                else "current"
                if calendars[underlying].get("state") == "open"
                and age is not None
                and 0 <= age <= 90
                else "historical",
            }
        )
    analyses = {}
    for underlying in ("SENSEX", "NIFTY"):
        analysis = store.read(
            f"analysis:{underlying}",
            {
                "status": "insufficient",
                "reason": "No validated candle analysis yet.",
                "underlying": underlying,
            },
        )
        if analysis.get("status") in {"current", "partial"} and analysis.get("as_of"):
            analysis_age = now - datetime.fromisoformat(analysis["as_of"])
            if calendars[underlying].get("state") != "open" or not timedelta(
                0
            ) <= analysis_age <= timedelta(minutes=3):
                analysis = {**analysis, "status": "historical"}
        analyses[underlying] = analysis
    ideas = [
        idea_view(store, idea, now, calendar.get("state") == "open", owner_id)
        for idea in store.ideas(100)
        if idea["state"] not in {"expired", "invalidated"}
        and datetime.fromisoformat(idea["expires_at"]) > now
    ]
    ideas.sort(
        key=lambda idea: (
            idea["state"] in {"expired", "invalidated"},
            -idea.get("rank", 0),
            -datetime.fromisoformat(idea["published_at"]).timestamp(),
        )
    )
    news = store.read("news", {"sources": [], "items": []})
    return {
        "as_of": now.isoformat(),
        "calendar": calendar,
        "worker": worker,
        "quotes": quotes,
        "analysis": analyses["SENSEX"],
        "analyses": analyses,
        "calendars": calendars,
        "current_ideas": ideas[:30],
        "news": news,
        "weekly": store.read("weekly", {"status": "not_started"}),
        "preferences": store.read(f"preferences:{owner_id}", {"position_budget": "0"})
        if owner_id
        else {},
        "reported_entries": store.entries(owner_id) if owner_id else [],
        "backup": store.read("backup", {}),
        "evaluation": evaluation_summary(store),
        "research_status": store.read("research_status", {"status": "not_requested"}),
        "insights": store.insights() if include_insights else [],
        "capabilities": {
            "nifty_analysis": True,
            "sensex_history": True,
            "options": True,
            "news": bool(news.get("items")),
            "weekly": True,
            "trading": False,
        },
    }


@app.get("/api/bot/insights")
def insights(
    after: int | None = Query(default=None, ge=0, le=9223372036854775807),
    saved_version: str = Query(default="", max_length=64),
    identifier: UUID = Depends(owner),
):
    now = datetime.now(UTC)
    value = context(app.state.store, now, include_insights=after is None, owner_id=str(identifier))
    if after is not None:
        value.update(app.state.store.changes(after))
        saved = app.state.store.saved(str(identifier))
        value["saved_ids"] = [item["id"] for item in saved]
        version = hashlib.sha256(
            json.dumps([(item["id"], item.get("revision", 0)) for item in saved]).encode()
        ).hexdigest()
        value["saved_version"] = version
        value["saved"] = saved if version != saved_version else []
        value["insights"] = [
            idea_view(
                app.state.store, item, now, value["calendar"]["state"] == "open", str(identifier)
            )
            for item in value["insights"]
        ]
        value["saved"] = [
            idea_view(
                app.state.store, item, now, value["calendar"]["state"] == "open", str(identifier)
            )
            for item in value["saved"]
        ]
    return value


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    position_budget: Decimal = Field(ge=0, le=10000000, max_digits=12, decimal_places=2)


@app.post("/api/bot/preferences")
def preferences(body: Preferences, identifier: UUID = Depends(owner)):
    app.state.store.write(f"preferences:{identifier}", body.model_dump(mode="json"))
    return body.model_dump(mode="json")


@app.get("/api/bot/push-key")
def push_key(identifier: UUID = Depends(owner)):
    from services.bot.notifications import public_key

    return {"public_key": public_key(app.state.store)}


class Subscription(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoint: str = Field(max_length=2000)
    keys: dict[str, str] = Field(max_length=2)
    expirationTime: int | None = None


@app.post("/api/bot/push")
def push_subscribe(body: Subscription, identifier: UUID = Depends(owner)):
    from services.bot.notifications import validate_subscription

    value = body.model_dump()
    try:
        digest = validate_subscription(value)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    with app.state.store.connect() as db:
        count = db.execute(
            "SELECT count(*) FROM documents WHERE key LIKE ?", (f"push:{identifier}:%",)
        ).fetchone()[0]
        key = f"push:{identifier}:{digest}"
        if count >= 5 and not db.execute("SELECT 1 FROM documents WHERE key=?", (key,)).fetchone():
            raise HTTPException(409, "DEVICE_SUBSCRIPTION_LIMIT")
    app.state.store.write(key, {"owner": str(identifier), "subscription": value})
    return {"subscribed": True}


@app.post("/api/bot/push/disable")
def push_disable(identifier: UUID = Depends(owner)):
    with app.state.store.connect() as db:
        db.execute("DELETE FROM documents WHERE key LIKE ?", (f"push:{identifier}:%",))
    return {"subscribed": False}


@app.post("/api/bot/ideas/{idea_id}/entry")
def reported_entry(idea_id: str, body: ReportedEntry, identifier: UUID = Depends(owner)):
    if body.entered_at > datetime.now(UTC) + timedelta(seconds=30):
        raise HTTPException(422, "ENTRY_TIME_IN_FUTURE")
    value = app.state.store.idea(idea_id)
    if not value or value.get("kind") != "idea" or not value.get("contract"):
        raise HTTPException(404, "IDEA_CONTRACT_NOT_FOUND")
    if body.quantity % value["contract"]["lot_size"]:
        raise HTTPException(422, "WHOLE_LOTS_REQUIRED")
    try:
        app.state.store.report_entry(str(identifier), idea_id, body.model_dump(mode="json"))
    except ValueError as error:
        raise HTTPException(409, str(error)) from None
    return {"reported": True, "broker_confirmed": False, "order_created": False}


@app.get("/api/bot/ideas/{idea_id}/revisions")
def revisions(idea_id: str, identifier: UUID = Depends(owner)):
    with app.state.store.connect() as db:
        rows = db.execute(
            "SELECT payload FROM idea_revisions WHERE idea_id=? ORDER BY revision DESC LIMIT 20",
            (idea_id,),
        ).fetchall()
    return {"revisions": [json.loads(row[0]) for row in rows]}


@app.get("/api/bot/events")
async def events(request: Request, identifier: UUID = Depends(owner)):
    async def notifications():
        last = None
        started = asyncio.get_running_loop().time()
        while (
            asyncio.get_running_loop().time() - started < 50 and not await request.is_disconnected()
        ):

            def marker():
                with app.state.store.connect() as db:
                    row = db.execute(
                        "SELECT seq FROM sqlite_sequence WHERE name='insight_feed'"
                    ).fetchone()
                market = app.state.store.read("option_market", {})
                return (row[0] if row else 0, market.get("at"))

            current = await asyncio.to_thread(marker)
            if current != last:
                yield "event: update\ndata: " + json.dumps({"cursor": current[0]}) + "\n\n"
                last = current
            else:
                yield ": heartbeat\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(
        notifications(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-store"},
    )


class Star(BaseModel):
    model_config = ConfigDict(extra="forbid")
    starred: bool


@app.post("/api/bot/insights/{insight_id}/star")
def star_insight(insight_id: str, body: Star, identifier: UUID = Depends(owner)):
    try:
        found = app.state.store.star(str(identifier), insight_id, body.starred)
    except ValueError:
        raise HTTPException(409, "SAVED_INSIGHT_LIMIT") from None
    if not found:
        raise HTTPException(404, "INSIGHT_EXPIRED_OR_NOT_FOUND")
    return {"id": insight_id, "starred": body.starred}


@app.get("/api/bot/insights/{insight_id}/evidence")
def insight_evidence(insight_id: str, identifier: UUID = Depends(owner)):
    value = app.state.store.evidence(insight_id)
    if value is None:
        raise HTTPException(404, "EVIDENCE_NOT_FOUND")
    return value


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=4000)


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=2000)
    history: list[Turn] = Field(default_factory=list, max_length=6)
    idea_id: str | None = Field(default=None, max_length=100)


@app.post("/api/chat/messages")
async def chat(body: Question, identifier: UUID = Depends(owner)):
    from services.bot.orchestration import respond

    if app.state.chat_lock.locked():
        raise HTTPException(429, "RESEARCH_BUSY_TRY_AGAIN")
    async with app.state.chat_lock:
        return await respond(
            body.question,
            [turn.model_dump() for turn in body.history],
            app.state.store,
            str(identifier),
            body.idea_id,
        )
