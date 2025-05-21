# app/auth/keycloak.py

import time
from typing import Dict, Any
import logging
import httpx
from jose import jwt, JWTError
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# ─── YOUR KEYCLOAK CONFIG ────────────────────────────────────────────
ISSUER     = "https://uat-auth.peoplestrong.com/auth/realms/3"
AUDIENCE   = "mcp"
JWKS_URL   = f"{ISSUER}/protocol/openid-connect/certs"
# ──────────────────────────────────────────────────────────────────────

logger = logging.getLogger("uvicorn")
bearer_scheme = HTTPBearer(auto_error=False)

# Simple in-process JWKS cache (rotate every 24h)
_jwks_cache: Dict[str, Any] = {}
_jwks_cache_ts: float = 0
_JWKS_TTL = 60 * 60 * 24


async def _get_jwks() -> Dict[str, Any]:
    global _jwks_cache, _jwks_cache_ts
    now = time.time()
    if not _jwks_cache or now - _jwks_cache_ts > _JWKS_TTL:
        async with httpx.AsyncClient() as client:
            logger.info("Fetching JWKS from %s", JWKS_URL)
            r = await client.get(JWKS_URL, timeout=5.0)
            r.raise_for_status()
            _jwks_cache = r.json()
            _jwks_cache_ts = now
    return _jwks_cache


async def verify_access_token(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> Dict[str, Any]:
    if not creds or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = creds.credentials
    jwks = await _get_jwks()
    logger.info("VERIFY ACCESS TOKEN %s", token)
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
    return payload
