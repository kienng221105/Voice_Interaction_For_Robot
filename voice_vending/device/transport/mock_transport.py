"""
Bản triển khai giả lập (Mock) của interface Transport phục vụ cho kiểm thử (testing).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable

from voice_vending.device.transport.base import Transport

logger = logging.getLogger("mock_transport")


class MockTransport(Transport):
    """
    In-memory Mock Transport.
    
    Thay vì gửi tin nhắn qua mạng, nó chỉ định tuyến các tin nhắn đã xuất bản
    trực tiếp đến bất kỳ callback nào đã đăng ký trong cùng một tiến trình Python.
    Hỗ trợ khớp mẫu MQTT cơ bản (+ và #).
    """

    def __init__(self) -> None:
        self._connected = False
        # topic_pattern -> list of callbacks
        self._subscriptions: dict[str, list[Callable[[str, str], None]]] = {}
        # Lịch sử của tất cả các tin nhắn đã xuất bản để phục vụ xác nhận (assertion) trong kiểm thử
        self.published_messages: list[tuple[str, str]] = []

    def connect(self, config: dict[str, Any]) -> bool:
        """Giả lập kết nối."""
        self._connected = True
        logger.info("Mock Transport connected.")
        return True

    def disconnect(self) -> None:
        """Giả lập ngắt kết nối."""
        self._connected = False
        logger.info("Mock Transport disconnected.")

    def is_connected(self) -> bool:
        return self._connected

    def publish(self, topic: str, payload: str, qos: int = 1) -> bool:
        """
        Ghi lại tin nhắn đã xuất bản và định tuyến nó đến các subscriber phù hợp.
        """
        if not self._connected:
            logger.error(f"Cannot publish to {topic}: mock transport not connected.")
            return False

        logger.debug(f"[Mock Publish] {topic} : {payload}")
        self.published_messages.append((topic, payload))

        # Route to subscribers
        for sub_topic, callbacks in self._subscriptions.items():
            if self._topic_matches(sub_topic, topic):
                for callback in callbacks:
                    try:
                        callback(topic, payload)
                    except Exception as e:
                        logger.error(f"Mock subscriber error on topic {topic}: {e}")

        return True

    def subscribe(self, topic: str, callback: Callable[[str, str], None]) -> bool:
        """Đăng ký một callback cho một mẫu topic."""
        if topic not in self._subscriptions:
            self._subscriptions[topic] = []
        self._subscriptions[topic].append(callback)
        logger.debug(f"Mock Subscribed to: {topic}")
        return True

    # ── Utilities ────────────────────────────────────────────

    def clear_history(self) -> None:
        """Xóa lịch sử tin nhắn đã xuất bản (hữu ích giữa các trường hợp kiểm thử)."""
        self.published_messages.clear()

    @staticmethod
    def _topic_matches(pattern: str, topic: str) -> bool:
        """
        Kiểm tra xem một topic có khớp với mẫu đăng ký MQTT hay không.
        Hỗ trợ '+' (một cấp) và '#' (nhiều cấp).
        """
        if pattern == topic:
            return True

        # Chuyển đổi mẫu MQTT sang Regex
        # Thay thế '+' bằng '[^/]+'
        # Thay thế '#' bằng '.*'
        regex_pattern = pattern.replace("+", r"[^/]+")
        regex_pattern = regex_pattern.replace("#", r".*")
        
        # Exact match required from start to end
        regex_pattern = f"^{regex_pattern}$"
        
        try:
            return bool(re.match(regex_pattern, topic))
        except re.error:
            return False
