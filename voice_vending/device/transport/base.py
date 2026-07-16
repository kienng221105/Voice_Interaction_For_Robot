"""
Transport Interface definition.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable

logger = logging.getLogger("transport")


class Transport(ABC):
    """
    Lớp cơ sở trừu tượng (Abstract Base Class) cho network transport.
    
    Cung cấp giao diện chung để xuất bản (publish) và đăng ký (subscribe) tin nhắn,
    bất kể giao thức bên dưới là gì (MQTT, HTTP, Serial, v.v.).
    """

    @abstractmethod
    def connect(self, config: dict[str, Any]) -> bool:
        """
        Thiết lập kết nối sử dụng cấu hình được cung cấp.
        
        Tham số:
            config: Từ điển chứa các thông số kết nối.
        Trả về:
            True nếu kết nối thành công, ngược lại False.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Đóng kết nối."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Trả về True nếu hiện đang kết nối."""
        pass

    @abstractmethod
    def publish(self, topic: str, payload: str, qos: int = 1) -> bool:
        pass

    @abstractmethod
    def subscribe(self, topic: str, callback: Callable[[str, str], None]) -> bool:
        """
        Đăng ký một topic/endpoint để nhận tin nhắn.
        
        Tham số:
            topic: Địa chỉ hoặc topic để lắng nghe.
            callback: Hàm được gọi khi có tin nhắn đến.
                      Chữ ký (Signature) phải là: callback(topic: str, payload: str)
        Trả về:
            True nếu thành công.
        """
        pass
