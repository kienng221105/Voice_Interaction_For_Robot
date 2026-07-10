"""
Order Service.
Manages the shopping cart and interacts with Inventory through interface.
Does NOT own inventory data - only consumes the IInventory interface.
"""

import logging
from typing import List, Optional
from client.core.inventory.interface import IInventory
from client.core.cart.cart import Cart, CartItem

logger = logging.getLogger("order_service")


class OrderService:
    """
    Handles order-related business logic:
    - Add/remove items from cart
    - Check stock via IInventory
    - Reserve stock when adding to cart
    - Commit or rollback when order completes or fails
    """

    def __init__(self, inventory: IInventory):
        self._inventory = inventory
        self._cart = Cart()

    @property
    def cart(self) -> Cart:
        """Access the current cart."""
        return self._cart

    def add_to_cart(self, product_id: str, quantity: int) -> bool:
        """
        Check stock, reserve it, and add to cart.
        Returns True if successful, False if out of stock.
        """
        if not self._inventory.check_stock(product_id, quantity):
            logger.warning(f"Out of stock: {quantity}x '{product_id}'")
            return False

        try:
            self._inventory.reserve(product_id, quantity)
            self._cart.add(product_id, quantity)
            return True
        except Exception as e:
            logger.error(f"Failed to reserve: {e}")
            return False

    def remove_from_cart(self, product_id: str) -> None:
        """Remove item from cart and release its reservation entirely."""
        for item in self._cart.get_items():
            if item.product_id == product_id:
                self._inventory.rollback(product_id, item.quantity)
                self._cart.remove(product_id)
                return

    def remove_quantity_from_cart(self, product_id: str, quantity: int) -> int:
        """
        Remove a specific quantity of an item from cart and release its reservation.
        Returns the actual quantity removed.
        """
        actual = self._cart.decrease(product_id, quantity)
        if actual > 0:
            self._inventory.rollback(product_id, actual)
        return actual

    def get_cart_items(self) -> List[CartItem]:
        """Return current cart contents."""
        return self._cart.get_items()

    def commit_order(self) -> List[CartItem]:
        """
        Finalize the order: commit all reserved stock.
        Returns the list of items that were committed.
        """
        items = self._cart.get_items()
        for item in items:
            self._inventory.commit(item.product_id, item.quantity)
        self._cart.clear()
        logger.info(f"Order committed: {len(items)} item(s)")
        return items

    def cancel_order(self) -> None:
        """Cancel the order: rollback all reservations and clear cart."""
        for item in self._cart.get_items():
            self._inventory.rollback(item.product_id, item.quantity)
        self._cart.clear()
        logger.info("Order cancelled, all reservations released")
