"""
Handler for 'confirm' intent.
Finalizes the order and triggers hardware dispensing.
"""

import logging
from typing import Dict, Any
from client.business.handlers.base_handler import BaseHandler
from client.business.services.order_service import OrderService
from client.business.services.device_service import DeviceService

logger = logging.getLogger("handler.confirm")


class ConfirmHandler(BaseHandler):
    def __init__(self, order_service: OrderService, device_service: DeviceService):
        self._order_service = order_service
        self._device_service = device_service

    def handle(self, response_data: Dict[str, Any]) -> str:
        """Commit the order and dispatch dispense commands to ESP32."""
        cart_items = self._order_service.get_cart_items()

        if not cart_items:
            return "Giỏ hàng đang trống, không có gì để xuất."

        # Commit stock (deduct permanently)
        committed_items = self._order_service.commit_order()

        # Enqueue hardware commands
        for item in committed_items:
            self._device_service.enqueue_dispense(item.product_id, item.quantity)

        names = [f"{item.quantity} {item.product_id}" for item in committed_items]
        return f"Đang xuất {', '.join(names)}. Vui lòng đợi tại khe nhận hàng."
