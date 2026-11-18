"""Local operator commands. Secrets are entered privately, never via CLI arguments."""

import argparse
import asyncio
import getpass
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from services.core.contracts import IST, RiskConfig
from services.core.database import make_engine
from services.core.models import Account, AuditEvent
from services.market.angelone import AngelOneClient
from services.market.catalog import InstrumentCatalog
from services.market.diagnostics import NAMES, evidence_context, run_diagnostic
from services.market.readiness import readiness
from services.market.settings import MarketSettings, ProviderError
from services.paper.engine import PaperEngine
from services.worker.runtime import TradingRuntime
from services.worker.store import RuntimeStore


async def execute(args) -> None:
    settings = MarketSettings()
    now = datetime.now(UTC)
    if args.command == "status":
        report = readiness(now)
        if args.account:
            engine = make_engine()
            try:
                state = RuntimeStore(engine, args.account).state()
                with Session(engine) as db:
                    account_row = db.get(Account, args.account)
                    if account_row is None:
                        raise ProviderError("PAPER_ACCOUNT_NOT_CONFIGURED")
                    report = readiness(
                        now,
                        account={"config": account_row.config},
                        runtime={"heartbeat": state["heartbeat"]},
                        **evidence_context(db, args.account),
                    )
                report["account"] = {
                    key: state[key] for key in ("enabled", "daily_blocked", "resume_requested")
                }
            finally:
                engine.dispose()
        print(json.dumps(report, indent=2))
        return
    if args.command == "catalog":
        catalog = await InstrumentCatalog.fetch()
        today = now.astimezone(IST).date()
        rows = [
            item for item in catalog.instruments.values() if 0 <= (item.expiry - today).days <= 7
        ]
        print(
            json.dumps(
                {
                    "source": "angelone-public-instrument-master",
                    "fetched_at": catalog.fetched_at.isoformat(),
                    "eligible_contracts": {
                        name: sum(item.underlying == name for item in rows)
                        for name in ("NIFTY", "SENSEX")
                    },
                    "expiries": sorted({str(item.expiry) for item in rows}),
                    "rejected_records": catalog.rejected,
                },
                indent=2,
            )
        )
        return
    if args.command == "check":
        client = AngelOneClient(settings)
        try:
            await client.verify_session()
            print(
                json.dumps(
                    {
                        "broker_authentication": "VERIFIED",
                        "access": "READ_ONLY_PROFILE",
                        "market_data_checked": False,
                        "broker_orders_placed": False,
                    },
                    indent=2,
                )
            )
        finally:
            await client.close()
        return
    if args.command == "login":
        if settings.missing():
            raise ProviderError("MISSING_CONFIGURATION:" + ",".join(settings.missing()))
        client = AngelOneClient(settings)
        try:
            pin = getpass.getpass("Angel One PIN (not saved): ")
            totp = getpass.getpass("Current authenticator TOTP (not saved): ")
            await client.login(pin, totp)
            pin = totp = ""
            print("Broker session saved privately. No broker orders were placed.")
        finally:
            await client.close()
        return
    engine = make_engine(connect_args={"options": "-clock_timeout=5000 -cstatement_timeout=15000"})
    try:
        paper = PaperEngine(engine)
        if getattr(args, "local_owner", False):
            with Session(engine) as db:
                owners = list(
                    db.scalars(
                        select(AuditEvent.account_id)
                        .where(AuditEvent.kind == "LOCAL_OWNER_ENROLLED")
                        .distinct()
                    )
                )
                if len(owners) != 1:
                    raise ProviderError("LOCAL_OWNER_ACCOUNT_REQUIRED")
                args.account = owners[0]
        if args.command == "create-account":
            config = RiskConfig.model_validate_json(args.risk_file.read_text(encoding="utf-8"))
            account = paper.create_account(config, now)
            RuntimeStore(engine, account).initialize(now)
            print(f"Paper account created paused: {account}")
            return
        if args.command == "worker":
            if not args.observe_only and settings.missing():
                raise ProviderError("MISSING_CONFIGURATION:" + ",".join(settings.missing()))
            await TradingRuntime(
                engine,
                args.account,
                settings,
                observe_only=args.observe_only,
                validation_only=args.validation_only,
            ).run()
        elif args.command == "diagnose":
            try:
                result = await asyncio.to_thread(run_diagnostic, engine, args.account, args.name)
            except ValueError:
                raise ProviderError("CONNECTION_CHECK_UNAVAILABLE_OR_ALREADY_RUNNING") from None
            print(json.dumps(result, indent=2))
        elif args.command == "pause":
            from services.paper.qualification import QualificationService
            from services.paper.validation import ValidationService

            ValidationService(engine, args.account).tick(now, force_reason="USER_PAUSE")
            QualificationService(engine, args.account).tick(now, "USER_PAUSE")
            RuntimeStore(engine, args.account).update(
                resume_requested=False, active_envelope=None, status="PAUSED", problem=None
            )
            paper.set_enabled(args.account, False, now)
            print("Entries paused. Open-position monitoring continues while the worker runs.")
        elif args.command == "resume":
            raise ProviderError("USE_EXPLICIT_PAPER_ARMING")
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    status = commands.add_parser(
        "status", help="Show configuration presence without exposing values"
    )
    status.add_argument("--account", type=UUID)
    commands.add_parser("catalog", help="Read actual public instrument metadata")
    commands.add_parser("check", help="Read-only verification of the saved broker session")
    commands.add_parser("login", help="Privately establish a broker data session")
    create = commands.add_parser(
        "create-account", help="Create a paused account from your risk settings"
    )
    create.add_argument("--risk-file", type=Path, required=True)
    for name in ("worker", "pause", "resume"):
        command = commands.add_parser(name)
        if name == "worker":
            account_group = command.add_mutually_exclusive_group(required=True)
            account_group.add_argument("--account", type=UUID)
            account_group.add_argument("--local-owner", action="store_true")
            modes = command.add_mutually_exclusive_group()
            modes.add_argument(
                "--validation-only",
                action="store_true",
                help="Require an explicit bounded paper-validation session for entries",
            )
            modes.add_argument(
                "--observe-only",
                action="store_true",
                help="Keep entries and agent generation disabled; monitor existing exposure",
            )
        else:
            command.add_argument("--account", type=UUID, required=True)
    diagnose = commands.add_parser(
        "diagnose", help="Explicit read-only connection test; records safe results"
    )
    diagnose.add_argument("name", choices=NAMES)
    diagnostic_account = diagnose.add_mutually_exclusive_group(required=True)
    diagnostic_account.add_argument("--account", type=UUID)
    diagnostic_account.add_argument("--local-owner", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    try:
        asyncio.run(execute(args))
    except KeyboardInterrupt:
        print("Stopped.")
    except ProviderError as error:
        parser.exit(1, f"Market connection unavailable: {error}\n")
    except Exception as error:
        parser.exit(
            1, f"Command could not complete ({type(error).__name__}). Check local configuration.\n"
        )


if __name__ == "__main__":
    main()
