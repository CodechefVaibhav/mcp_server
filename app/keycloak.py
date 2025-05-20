# app/auth/keycloak.py
import asyncio
import time
from typing import Dict, Any

import httpx
from jose import jwt, JWTError
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# ─── YOUR KEYCLOAK CONFIG ────────────────────────────────────────────
ISSUER = "https://uat-auth.peoplestrong.com/auth/realms/3"
AUDIENCE = "mcp"
JWKS_URL = f"{ISSUER}/protocol/openid-connect/certs"
# ──────────────────────────────────────────────────────────────────────

# HTTPBearer will extract and validate the "Authorization: Bearer <token>" header
bearer_scheme = HTTPBearer(auto_error=False)

# Simple in-process cache for JWKS (rotate every 24h)
_jwks_cache: Dict[str, Any] = {}
_jwks_cache_ts: float = 0
_JWKS_CACHE_TTL = 60 * 60 * 24  # seconds


async def _get_jwks() -> Dict[str, Any]:
    global _jwks_cache, _jwks_cache_ts
    now = time.time()
    # reload if stale
    if not _jwks_cache or now - _jwks_cache_ts > _JWKS_CACHE_TTL:
        async with httpx.AsyncClient() as client:
            r = await client.get(JWKS_URL, timeout=5.0)
            r.raise_for_status()
            _jwks_cache = r.json()
            _jwks_cache_ts = now
    return _jwks_cache


async def verify_access_token(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> Dict[str, Any]:
    """
    FastAPI dependency that:
     - reads Authorization header
     - fetches & caches JWKS
     - verifies signature, issuer, audience, expiry
     - returns the decoded payload with at least 'azp' and 'scope'
    """
    if not creds or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = creds.credentials
    jwks = await _get_jwks()
    try:
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            issuer=ISSUER,
            audience=AUDIENCE,
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token validation failed",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # you can enforce required scopes here if you like
    # e.g. if "offer:write" not in payload.get("scope","").split(): 403

    return payload  # all the claims, including 'azp', 'scope', etc.
