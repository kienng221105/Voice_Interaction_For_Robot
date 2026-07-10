"""
Handler for simple text responses like greetings or help.
"""

from typing import Dict, Any
from client.business.handlers.base_handler import BaseHandler

class SimpleTextHandler(BaseHandler):
    def __init__(self, text: str):
        self._text = text

    def handle(self, response_data: Dict[str, Any]) -> str:
        return self._text
