from pathlib import Path

from pydantic import Field, IPvAnyAddress, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class MarketSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_prefix="ANGELONE_",
        extra="ignore",
        hide_input_in_errors=True,
    )
    api_key: SecretStr = SecretStr("")
    client_code: SecretStr = SecretStr("")
    local_ip: IPvAnyAddress | None = None
    public_ip: IPvAnyAddress | None = None
    mac_address: str = ""
    nifty_index_token: str = ""
    sensex_index_token: str = ""
    strikes_each_side: int = Field(default=8, ge=1, le=30)
    max_subscriptions: int = Field(default=200, ge=1, le=1000)
    greek_max_age_seconds: int = Field(default=180, ge=1, le=300)
    session_file: Path = ROOT / ".local" / "angel-session.json"
    calendar_file: Path = ROOT / "config" / "exchange-calendar.json"

    def missing(self) -> list[str]:
        fields = ("api_key", "client_code", "local_ip", "public_ip", "mac_address")
        return [
            "ANGELONE_" + name.upper()
            for name in fields
            if not (
                getattr(self, name).get_secret_value()
                if isinstance(getattr(self, name), SecretStr)
                else getattr(self, name)
            )
        ]

    def missing_references(self) -> list[str]:
        return [
            "ANGELONE_" + name.upper()
            for name in ("nifty_index_token", "sensex_index_token")
            if not getattr(self, name)
        ]


class ProviderError(RuntimeError):
    """Safe error code only. Never includes headers, token values or response bodies."""


class AuthenticationRequired(ProviderError):
    pass
