# app/routers/register.py

import logging
from fastapi import APIRouter, HTTPException
from typing import Dict, List

from app.schema.common import ContextNode
from app.schema.tool import ToolListResponse

logger = logging.getLogger("register")
router = APIRouter()

# In-memory store shared by all endpoints here
STORE: Dict[str, ContextNode] = {}


#
# — alias MCP endpoints (for ChatMCP compatibility) —
#
@router.post(
    "/context",
    response_model=ContextNode,
    status_code=200,
    summary="Register a tool/context node (alias)"
)
async def register_context_alias(node: ContextNode):
    """
    POST /context  → ContextNode
    (alias form for ChatMCP)
    """
    logger.info(f"[alias] registering {node.id}")
    if node.id in STORE:
        raise HTTPException(400, "Node already exists")
    STORE[node.id] = node
    return node


@router.get(
    "/context",
    response_model=ToolListResponse,
    status_code=200,
    summary="List all registered context nodes (alias)"
)
def list_contexts_alias():
    """
    GET /context  → { tools: [ ... ] }
    auto-seeds built-in candidate_search
    """
    logger.info("[alias] listing contexts")
    default_ctx = ContextNode(
        id="candidate_search",
        name="Candidate Search",
        description="Search candidates by experience, location, and department",
        prompt="",
        parameters={}
    )
    STORE.setdefault(default_ctx.id, default_ctx)
    return ToolListResponse(tools=list(STORE.values()))


@router.get(
    "/context/{node_id}",
    response_model=ContextNode,
    status_code=200,
    summary="Retrieve a registered context node by ID (alias)"
)
def get_context_alias(node_id: str):
    """
    GET /context/{node_id}  → ContextNode
    """
    logger.info(f"[alias] getting context {node_id}")
    node = STORE.get(node_id)
    if not node:
        raise HTTPException(404, "Context node not found")
    return node


#
# — “mcp_server.py” style endpoints —
#
@router.post(
    "/register",
    response_model=ContextNode,
    status_code=200,
    summary="Register a tool/context node"
)
async def register_context(node: ContextNode):
    """
    POST /register  → ContextNode
    (classic MCP-server style)
    """
    logger.info(f"[mcp] registering {node.id}")
    if node.id in STORE:
        raise HTTPException(400, "Node already exists")
    STORE[node.id] = node
    return node


@router.get(
    "/context-all",
    response_model=List[ContextNode],
    status_code=200,
    summary="List all registered context nodes (flat)"
)
def list_contexts_mcp_server():
    """
    GET /context-all  → [ ContextNode, ... ]
    """
    logger.info("[mcp] listing contexts flat")
    return list(STORE.values())


@router.post(
    "/resolve",
    response_model=Dict[str, List[ContextNode]],
    status_code=200,
    summary="Resolve a bundle of context node IDs"
)
def resolve_bundle(ids: List[str]):
    """
    POST /resolve  ["id1","id2"]  → { "bundle": [ node1, node2 ] }
    """
    logger.info(f"[mcp] resolving bundle {ids}")
    bundle: List[ContextNode] = []
    for node_id in ids:
        node = STORE.get(node_id)
        if not node:
            raise HTTPException(404, f"Node {node_id} not found")
        bundle.append(node)
    return {"bundle": bundle}
