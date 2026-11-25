"""Bounded daily authentication job; never changes trading permission."""

import argparse
import asyncio
import getpass
import json
import os
import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pyotp

from services.core.contracts import IST
from services.market.angelone import AngelOneClient
from services.market.calendar import SessionCalendar
from services.market.credentials import write_private_json
from services.market.settings import AuthenticationRequired, MarketSettings, ProviderError

DEFAULT_FILE = Path("/run/broker-auth/credentials.json")
TRANSIENT = {"PROVIDER_NETWORK_UNAVAILABLE", "PROVIDER_RATE_LIMITED", "PROVIDER_RETRY_LIMIT"}


def calendar_skip(path: Path, now: datetime) -> str | None:
    """Check whether a verified session remains today, including pre-open time."""
    try:
        calendar = SessionCalendar(path)
    except ProviderError:
        return "SKIPPED_CALENDAR_UNAVAILABLE"
    day = now.astimezone(IST).date()
    sessions = [calendar.get(venue, day) for venue in ("NFO", "BFO")]
    if any(session and now < session.closes_at for session in sessions):
        return None
    if all(
        session or (venue, day) in calendar.closed_days
        for venue, session in zip(("NFO", "BFO"), sessions)
    ):
        return "SKIPPED_MARKET_CLOSED"
    return "SKIPPED_CALENDAR_UNKNOWN"


def read_credentials(path: Path) -> tuple[str, str]:
    try:
        mode = path.lstat()
        if not stat.S_ISREG(mode.st_mode) or (os.name == "posix" and mode.st_mode & 0o077):
            raise ValueError
        value = json.loads(path.read_text(encoding="utf-8"))
        pin, seed = value["pin"], value["totp_secret"]
        if not isinstance(pin, str) or not pin or pin != pin.strip():
            raise ValueError
        if not isinstance(seed, str):
            raise ValueError
        pyotp.TOTP(seed).now()
        return pin, seed
    except (OSError, ValueError, KeyError, TypeError):
        raise ProviderError("AUTOLOGIN_CREDENTIALS_INVALID_OR_NOT_PRIVATE") from None


def configure(path: Path) -> None:
    pin = getpass.getpass("Angel One PIN (stored privately on this server): ")
    seed = getpass.getpass("TOTP setup secret (not the six-digit code): ").replace(" ", "").upper()
    try:
        if not pin or pin != pin.strip():
            raise ValueError
        pyotp.TOTP(seed).now()
    except Exception:
        raise ProviderError("INVALID_PIN_OR_TOTP_SETUP_SECRET") from None
    write_private_json(path, {"pin": pin, "totp_secret": seed})
    print("Automatic-login credentials saved privately. No broker request or order was made.")


async def authenticate(client: AngelOneClient, pin: str, seed: str) -> str:
    """Reuse a verified current-day session; otherwise establish and verify a new one."""
    try:
        saved = client.store.load()
        now = datetime.now(UTC)
        if saved.created_at.astimezone(IST).date() == now.astimezone(
            IST
        ).date() and saved.expires_at > now + timedelta(seconds=60):
            await client.verify_session()
            return "EXISTING_SESSION_VERIFIED"
    except AuthenticationRequired:
        pass
    for attempt in range(3):
        try:
            await client.login(pin, pyotp.TOTP(seed).now())
            await client.verify_session()
            return "NEW_SESSION_VERIFIED"
        except ProviderError as error:
            if str(error) not in TRANSIENT or attempt == 2:
                raise
            # A new TOTP window on retry; invalid credentials never loop.
            await asyncio.sleep(35)
    raise ProviderError("AUTOLOGIN_RETRY_LIMIT")


async def run(path: Path) -> None:
    # All scheduled/manual runs share this lock. API and worker never receive the seed.
    from importlib import import_module

    fcntl = import_module("fcntl")

    lock = path.with_suffix(".lock")
    descriptor = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
    client = None
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ProviderError("AUTOLOGIN_ALREADY_RUNNING") from None
        try:
            settings = MarketSettings()
            outcome = calendar_skip(settings.calendar_file, datetime.now(UTC))
            if outcome is None:
                pin, seed = read_credentials(path)
                client = AngelOneClient(settings)
                outcome = await authenticate(client, pin, seed)
        except ProviderError as error:
            write_private_json(
                path.with_name("status.json"),
                {"at": datetime.now(UTC).isoformat(), "status": "FAILED", "code": str(error)},
            )
            raise
        write_private_json(
            path.with_name("status.json"),
            {"at": datetime.now(UTC).isoformat(), "status": outcome},
        )
        print(outcome + ". No trading permission changed; no broker orders placed.")
    finally:
        if client:
            await client.close()
        os.close(descriptor)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("configure", "run", "status"))
    parser.add_argument("--credentials", type=Path, default=DEFAULT_FILE)
    args = parser.parse_args()
    try:
        if args.action == "configure":
            configure(args.credentials)
        elif args.action == "status":
            try:
                print(args.credentials.with_name("status.json").read_text(encoding="utf-8"))
            except OSError:
                raise ProviderError("AUTOLOGIN_NOT_RUN") from None
        else:
            asyncio.run(run(args.credentials))
    except ProviderError as error:
        raise SystemExit(str(error)) from None


if __name__ == "__main__":
    main()
