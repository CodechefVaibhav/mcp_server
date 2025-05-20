from pydantic import BaseModel
from typing import Any, Dict

class ContextNode(BaseModel):
    id: str
    name: str
    description: str
    prompt: str
    parameters: Dict[str, Any]