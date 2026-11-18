"""Calendar boundaries and fee drafts cannot masquerade as executable readiness."""

import json
from datetime import UTC, date, datetime

import pytest

from services.core.execution import FeeSchedule
from services.market.calendar import SessionCalendar
from services.paper.settings import configuration_status


def test_calendar_reports_imported_sessions_and_never_infers_dates(tmp_path):
    path = tmp_path / "calendar.json"
    sessions = []
    for venue in ("NFO", "BFO"):
        for day in ("2026-11-18", "2026-11-19"):
            sessions.append(
                {
                    "exchange": venue,
                    "official_source_url": "https://www.nseindia.com/test",
                    "session": {
                        "key": day,
                        "opens_at": day + "T09:15:00+05:30",
                        "closes_at": day + "T15:40:00+05:30",
                        "verified": True,
                        "calendar_source": "isolated test",
                    },
                }
            )
    path.write_text(json.dumps({"schema_version": 1, "sessions": sessions}), encoding="utf-8")
    calendar = SessionCalendar(path)
    opened = datetime(2026, 11, 18, 3, 45, tzinfo=UTC)
    closed = datetime(2026, 11, 18, 10, 10, tzinfo=UTC)
    assert calendar.state("NFO", opened) == "open"
    assert calendar.state("NFO", closed) == "closed"
    report = calendar.describe("BFO", closed)
    assert report["next_verified_open"] == "2026-11-19T09:15:00+05:30"
    assert report["last_covered_day"] == "2026-11-19"
    gap = calendar.describe("NFO", datetime(2026, 11, 20, 4, tzinfo=UTC))
    assert gap["state"] == "unknown"
    assert gap["next_verified_open"] is None
    assert gap["opens_at"] is None
    # Midnight UTC is not the exchange day boundary.
    assert calendar.describe("NFO", datetime(2026, 11, 18, 19, tzinfo=UTC))["day"] == "2026-11-19"


def test_unverified_fee_draft_lists_component_and_evidence_blockers():
    draft = {
        "version": "isolated-draft",
        "exchange": "BFO",
        "effective_from": "2026-11-18",
        "notes": "Test only, no production tariff claims",
        "rules": [
            {
                "code": "BROKERAGE",
                "sides": ["BUY", "SELL"],
                "calculation": "flat_per_order",
                "amount": "20.00",
                "rounding_increment": "0.01",
                "rounding_mode": "HALF_UP",
                "rounding_scope": "cumulative_order",
                "sources": [
                    {
                        "url": "https://example.test/fee",
                        "checked_at": "2026-11-18T00:00:00Z",
                        "finding": "Unverified fixture",
                        "status": "unverified",
                    }
                ],
            }
        ],
    }
    schedule = FeeSchedule.model_validate(draft)
    assert schedule.applies(date(2026, 11, 18))
    assert not schedule.applies(date(2026, 11, 17))
    problems = schedule.blockers()
    assert "BFO_ACCOUNT_PRICING_UNVERIFIED" in problems
    assert "BFO_FEE_COMPONENT_IPFT_MISSING" in problems
    assert "BFO_FEE_EVIDENCE_UNVERIFIED" in problems
    assert "BFO_FEE_SCHEDULE_NOT_REVIEWED" in problems
    # Setting a review flag cannot bypass incomplete component/evidence validation.
    with pytest.raises(ValueError):
        FeeSchedule.model_validate({**draft, "reviewed": True, "account_pricing_verified": True})


def test_evidence_checklist_matches_blockers_and_preserves_unverified_findings(tmp_path):
    path = tmp_path / "execution.json"
    source = {
        "url": "https://example.test/isolated-tariff",
        "checked_at": "2026-11-18T00:00:00Z",
        "finding": "Fixture rounding scope has not been verified",
        "status": "unverified",
    }
    document = {
        "version": "isolated-inventory",
        "execution": {"version": "test", "notes": "Isolated test"},
        "fee_schedules": [
            {
                "version": "test-bfo",
                "exchange": "BFO",
                "effective_from": "2026-11-18",
                "effective_until": "2026-11-19",
                "notes": "Test only",
                "rules": [
                    {
                        "code": "BROKERAGE",
                        "sides": ["BUY", "SELL"],
                        "calculation": "flat_per_order",
                        "amount": "1",
                        "rounding_increment": "0.01",
                        "rounding_mode": "HALF_UP",
                        "rounding_scope": "cumulative_order",
                        "sources": [source],
                    }
                ],
            }
        ],
    }
    path.write_text(json.dumps(document), encoding="utf-8")
    before = path.read_bytes()
    report = configuration_status(date(2026, 11, 18), path)
    rows = {row["code"]: row for row in report["requirements"]}
    assert set(rows) == set(report["blockers"]) - {"FINAL_CONNECTED_QA_PENDING"}
    assert "Order-entry quantity documentation alone" in rows["QUANTITY_UNIT_UNVERIFIED"]["detail"]
    assert rows["BFO_FEE_EVIDENCE_UNVERIFIED"]["detail"] == source["finding"]
    assert rows["BFO_FEE_EVIDENCE_UNVERIFIED"]["fields"] == [
        "fee_schedules[test-bfo].rules.BROKERAGE"
    ]
    assert rows["BFO_FEE_EVIDENCE_UNVERIFIED"]["sources"] == [source["url"]]
    assert "zero charge" in rows["BFO_FEE_COMPONENT_IPFT_MISSING"]["detail"]
    assert report["engine_ready"] is False
    assert path.read_bytes() == before
    # Expiry is a missing current schedule, not a list of issues in an inactive draft.
    expired = configuration_status(date(2026, 11, 20), path)
    assert "BFO_FEE_SCHEDULE_MISSING" in {r["code"] for r in expired["requirements"]}
    assert not any(r["code"] == "BFO_FEE_EVIDENCE_UNVERIFIED" for r in expired["requirements"])


def test_valid_configuration_checklist_cannot_grant_autonomous_permission(tmp_path):
    from services.core.execution import REQUIRED_FEE_CODES

    source = {
        "url": "https://example.test/isolated-evidence",
        "checked_at": "2026-11-18T00:00:00Z",
        "finding": "Isolated test inputs only, not actual market evidence",
        "status": "documented",
    }
    document = {
        "version": "test",
        "execution": {
            "version": "test",
            "notes": "Isolated fixture",
            "reviewed": True,
            "assumed_latency_ms": 250,
            "displayed_participation": "0.1",
            "extra_adverse_slippage_bps": "5",
            "market_protection_bps": "100",
            "quote_max_age_ms": 2000,
            "pending_entry_lifetime_ms": 5000,
            "partial_fill_granularity": "lots",
            "quantity_unit": "units",
            "quantity_unit_sources": [source],
        },
        "fee_schedules": [
            {
                "version": "fixture-" + venue,
                "exchange": venue,
                "effective_from": "2026-11-18",
                "reviewed": True,
                "account_pricing_verified": True,
                "notes": "No production tariff claim",
                "rules": [
                    {
                        "code": code,
                        "sides": ["BUY", "SELL"],
                        "calculation": "flat_per_order",
                        "amount": "1",
                        "rounding_increment": "0.01",
                        "rounding_mode": "HALF_UP",
                        "rounding_scope": "cumulative_order",
                        "sources": [source],
                    }
                    for code in sorted(REQUIRED_FEE_CODES)
                ],
            }
            for venue in ("NFO", "BFO")
        ],
    }
    path = tmp_path / "execution.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    report = configuration_status(date(2026, 11, 18), path)
    assert report["configuration_ready"] is True
    assert report["requirements"] == []
    assert report["engine_ready"] is False
    assert report["blockers"] == ["FINAL_CONNECTED_QA_PENDING"]
    qualified = configuration_status(date(2026, 11, 18), path, qualification_valid=True)
    assert qualified["engine_ready"] is True
    assert qualified["blockers"] == []


def test_unreadable_configuration_has_an_actionable_evidence_requirement(tmp_path):
    path = tmp_path / "missing.json"
    for contents in (None, "{invalid", "{}"):
        if contents is not None:
            path.write_text(contents, encoding="utf-8")
        report = configuration_status(date(2026, 11, 18), path)
        assert report["configuration_valid"] is False
        assert len(report["requirements"]) == 1
        assert report["requirements"][0]["code"] == "PAPER_EXECUTION_CONFIG_UNAVAILABLE_OR_INVALID"
        assert report["requirements"][0]["action"]
