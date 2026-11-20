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


def token_usage(value: object) -> int | None:
    if not isinstance(value, dict):
        return None
    total = value.get("total_tokens")
    return total if type(total) is int and total >= 0 else None


def normalized_usage(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    result: dict[str, object] = {
        key: count
        for key in ("input_tokens", "output_tokens", "total_tokens")
        if type(count := value.get(key)) is int and count >= 0
    }
    for field, key in (
        ("input_tokens_details", "cached_tokens"),
        ("output_tokens_details", "reasoning_tokens"),
    ):
        detail = value.get(field)
        count = detail.get(key) if isinstance(detail, dict) else None
        if type(count) is int and count >= 0:
            result[field] = {key: count}
    return result or None
