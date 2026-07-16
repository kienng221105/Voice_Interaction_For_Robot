"""
Bản triển khai MQTT của giao diện Transport sử dụng paho-mqtt.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

import paho.mqtt.client as mqtt

from voice_vending.device.transport.base import Transport

logger = logging.getLogger("mqtt_transport")


class MQTTTransport(Transport):
    """
    Bản triển khai Transport cụ thể sử dụng giao thức MQTT.
    """

    def __init__(self, client_id: str = "") -> None:
        self.client_id = client_id
        
        # Hỗ trợ cả API paho-mqtt v1 và v2
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=self.client_id)
        except (AttributeError, TypeError):
            self.client = mqtt.Client(client_id=self.client_id)
            
        self._connected = False
        self._callbacks: dict[str, list[Callable[[str, str], None]]] = {}
        
        # Gắn các callback nội bộ
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def connect(self, config: dict[str, Any]) -> bool:
        """Kết nối đến broker MQTT."""
        broker = config.get("broker", "localhost")
        port = int(config.get("port", 1883))
        keepalive = int(config.get("keepalive", 60))
        use_tls = config.get("use_tls", False)
        username = config.get("username", "")
        password = config.get("password", "")

        if username:
            self.client.username_pw_set(username, password)
        if use_tls:
            self.client.tls_set()

        try:
            logger.info(f"Đang kết nối đến MQTT broker tại {broker}:{port}...")
            self.client.connect(broker, port, keepalive=keepalive)
            self.client.loop_start()  # Bắt đầu luồng nền cho kết nối mạng
            
            # Đợi một chút để xác nhận kết nối
            deadline = time.time() + 5.0
            while not self._connected and time.time() < deadline:
                time.sleep(0.1)
                
            if not self._connected:
                logger.error("Hết thời gian chờ kết nối MQTT.")
                return False
                
            return True
        except Exception as e:
            logger.error(f"Kết nối MQTT thất bại: {e}")
            return False

    def disconnect(self) -> None:
        """Ngắt kết nối khỏi broker và dừng luồng chạy ngầm."""
        logger.info("Đang ngắt kết nối MQTT...")
        self.client.loop_stop()
        self.client.disconnect()
        self._connected = False

    def is_connected(self) -> bool:
        """Trả về True nếu đã kết nối với broker."""
        return self._connected

    def publish(self, topic: str, payload: str, qos: int = 1) -> bool:
        """Xuất bản tin nhắn lên topic MQTT."""
        if not self._connected:
            logger.error(f"Không thể xuất bản tới {topic}: chưa kết nối")
            return False
            
        try:
            info = self.client.publish(topic, payload, qos=qos)
            return True
        except Exception as e:
            logger.error(f"Publish failed: {e}")
            return False

    def subscribe(self, topic: str, callback: Callable[[str, str], None]) -> bool:
        """
        Subscribe to an MQTT topic.
        Registers the callback in an internal dictionary.
        """
        if topic not in self._callbacks:
            self._callbacks[topic] = []
        self._callbacks[topic].append(callback)
        
        if self._connected:
            try:
                self.client.subscribe(topic)
                logger.info(f"Subscribed to topic: {topic}")
                return True
            except Exception as e:
                logger.error(f"Subscribe failed: {e}")
                return False
        return True # Will be subscribed automatically upon connection (paho-mqtt handles this)

    # ── Internal Callbacks ───────────────────────────────────

    def _on_connect(self, client: mqtt.Client, userdata: object, flags: dict, rc: int) -> None:
        if rc == 0:
            logger.info("MQTT connected successfully.")
            self._connected = True
            # Resubscribe to all topics if reconnected
            for topic in self._callbacks.keys():
                self.client.subscribe(topic)
        else:
            logger.error(f"MQTT connection refused with code {rc}")

    def _on_disconnect(self, client: mqtt.Client, userdata: object, rc: int) -> None:
        self._connected = False
        if rc != 0:
            logger.warning("Unexpected MQTT disconnection.")

    def _on_message(self, client: mqtt.Client, userdata: object, msg: mqtt.MQTTMessage) -> None:
        topic = msg.topic
        try:
            payload = msg.payload.decode("utf-8", errors="replace")
        except Exception:
            payload = ""
            
        # Dispatch to all registered callbacks for this topic
        handlers = self._callbacks.get(topic, [])
        for handler in handlers:
            try:
                handler(topic, payload)
            except Exception as e:
                logger.error(f"Error in message handler for {topic}: {e}")
