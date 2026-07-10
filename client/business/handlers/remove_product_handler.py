"""
Handler for 'remove_product' intent.
Removes a specific quantity of an item from the cart.
"""

import logging
from typing import Dict, Any
from client.business.handlers.base_handler import BaseHandler
from client.business.services.order_service import OrderService

logger = logging.getLogger("handler.remove_product")


class RemoveProductHandler(BaseHandler):
    def __init__(self, order_service: OrderService):
        self._order_service = order_service

    def handle(self, response_data: Dict[str, Any]) -> str:
        """Parse entities and remove items from the cart."""
        entities = response_data.get("entities", {})
        products = entities.get("products", [])

        if not products:
            return "Bạn muốn bỏ sản phẩm nào khỏi giỏ hàng?"

        removed = []
        for p in products:
            prod_id = p.get("product")
            qty = p.get("quantity", 1)

            if prod_id:
                actual = self._order_service.remove_quantity_from_cart(prod_id, qty)
                if actual > 0:
                    removed.append(f"{actual} {prod_id}")

        if removed:
            return f"Đã bỏ {', '.join(removed)} khỏi giỏ hàng."
        else:
            return "Không tìm thấy sản phẩm đó trong giỏ hàng."
