# --- monkey‐patch to guard against None status_code ---------------------------------
import starlette.responses

_orig_init_headers = starlette.responses.Response.init_headers

def _safe_init_headers(self, headers=None):
    # If status_code was somehow left None, default to 200
    if getattr(self, "status_code", None) is None:
        self.status_code = 200
    return _orig_init_headers(self, headers)

starlette.responses.Response.init_headers = _safe_init_headers
# ------------------------------------------------------------------------------------

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.schema.common import ContextNode
from app.schema.tool   import ToolListResponse
from app.routers       import register, tools
from app.routers.register import list_contexts

logger = logging.getLogger("uvicorn")

FastAPI.debug = False

app = FastAPI(
    title="MCP Candidate Portal SSE Server",
    version="1.0.0",
    description="Expose candidate search as an MCP tool via SSE"
)

# Allow ChatMCP client origins
try:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
except RuntimeError:
    # In test environments (TestClient import), Starlette may consider
    # the app "started" already—silently skip if so.
    import logging
    logging.getLogger("uvicorn.error").warning(
        "Skipping CORS middleware—app already started"
    )

@app.on_event("startup")
def register_default_contexts():
    # Pre-register built-in SSE tool
    candidate_context = ContextNode(
        id="candidate_search",
        name="Candidate Search",
        description="Search candidates by experience, location, and department",
        prompt="",      # no default prompt, it's generated dynamically
        parameters={}   # if you had schema for params you could list them
    )
    from app.routers import register as reg_module
    reg_module.STORE[candidate_context.id] = candidate_context
    logger.info("Registered built-in context: candidate_search")


  # Also seed at import time so TestClient (without a lifespan context) still sees it:
register_default_contexts()

@app.get("/", status_code=200,summary="Root health check")
def root():
    return {"message": "MCP SSE Server is up and running"}

@app.get(
    "/.well-known/mcp.json",
    status_code=200,
    summary="MCP Discovery endpoint",
    response_model=ToolListResponse
)
def mcp_discovery():
    # ChatMCP will fetch this to discover available tools
    return list_contexts()

# Alias for clients that expect /mcp.json
app.add_api_route(
    "/mcp.json",
    endpoint=mcp_discovery,
    methods=["GET"],
    summary="Alias for MCP Discovery",
    status_code=200,
)

# Mount routers
app.include_router(register.router, prefix="",         tags=["register"])
app.include_router(register.router, prefix="/register", tags=["register"])
app.include_router(tools.router,    prefix="/tools",    tags=["tools"])

@app.get("/health",status_code=200, summary="Health check")
def health():
    return {"status": "ok"}
