"""
Handler for 'cancel' intent.
Cancels the current order and releases all reservations.
"""

import logging
from typing import Dict, Any
from client.business.handlers.base_handler import BaseHandler
from client.business.services.order_service import OrderService

logger = logging.getLogger("handler.cancel")


class CancelHandler(BaseHandler):
    def __init__(self, order_service: OrderService):
        self._order_service = order_service

    def handle(self, response_data: Dict[str, Any]) -> str:
        """Cancel the order, rollback inventory, clear cart."""
        self._order_service.cancel_order()
        return response_data.get("reply", "Đã hủy giao dịch.")
