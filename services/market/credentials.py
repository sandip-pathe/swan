"""Private session storage. Optional daily-login secrets use a separate private file."""

import base64
import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, SecretStr

from services.core.contracts import IST
from services.market.settings import AuthenticationRequired, ProviderError


class BrokerSession(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)
    jwt: SecretStr
    refresh: SecretStr
    feed: SecretStr
    client_code: SecretStr
    expires_at: AwareDatetime
    created_at: AwareDatetime

    @classmethod
    def from_response(cls, data: dict, client_code: str, now: datetime):
        midnight = (now.astimezone(IST) + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        try:
            jwt = data["jwtToken"].removeprefix("Bearer ")
            # The claim is only a renewal hint; the provider still authenticates every request.
            payload = jwt.split(".")[1]
            claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
            expires = min(datetime.fromtimestamp(int(claims["exp"]), UTC), midnight)
            return cls(
                jwt=jwt,
                refresh=data["refreshToken"],
                feed=data["feedToken"],
                client_code=SecretStr(client_code),
                expires_at=expires,
                created_at=now,
            )
        except (KeyError, ValueError, TypeError, IndexError) as error:
            raise ProviderError("INVALID_AUTH_RESPONSE") from error


def write_private_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ProviderError("UNSAFE_SESSION_DESTINATION")
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        if os.name == "nt":
            identity = subprocess.check_output(["whoami.exe"], text=True).strip()
            result = subprocess.run(
                [
                    "icacls.exe",
                    str(temporary),
                    "/inheritance:r",
                    "/grant:r",
                    identity + ":F",
                    "SYSTEM:F",
                ],
                capture_output=True,
                check=False,
            )
            if result.returncode:
                raise ProviderError("SESSION_PERMISSION_FAILED")
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = -1
            json.dump(value, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


class SessionStore:
    def __init__(self, path: Path, client_code: str):
        self.path = path
        self.client_code = client_code

    def load(self) -> BrokerSession:
        try:
            session = BrokerSession.model_validate_json(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise AuthenticationRequired("BROKER_LOGIN_REQUIRED") from error
        if session.client_code.get_secret_value() != self.client_code:
            raise AuthenticationRequired("BROKER_ACCOUNT_MISMATCH")
        return session

    def save(self, session: BrokerSession) -> None:
        write_private_json(
            self.path,
            {
                "jwt": session.jwt.get_secret_value(),
                "refresh": session.refresh.get_secret_value(),
                "feed": session.feed.get_secret_value(),
                "client_code": self.client_code,
                "expires_at": session.expires_at.isoformat(),
                "created_at": session.created_at.isoformat(),
            },
        )
