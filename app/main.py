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
from fastapi import FastAPI, Query
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from app.schema.common import ContextNode
from app.schema.tool import ToolListResponse
from app.routers import register, tools
from app.routers.register import list_contexts_alias

# Ensure FastAPI.debug exists under pytest
import fastapi.applications
fastapi.applications.FastAPI.debug = False

logger = logging.getLogger("uvicorn")

app = FastAPI(
    title="MCP Candidate Portal SSE Server",
    version="1.0.0",
    description="Expose candidate search as an MCP tool via SSE"
)

# Single CORS middleware, safe under TestClient
try:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
except RuntimeError:
    logger.warning("Skipping CORS (already started)")

# Auto-seed our built-in SSE tool on import so TestClient sees it immediately
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
# NEW: Claude “MCP Tools” discovery (OAuth-style) endpoint
# ----------------------------------------------------------------
from fastapi import Request, status
from fastapi.responses import JSONResponse

@app.get(
    "/mcp/.well-known/mcp-tools",
    summary="MCP Tools discovery (for Claude inspector)",
    status_code=200,
)
async def mcp_tools_discovery(request: Request):
    """
    Claude’s inspector will GET this and expect:
      {
        "version": "YYYY-MM-DD",
        "tools": {
          "<tool_id>": {
            "description": "...",
            "parameters": { ... JSON Schema ... },
            "auth": { "type": "none" }
          },
          …
        }
      }
    """
    # OPTIONAL: enforce Bearer token
    #auth = request.headers.get("authorization", "")
    #if not auth.startswith("Bearer "):
    #    return JSONResponse(
    #        status_code=status.HTTP_401_UNAUTHORIZED,
    #        headers={"WWW-Authenticate": 'Bearer realm="MCP"'},
    #        content={}
    #   )

    # build the tools map from our in-memory registry
    from app.routers.register import STORE
    tools_map: dict[str, dict] = {}
    for ctx in STORE.values():
        tools_map[ctx.id] = {
            "description": ctx.description,
            # here we assume ctx.parameters is already a JSON-schema fragment:
            "parameters": {
                "type": "object",
                "properties": ctx.parameters,
                "required": list(ctx.parameters.keys()),
            },
            "auth": {"type": "none"}
        }

    return {
        "version": "2025-05-20",   # you can update to today’s date
        "tools": tools_map
    }
# ----------------------------------------------------------------



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
    """
    Claude will hit this URL to initiate auth.
    We don't actually do OAuth here, so immediately bounce back
    to the supplied redirect_url.
    """
    # (You could sanity-check org_id or registration_id here if you want.)
    return RedirectResponse(url=redirect_url)

@app.get("/", summary="Root health check", status_code=200)
def root():
    return {"message": "MCP SSE Server is up and running"}


@app.get(
    "/.well-known/mcp.json",
    summary="MCP Discovery endpoint",
    response_model=ToolListResponse,
    status_code=200
)
def mcp_discovery():
    """
    ChatMCP discovery URL: returns { tools: [ ... ] }
    """
    return list_contexts_alias()


# Alias for /mcp.json
app.add_api_route(
    "/mcp.json",
    mcp_discovery,
    methods=["GET"],
    summary="Alias for MCP Discovery",
    status_code=200,
)

# Mount our routers
app.include_router(register.router, prefix="", tags=["register"])
app.include_router(tools.router,    prefix="/tools", tags=["tools"])


@app.get("/health", summary="Health check", status_code=200)
def health():
    return {"status": "ok"}
