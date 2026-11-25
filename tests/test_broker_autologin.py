from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from services.market.autologin import authenticate, calendar_skip, read_credentials, run
from services.market.settings import AuthenticationRequired, ProviderError

SEED = "JBSWY3DPEHPK3PXP"  # Public test fixture, never a real credential.


def client():
    return SimpleNamespace(
        store=SimpleNamespace(
            load=Mock(side_effect=AuthenticationRequired("BROKER_LOGIN_REQUIRED"))
        ),
        login=AsyncMock(),
        verify_session=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_missing_session_logs_in_with_generated_code_and_verifies():
    broker = client()
    assert await authenticate(broker, "test-pin", SEED) == "NEW_SESSION_VERIFIED"
    code = broker.login.call_args.args[1]
    assert len(code) == 6 and code.isdigit()
    broker.verify_session.assert_awaited_once()


@pytest.mark.asyncio
async def test_current_verified_session_is_reused():
    broker = client()
    now = datetime.now(UTC)
    broker.store.load = Mock(
        return_value=SimpleNamespace(created_at=now, expires_at=now + timedelta(hours=1))
    )
    assert await authenticate(broker, "test-pin", SEED) == "EXISTING_SESSION_VERIFIED"
    broker.login.assert_not_awaited()


@pytest.mark.asyncio
async def test_yesterday_requires_fresh_login_even_with_future_expiry():
    broker = client()
    now = datetime.now(UTC)
    broker.store.load = Mock(
        return_value=SimpleNamespace(
            created_at=now - timedelta(days=1), expires_at=now + timedelta(hours=1)
        )
    )
    assert await authenticate(broker, "test-pin", SEED) == "NEW_SESSION_VERIFIED"
    broker.login.assert_awaited_once()


@pytest.mark.asyncio
async def test_invalid_credentials_do_not_retry():
    broker = client()
    broker.login.side_effect = AuthenticationRequired("BROKER_AUTH_REJECTED")
    with pytest.raises(AuthenticationRequired):
        await authenticate(broker, "test-pin", SEED)
    assert broker.login.await_count == 1


@pytest.mark.asyncio
async def test_transient_failure_is_bounded(monkeypatch):
    broker = client()
    broker.login.side_effect = ProviderError("PROVIDER_NETWORK_UNAVAILABLE")
    sleep = AsyncMock()
    monkeypatch.setattr("services.market.autologin.asyncio.sleep", sleep)
    with pytest.raises(ProviderError, match="PROVIDER_NETWORK_UNAVAILABLE"):
        await authenticate(broker, "test-pin", SEED)
    assert broker.login.await_count == 3
    assert sleep.await_count == 2


def test_invalid_private_file_does_not_expose_contents(tmp_path):
    path = tmp_path / "credentials.json"
    path.write_text('{"pin":"do-not-print-this","totp_secret":"invalid!"}')
    path.chmod(0o600)
    with pytest.raises(ProviderError, match="^AUTOLOGIN_CREDENTIALS_INVALID_OR_NOT_PRIVATE$"):
        read_credentials(path)


@pytest.mark.parametrize(
    "stamp,expected",
    [
        ("2026-11-24T08:55:00+05:30", "SKIPPED_MARKET_CLOSED"),
        ("2026-11-22T08:55:00+05:30", "SKIPPED_MARKET_CLOSED"),
        ("2026-11-25T08:55:00+05:30", None),
        ("2026-11-25T18:00:00+05:30", "SKIPPED_MARKET_CLOSED"),
        ("2030-01-01T08:55:00+05:30", "SKIPPED_CALENDAR_UNKNOWN"),
    ],
)
def test_calendar_uses_sessions_for_day_not_currently_open(stamp, expected):
    assert (
        calendar_skip(Path("config/exchange-calendar.json"), datetime.fromisoformat(stamp))
        == expected
    )


def test_missing_calendar_skips_instead_of_inventing_session(tmp_path):
    assert (
        calendar_skip(tmp_path / "missing.json", datetime.now(UTC))
        == "SKIPPED_CALENDAR_UNAVAILABLE"
    )


@pytest.mark.asyncio
async def test_skip_does_not_read_credentials_or_construct_broker_client(tmp_path, monkeypatch):
    from importlib import import_module

    monkeypatch.setattr(
        "importlib.import_module",
        lambda name: (
            SimpleNamespace(flock=Mock(), LOCK_EX=2, LOCK_NB=4)
            if name == "fcntl"
            else import_module(name)
        ),
    )
    monkeypatch.setattr(
        "services.market.autologin.calendar_skip", lambda *_: "SKIPPED_MARKET_CLOSED"
    )
    read = Mock(side_effect=AssertionError("Credentials should not be read"))
    factory = Mock(side_effect=AssertionError("Broker should not be contacted"))
    monkeypatch.setattr("services.market.autologin.read_credentials", read)
    monkeypatch.setattr("services.market.autologin.AngelOneClient", factory)
    await run(tmp_path / "credentials.json")
    read.assert_not_called()
    factory.assert_not_called()
    assert "SKIPPED_MARKET_CLOSED" in (tmp_path / "status.json").read_text()
