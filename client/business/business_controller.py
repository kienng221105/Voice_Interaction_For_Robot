"""
Business Controller (Workflow Orchestrator).
Receives AI Backend responses and routes them to the correct Handler.
Uses Handler Pattern to comply with Open/Closed Principle.
"""

import logging
from typing import Dict, Any, Optional
from client.business.handlers.base_handler import BaseHandler
from client.business.services.order_service import OrderService
from client.business.services.device_service import DeviceService
from client.business.handlers.buy_product_handler import BuyProductHandler
from client.business.handlers.remove_product_handler import RemoveProductHandler
from client.business.handlers.change_product_handler import ChangeProductHandler
from client.business.handlers.cancel_handler import CancelHandler
from client.business.handlers.confirm_handler import ConfirmHandler
from client.business.handlers.show_menu_handler import ShowMenuHandler
from client.business.handlers.simple_text_handler import SimpleTextHandler
from client.core.inventory.json_inventory import JsonInventory

logger = logging.getLogger("business_controller")


class BusinessController:
    """
    Central orchestrator for the vending machine client.

    Responsibilities:
    - Receive JSON from AI Backend
    - Look up the correct Handler based on intent
    - Delegate execution to that Handler
    - Return the TTS response string

    To add a new intent: create a new Handler file and register it in _register_handlers().
    No modification to this class is needed (Open/Closed Principle).
    """

    def __init__(self, order_service: OrderService,
                 device_service: DeviceService,
                 inventory: JsonInventory):
        self._order_service = order_service
        self._device_service = device_service
        self._inventory = inventory
        self._handlers: Dict[str, BaseHandler] = {}

        self._register_handlers()

    def _register_handlers(self) -> None:
        """Wire up all intent handlers with their dependencies."""
        self._handlers["buy_product"] = BuyProductHandler(self._order_service)
        self._handlers["add_product"] = BuyProductHandler(self._order_service)  # Same logic
        self._handlers["remove_product"] = RemoveProductHandler(self._order_service)
        self._handlers["change_product"] = ChangeProductHandler(self._order_service)
        self._handlers["cancel"] = CancelHandler(self._order_service)
        self._handlers["confirm"] = ConfirmHandler(self._order_service, self._device_service)
        self._handlers["payment"] = self._handlers["confirm"]  # Payment is confirming the order
        self._handlers["show_menu"] = ShowMenuHandler(self._inventory)
        self._handlers["check_stock"] = ShowMenuHandler(self._inventory)
        self._handlers["greeting"] = SimpleTextHandler("Xin chào! Tôi có thể giúp gì cho bạn?")
        self._handlers["help"] = SimpleTextHandler("Bạn có thể gọi món, hỏi giá, hoặc nói hủy đơn.")

    def process(self, response_data: Dict[str, Any]) -> str:
        """
        Main entry point. Takes the full AI Backend JSON response,
        finds the correct handler, and returns TTS text.
        """
        intent = response_data.get("intent", "unknown")
        logger.info(f"Processing intent: '{intent}'")

        handler = self._handlers.get(intent)

        if handler:
            return handler.handle(response_data)

        # Fallback: return whatever Backend already generated as reply
        reply = response_data.get("reply", "")
        if reply:
            return reply
        return "Xin lỗi, tôi chưa hiểu ý bạn."
