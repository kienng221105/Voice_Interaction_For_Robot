"""
Bộ xử lý (Handler) cho ý định 'buy_product' (mua sản phẩm).
Thêm các sản phẩm được yêu cầu vào giỏ hàng sau khi kiểm tra kho.
"""

import logging
from typing import Dict, Any
from client.business.handlers.base_handler import BaseHandler
from client.business.services.order_service import OrderService

logger = logging.getLogger("handler.buy_product")


class BuyProductHandler(BaseHandler):
    def __init__(self, order_service: OrderService):
        self._order_service = order_service

    def handle(self, response_data: Dict[str, Any]) -> str:
        """
        Xử lý ý định mua sản phẩm.
        Trả về tin nhắn TTS cho người dùng.
        """
        entities = response_data.get("entities", {})
        products = entities.get("products", [])

        if not products:
            return response_data.get("reply", "Bạn muốn mua nước gì?")

        added = []
        failed = []

        for item in products:
            product_id = item.get("product", "")
            quantity = item.get("quantity", 1)

            if self._order_service.add_to_cart(product_id, quantity):
                added.append(f"{quantity} {product_id}")
            else:
                failed.append(product_id)

        # Xây dựng phản hồi
        if added and not failed:
            return response_data.get("reply", f"Đã thêm {', '.join(added)} vào giỏ.")
        elif failed:
            return f"Xin lỗi, {', '.join(failed)} đã hết hàng."
        else:
            return "Không thể thêm sản phẩm vào giỏ."
