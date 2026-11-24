"""Real paper ledger tests in disposable schemas, not market acceptance."""

# ruff: noqa: F811

from datetime import timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_durable import durable, observed  # noqa: F401

from services.core.contracts import UnderlyingExitPolicy
from services.core.models import Account, PaperPosition
from services.market.reference_contracts import IndexReference
from services.paper.accounting import reconcile_account
from services.worker.models import RuntimeControl

pytestmark = pytest.mark.integration


def test_underlying_only_order_fills_and_uses_actual_average_stop(durable):
    d = durable
    policy = UnderlyingExitPolicy(
        underlying="NIFTY", direction="BULLISH", invalidation="24995", target="25110",
        premium_stop_fraction="0.20",
        entry_deadline_only=True,
    )
    envelope = d.scenario.envelope.model_copy(update={
        "stop_loss": Decimal("80"), "min_entry": Decimal("90"), "max_entry": Decimal("100"),
        "target": None, "underlying_exit_policy": policy,
        "expires_at": d.scenario.now + timedelta(seconds=1),
    })
    decision = d.scenario.decision.model_copy(update={"stop_loss": Decimal("80"), "target": None})
    with Session(d.engine) as db, db.begin():
        account = db.get(Account, d.account)
        account.config = {**account.config, "max_trade_risk_pct": "0.01"}
        db.get(RuntimeControl, d.account).active_envelope = envelope.model_dump(mode="json")
    quote = observed(d)
    envelope = envelope.model_copy(update={"evidence_ids": (quote.id,)})
    decision = decision.model_copy(update={"snapshot_ids": (quote.id,)})
    with Session(d.engine) as db, db.begin():
        db.get(RuntimeControl, d.account).active_envelope = envelope.model_dump(mode="json")
    result = d.service.admit(decision, d.instrument, quote, envelope,
                             d.scenario.session, {d.instrument.id: quote})
    assert result["status"] == "OPEN", result
    order_id = UUID(result["order_id"])
    d.clock.now = d.scenario.now.replace(microsecond=300000)
    fill_quote = observed(d, elapsed=300, bid="98.95", ask="99.00")
    d.service.matcher.match_order(d.account, order_id, d.instrument, fill_quote)
    with Session(d.engine) as db:
        position = db.scalar(select(PaperPosition))
        assert position is not None
        assert position.target is None
        assert position.average_price == Decimal("99")
        assert position.stop_loss == Decimal("79.20")
        assert reconcile_account(db, db.get(Account, d.account)) == []
    d.clock.now = d.scenario.now + timedelta(seconds=2)
    fill_quote = observed(d, elapsed=2000, bid="98.95", ask="99.00")
    reference = IndexReference(underlying="NIFTY", exchange="NSE", provider_token="test",
                               timestamp=d.clock.now, received_at=d.clock.now, last_price="25010")
    d.service.cycle({d.instrument.id: fill_quote}, {"NFO": d.scenario.session},
                    healthy=True, references={"NIFTY": reference})
    with Session(d.engine) as db:
        assert db.scalar(select(PaperPosition)).pending_exit is None
    reference = IndexReference(underlying="NIFTY", exchange="NSE", provider_token="test",
                               timestamp=d.clock.now, received_at=d.clock.now, last_price="25110")
    d.service.cycle({d.instrument.id: fill_quote}, {"NFO": d.scenario.session},
                    healthy=True, references={"NIFTY": reference})
    with Session(d.engine) as db:
        assert db.scalar(select(PaperPosition)).pending_exit == "UNDERLYING_TARGET"
