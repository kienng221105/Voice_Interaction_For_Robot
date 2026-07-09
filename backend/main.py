"""
FastAPI Application Entry Point.
"""

import os
import logging
from fastapi import FastAPI
from backend.routers import voice_ws, chat_api
from backend.services.session_manager import SessionManager
from backend.ai.stt import STTEngine
from backend.ai.nlu import NLUEngine
from backend.ai.dialogue import DialogueManager

# Basic logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

app = FastAPI(title="Voice Vending AI Backend")

# Initialize Singletons and store in app state
session_manager = SessionManager()
stt_engine = STTEngine(api_key=os.environ.get("GROQ_API_KEY", ""))
nlu_engine = NLUEngine(model_path=os.environ.get("MODEL_PATH", "model.gguf"))
dialogue_manager = DialogueManager()

app.state.session_manager = session_manager
app.state.stt_engine = stt_engine
app.state.nlu_engine = nlu_engine
app.state.dialogue_manager = dialogue_manager

app.include_router(voice_ws.router)
app.include_router(chat_api.router)

@app.get("/health")
def health_check():
    """Health check for GCP Load Balancer."""
    return {"status": "ok"}
