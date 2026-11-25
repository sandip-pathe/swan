"""Only bot reads and chat are exposed; no legacy routers or account writes."""

import asyncio
import hashlib
import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from services.api.auth import settings, verified_claims
from services.bot.session import market_context
from services.bot.store import Store
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


app = FastAPI(title="SWAN market bot", lifespan=lifespan, docs_url=None,
              redoc_url=None, openapi_url=None)
app.add_middleware(CORSMiddleware, allow_origins=settings().swan_web_origins,
                   allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])


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


def context(store: Store, now: datetime, include_insights: bool = True) -> dict:
    try:
        source_calendar = SessionCalendar(MarketSettings().calendar_file)
        calendars = {name: market_context(source_calendar, now, venue) for name, venue in
                     (("SENSEX", "BFO"), ("NIFTY", "NFO"))}
    except ProviderError:
        calendars = {name: {"state": "unknown"} for name in ("SENSEX", "NIFTY")}
    calendar = calendars["SENSEX"]
    worker = store.read("worker", {"status": "not_started"})
    heartbeat = worker.get("heartbeat")
    worker = {**worker, "heartbeat_current": bool(heartbeat and
              timedelta(0) <= now - datetime.fromisoformat(heartbeat) <= timedelta(minutes=3))}
    quotes = []
    for underlying in ("NIFTY", "SENSEX"):
        quote = store.read(f"quote:{underlying}")
        age = (now - datetime.fromisoformat(quote["timestamp"])).total_seconds() if quote else None
        quotes.append({"underlying": underlying, "quote": quote, "age_seconds": age,
                       "status": "unavailable" if quote is None else "current" if
                       calendars[underlying].get("state") == "open" and age is not None and 0 <= age <= 90
                       else "historical"})
    analyses = {}
    for underlying in ("SENSEX", "NIFTY"):
        analysis = store.read(f"analysis:{underlying}", {
            "status": "insufficient", "reason": "No validated candle analysis yet.",
            "underlying": underlying})
        if analysis.get("status") == "current":
            analysis_age = now - datetime.fromisoformat(analysis["as_of"])
            if (calendars[underlying].get("state") != "open" or
                    not timedelta(0) <= analysis_age <= timedelta(minutes=3)):
                analysis = {**analysis, "status": "historical"}
        analyses[underlying] = analysis
    return {"as_of": now.isoformat(), "calendar": calendar, "worker": worker,
            "quotes": quotes, "analysis": analyses["SENSEX"], "analyses": analyses,
            "calendars": calendars,
            "insights": store.insights() if include_insights else [], "capabilities": {
                "nifty_analysis": True, "sensex_history": True, "options": False,
                "news": False, "trading": False}}


@app.get("/api/bot/insights")
def insights(after: int | None = Query(default=None, ge=0, le=9223372036854775807),
             saved_version: str = Query(default="", max_length=64),
             identifier: UUID = Depends(owner)):
    value = context(app.state.store, datetime.now(UTC), include_insights=after is None)
    if after is not None:
        value.update(app.state.store.changes(after))
        saved = app.state.store.saved(str(identifier))
        value["saved_ids"] = [item["id"] for item in saved]
        version = hashlib.sha256("\n".join(value["saved_ids"]).encode()).hexdigest()
        value["saved_version"] = version
        value["saved"] = saved if version != saved_version else []
    return value


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


@app.post("/api/chat/messages")
async def chat(body: Question, identifier: UUID = Depends(owner)):
    from services.bot.chat import answer

    if app.state.chat_lock.locked():
        raise HTTPException(429, "RESEARCH_BUSY_TRY_AGAIN")
    async with app.state.chat_lock:
        evidence = await asyncio.to_thread(context, app.state.store, datetime.now(UTC))
        return await answer(body.question, evidence, app.state.store,
                            [turn.model_dump() for turn in body.history])
