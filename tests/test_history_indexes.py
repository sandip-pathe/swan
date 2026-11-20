"""Bounded history query plans on disposable synthetic audit data, not live load acceptance."""

from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text, tuple_

from services.core.models import AuditEvent

pytestmark = pytest.mark.integration


def nodes(plan):
    yield plan
    for child in plan.get("Plans", []):
        yield from nodes(child)


def test_history_indexes_bound_first_and_older_pages_and_survive_roundtrip(paper, scenario):
    engine, owner = paper[0].engine, paper[1]
    evaluation = uuid4()
    with engine.begin() as connection:
        # Reversible migration, including re-creation, in this disposable schema only.
        config = Config("alembic.ini")
        config.attributes["connection"] = connection
        command.downgrade(config, "e6d0fab21811")
        command.upgrade(config, "head")
        connection.execute(
            AuditEvent.__table__.insert(),
            [
                {
                    "id": UUID(int=i + 1),
                    "account_id": owner,
                    "timestamp": scenario.now,
                    "kind": kind,
                    "details": {
                        "evaluation_id": str(evaluation if i < 300 else uuid4()),
                        "request": {"evaluation_id": str(evaluation if i < 300 else uuid4())},
                    },
                }
                for i in range(30000)
                for kind in ["AI_OUTPUT" if i % 2 == 0 else "AI_RESERVATION"]
            ],
        )
        connection.execute(text("ANALYZE audit_events"))
        for nested, expected in [
            (False, "audit_evaluation_history"),
            (True, "audit_request_history"),
        ]:
            expression = (
                AuditEvent.details["request"]["evaluation_id"]
                if nested
                else AuditEvent.details["evaluation_id"]
            ).as_string()
            for older in [False, True]:
                query = select(AuditEvent).where(
                    AuditEvent.account_id == owner,
                    AuditEvent.kind == ("AI_RESERVATION" if nested else "AI_OUTPUT"),
                    expression == str(evaluation),
                )
                if older:
                    query = query.where(
                        tuple_(AuditEvent.timestamp, AuditEvent.id) < (scenario.now, UUID(int=200))
                    )
                # Requests use ascending order; output pages use descending order.
                query = query.order_by(
                    AuditEvent.timestamp if nested else AuditEvent.timestamp.desc(),
                    AuditEvent.id if nested else AuditEvent.id.desc(),
                ).limit(21)
                sql = str(query.compile(connection, compile_kwargs={"literal_binds": True}))
                plan = connection.execute(
                    text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql)
                ).scalar_one()[0]
                tree = list(nodes(plan["Plan"]))
                assert any(node.get("Index Name") == expected for node in tree), plan
                assert not any(node["Node Type"] in ("Seq Scan", "Sort") for node in tree), plan
                assert plan["Plan"]["Actual Rows"] == 21
                assert sum(node.get("Rows Removed by Filter", 0) for node in tree) < 100
                print(
                    {
                        "index": expected,
                        "older": older,
                        "rows": 21,
                        "milliseconds": plan["Execution Time"],
                        "shared_blocks": plan["Plan"].get("Shared Hit Blocks", 0),
                    }
                )
