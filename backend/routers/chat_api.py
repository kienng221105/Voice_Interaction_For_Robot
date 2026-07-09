"""
REST API Router for Text-based Chat (Fallback).
"""

from fastapi import APIRouter, Request
from backend.schemas.chat import ChatRequest, ChatResponse

router = APIRouter()

@router.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: Request, payload: ChatRequest):
    """
    Process text input directly to retrieve AI inference and dialogue state.
    """
    app_state = request.app.state
    
    # 1. Get Session
    session = app_state.session_manager.get_session(payload.session_id)
    
    # 2. Extract Intent & Entities (NLU)
    intent, entities, confidence = app_state.nlu_engine.extract(payload.text)
    
    # 3. Process Dialogue State Machine
    next_state, reply = app_state.dialogue_manager.process(intent, entities, session)
    
    # 4. Save Session
    app_state.session_manager.save_session(payload.session_id, session)
    
    # 5. Return JSON Response (Schema Validated)
    return ChatResponse(
        session_id=payload.session_id,
        reply=reply,
        intent=intent,
        entities=entities,
        dialogue_state=next_state,
        confidence=confidence
    )
