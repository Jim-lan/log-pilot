from pydantic import BaseModel
from typing import Optional, Dict, Any

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    answer: Optional[str]
    intent: Optional[str]
    context: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
