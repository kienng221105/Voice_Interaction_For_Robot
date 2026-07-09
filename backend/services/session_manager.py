"""
Session Management Service.
Stores conversation state and history independent of the AI engine.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("session_manager")

class SessionData:
    def __init__(self):
        self.dialogue_state: str = "IDLE"
        self.history: list[str] = []
        self.context: Dict[str, Any] = {}

class SessionManager:
    def __init__(self):
        # In-memory session store for MVP
        self._sessions: Dict[str, SessionData] = {}

    def get_session(self, session_id: str) -> SessionData:
        """Get existing session or create a new one."""
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionData()
        return self._sessions[session_id]

    def save_session(self, session_id: str, data: SessionData) -> None:
        """Save session state. For in-memory, it's modified in place, but kept for interface completeness."""
        self._sessions[session_id] = data

    def clear_session(self, session_id: str) -> None:
        """Clear a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
