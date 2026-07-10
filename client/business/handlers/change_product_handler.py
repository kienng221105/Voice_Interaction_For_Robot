"""
Handler for 'change_product' intent.
Replaces one product in the cart with another.
"""

import logging
from typing import Dict, Any
from client.business.handlers.base_handler import BaseHandler
from client.business.services.order_service import OrderService

logger = logging.getLogger("handler.change_product")


class ChangeProductHandler(BaseHandler):
    def __init__(self, order_service: OrderService):
        self._order_service = order_service

    def handle(self, response_data: Dict[str, Any]) -> str:
        entities = response_data.get("entities", {})
        products = entities.get("products", [])

        if not products:
            return "Bạn muốn đổi sản phẩm nào?"

        cart_items = self._order_service.get_cart_items()

        # Case 1: User specified both what to remove and what to add (e.g. "đổi coca lấy pepsi")
        if len(products) >= 2:
            remove_prod = products[0].get("product")
            remove_qty = products[0].get("quantity", 1)
            add_prod = products[-1].get("product")
            add_qty = products[-1].get("quantity", 1)

            actual_removed = self._order_service.remove_quantity_from_cart(remove_prod, remove_qty)
            if actual_removed == 0:
                return f"Không tìm thấy {remove_prod} trong giỏ hàng để đổi."
            
            success = self._order_service.add_to_cart(add_prod, add_qty)
            if success:
                return f"Đã đổi {actual_removed} {remove_prod} thành {add_qty} {add_prod}."
            else:
                return f"Đã bỏ {actual_removed} {remove_prod}, nhưng {add_prod} đã hết hàng."

        # Case 2: User only specified what to add (e.g. "đổi sang pepsi")
        elif len(products) == 1:
            add_prod = products[0].get("product")
            add_qty = products[0].get("quantity", 1)

            if len(cart_items) == 0:
                return "Giỏ hàng đang trống, không có gì để đổi."
            elif len(cart_items) == 1:
                # If only 1 type of product in cart, safely swap it out
                remove_prod = cart_items[0].product_id
                actual_removed = self._order_service.remove_quantity_from_cart(remove_prod, cart_items[0].quantity)
                
                success = self._order_service.add_to_cart(add_prod, add_qty)
                if success:
                    return f"Đã đổi {remove_prod} thành {add_qty} {add_prod}."
                else:
                    return f"Đã bỏ {remove_prod}, nhưng {add_prod} đã hết hàng."
            else:
                # Multiple types of items in cart, we don't know which one to remove
                return f"Giỏ hàng có nhiều loại nước. Bạn muốn đổi sản phẩm nào sang {add_prod}?"
        
        return "Xin lỗi, tôi chưa rõ bạn muốn đổi như thế nào."
