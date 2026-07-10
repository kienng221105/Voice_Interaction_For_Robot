"""
Base Handler Interface.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseHandler(ABC):
    @abstractmethod
    def handle(self, response_data: Dict[str, Any]) -> None:
        """Execute logic based on Backend response."""
        pass
