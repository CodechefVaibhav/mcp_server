# app/main.py

# Monkey-patch to avoid None status_code in tests
import starlette.responses
_orig = starlette.responses.Response.init_headers
def _safe_init(self, headers=None):
    if getattr(self, "status_code", None) is None:
        self.status_code = 200
    return _orig(self, headers)
starlette.responses.Response.init_headers = _safe_init
# —————————————————————————————————————————————————————————

import logging
from fastapi import FastAPI, Depends, status, Query
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from app.schema.common import ContextNode
from app.schema.tool import ToolListResponse
from app.routers import register, tools
from app.routers.register import list_contexts_alias, STORE
from app.keycloak import verify_access_token, ISSUER, OIDC_BASE

import fastapi.applications
fastapi.applications.FastAPI.debug = False

logger = logging.getLogger("uvicorn")
app = FastAPI(
    title="MCP Candidate Portal SSE Server",
    version="1.0.0",
    description="Expose candidate search as an MCP tool via SSE"
)

# CORS (once)
try:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
except RuntimeError:
    logger.warning("Skipping CORS (already started)")

# Seed built-in context
def _seed():
    ctx = ContextNode(
        id="candidate_search",
        name="Candidate Search",
        description="Search candidates by experience, location, and department",
        prompt="",
        parameters={}
    )
    STORE.setdefault(ctx.id, ctx)
    logger.info("Seeded built-in context")
_seed()

# 1) OAuth-protected resource metadata
@app.get(
    "/mcp/.well-known/oauth-protected-resource",
    summary="Protected-resource discovery",
    response_class=JSONResponse,
    status_code=status.HTTP_200_OK,
)
async def oauth_protected_resource():
    return {
        "resource": f"{app.root_path}/mcp",
        "authorization_servers": [ISSUER]
    }

# 2) OIDC metadata
@app.get(
    "/.well-known/oauth-authorization-server",
    summary="OIDC discovery (complete)",
    response_class=JSONResponse,
    status_code=status.HTTP_200_OK,
)
def oidc_discovery_complete():
    """
    Returns a complete OIDC discovery document
    """
    base_url = "https://uat-auth.peoplestrong.com/auth/realms/3"
    return {
        "issuer": base_url,
        "authorization_endpoint": f"{ISSUER}/protocol/openid-connect/auth",
        "token_endpoint": f"{ISSUER}/protocol/openid-connect/token",
        "token_introspection_endpoint": f"{ISSUER}/protocol/openid-connect/token/introspect",
        "userinfo_endpoint": f"{ISSUER}/protocol/openid-connect/userinfo",
        "end_session_endpoint": f"{ISSUER}/protocol/openid-connect/logout",
        "jwks_uri": f"{ISSUER}/protocol/openid-connect/certs",
        "check_session_iframe": f"{ISSUER}/protocol/openid-connect/login-status-iframe.html",
        "grant_types_supported": [
            "authorization_code",
            "implicit",
            "refresh_token",
            "password",
            "client_credentials"
        ],
        "response_types_supported": [
            "code",
            "none",
            "id_token",
            "token",
            "id_token token",
            "code id_token",
            "code token",
            "code id_token token"
        ],
        "subject_types_supported": ["public", "pairwise"],
        "id_token_signing_alg_values_supported": [
            "PS384", "ES384", "RS384", "HS256", "HS512", "ES256", "RS256", "HS384",
            "ES512", "PS256", "PS512", "RS512"
        ],
        "id_token_encryption_alg_values_supported": ["RSA-OAEP", "RSA1_5"],
        "id_token_encryption_enc_values_supported": ["A128GCM", "A128CBC-HS256"],
        "userinfo_signing_alg_values_supported": [
            "PS384", "ES384", "RS384", "HS256", "HS512", "ES256", "RS256", "HS384",
            "ES512", "PS256", "PS512", "RS512", "none"
        ],
        "request_object_signing_alg_values_supported": [
            "PS384", "ES384", "RS384", "HS256", "HS512", "ES256", "RS256", "HS384",
            "ES512", "PS256", "PS512", "RS512", "none"
        ],
        "response_modes_supported": ["query", "fragment", "form_post"],
        "registration_endpoint": f"{ISSUER}/clients-registrations/openid-connect",
        "token_endpoint_auth_methods_supported": [
            "private_key_jwt",
            "client_secret_basic",
            "client_secret_post",
            "tls_client_auth",
            "client_secret_jwt"
        ],
        "token_endpoint_auth_signing_alg_values_supported": [
            "PS384", "ES384", "RS384", "HS256", "HS512", "ES256", "RS256", "HS384",
            "ES512", "PS256", "PS512", "RS512"
        ],
        "claims_supported": [
            "aud", "sub", "iss", "auth_time", "name", "given_name", "family_name",
            "preferred_username", "email", "acr"
        ],
        "claim_types_supported": ["normal"],
        "claims_parameter_supported": False,
        "scopes_supported": [
            "openid", "offer:write", "microprofile-jwt", "web-origins", "roles",
            "offline_access", "phone", "address", "email", "profile"
        ],
        "request_parameter_supported": True,
        "request_uri_parameter_supported": True,
        "require_request_uri_registration": True,
        "code_challenge_methods_supported": ["plain", "S256"],
        "tls_client_certificate_bound_access_tokens": True
    }

# 3) Inspector-style MCP-tools discovery
@app.get(
    "/mcp/.well-known/mcp-tools",
    summary="OAuth-protected MCP-tools discovery",
    response_class=JSONResponse,
    status_code=status.HTTP_200_OK,
)
async def mcp_tools_discovery():
    tools_map = {}
    for ctx in STORE.values():
        tools_map[ctx.id] = {
            "description": ctx.description,
            "parameters": {
                "type": "object",
                "properties": { **ctx.parameters },
                "required": list(ctx.parameters.keys()),
            },
            "auth": {
                "type": "oauth2",
                "client_id": "claude-mcp",  # your registered MCP client
                "registration_endpoint":
                  f"{app.root_path}/api/organizations/{{orgId}}/mcp/start-auth/{{registrationId}}",
                "scopes": {},
            }
        }
    return {
        "version": "2025-05-20",
        "tools": tools_map
    }

# 4) Start-auth hook (no-op redirect back into Claude)
@app.get(
    "/api/organizations/{org_id}/mcp/start-auth/{registration_id}",
    summary="Start-auth hook",
)
def claude_start_auth(
    org_id: str,
    registration_id: str,
    redirect_url: str = Query(...),
    open_in_browser: bool = Query(False),
):
    return RedirectResponse(url=redirect_url)

# 5) Unprotected ChatMCP discovery
@app.get(
    "/.well-known/mcp.json",
    summary="ChatMCP discovery",
    response_model=ToolListResponse,
    status_code=200,
)
def mcp_discovery():
    return list_contexts_alias()

app.add_api_route(
    "/mcp.json",
    endpoint=mcp_discovery,
    methods=["GET"],
    summary="Alias for MCP Discovery",
    status_code=200,
)

# 6) Mount your existing register & tools routers
app.include_router(register.router, prefix="", tags=["register"])
app.include_router(tools.router,    prefix="/tools", tags=["tools"])

# 7) Health & root
@app.get("/",    summary="Root health",   status_code=200)
def root():    return {"message": "MCP SSE Server is up"}
@app.get("/health", summary="Health check", status_code=200)
def health():  return {"status": "ok"}
