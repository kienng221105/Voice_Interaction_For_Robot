"""
Network module: Client to AI Backend communication.
Supports both REST (POST /api/chat) and WebSocket (/ws/audio).
"""

import json
import logging
from typing import Dict, Any, Optional

import requests

logger = logging.getLogger("backend_client")


class BackendClient:
    """
    Handles communication between Laptop Client and AI Backend.
    Backend URL is injected via constructor (no hardcode).
    """

    def __init__(self, backend_url: str):
        self._backend_url = backend_url.rstrip("/")

    def send_text(self, session_id: str, text: str) -> Optional[Dict[str, Any]]:
        """
        Send text to Backend via REST API and return the parsed response.
        Returns None if the request fails.
        """
        url = f"{self._backend_url}/api/chat"
        payload = {"session_id": session_id, "text": text}

        try:
            resp = requests.post(url, json=payload, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            else:
                logger.error(f"Backend error {resp.status_code}: {resp.text}")
                return None
        except requests.RequestException as e:
            logger.error(f"Backend request failed: {e}")
            return None

    def health_check(self) -> bool:
        """Check if Backend is reachable."""
        try:
            resp = requests.get(f"{self._backend_url}/health", timeout=5)
            return resp.status_code == 200
        except requests.RequestException:
            return False
