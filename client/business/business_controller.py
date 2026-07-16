"""
Business Controller (Trình điều phối Luồng công việc).
Nhận phản hồi từ AI Backend và định tuyến chúng đến Handler (Bộ xử lý) phù hợp.
Sử dụng Handler Pattern để tuân thủ Nguyên lý Đóng/Mở (Open/Closed Principle).
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
from client.business.handlers.payment_handler import PaymentHandler
from client.business.handlers.show_menu_handler import ShowMenuHandler
from client.business.handlers.simple_text_handler import SimpleTextHandler
from client.core.inventory.json_inventory import JsonInventory

logger = logging.getLogger("business_controller")


class BusinessController:
    """
    Trình điều phối trung tâm cho máy bán hàng tự động.

    Trách nhiệm:
    - Nhận JSON từ AI Backend
    - Tìm Handler phù hợp dựa trên ý định (intent)
    - Ủy quyền thực thi cho Handler đó
    - Trả về chuỗi phản hồi TTS

    Để thêm ý định mới: tạo tệp Handler mới và đăng ký nó trong _register_handlers().
    Không cần sửa đổi lớp này (Nguyên lý Đóng/Mở).
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
        """Liên kết tất cả các bộ xử lý ý định (intent handlers) với các phụ thuộc của chúng."""
        self._handlers["buy_product"] = BuyProductHandler(self._order_service)
        self._handlers["add_product"] = BuyProductHandler(self._order_service)
        self._handlers["remove_product"] = RemoveProductHandler(self._order_service)
        self._handlers["change_product"] = ChangeProductHandler(self._order_service)
        self._handlers["cancel"] = CancelHandler(self._order_service)
        self._handlers["confirm"] = ConfirmHandler(self._order_service, self._device_service)
        self._handlers["payment"] = PaymentHandler(self._order_service)  # Thanh toán mở QR
        self._handlers["show_menu"] = ShowMenuHandler(self._inventory)
        self._handlers["check_stock"] = ShowMenuHandler(self._inventory)
        self._handlers["greeting"] = SimpleTextHandler("Xin chào! Tôi có thể giúp gì cho bạn?")
        self._handlers["help"] = SimpleTextHandler("Bạn có thể gọi món, hỏi giá, hoặc nói hủy đơn.")

    def process(self, response_data: Dict[str, Any]) -> str:
        """
        Điểm vào chính. Nhận toàn bộ phản hồi JSON từ AI Backend,
        tìm handler phù hợp và trả về văn bản TTS.
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
