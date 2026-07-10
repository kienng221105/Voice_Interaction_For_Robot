"""
Handler for 'show_menu' / 'check_stock' intent.
Returns available products from local inventory.
"""

import logging
from typing import Dict, Any
from client.business.handlers.base_handler import BaseHandler
from client.core.inventory.json_inventory import JsonInventory

logger = logging.getLogger("handler.show_menu")


class ShowMenuHandler(BaseHandler):
    def __init__(self, inventory: JsonInventory):
        self._inventory = inventory

    def handle(self, response_data: Dict[str, Any]) -> str:
        """List available products from inventory."""
        available = self._inventory.get_all_available()

        if not available:
            return "Xin lỗi, hiện tại máy đã hết hàng."

        names = [f"{p.display_name} ({p.stock} chai)" for p in available]
        return f"Máy đang có: {', '.join(names)}. Bạn muốn mua gì?"
