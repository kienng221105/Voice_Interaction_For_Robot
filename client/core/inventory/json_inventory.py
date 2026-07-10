"""
JSON-based Inventory Manager implementing IInventory.
Manages product stock using a local JSON file.
"""

import json
import logging
import threading
from typing import Dict, List, Optional
from dataclasses import dataclass
from client.core.inventory.interface import IInventory

logger = logging.getLogger("inventory")


@dataclass
class ProductInfo:
    """Represents a product in the vending machine."""
    product_id: str
    display_name: str
    slot: Optional[int]
    stock: int
    price: int
    enabled: bool


class OutOfStockError(Exception):
    """Raised when requested quantity exceeds available stock."""
    pass


class JsonInventory(IInventory):
    """
    File-backed inventory manager.
    Supports reserve/commit/rollback pattern for safe concurrent access.
    """

    def __init__(self, config_path: str):
        self._config_path = config_path
        self._lock = threading.RLock()
        self._products: Dict[str, ProductInfo] = {}
        self._reservations: Dict[str, int] = {}
        self._machine_id: str = ""
        self._load()

    def _load(self) -> None:
        """Load inventory from JSON file."""
        with open(self._config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._machine_id = data.get("machine_id", "VM_UNKNOWN")

        for pid, info in data.get("products", {}).items():
            self._products[pid] = ProductInfo(
                product_id=pid,
                display_name=info.get("display_name", pid),
                slot=info.get("slot"),
                stock=info.get("stock", 0),
                price=info.get("price", 0),
                enabled=info.get("enabled", True),
            )
            self._reservations[pid] = 0

        logger.info(f"Loaded {len(self._products)} products for machine {self._machine_id}")

    def _save(self) -> None:
        """Persist current state to JSON file."""
        data = {"machine_id": self._machine_id, "products": {}}
        for pid, p in self._products.items():
            data["products"][pid] = {
                "display_name": p.display_name,
                "slot": p.slot,
                "stock": p.stock,
                "price": p.price,
                "enabled": p.enabled,
            }
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @property
    def machine_id(self) -> str:
        return self._machine_id

    def check_stock(self, product_id: str, quantity: int) -> bool:
        """Check if enough stock is available (accounting for reservations)."""
        with self._lock:
            product = self._products.get(product_id)
            if not product or not product.enabled or product.slot is None:
                return False
            available = product.stock - self._reservations.get(product_id, 0)
            return available >= quantity

    def reserve(self, product_id: str, quantity: int) -> None:
        """Reserve stock. Raises OutOfStockError if insufficient."""
        with self._lock:
            if not self.check_stock(product_id, quantity):
                raise OutOfStockError(f"Cannot reserve {quantity}x '{product_id}'")
            self._reservations[product_id] = self._reservations.get(product_id, 0) + quantity
            logger.info(f"Reserved {quantity}x '{product_id}'")

    def commit(self, product_id: str, quantity: int) -> None:
        """Confirm dispensing: reduce stock permanently."""
        with self._lock:
            product = self._products.get(product_id)
            if product:
                product.stock = max(0, product.stock - quantity)
            self._reservations[product_id] = max(0, self._reservations.get(product_id, 0) - quantity)
            self._save()
            logger.info(f"Committed {quantity}x '{product_id}'. Remaining: {product.stock if product else '?'}")

    def rollback(self, product_id: str, quantity: int) -> None:
        """Release reservation without reducing stock."""
        with self._lock:
            self._reservations[product_id] = max(0, self._reservations.get(product_id, 0) - quantity)
            logger.info(f"Rolled back {quantity}x '{product_id}'")

    def get_product(self, product_id: str) -> Optional[ProductInfo]:
        """Get product info by ID."""
        return self._products.get(product_id)

    def get_slot(self, product_id: str) -> Optional[int]:
        """Get the physical slot number for a product."""
        product = self._products.get(product_id)
        return product.slot if product else None

    def get_all_available(self) -> List[ProductInfo]:
        """Return all products that are enabled and in stock."""
        return [
            p for p in self._products.values()
            if p.enabled and p.slot is not None and p.stock > 0
        ]
