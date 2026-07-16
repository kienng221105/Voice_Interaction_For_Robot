"""
Dịch vụ Quản lý Hội thoại.

Xử lý máy trạng thái (state machine) của cuộc hội thoại. Tách biệt với logic NLU.
Nhận Ý định & Thực thể (Intents & Entities) có cấu trúc và trả về chuỗi TTS (phản hồi).
Gửi lệnh đến kho hàng (Inventory) và Hàng đợi lệnh (CommandQueue) khi đơn hàng được chốt.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from voice_vending.services.command_queue import CommandQueue
from voice_vending.services.inventory_manager import InventoryManager

logger = logging.getLogger("dialogue")


class DialogueState(Enum):
    IDLE = "idle"
    WAITING_QUANTITY = "waiting_quantity"
    WAITING_CONFIRMATION = "waiting_confirmation"


@dataclass
class ConversationContext:
    """Lưu trữ chi tiết của đơn hàng đang diễn ra."""
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    quantity: int = 0
    
    def clear(self) -> None:
        self.product_id = None
        self.product_name = None
        self.quantity = 0


class DialogueManager:
    """
    Quản lý các trạng thái hội thoại và thực thi logic bán hàng dựa trên ý định (intents) từ AI.
    """

    def __init__(self, inventory: InventoryManager, queue: CommandQueue) -> None:
        self.inventory = inventory
        self.queue = queue
        
        self.state = DialogueState.IDLE
        self.context = ConversationContext()

    def process_intent(self, intent: str, entities: dict[str, Any]) -> str:
        """
        Xử lý một ý định NLP và trả về phản hồi văn bản cho TTS.
        """
        logger.info(f"State: {self.state.value} | Intent: {intent} | Entities: {entities}")
        
        if intent == "cancel":
            return self._handle_cancel()
            
        if intent == "check_stock":
            return self._handle_check_stock(entities)
            
        if self.state == DialogueState.IDLE:
            if intent == "buy_product":
                return self._handle_buy_product(entities)
                
        elif self.state == DialogueState.WAITING_QUANTITY:
            if intent == "provide_quantity":
                return self._handle_provide_quantity(entities)
                
        elif self.state == DialogueState.WAITING_CONFIRMATION:
            if intent == "confirm_yes":
                return self._handle_confirm_yes()
            elif intent == "confirm_no":
                return self._handle_cancel()
                
        # Dự phòng cho các ý định không mong đợi trong trạng thái hiện tại
        self.state = DialogueState.IDLE
        self.context.clear()
        return "Xin lỗi, tôi chưa hiểu ý bạn. Bạn muốn mua nước gì?"

    # ── Intent Handlers ──────────────────────────────────────────

    def _handle_cancel(self) -> str:
        self.state = DialogueState.IDLE
        self.context.clear()
        return "Đã hủy giao dịch. Bạn cần mua gì khác không?"

    def _handle_check_stock(self, entities: dict[str, Any]) -> str:
        product_raw = entities.get("product")
        
        if product_raw:
            pid = self.inventory.resolve_alias(product_raw)
            if pid:
                prod = self.inventory.get_product(pid)
                if prod and prod.stock > 0:
                    return f"Máy còn {prod.stock} {prod.display_name}. Bạn muốn mua mấy chai?"
                else:
                    return f"Xin lỗi, {product_raw} đã hết hàng."
            return f"Xin lỗi, máy không bán {product_raw}."
            
        # Không hỏi sản phẩm cụ thể, liệt kê danh sách có sẵn
        available = self.inventory.get_all_available()
        if not available:
            return "Hiện tại máy đã hết sạch hàng, xin lỗi quý khách."
            
        names = [p.display_name for p in available]
        return f"Hiện tại máy đang có: {', '.join(names)}. Bạn muốn dùng gì?"

    def _handle_buy_product(self, entities: dict[str, Any]) -> str:
        product_raw = entities.get("product")
        if not product_raw:
            return "Bạn muốn mua nước gì?"
            
        pid = self.inventory.resolve_alias(product_raw)
        if not pid:
            return f"Xin lỗi, máy không bán {product_raw}."
            
        prod = self.inventory.get_product(pid)
        if not prod or not prod.enabled or prod.slot is None:
            return f"Xin lỗi, {prod.display_name if prod else product_raw} hiện không phục vụ."
            
        # Kiểm tra số lượng
        qty = entities.get("quantity")
        if not qty or int(qty) <= 0:
            # Thiếu số lượng, hỏi người dùng
            self.context.product_id = pid
            self.context.product_name = prod.display_name
            self.state = DialogueState.WAITING_QUANTITY
            return f"Bạn muốn mua mấy {prod.display_name}?"
            
        qty = int(qty)
        return self._prepare_confirmation(pid, prod.display_name, qty)

    def _handle_provide_quantity(self, entities: dict[str, Any]) -> str:
        qty = entities.get("quantity")
        if not qty or int(qty) <= 0:
            return "Bạn vui lòng nói rõ số lượng muốn mua."
            
        qty = int(qty)
        return self._prepare_confirmation(
            self.context.product_id, 
            self.context.product_name, 
            qty
        )

    def _prepare_confirmation(self, pid: str, name: str, qty: int) -> str:
        """Kiểm tra kho trước khi yêu cầu xác nhận."""
        if not self.inventory.check_stock(pid, qty):
            prod = self.inventory.get_product(pid)
            available = prod.stock if prod else 0
            self.state = DialogueState.IDLE
            self.context.clear()
            if available > 0:
                return f"Xin lỗi, máy chỉ còn {available} {name}. Vui lòng mua số lượng ít hơn."
            else:
                return f"Xin lỗi, {name} hiện đã hết hàng."
                
        # Kho còn hàng, tiếp tục xác nhận
        self.context.product_id = pid
        self.context.product_name = name
        self.context.quantity = qty
        self.state = DialogueState.WAITING_CONFIRMATION
        
        total_price = self.inventory.get_price(pid) * qty
        return f"Bạn muốn mua {qty} {name}, tổng cộng {total_price} đồng, đúng không ạ?"

    def _handle_confirm_yes(self) -> str:
        pid = self.context.product_id
        qty = self.context.quantity
        name = self.context.product_name
        
        self.state = DialogueState.IDLE
        self.context.clear()
        
        if not pid or qty <= 0:
            return "Đã có lỗi xảy ra, vui lòng thử lại."
            
        # Thử đưa đơn hàng vào hàng đợi
        success = self.queue.enqueue(pid, qty)
        if success:
            return f"Đang xuất {qty} {name}. Vui lòng đợi ở khe nhận hàng."
        else:
            return f"Xin lỗi, {name} vừa hết hàng. Vui lòng chọn món khác."
