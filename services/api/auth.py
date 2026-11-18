import os
from functools import lru_cache
from threading import Lock
from time import time
from uuid import UUID

import requests
from cachecontrol import CacheControl
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth import jwt
from google.auth.exceptions import GoogleAuthError, TransportError
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.id_token import verify_firebase_token
from pydantic_settings import BaseSettings, SettingsConfigDict

from services.market.settings import ROOT

_initialization_lock = Lock()


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", extra="ignore", hide_input_in_errors=True
    )
    firebase_project_id: str = ""
    swan_account_bindings: dict[str, UUID] = {}
    swan_local_owner_bootstrap: bool = False
    swan_web_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]


@lru_cache
def settings() -> ApiSettings:
    return ApiSettings()


@lru_cache
def public_key_request() -> GoogleRequest:
    # Google's public certificate response is cached according to its HTTP headers.
    return GoogleRequest(session=CacheControl(requests.Session()))


def verified_claims(token: str) -> dict:
    project = settings().firebase_project_id
    if not project or os.environ.get("FIREBASE_AUTH_EMULATOR_HOST"):
        raise HTTPException(503, "AUTH_NOT_CONFIGURED")
    try:
        header = jwt.decode_header(token)
        if (
            header.get("alg") != "RS256"
            or not isinstance(header.get("kid"), str)
            or not header["kid"]
        ):
            raise ValueError("Unsupported signing header")
        with _initialization_lock:

            def fetch_keys(*args, **kwargs):
                return public_key_request()(*args, **{**kwargs, "timeout": 5})

            claims = dict(verify_firebase_token(token, fetch_keys, audience=project))
        subject, auth_time = claims.get("sub"), claims.get("auth_time")
        if (
            claims.get("iss") != f"https://securetoken.google.com/{project}"
            or claims.get("aud") != project
            or not isinstance(subject, str)
            or not 1 <= len(subject) <= 128
            or type(auth_time) is not int
            or not 0 <= auth_time <= time()
            or type(claims.get("iat")) is not int
            or type(claims.get("exp")) is not int
            or claims["iat"] > time()
            or claims["exp"] <= time()
            or auth_time > claims["iat"]
        ):
            raise ValueError("Invalid Firebase identity claims")
        return claims
    except TransportError:
        raise HTTPException(503, "AUTH_VERIFICATION_UNAVAILABLE") from None
    except (ValueError, TypeError, KeyError, GoogleAuthError):
        raise HTTPException(
            401, "SESSION_INVALID", headers={"WWW-Authenticate": "Bearer"}
        ) from None


def account_identity(
    request: Request,
    token: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
) -> UUID:
    if token is None or len(token.credentials) > 10000:
        raise HTTPException(401, "SIGN_IN_REQUIRED", headers={"WWW-Authenticate": "Bearer"})
    claims = verified_claims(token.credentials)
    uid = claims["sub"]
    account = settings().swan_account_bindings.get(uid)
    if account is not None:
        return account
    if not settings().swan_local_owner_bootstrap:
        raise HTTPException(403, "ACCOUNT_NOT_AUTHORIZED")
    # Local first-owner enrollment is an explicit local setting, not a hosting default.
    if request.client is None or request.client.host not in {"127.0.0.1", "::1"}:
        raise HTTPException(403, "LOCAL_ONBOARDING_ONLY")
    from services.api.owner import local_owner_account

    return local_owner_account(request.app.state.engine, settings().firebase_project_id, uid)
