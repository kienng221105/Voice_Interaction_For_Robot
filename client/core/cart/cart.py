"""
Shopping Cart.
Tracks items the customer wants to buy in the current session.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger("cart")


@dataclass
class CartItem:
    """A single item in the cart."""
    product_id: str
    quantity: int


class Cart:
    """Simple in-memory shopping cart for a single customer session."""

    def __init__(self):
        self._items: List[CartItem] = []

    def add(self, product_id: str, quantity: int) -> None:
        """Add or increment an item in the cart."""
        for item in self._items:
            if item.product_id == product_id:
                item.quantity += quantity
                logger.info(f"Updated cart: {product_id} -> {item.quantity}")
                return
        self._items.append(CartItem(product_id=product_id, quantity=quantity))
        logger.info(f"Added to cart: {quantity}x {product_id}")

    def remove(self, product_id: str) -> None:
        """Remove an item from the cart entirely."""
        self._items = [i for i in self._items if i.product_id != product_id]

    def decrease(self, product_id: str, quantity: int) -> int:
        """
        Decrease an item's quantity in the cart. 
        Returns the actual amount reduced. Removes item if quantity <= 0.
        """
        for i, item in enumerate(self._items):
            if item.product_id == product_id:
                if item.quantity <= quantity:
                    actual = item.quantity
                    del self._items[i]
                    logger.info(f"Removed {product_id} from cart entirely.")
                    return actual
                else:
                    item.quantity -= quantity
                    logger.info(f"Decreased cart: {product_id} -> {item.quantity}")
                    return quantity
        return 0

    def get_items(self) -> List[CartItem]:
        """Return a copy of all items."""
        return list(self._items)

    def clear(self) -> None:
        """Empty the cart."""
        self._items.clear()

    def is_empty(self) -> bool:
        """Check if cart has no items."""
        return len(self._items) == 0
