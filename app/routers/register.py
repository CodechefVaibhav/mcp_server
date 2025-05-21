# app/routers/register.py

import logging
from fastapi import APIRouter, HTTPException
from typing import Dict, List

from app.schema.common import ContextNode
from app.schema.tool import ToolListResponse

logger = logging.getLogger("register")
router = APIRouter()

# Shared in-memory store
STORE: Dict[str, ContextNode] = {}

#
# — ChatMCP–style “alias” endpoints —
#
@router.post(
    "/context",
    response_model=ContextNode,
    status_code=200,
    summary="Register a tool/context node (alias)"
)
async def register_context_alias(node: ContextNode):
    logger.info("[alias] registering %s", node.id)
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
    logger.info("[alias] listing contexts")
    default = ContextNode(
        id="candidate_search",
        name="Candidate Search",
        description="Search candidates by experience, location, and department",
        prompt="",
        parameters={}
    )
    STORE.setdefault(default.id, default)
    return ToolListResponse(tools=list(STORE.values()))

@router.get(
    "/context/{node_id}",
    response_model=ContextNode,
    status_code=200,
    summary="Retrieve a registered context node by ID (alias)"
)
def get_context_alias(node_id: str):
    logger.info("[alias] getting context %s", node_id)
    node = STORE.get(node_id)
    if not node:
        raise HTTPException(404, "Context node not found")
    return node

#
# — classic MCP-server–style endpoints —
#
@router.post(
    "/register",
    response_model=ContextNode,
    status_code=200,
    summary="Register a tool/context node"
)
async def register_context(node: ContextNode):
    logger.info("[mcp] registering %s", node.id)
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
    logger.info("[mcp] listing contexts flat")
    return list(STORE.values())

@router.post(
    "/resolve",
    response_model=Dict[str, List[ContextNode]],
    status_code=200,
    summary="Resolve a bundle of context node IDs"
)
def resolve_bundle(ids: List[str]):
    logger.info("[mcp] resolving bundle %s", ids)
    bundle: List[ContextNode] = []
    for node_id in ids:
        node = STORE.get(node_id)
        if not node:
            raise HTTPException(404, f"Node {node_id} not found")
        bundle.append(node)
    return {"bundle": bundle}
