from pydantic import BaseModel
from typing import List
from .common import ContextNode

class ToolRegistration(BaseModel):
    node: ContextNode

class ToolListResponse(BaseModel):
    tools: List[ContextNode]