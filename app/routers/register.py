import logging
from fastapi import APIRouter, HTTPException
from typing import List

from app.schema.common import ContextNode
from app.schema.tool import ToolListResponse

logger = logging.getLogger("register")
router = APIRouter()

# In-memory store of registered contexts
STORE: dict[str, ContextNode] = {}


@router.post(
    "/context",
    response_model=ContextNode,
    status_code=200,
    summary="Register a tool/context node"
)
async def register_context(node: ContextNode):
    logger.info(f"Register attempt: {node.id}")
    if node.id in STORE:
        logger.warning(f"Node {node.id} already exists")
        raise HTTPException(status_code=400, detail="Node already exists")
    STORE[node.id] = node
    logger.info(f"Node {node.id} registered successfully")
    return node


@router.get(
    "/context/{node_id}",
    response_model=ContextNode,
    status_code=200,
    summary="Retrieve a registered context node by ID"
)
def get_context(node_id: str):
    node = STORE.get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Context node not found")
    return node


@router.get(
    "/context",
    response_model=ToolListResponse,
    status_code=200,
    summary="List all registered context nodes"
)
def list_contexts():
    logger.info("List contexts requested")

    # Ensure the built-in candidate_search is always present
    default_ctx = ContextNode(
        id="candidate_search",
        name="Candidate Search",
        description="Search candidates by experience, location, and department",
        prompt="",
        parameters={}
    )
    STORE.setdefault(default_ctx.id, default_ctx)

    nodes: List[ContextNode] = list(STORE.values())
    return ToolListResponse(tools=nodes)
