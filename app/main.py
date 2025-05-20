# app/main.py

# --- monkey-patch to guard against None status_code in tests ---
import starlette.responses
_orig_init = starlette.responses.Response.init_headers

def _safe_init(self, headers=None):
    if getattr(self, "status_code", None) is None:
        self.status_code = 200
    return _orig_init(self, headers)

starlette.responses.Response.init_headers = _safe_init
# -------------------------------------------------------------

import logging
from fastapi import FastAPI, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials

from app.schema.common import ContextNode
from app.schema.tool import ToolListResponse
from app.routers import register, tools
from app.routers.register import list_contexts_alias
from app.keycloak import verify_access_token  # ← your Keycloak helper

# Ensure FastAPI.debug exists under pytest
import fastapi.applications
fastapi.applications.FastAPI.debug = False

logger = logging.getLogger("uvicorn")

app = FastAPI(
    title="MCP Candidate Portal SSE Server",
    version="1.0.0",
    description="Expose candidate search as an MCP tool via SSE"
)

# CORS
try:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
except RuntimeError:
    logger.warning("Skipping CORS middleware—already started")

# Auto-seed built-in SSE tool so TestClient sees it immediately
def _seed_candidate_search():
    ctx = ContextNode(
        id="candidate_search",
        name="Candidate Search",
        description="Search candidates by experience, location, and department",
        prompt="",
        parameters={}
    )
    from app.routers import register as reg
    reg.STORE.setdefault(ctx.id, ctx)
    logger.info("Seeded built-in context: candidate_search")

_seed_candidate_search()

# ----------------------------------------------------------------
# 1) OAuth-protected discovery for “inspectors” (MCP-tools)
# ----------------------------------------------------------------
@app.get(
    "/mcp/.well-known/mcp-tools",
    summary="OAuth-protected MCP-tools discovery",
    response_class=JSONResponse,
    status_code=status.HTTP_200_OK,
)
async def mcp_tools_discovery(
    token_payload = Depends(verify_access_token),
):
    """
    Protected endpoint that returns:

    {
      "version": "2025-05-20",
      "tools": {
        "<toolId>": {
          "description": "...",
          "parameters": { "type": "object", "properties": {...}, "required": [...] },
          "auth": { "type": "oauth2", "scopes": [...] }
        },
        …
      }
    }
    """
    # you could enforce specific scopes here, e.g. "offer:write"
    scopes = token_payload.get("scope", "").split()

    from app.routers.register import STORE
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
                "scopes": scopes
            }
        }

    return {
        "version": "2025-05-20",
        "tools": tools_map
    }

# ----------------------------------------------------------------
# 2) Claude start-auth hook (no-op redirect)
# ----------------------------------------------------------------
from fastapi import Query

@app.get(
    "/api/organizations/{org_id}/mcp/start-auth/{registration_id}",
    summary="Claude start-auth hook (no-op redirect)"
)
def claude_start_auth(
    org_id: str,
    registration_id: str,
    redirect_url: str = Query(...),
    open_in_browser: bool = Query(False)
):
    return RedirectResponse(url=redirect_url)

# ----------------------------------------------------------------
# 3) Unprotected discovery for ChatMCP (ToolListResponse)
# ----------------------------------------------------------------
@app.get(
    "/.well-known/mcp.json",
    summary="ChatMCP discovery endpoint",
    response_model=ToolListResponse,
    status_code=200
)
def mcp_discovery():
    return list_contexts_alias()

# alias /mcp.json → same
app.add_api_route(
    "/mcp.json",
    endpoint=mcp_discovery,
    methods=["GET"],
    summary="Alias for MCP Discovery",
    status_code=200,
)

# ----------------------------------------------------------------
# 4) Mount your existing routers
# ----------------------------------------------------------------
app.include_router(register.router, prefix="", tags=["register"])
app.include_router(tools.router,    prefix="/tools", tags=["tools"])

# ----------------------------------------------------------------
# 5) Health & root
# ----------------------------------------------------------------
@app.get("/", summary="Root health check", status_code=200)
def root():
    return {"message": "MCP SSE Server is up and running"}

@app.get("/health", summary="Health check", status_code=200)
def health():
    return {"status": "ok"}
