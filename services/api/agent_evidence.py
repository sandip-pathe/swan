"""Only explicitly linked, account-owned evidence; no time-based reconstruction."""

from datetime import datetime
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from services.agents.contracts import Analysis, Proposal, Review
from services.agents.news import Headline
from services.api.auth import account_identity
from services.core.contracts import Instrument, Quote
from services.core.models import AuditEvent

router = APIRouter()


def age_seconds(reference: datetime, observation: datetime) -> int | None:
    seconds = (reference - observation).total_seconds()
    return int(seconds) if seconds >= 0 else None



@router.get("/api/paper/agent-activity/{event_id}/evidence")
def evidence(event_id: UUID, request: Request, owner: UUID = Depends(account_identity)):
    with Session(request.app.state.engine) as db:
        db.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        event = db.get(AuditEvent, event_id)
        if event is None or event.account_id != owner or event.kind != "AI_OUTPUT":
            raise HTTPException(404, "ACTIVITY_NOT_FOUND")
        unavailable = {"available": False, "quotes": [], "headlines": [], "missing": None}
        try:
            models: dict[str, type[Analysis] | type[Proposal] | type[Review]] = {
                "analysis": Analysis,
                "proposal": Proposal,
                "review": Review,
            }
            model = models.get(str(event.details.get("role", "")))
            if model is None:
                return unavailable
            output = model.model_validate(event.details.get("output"))
            context_id = UUID(str(event.details.get("context_id")))
        except (ValueError, TypeError):
            return unavailable
        context = db.get(AuditEvent, context_id)
        if context is None or context.account_id != owner or context.kind != "AI_CONTEXT":
            return unavailable
        quote_ids = list(dict.fromkeys(output.evidence_ids))
        news_ids = list(dict.fromkeys(output.news_ids)) if isinstance(output, Analysis) else []
        quotes, headlines = {}, {}
        labels = {}
        raw_instruments = context.details.get("instruments", [])
        for raw in (raw_instruments if isinstance(raw_instruments, list) else [])[:40]:
            try:
                instrument = Instrument.model_validate(raw)
                labels[instrument.id] = (
                    f"{instrument.underlying} {instrument.strike} {instrument.option_type} / {instrument.expiry}"
                )
            except (ValueError, TypeError):
                continue
        raw_quotes = context.details.get("quotes", [])
        raw_news = context.details.get("headlines", [])
        for raw in (raw_quotes if isinstance(raw_quotes, list) else [])[:40]:
            try:
                q = Quote.model_validate(raw)
                key = str(q.id)
                if key in quote_ids:
                    quotes[key] = {
                        "id": key,
                        "instrument": labels.get(q.instrument_id, "Contract details unavailable"),
                        "timestamp": q.timestamp.isoformat(),
                        "received_at": q.received_at.isoformat(),
                        "source": q.source[:100],
                        "timestamp_basis": q.timestamp_basis,
                        "age_at_output_seconds": age_seconds(event.timestamp, q.timestamp),
                        "receipt_lag_seconds": age_seconds(q.received_at, q.timestamp),
                        "bid": str(q.bid) if q.bid is not None else None,
                        "ask": str(q.ask) if q.ask is not None else None,
                        "last_price": str(q.last_price) if q.last_price is not None else None,
                    }
            except (ValueError, TypeError):
                continue
        for raw in (raw_news if isinstance(raw_news, list) else [])[:100]:
            try:
                h = Headline.model_validate(raw)
                parsed_url = urlsplit(h.url)
                if h.id in news_ids and h.provider_delay_seconds >= 0:
                    headlines[h.id] = {
                        "id": h.id,
                        "title": h.title[:400],
                        "source": h.source[:100],
                        "url": (
                            h.url
                            if parsed_url.scheme.lower() in {"http", "https"}
                            and parsed_url.netloc
                            else None
                        ),
                        "provider_name": h.provider_name,
                        "published_at": h.published_at.isoformat(),
                        "fetched_at": h.fetched_at.isoformat(),
                        "provider_delay_seconds": h.provider_delay_seconds,
                        "published_age_at_output_seconds": age_seconds(event.timestamp, h.published_at),
                        "retrieved_age_at_output_seconds": age_seconds(event.timestamp, h.fetched_at),
                        "publication_to_retrieval_seconds": age_seconds(h.fetched_at, h.published_at),
                    }
            except (ValueError, TypeError):
                continue
        return {
            "available": True,
            "quotes": list(quotes.values())[:40],
            "headlines": list(headlines.values())[:100],
            "missing": len(set(quote_ids) - quotes.keys()) + len(set(news_ids) - headlines.keys()),
        }
