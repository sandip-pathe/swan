"""Stable release evidence excludes daily JWTs; runtime evidence does not."""

import hashlib

from services.core.models import Account
from services.core.setup import CONFIG_FILES, digest
from services.market.readiness import connection_fingerprint
from services.market.settings import ROOT, MarketSettings


def qualification_binding(account: Account) -> str:
    try:
        code = hashlib.sha256()
        for path in sorted((ROOT / "services").rglob("*.py")):
            code.update(str(path.relative_to(ROOT)).encode())
            code.update(path.read_bytes())
        code.update((ROOT / "uv.lock").read_bytes())
        market = MarketSettings()
        broker = market.model_dump(mode="json")
        broker.update(
            api_key=market.api_key.get_secret_value(),
            client_code=market.client_code.get_secret_value(),
        )
        return digest(
            {
                "code": code.hexdigest(),
                "policy": account.config,
                "configuration": {
                    name: path.read_text(encoding="utf-8") for name, path in CONFIG_FILES.items()
                },
                "broker_settings": broker,
                "ai": connection_fingerprint("ai"),
                "news": connection_fingerprint("news"),
            }
        )
    except (OSError, ValueError):
        raise ValueError("QUALIFICATION_INPUTS_UNAVAILABLE") from None
