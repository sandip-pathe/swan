"""Opt-in browser push, authenticated subscriptions and short-lived update notices."""

import base64
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import WebPushException, webpush
from requests.exceptions import RequestException

from services.bot.store import Store

HOSTS = {"fcm.googleapis.com", "updates.push.services.mozilla.com", "web.push.apple.com"}


def key_file(store: Store) -> Path:
    path = Path(store.path).parent / "push-vapid.pem"
    if not path.exists():
        private = ec.generate_private_key(ec.SECP256R1())
        value = private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, "wb") as output:
                output.write(value)
    return path


def public_key(store: Store) -> str:
    private = serialization.load_pem_private_key(key_file(store).read_bytes(), password=None)
    if not isinstance(private, ec.EllipticCurvePrivateKey):
        raise ValueError("PUSH_KEY_TYPE_INVALID")
    public = private.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return base64.urlsafe_b64encode(public).rstrip(b"=").decode()


def validate_subscription(value: dict) -> str:
    url = urlsplit(value.get("endpoint", ""))
    if (
        url.scheme != "https"
        or url.hostname not in HOSTS
        or url.port not in (None, 443)
        or url.username
        or url.password
        or len(value["endpoint"]) > 2000
    ):
        raise ValueError("PUSH_ENDPOINT_NOT_ALLOWED")
    keys = value.get("keys", {})
    for name, expected in (("p256dh", 65), ("auth", 16)):
        data = keys.get(name, "")
        if not isinstance(data, str) or len(data) > 120:
            raise ValueError("PUSH_KEY_INVALID")
        try:
            decoded = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
        except (ValueError, TypeError):
            raise ValueError("PUSH_KEY_INVALID") from None
        if len(decoded) != expected:
            raise ValueError("PUSH_KEY_INVALID")
        if name == "p256dh":
            ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), decoded)
    return hashlib.sha256(value["endpoint"].encode()).hexdigest()


def deliver(store: Store, idea: dict) -> None:
    # No prices or buy commands on a lock screen; the app must revalidate on open.
    with store.connect() as db:
        rows = db.execute("SELECT key,payload FROM documents WHERE key LIKE 'push:%'").fetchall()
    if not rows:
        return
    for key, payload in rows[:10]:
        value = json.loads(payload)
        if idea["state"] != "eligible" and idea["state"] != "invalidated":
            continue
        if idea["state"] == "eligible":
            preferences = store.read("preferences:" + value["owner"], {})
            from decimal import Decimal

            if Decimal(preferences.get("position_budget", "0")) < Decimal(
                (idea.get("economics") or {}).get("premium_required", "1")
            ):
                continue
        if idea["state"] == "invalidated":
            with store.connect() as db:
                entered = db.execute(
                    "SELECT 1 FROM reported_entries WHERE owner=? AND idea_id=?",
                    (value["owner"], idea["id"]),
                ).fetchone()
            if not entered:
                continue
        try:
            validate_subscription(value["subscription"])
            webpush(
                value["subscription"],
                data=json.dumps(
                    {
                        "title": "SWAN idea updated",
                        "body": "Open Insights for fresh conditions and source times.",
                        "idea_id": idea["id"],
                        "published_at": idea["published_at"],
                    }
                ),
                vapid_private_key=str(key_file(store)),
                vapid_claims={"sub": "https://swan-one.vercel.app"},
                ttl=60,
                timeout=8,
            )
        except WebPushException as error:
            if error.response is not None and error.response.status_code in (404, 410):
                with store.connect() as db:
                    db.execute("DELETE FROM documents WHERE key=?", (key,))
        except (ValueError, OSError, RequestException):
            continue
