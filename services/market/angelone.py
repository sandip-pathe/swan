"""Endpoint-allowlisted SmartAPI client with bounded, redacted failures."""

import asyncio
import random
import re
import time
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx

from services.core.contracts import IST
from services.market.credentials import BrokerSession, SessionStore
from services.market.settings import AuthenticationRequired, MarketSettings, ProviderError

LOGIN = "/rest/auth/angelbroking/user/v1/loginByPassword"
REFRESH = "/rest/auth/angelbroking/jwt/v1/generateTokens"
QUOTES = "/rest/secure/angelbroking/market/v1/quote/"
GREEKS = "/rest/secure/angelbroking/marketData/v1/optionGreek"
CANDLES = "/rest/secure/angelbroking/historical/v1/getCandleData"
PROFILE = "/rest/secure/angelbroking/user/v1/getProfile"
ALLOWED = frozenset((LOGIN, REFRESH, QUOTES, GREEKS, CANDLES))


def rejection_code(payload: object, fallback: str) -> str:
    """Expose only a strictly formatted provider code, never its arbitrary message/body."""
    code = payload.get("errorcode") if isinstance(payload, dict) else None
    if not isinstance(code, str) or re.fullmatch(r"(?:AB|AG)[0-9]{4}", code) is None:
        return fallback
    hints = {
        "AB1050": "INVALID_TOTP_USE_FRESH_AUTHENTICATOR_CODE",
        "AB1053": "INVALID_API_KEY_CHECK_SMARTAPI_APP_KEY",
        "AB1000": "INVALID_LOGIN_CREDENTIALS",
        "AB1007": "LOGIN_OR_PROVIDER_AMX_ERROR",
        "AB1032": "USER_NOT_FOUND_CHECK_CLIENT_CODE",
    }
    suffix = ":" + hints[code] if code in hints else ""
    return fallback + ":" + code + suffix


class AngelOneClient:
    def __init__(self, settings: MarketSettings):
        self.settings = settings
        self.store = SessionStore(settings.session_file, settings.client_code.get_secret_value())
        self.http = httpx.AsyncClient(
            base_url="https://apiconnect.angelone.in", timeout=15, follow_redirects=False
        )
        self.rate_lock = asyncio.Lock()
        self.auth_lock = asyncio.Lock()
        self.next_request = 0.0

    async def close(self) -> None:
        await self.http.aclose()

    def _headers(self, session: BrokerSession | None) -> dict[str, str]:
        missing = self.settings.missing()
        if missing:
            raise ProviderError("MISSING_CONFIGURATION:" + ",".join(missing))
        headers = {
            "X-PrivateKey": self.settings.api_key.get_secret_value(),
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": str(self.settings.local_ip),
            "X-ClientPublicIP": str(self.settings.public_ip),
            "X-MACAddress": self.settings.mac_address,
            "Accept": "application/json",
        }
        if session:
            headers["Authorization"] = "Bearer " + session.jwt.get_secret_value()
        return headers

    async def _post(self, route: str, body: dict, session: BrokerSession | None = None):
        if route not in ALLOWED:
            raise ProviderError("ENDPOINT_NOT_ALLOWED")
        # Conservative shared 1-request/sec budget, including retries and Greeks.
        attempts = 1 if route in {LOGIN, REFRESH} else 3
        for attempt in range(attempts):
            async with self.rate_lock:
                await asyncio.sleep(max(0, self.next_request - time.monotonic()))
                self.next_request = time.monotonic() + 1.05
                try:
                    response = await self.http.post(
                        route, json=body, headers=self._headers(session)
                    )
                except httpx.RequestError:
                    if attempt == attempts - 1:
                        raise ProviderError("PROVIDER_NETWORK_UNAVAILABLE") from None
                    continue
            if response.status_code in (401, 403):
                # SmartAPI also uses 403 for throttling, including plain-text
                # historical-endpoint responses. Do not misdiagnose a valid login.
                if response.status_code == 403 and any(
                    marker in response.text.lower()
                    for marker in ("exceeding access rate", "too many requests")
                ):
                    raise ProviderError("PROVIDER_RATE_LIMITED")
                try:
                    rejection = response.json()
                except ValueError:
                    rejection = None
                if response.status_code == 403 and isinstance(rejection, dict) and (
                    rejection.get("errorcode") == "AB1021"
                ):
                    raise ProviderError("PROVIDER_RATE_LIMITED")
                raise AuthenticationRequired(rejection_code(rejection, "BROKER_AUTH_REJECTED"))
            if response.status_code == 429 or response.status_code >= 500:
                await asyncio.sleep(min(8, 2**attempt) + random.random())
                continue
            if response.status_code != 200:
                raise ProviderError("PROVIDER_HTTP_" + str(response.status_code))
            try:
                payload = response.json(parse_float=Decimal)
            except ValueError:
                raise ProviderError("INVALID_PROVIDER_JSON") from None
            if not isinstance(payload, dict) or payload.get("status") is not True:
                code = payload.get("errorcode") if isinstance(payload, dict) else None
                if code in {"AG8001", "AG8002", "AG8003", "AB8050", "AB8051", "AB1010", "AB1011"}:
                    raise AuthenticationRequired("BROKER_SESSION_EXPIRED")
                raise ProviderError(rejection_code(payload, "PROVIDER_REQUEST_REJECTED"))
            return payload.get("data")
        raise ProviderError("PROVIDER_RETRY_LIMIT")

    async def login(self, pin: str, totp: str) -> None:
        if not pin or pin != pin.strip():
            raise AuthenticationRequired("PIN_EMPTY_OR_CONTAINS_SURROUNDING_SPACES")
        if re.fullmatch(r"[0-9]{6}", totp) is None:
            raise AuthenticationRequired("TOTP_MUST_BE_SIX_DIGITS_FROM_AUTHENTICATOR")
        now = datetime.now(UTC)
        data = await self._post(
            LOGIN,
            {
                "clientcode": self.settings.client_code.get_secret_value(),
                "password": pin,
                "totp": totp,
            },
        )
        self.store.save(BrokerSession.from_response(data, self.store.client_code, now))

    async def session(self) -> BrokerSession:
        async with self.auth_lock:
            session = self.store.load()
            now = datetime.now(UTC)
            if now.astimezone(IST).date() != session.created_at.astimezone(IST).date():
                raise AuthenticationRequired("DAILY_BROKER_LOGIN_REQUIRED")
            if session.expires_at <= now + timedelta(seconds=60):
                data = await self._post(
                    REFRESH, {"refreshToken": session.refresh.get_secret_value()}, session
                )
                session = BrokerSession.from_response(data, self.store.client_code, now)
                if session.expires_at <= now:
                    raise AuthenticationRequired("BROKER_LOGIN_REQUIRED")
                self.store.save(session)
            return session

    async def quotes(self, exchange_tokens: dict[str, list[str]]) -> list[dict]:
        count = sum(len(tokens) for tokens in exchange_tokens.values())
        if not 1 <= count <= 50 or not set(exchange_tokens) <= {"NSE", "BSE", "NFO", "BFO"}:
            raise ProviderError("INVALID_QUOTE_BATCH")
        data = await self._post(
            QUOTES, {"mode": "FULL", "exchangeTokens": exchange_tokens}, await self.session()
        )
        if not isinstance(data, dict) or not isinstance(data.get("fetched"), list):
            raise ProviderError("INVALID_QUOTE_RESPONSE")
        return data["fetched"]

    async def candles(self, query, instrument, now: datetime) -> dict:
        from services.market.history import normalize_bars

        body = query.provider_body(instrument, now)
        data = await self._post(CANDLES, body, await self.session())
        received_at = datetime.now(UTC)
        return {
            "bars": normalize_bars(data, query, received_at),
            "raw_rows": data,
            "received_at": received_at.isoformat(),
            "provider_request": body,
        }

    async def index_candles(self, query):
        """Read configured NIFTY/NSE index bars without option Instrument coercion."""
        from services.market.index_history import normalize_index_bars

        requested_at = datetime.now(UTC)
        body = query.provider_body(self.settings, requested_at)
        data = await self._post(CANDLES, body, await self.session())
        received_at = datetime.now(UTC)
        return normalize_index_bars(data, query, received_at, body)

    async def verify_session(self) -> None:
        """Read-only authentication check. Do not return or log profile personal data."""
        session = await self.session()
        try:
            response = await self.http.get(PROFILE, headers=self._headers(session))
        except httpx.RequestError:
            raise ProviderError("PROVIDER_NETWORK_UNAVAILABLE") from None
        try:
            payload = response.json()
        except ValueError:
            raise ProviderError("INVALID_PROVIDER_JSON") from None
        if (
            response.status_code != 200
            or not isinstance(payload, dict)
            or payload.get("status") is not True
        ):
            raise AuthenticationRequired(rejection_code(payload, "BROKER_SESSION_CHECK_REJECTED"))
        data = payload.get("data")
        if (
            not isinstance(data, dict)
            or data.get("clientcode") != self.settings.client_code.get_secret_value()
        ):
            raise AuthenticationRequired("BROKER_PROFILE_CLIENT_MISMATCH")

    async def greeks(self, underlying: str, expiry: date) -> list[dict]:
        if underlying != "NIFTY":
            raise ProviderError("BSE_GREEKS_NOT_ESTABLISHED")
        data = await self._post(
            GREEKS,
            {"name": underlying, "expirydate": expiry.strftime("%d%b%Y").upper()},
            await self.session(),
        )
        if not isinstance(data, list):
            raise ProviderError("INVALID_GREEKS_RESPONSE")
        return data
