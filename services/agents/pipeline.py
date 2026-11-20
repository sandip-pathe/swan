import asyncio
import hashlib
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from services.agents.checks import FAILURES
from services.agents.contracts import Analysis, Proposal, Review
from services.agents.news import NewsReader
from services.agents.provider import StructuredProvider
from services.agents.settings import AgentSettings
from services.core.contracts import ExchangeSession, Instrument, Quote, RiskConfig, StrategyEnvelope
from services.core.models import AuditEvent
from services.market.settings import ProviderError

STRATEGY_VERSION = "agents-v1"
PIPELINE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


class AgentPipeline:
    def __init__(self, engine: Engine, account_id: UUID):
        self.settings = AgentSettings()
        self.provider = StructuredProvider(engine, account_id, self.settings)
        self.news = NewsReader(self.settings.swan_news_config, self.settings.news_api_key)

    async def evaluate(
        self,
        instruments: dict[str, Instrument],
        quotes: list[Quote],
        session: ExchangeSession,
        config: RiskConfig,
        evaluation_id: UUID | None = None,
    ) -> StrategyEnvelope | None:
        if not self.settings.ready():
            raise ProviderError("AI_NOT_CONFIGURED")
        async with asyncio.timeout(100):
            headlines = await self.news.read()
            # Small, deterministic evidence selection, never generated prices or gap filling.
            selected = sorted(
                quotes, key=lambda row: (row.timestamp, row.instrument_id), reverse=True
            )[:40]
            evidence = {str(row.id): row for row in selected}
            if not evidence:
                raise ProviderError("AI_NO_MARKET_EVIDENCE")
            context = {
                "as_of": datetime.now(UTC).isoformat(),
                "implementation": {
                    "strategy_version": STRATEGY_VERSION,
                    "pipeline_sha256": PIPELINE_SHA256,
                },
                "evaluation_id": str(evaluation_id) if evaluation_id else None,
                "session": session.model_dump(mode="json"),
                "risk": config.model_dump(mode="json"),
                "instruments": [
                    instruments[row.instrument_id].model_dump(mode="json") for row in selected
                ],
                "quotes": [row.model_dump(mode="json") for row in selected],
                "headlines": [row.model_dump(mode="json") for row in headlines],
            }
            context["context_id"] = str(await asyncio.to_thread(self.persist_context, context))
            async with self.stage(context, "analysis"):
                analysis = await self.provider.generate("analysis", context, Analysis)
                self.check_citations(analysis.evidence_ids, evidence)
                if not set(analysis.news_ids) <= {row.id for row in headlines}:
                    raise ProviderError("AI_UNKNOWN_NEWS_CITATION")
                context["analysis"] = analysis.model_dump()
            async with self.stage(context, "proposal"):
                proposal = await self.provider.generate("proposal", context, Proposal)
                self.check_citations(proposal.evidence_ids, evidence)
                fields = (
                    proposal.instrument_id,
                    proposal.min_entry,
                    proposal.max_entry,
                    proposal.stop_loss,
                    proposal.target,
                )
                if proposal.action == "WAIT":
                    if any(value is not None for value in fields):
                        raise ProviderError("AI_INVALID_WAIT")
                    return None
                if any(value is None for value in fields):
                    raise ProviderError("AI_INCOMPLETE_PROPOSAL")
                instrument = instruments.get(proposal.instrument_id or "")
                if instrument is None or instrument.id not in {
                    evidence[identifier].instrument_id for identifier in proposal.evidence_ids
                }:
                    raise ProviderError("AI_UNSUPPORTED_INSTRUMENT")
                if proposal.action != "BUY_" + instrument.option_type:
                    raise ProviderError("AI_OPTION_DIRECTION_MISMATCH")
                context["proposal"] = proposal.model_dump()
            async with self.stage(context, "review"):
                review = await self.provider.generate("review", context, Review)
                self.check_citations(review.evidence_ids, evidence)
                if not review.approved:
                    return None
                if not set(proposal.evidence_ids) <= set(review.evidence_ids):
                    raise ProviderError("AI_REVIEW_MISSING_EVIDENCE")
            async with self.stage(context, "strategy"):
                # Lifetime starts at evidence capture, never renewed by model latency.
                issued = min(
                    evidence[identifier].received_at for identifier in proposal.evidence_ids
                )
                expires = min(
                    issued + timedelta(seconds=180),
                    session.closes_at - timedelta(minutes=config.entry_cutoff_minutes),
                )
                if expires <= datetime.now(UTC):
                    raise ProviderError("AI_STRATEGY_EXPIRED")
                return StrategyEnvelope.model_validate(
                    {
                        "version": STRATEGY_VERSION,
                        "instrument_ids": (instrument.id,),
                        "action": proposal.action,
                        "issued_at": issued,
                        "expires_at": expires,
                        "evidence_ids": tuple(UUID(value) for value in proposal.evidence_ids),
                        "min_entry": proposal.min_entry,
                        "max_entry": proposal.max_entry,
                        "stop_loss": proposal.stop_loss,
                        "target": proposal.target,
                        "max_holding_seconds": min(config.max_holding_seconds, 300),
                    }
                )

    @asynccontextmanager
    async def stage(self, context: dict, stage: str):
        try:
            yield
        except ProviderError as error:
            code = str(error)
            if code.startswith("AI_HTTP_") and code[8:].isdigit():
                code = "UNAVAILABLE"
            await asyncio.to_thread(
                self.persist_check,
                context,
                stage,
                "FAILED",
                code if code in FAILURES else "UNAVAILABLE",
            )
            raise
        except ValueError:
            await asyncio.to_thread(
                self.persist_check, context, stage, "FAILED", "INVALID_RESPONSE"
            )
            raise
        except asyncio.CancelledError:
            await asyncio.to_thread(
                self.persist_check, context, stage, "INTERRUPTED", "INTERRUPTED"
            )
            raise
        else:
            await asyncio.to_thread(self.persist_check, context, stage, "PASSED", None)

    def persist_check(self, context: dict, stage: str, state: str, reason: str | None):
        if not context.get("evaluation_id"):
            return
        with Session(self.provider.engine) as db, db.begin():
            db.add(
                AuditEvent(
                    account_id=self.provider.account_id,
                    kind="AI_STAGE_CHECK",
                    timestamp=datetime.now(UTC),
                    details={
                        "evaluation_id": context["evaluation_id"],
                        "context_id": context["context_id"],
                        "stage": stage,
                        "state": state,
                        "reason": reason,
                    },
                )
            )

    def persist_context(self, context: dict) -> UUID:
        with Session(self.provider.engine) as db, db.begin():
            event = AuditEvent(
                account_id=self.provider.account_id,
                kind="AI_CONTEXT",
                timestamp=datetime.now(UTC),
                details=context,
            )
            db.add(event)
            db.flush()
            return event.id

    @staticmethod
    def check_citations(identifiers: list[str], evidence: dict[str, Quote]) -> None:
        if not identifiers or not set(identifiers) <= evidence.keys():
            raise ProviderError("AI_UNKNOWN_OR_MISSING_EVIDENCE")
