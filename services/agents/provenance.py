"""Small non-secret provenance fields; never substitute current configuration."""

import hashlib
import json
import re


def fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def name(value: object) -> str | None:
    return (
        value if isinstance(value, str) and re.fullmatch(r"[a-zA-Z0-9._:-]{1,150}", value) else None
    )


def checksum(value: object) -> str | None:
    return value if isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) else None
