"""
Inventory Interface and Models.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any

class IInventory(ABC):
    @abstractmethod
    def check_stock(self, product_id: str, quantity: int) -> bool:
        pass

    @abstractmethod
    def reserve(self, product_id: str, quantity: int) -> None:
        pass

    @abstractmethod
    def commit(self, product_id: str, quantity: int) -> None:
        pass

    @abstractmethod
    def rollback(self, product_id: str, quantity: int) -> None:
        pass
