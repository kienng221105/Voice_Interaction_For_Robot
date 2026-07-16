"""
Handler for 'payment' intent.
This step pauses the process to display a QR code before confirming the order.
"""

import logging
from typing import Dict, Any
from client.business.handlers.base_handler import BaseHandler
from client.business.services.order_service import OrderService

logger = logging.getLogger("handler.payment")

class PaymentHandler(BaseHandler):
    def __init__(self, order_service: OrderService):
        self._order_service = order_service

    def handle(self, response_data: Dict[str, Any]) -> str:
        """Return instruction to scan QR."""
        cart_items = self._order_service.get_cart_items()
        
        if not cart_items:
            return "Giỏ hàng đang trống, không có gì để thanh toán."
            
        return "Vui lòng quét mã QR trên màn hình để thanh toán."
