"""
ARES API Security & Authentication Dependencies.
Supports API Key authentication via `X-Ares-Api-Key` or `Authorization: Bearer <key>`.
Configurable via settings.auth_enabled.
"""

from __future__ import annotations

import hmac
from typing import Optional

from fastapi import Depends, HTTPException, Header, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from ares.config import settings

api_key_header = APIKeyHeader(name="X-Ares-Api-Key", auto_error=False)
bearer_auth = HTTPBearer(auto_error=False)


async def verify_api_key(
    x_api_key: Optional[str] = Security(api_key_header),
    bearer: Optional[HTTPAuthorizationCredentials] = Security(bearer_auth),
    x_ares_user_email: Optional[str] = Header(None, alias="X-Ares-User-Email"),
) -> dict:
    """
    Verify incoming API key or bearer token against configured credentials.
    In development or when auth_enabled=False, permissive pass-through is supported.
    """
    token = x_api_key
    if not token and bearer:
        token = bearer.credentials

    # If auth is strictly required
    if settings.auth_enabled:
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication credentials were not provided. Include 'X-Ares-Api-Key' or 'Authorization: Bearer <token>'.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Constant-time comparison to prevent timing attacks
        valid_key = settings.api_key.encode("utf-8")
        provided_key = token.encode("utf-8")
        if not hmac.compare_digest(valid_key, provided_key):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Invalid ARES API Key.",
            )

    return {
        "authenticated": bool(token and token == settings.api_key) or not settings.auth_enabled,
        "user_email": x_ares_user_email or "system@ares.local",
        "role": "admin" if (token and token == settings.api_key) else "analyst",
    }
