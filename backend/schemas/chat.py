"""
Pydantic schemas for AI Backend API.
"""

from typing import List, Optional, Dict
from pydantic import BaseModel

class EntityProduct(BaseModel):
    product: str
    quantity: int

class Entities(BaseModel):
    products: List[EntityProduct] = []

class ChatRequest(BaseModel):
    """Used for REST API."""
    session_id: str
    text: str

class ChatResponse(BaseModel):
    """Used for both REST API and WebSocket."""
    session_id: str
    reply: str
    intent: str
    entities: Entities
    dialogue_state: str
    confidence: float
