"""Shared local readiness evaluator. Evaluation never calls external providers."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from services.agents.settings import AgentSettings
from services.core.contracts import IST
from services.core.setup import NewsPolicy, digest
from services.market.calendar import SessionCalendar
from services.market.credentials import SessionStore
from services.market.settings import MarketSettings, ProviderError
from services.paper.settings import configuration_status

Status = Literal["passed", "failed", "not_checked", "waiting_for_market", "not_applicable"]


class ReadinessCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    title: str
    status: Status
    detail: str
    action: str
    checked_at: datetime | None = None
    diagnostic: str | None = None


def connection_fingerprint(name: str) -> str:
    """Bind evidence to relevant inputs; only the digest may be persisted."""
    if name in {"broker", "stream"}:
        market = MarketSettings()
        values = market.model_dump(mode="json")
        values["api_key"] = market.api_key.get_secret_value()
        values["client_code"] = market.client_code.get_secret_value()
        try:
            values["session"] = market.session_file.read_text(encoding="utf-8")
        except OSError:
            values["session"] = None
    elif name in {"ai", "ai_schema"}:
        agents = AgentSettings()
        values = {"key": agents.openai_api_key.get_secret_value(), "model": agents.openai_model}
    elif name == "news":
        agents = AgentSettings()
        values = {
            "sources": Path(agents.swan_news_config).read_text(encoding="utf-8"),
            "key": agents.news_api_key.get_secret_value(),
        }
    else:
        values = {"provider": "angelone-instrument-master-v1"}
    return digest(values)


def readiness(
    now: datetime,
    *,
    account: dict | None = None,
    runtime: dict | None = None,
    evidence: dict | None = None,
    risk_review: str | None = None,
    latest_quote_at: datetime | None = None,
    qualification: dict | None = None,
) -> dict:
    checks: list[ReadinessCheck] = []

    def add(code, title, passed, detail, action):
        checks.append(
            ReadinessCheck(
                code=code,
                title=title,
                status="passed" if passed else "failed",
                detail=detail,
                action=action,
                checked_at=now,
            )
        )

    missing = []
    broker = "NOT_CONFIGURED"
    try:
        settings = MarketSettings()
        missing = settings.missing() + settings.missing_references()
        add(
            "BROKER_CONFIGURATION",
            "Broker configuration",
            not missing,
            "Broker settings and both index references are present."
            if not missing
            else "Missing settings: " + ", ".join(missing),
            "Configure server-side broker settings and index reference tokens.",
        )
        try:
            session = SessionStore(
                settings.session_file, settings.client_code.get_secret_value()
            ).load()
            broker = (
                "SAVED"
                if session.expires_at > now
                and (session.created_at.astimezone(IST).date() == now.astimezone(IST).date())
                else "EXPIRED"
            )
        except ProviderError:
            pass
        add(
            "BROKER_SESSION",
            "Saved broker session",
            broker == "SAVED",
            "A current session is saved; authentication still needs its connection test."
            if broker == "SAVED"
            else "Broker login is expired or unavailable.",
            "Run market.cmd login privately, then test Broker authentication.",
        )
    except (ValueError, OSError):
        settings = None
        add(
            "BROKER_CONFIGURATION",
            "Broker configuration",
            False,
            "Broker settings are invalid.",
            "Correct server-side broker settings.",
        )

    exchanges = []
    calendar_details: list[dict] = []
    try:
        if settings is None:
            raise ValueError("Invalid broker settings")
        calendar = SessionCalendar(settings.calendar_file)
        day = now.astimezone(IST).date()
        exchanges = [venue for venue in ("NFO", "BFO") if calendar.get(venue, day)]
        states = [calendar.state(venue, now) for venue in ("NFO", "BFO")]
        calendar_details = [calendar.describe(venue, now) for venue in ("NFO", "BFO")]
    except (ProviderError, ValueError, OSError):
        states = ["unknown", "unknown"]
    market_state = states[0] if len(set(states)) == 1 else "partial"
    calendar_ready = "unknown" not in states
    add(
        "EXCHANGE_CALENDAR",
        "Exchange calendar",
        calendar_ready,
        "Both venues have verified coverage today. "
        + " ".join(
            f"{row['exchange']}: "
            + (
                f"{datetime.fromisoformat(row['opens_at']).astimezone(IST):%H:%M}–"
                f"{datetime.fromisoformat(row['closes_at']).astimezone(IST):%H:%M} IST."
                if row["opens_at"]
                else f"Closed ({row['closure_reason']})."
            )
            + (
                f" Next imported opening: {datetime.fromisoformat(row['next_verified_open']).astimezone(IST):%d %b %H:%M} IST."
                if row["next_verified_open"]
                else " No future session imported."
            )
            for row in calendar_details
        )
        if calendar_ready
        else "Missing or invalid session/closure coverage for: "
        + ", ".join(venue for venue, state in zip(("NFO", "BFO"), states) if state == "unknown")
        + ".",
        "Import a sourced calendar, including explicit closure dates for holidays.",
    )

    execution = configuration_status(now.astimezone(IST).date())
    if qualification is not None and qualification.get("valid") is True:
        execution = configuration_status(
            now.astimezone(IST).date(), qualification_valid=qualification.get("valid") is True
        )
    add(
        "EXECUTION_CONFIGURATION",
        "Execution policy and fees",
        execution["configuration_ready"],
        "Reviewed execution inputs and effective fees are configured."
        if execution["configuration_ready"]
        else "Required: "
        + ", ".join(
            code.lower().replace("_", " ")
            for code in execution["blockers"]
            if code != "FINAL_CONNECTED_QA_PENDING"
        ),
        "Review execution assumptions and import sourced NFO/BFO fee schedules.",
    )
    if account is not None:
        reviewed = risk_review == digest(account["config"])
        add(
            "RISK_POLICY_REVIEW",
            "Account risk policy",
            reviewed,
            "The current policy has been explicitly reviewed."
            if reviewed
            else "The policy has unreviewed startup limits, including its quantity cap.",
            "Review the complete policy in Risk settings and save your approval.",
        )

    try:
        agents = AgentSettings()
        ai_missing = [
            name
            for name, present in (
                ("API key", bool(agents.openai_api_key.get_secret_value())),
                ("model", bool(agents.openai_model)),
                ("daily token budget", agents.swan_ai_daily_token_budget > 0),
            )
            if not present
        ]
        add(
            "AI_CONFIGURATION",
            "Agent configuration",
            not ai_missing,
            "Model and bounded token settings are configured."
            if not ai_missing
            else "Missing: " + ", ".join(ai_missing),
            "Choose a model and token budget in Agent settings below.",
        )
        news = NewsPolicy.model_validate_json(
            Path(agents.swan_news_config).read_text(encoding="utf-8")
        )
        news_ready = (
            bool(agents.news_api_key.get_secret_value())
            if news.provider == "newsdata_free"
            else bool(news.sources)
        )
        add(
            "NEWS_CONFIGURATION",
            "News configuration",
            news_ready,
            "NewsData.io free API configured: 12-hour delayed background context, not live news."
            if news_ready and news.provider == "newsdata_free"
            else "Permitted news sources are configured."
            if news_ready
            else "No news sources configured.",
            "Import permitted news sources with license and timestamp information.",
        )
    except (ValueError, OSError):
        if not any(c.code == "AI_CONFIGURATION" for c in checks):
            add(
                "AI_CONFIGURATION",
                "Agent configuration",
                False,
                "Agent settings are invalid.",
                "Correct Agent settings.",
            )
        add(
            "NEWS_CONFIGURATION",
            "News configuration",
            False,
            "News settings are missing or invalid.",
            "Import a valid permitted news configuration.",
        )

    config_codes = {
        "BROKER_CONFIGURATION",
        "BROKER_SESSION",
        "EXCHANGE_CALENDAR",
        "EXECUTION_CONFIGURATION",
        "RISK_POLICY_REVIEW",
        "AI_CONFIGURATION",
        "NEWS_CONFIGURATION",
    }
    configuration_complete = all(c.status == "passed" for c in checks if c.code in config_codes)
    evidence = evidence or {}
    for name, title in (
        ("broker", "Broker authentication"),
        ("catalog", "Instrument metadata"),
        ("stream", "Stream transport"),
        ("ai", "OpenAI access"),
        ("ai_schema", "Model structured output"),
        ("news", "News retrieval"),
    ):
        result = evidence.get(name)
        valid = False
        checked_stamp = None
        if result:
            try:
                checked_stamp = datetime.fromisoformat(result["checked_at"])
                valid = timedelta(0) <= now - checked_stamp <= timedelta(minutes=15) and result[
                    "fingerprint"
                ] == connection_fingerprint(name)
            except (ValueError, KeyError, OSError, TypeError):
                pass
        checks.append(
            ReadinessCheck(
                code="CONNECTION_" + name.upper(),
                title=title,
                status=result["status"] if valid and result else "not_checked",
                detail=result["detail"]
                if valid and result
                else "No current connection test for these settings.",
                action="Run this connection test. Results expire after 15 minutes or relevant setting changes.",
                checked_at=checked_stamp if valid else None,
                diagnostic=name,
            )
        )
    connections_verified = all(c.status == "passed" for c in checks if c.diagnostic)
    heartbeat = runtime.get("heartbeat") if runtime else None
    try:
        heartbeat_stamp = (
            datetime.fromisoformat(heartbeat) if isinstance(heartbeat, str) else heartbeat
        )
        worker_online = heartbeat_stamp is not None and timedelta(
            0
        ) <= now - heartbeat_stamp <= timedelta(seconds=10)
    except (ValueError, TypeError):
        worker_online = False
    if account is not None:
        add(
            "WORKER_PROCESS",
            "Trading worker",
            worker_online,
            "A recent heartbeat is present; this does not establish feed freshness."
            if worker_online
            else "The worker is not reporting a recent heartbeat.",
            "Start local services to run the paused observation worker.",
        )
    fresh = latest_quote_at is not None and timedelta(0) <= now - latest_quote_at <= timedelta(
        seconds=2
    )
    checks.append(
        ReadinessCheck(
            code="FRESH_MARKET_DATA",
            title="Fresh executable market data",
            status="waiting_for_market" if market_state == "closed" else "not_checked",
            detail="The verified exchange sessions are closed."
            if market_state == "closed"
            else "Recent observations exist; each instrument still needs admission-time depth checks."
            if fresh
            else "No current market observation has been verified.",
            action="Verify instrument-specific live depth during an open session.",
            checked_at=latest_quote_at,
        )
    )
    checks.append(
        ReadinessCheck(
            code="CONNECTED_PAPER_VALIDATION",
            title="Actual-market paper validation",
            status="passed"
            if execution.get("final_connected_qa_complete", False)
            else "not_checked",
            detail="Current qualification covers only the reviewed instruments and strategy versions. Explicit arming is still required."
            if execution.get("final_connected_qa_complete", False)
            else "Connected fill and protection validation remains a separate release gate.",
            action="Complete controlled paper validation with actual fresh market evidence.",
        )
    )
    failed = next((c for c in checks if c.status == "failed" and c.code in config_codes), None)
    if failed:
        title, detail = failed.title + " needs attention", failed.detail + " " + failed.action
    elif not connections_verified:
        title, detail = (
            "Connection tests required",
            "Run the individual connection checks in System setup.",
        )
    elif not worker_online:
        title, detail = (
            "Start the observation worker",
            "Configuration and connection checks passed.",
        )
    elif market_state == "closed":
        title, detail = (
            "Setup complete · Market closed",
            "Qualified scope remains subject to fresh-session checks and explicit arming."
            if execution.get("final_connected_qa_complete", False)
            else "Awaiting fresh-market paper validation. Entries remain paused.",
        )
    elif execution["engine_ready"]:
        title, detail = (
            "Paper scope qualified",
            "Review the qualified scope and explicitly arm paper entries in Paper controls.",
        )
    else:
        title, detail = (
            "Awaiting market validation",
            "Complete actual-market checks before autonomous paper entries.",
        )
    return {
        "as_of": now.isoformat(),
        "checks": [c.model_dump(mode="json") for c in checks],
        "configuration_complete": configuration_complete,
        "connections_verified": connections_verified,
        "worker_online": worker_online,
        "market_state": market_state,
        "title": title,
        "detail": detail,
        "missing_configuration": missing,
        "broker_session": broker,
        "calendar_exchanges_today": exchanges,
        "calendar_venues": calendar_details,
        "live_connection_checked": any(
            c.code == "CONNECTION_BROKER" and c.status == "passed" for c in checks
        ),
        "paper_execution": execution,
    }
