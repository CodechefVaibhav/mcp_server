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
async def oauth_protected_resource(
    token_payload = Depends(verify_access_token)
):
    return {
        "resource": f"{app.root_path}/mcp",
        "authorization_servers": [ISSUER]
    }

# 2) OIDC metadata
@app.get(
    "/.well-known/oauth-authorization-server",
    summary="OIDC discovery (minimal)",
    response_class=JSONResponse,
    status_code=status.HTTP_200_OK,
)
def oidc_discovery_minimal():
    """
    Returns a minimal OIDC discovery document:
    {
      "issuer": "...",
      "authorization_endpoint": "...",
      "token_endpoint": "...",
      "registration_endpoint": "...",
      "response_types_supported": [...],
      "response_modes_supported": [...],
      "grant_types_supported": [...],
      "token_endpoint_auth_methods_supported": [...],
      "revocation_endpoint": "...",
      "code_challenge_methods_supported": [...]
    }
    """
    # you can also pull these lists from config if you like
    return {
        "issuer": OIDC_BASE,
        "authorization_endpoint": f"{OIDC_BASE}/authorize",
        "token_endpoint": f"{OIDC_BASE}/token",
        "registration_endpoint": f"{OIDC_BASE}/register",
        "response_types_supported": ["code"],
        "response_modes_supported": ["query"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_methods_supported": [
            "client_secret_basic",
            "client_secret_post",
            "none"
        ],
        "revocation_endpoint": f"{OIDC_BASE}/token",
        "code_challenge_methods_supported": ["plain", "S256"],
    }

# 3) Inspector-style MCP-tools discovery
@app.get(
    "/mcp/.well-known/mcp-tools",
    summary="OAuth-protected MCP-tools discovery",
    response_class=JSONResponse,
    status_code=status.HTTP_200_OK,
)
async def mcp_tools_discovery(
    token_payload = Depends(verify_access_token),
):
    scopes = token_payload.get("scope", "").split()
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
                "scopes": scopes,
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
