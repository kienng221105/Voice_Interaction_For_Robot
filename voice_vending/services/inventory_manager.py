"""
Trình quản lý Kho hàng (Inventory Manager).

Quản lý các sản phẩm, ánh xạ đến khe chứa (slots) và mức tồn kho.
Hoàn toàn độc lập với MQTT và các đặc thù của phần cứng.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Optional

from voice_vending.core.models import Product

logger = logging.getLogger("inventory")


class InventoryError(Exception):
    """Lỗi cơ bản cho các thao tác kho hàng."""
    pass


class OutOfStockError(InventoryError):
    pass


class InvalidProductError(InventoryError):
    pass


class InventoryManager:
    """
    Quản lý kho hàng của máy bán hàng tự động.
    
    Triển khai an toàn luồng (Thread-safe) để kiểm tra tồn kho, giữ chỗ sản phẩm (trong khi thanh toán),
    và xác nhận/nhả lệnh xả hàng.
    """

    def __init__(self, config_path: str) -> None:
        self.config_path = config_path
        self.machine_id: str = ""
        self._products: dict[str, Product] = {}
        # Map giữ chỗ tạm thời trong bộ nhớ: product_id -> số lượng giữ chỗ
        self._reservations: dict[str, int] = {}
        self._lock = threading.RLock()
        
        self.load_inventory()

    def load_inventory(self) -> None:
        """Tải kho hàng từ tệp JSON."""
        with self._lock:
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                self.machine_id = data.get("machine_id", "UNKNOWN")
                
                self._products.clear()
                self._reservations.clear()
                
                products_data = data.get("products", {})
                for pid, pdata in products_data.items():
                    product = Product.from_dict(pid, pdata)
                    self._products[pid] = product
                    self._reservations[pid] = 0
                    
                logger.info(f"Đã tải {len(self._products)} sản phẩm từ {self.config_path}")
            except Exception as e:
                logger.error(f"Không thể tải kho hàng: {e}")
                raise

    def save_inventory(self) -> None:
        """Lưu tồn kho hiện tại vào tệp JSON."""
        with self._lock:
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Cập nhật chỉ các giá trị tồn kho
                for pid, product in self._products.items():
                    if pid in data.get("products", {}):
                        data["products"][pid]["stock"] = product.stock
                        
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    
                logger.debug("Kho hàng đã được lưu xuống đĩa.")
            except Exception as e:
                logger.error(f"Không thể lưu kho hàng: {e}")

    # ── Queries ──────────────────────────────────────────────────

    def get_product(self, product_id: str) -> Optional[Product]:
        """Lấy sản phẩm theo ID."""
        with self._lock:
            return self._products.get(product_id)

    def find_slot(self, product_id: str) -> Optional[int]:
        """Lấy số thứ tự khe chứa của một sản phẩm."""
        product = self.get_product(product_id)
        if product and product.enabled:
            return product.slot
        return None

    def get_price(self, product_id: str) -> int:
        """Lấy giá của sản phẩm."""
        product = self.get_product(product_id)
        if not product:
            raise InvalidProductError(f"Không tìm thấy sản phẩm '{product_id}'.")
        return product.price

    def resolve_alias(self, alias: str) -> Optional[str]:
        """
        Chuyển đổi một tên gọi (alias) thành product_id chuẩn.
        Ví dụ: 'bep si' -> 'pepsi'.
        """
        alias_lower = alias.lower().strip()
        with self._lock:
            # Kiểm tra khớp trực tiếp trước
            if alias_lower in self._products:
                return alias_lower
                
            # Kiểm tra các tên gọi khác
            for pid, product in self._products.items():
                if alias_lower in product.aliases:
                    return pid
        return None

    def get_all_available(self) -> list[Product]:
        """Lấy danh sách các sản phẩm đang bật và còn hàng."""
        with self._lock:
            return [
                p for p in self._products.values()
                if p.enabled and p.slot is not None and (p.stock - self._reservations[p.id]) > 0
            ]

    # ── Stock Operations ─────────────────────────────────────────

    def check_stock(self, product_id: str, quantity: int = 1) -> bool:
        """Kiểm tra xem có đủ hàng chưa được đặt trước hay không."""
        with self._lock:
            product = self.get_product(product_id)
            if not product or not product.enabled or product.slot is None:
                return False
                
            available = product.stock - self._reservations.get(product_id, 0)
            return available >= quantity

    def reserve(self, product_id: str, quantity: int) -> None:
        """
        Giữ chỗ tồn kho tạm thời (ví dụ: trong khi chờ phần cứng xả hàng).
        Báo lỗi OutOfStockError nếu không đủ hàng.
        """
        with self._lock:
            if not self.check_stock(product_id, quantity):
                raise OutOfStockError(f"Không đủ hàng cho '{product_id}'")
            self._reservations[product_id] += quantity
            logger.debug(f"Đã giữ chỗ {quantity}x '{product_id}'. Tổng đã giữ: {self._reservations[product_id]}")

    def confirm_dispense(self, product_id: str, quantity: int) -> None:
        """
        Phần cứng đã xả hàng thành công. Trừ vào tồn kho thực tế và xóa giữ chỗ.
        """
        with self._lock:
            if product_id not in self._products:
                raise InvalidProductError(f"Không tìm thấy sản phẩm '{product_id}'.")
                
            # Trừ tồn kho thực tế
            self._products[product_id].stock -= quantity
            
            # Giảm số lượng giữ chỗ (giới hạn ở mức 0 để phòng hờ)
            self._reservations[product_id] = max(0, self._reservations[product_id] - quantity)
            
            logger.info(f"Xác nhận xả {quantity}x '{product_id}'. Tồn kho mới: {self._products[product_id].stock}")
            
            # Tự động lưu sau khi xả hàng thành công
            self.save_inventory()

    def release(self, product_id: str, quantity: int) -> None:
        """
        Phần cứng xả hàng thất bại. Nhả lại số lượng tồn kho đã giữ chỗ.
        """
        with self._lock:
            if product_id in self._reservations:
                self._reservations[product_id] = max(0, self._reservations[product_id] - quantity)
                logger.info(f"Đã nhả giữ chỗ cho {quantity}x '{product_id}'.")

    # ── Admin ────────────────────────────────────────────────────

    def restock(self, product_id: str, quantity: int) -> None:
        """Lệnh quản trị để thêm số lượng tồn kho."""
        with self._lock:
            product = self.get_product(product_id)
            if not product:
                raise InvalidProductError(f"Không tìm thấy sản phẩm '{product_id}'.")
                
            product.stock = min(product.max_stock, product.stock + quantity)
            self.save_inventory()
