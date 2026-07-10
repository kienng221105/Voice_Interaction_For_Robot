"""
Inventory Manager.

Manages products, mapping to slots, and stock levels.
Completely independent of MQTT and hardware specifics.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Optional

from voice_vending.core.models import Product

logger = logging.getLogger("inventory")


class InventoryError(Exception):
    """Base exception for inventory operations."""
    pass


class OutOfStockError(InventoryError):
    pass


class InvalidProductError(InventoryError):
    pass


class InventoryManager:
    """
    Manages vending machine inventory.
    
    Thread-safe implementation for checking stock, reserving items (during payment),
    and confirming/releasing dispenses.
    """

    def __init__(self, config_path: str) -> None:
        self.config_path = config_path
        self.machine_id: str = ""
        self._products: dict[str, Product] = {}
        # In-memory transient reservations mapping product_id to reserved qty
        self._reservations: dict[str, int] = {}
        self._lock = threading.RLock()
        
        self.load_inventory()

    def load_inventory(self) -> None:
        """Load inventory from JSON file."""
        with self._lock:
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                self.machine_id = data.get("machine_id", "UNKNOWN")
                
                self._products.clear()
                self._reservations.clear()
                
                products_data = data.get("products", {})
                for pid, pdata in products_data.items():
                    product = Product.from_dict(pid, pdata)
                    self._products[pid] = product
                    self._reservations[pid] = 0
                    
                logger.info(f"Loaded {len(self._products)} products from {self.config_path}")
            except Exception as e:
                logger.error(f"Failed to load inventory: {e}")
                raise

    def save_inventory(self) -> None:
        """Persist current stock back to JSON file."""
        with self._lock:
            try:
                # Read original file to keep structure
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Update only the stock values
                for pid, product in self._products.items():
                    if pid in data.get("products", {}):
                        data["products"][pid]["stock"] = product.stock
                        
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    
                logger.debug("Inventory persisted to disk.")
            except Exception as e:
                logger.error(f"Failed to save inventory: {e}")

    # ── Queries ──────────────────────────────────────────────────

    def get_product(self, product_id: str) -> Optional[Product]:
        """Get product by ID."""
        with self._lock:
            return self._products.get(product_id)

    def find_slot(self, product_id: str) -> Optional[int]:
        """Get slot number for a product."""
        product = self.get_product(product_id)
        if product and product.enabled:
            return product.slot
        return None

    def get_price(self, product_id: str) -> int:
        """Get price for a product."""
        product = self.get_product(product_id)
        if not product:
            raise InvalidProductError(f"Product '{product_id}' not found.")
        return product.price

    def resolve_alias(self, alias: str) -> Optional[str]:
        """
        Convert a spoken alias to canonical product_id.
        E.g. 'bep si' -> 'pepsi'.
        """
        alias_lower = alias.lower().strip()
        with self._lock:
            # Check direct match first
            if alias_lower in self._products:
                return alias_lower
                
            # Check aliases
            for pid, product in self._products.items():
                if alias_lower in product.aliases:
                    return pid
        return None

    def get_all_available(self) -> list[Product]:
        """Get list of products that are enabled and in stock."""
        with self._lock:
            return [
                p for p in self._products.values()
                if p.enabled and p.slot is not None and (p.stock - self._reservations[p.id]) > 0
            ]

    # ── Stock Operations ─────────────────────────────────────────

    def check_stock(self, product_id: str, quantity: int = 1) -> bool:
        """Check if enough unreserved stock is available."""
        with self._lock:
            product = self.get_product(product_id)
            if not product or not product.enabled or product.slot is None:
                return False
                
            available = product.stock - self._reservations.get(product_id, 0)
            return available >= quantity

    def reserve(self, product_id: str, quantity: int) -> None:
        """
        Temporarily reserve stock (e.g. while waiting for hardware to dispense).
        Raises OutOfStockError if not enough stock.
        """
        with self._lock:
            if not self.check_stock(product_id, quantity):
                raise OutOfStockError(f"Not enough stock for '{product_id}'")
            self._reservations[product_id] += quantity
            logger.debug(f"Reserved {quantity}x '{product_id}'. Total reserved: {self._reservations[product_id]}")

    def confirm_dispense(self, product_id: str, quantity: int) -> None:
        """
        Hardware successfully dispensed. Deduct from actual stock and clear reservation.
        """
        with self._lock:
            if product_id not in self._products:
                raise InvalidProductError(f"Product '{product_id}' not found.")
                
            # Decrease actual stock
            self._products[product_id].stock -= quantity
            
            # Decrease reservation (clamp to 0 just in case)
            self._reservations[product_id] = max(0, self._reservations[product_id] - quantity)
            
            logger.info(f"Confirmed dispense {quantity}x '{product_id}'. New stock: {self._products[product_id].stock}")
            
            # Auto-save after successful dispense
            self.save_inventory()

    def release(self, product_id: str, quantity: int) -> None:
        """
        Hardware failed to dispense. Release the reserved stock back.
        """
        with self._lock:
            if product_id in self._reservations:
                self._reservations[product_id] = max(0, self._reservations[product_id] - quantity)
                logger.info(f"Released reservation for {quantity}x '{product_id}'.")

    # ── Admin ────────────────────────────────────────────────────

    def restock(self, product_id: str, quantity: int) -> None:
        """Admin command to add stock."""
        with self._lock:
            product = self.get_product(product_id)
            if not product:
                raise InvalidProductError(f"Product '{product_id}' not found.")
                
            product.stock = min(product.max_stock, product.stock + quantity)
            logger.info(f"Restocked '{product_id}'. New stock: {product.stock}")
            self.save_inventory()
