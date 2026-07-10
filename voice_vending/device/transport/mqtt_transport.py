"""
MQTT implementation of the Transport interface using paho-mqtt.
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
    Concrete Transport implementation using MQTT protocol.
    """

    def __init__(self, client_id: str = "") -> None:
        self.client_id = client_id
        
        # Support both paho-mqtt v1 and v2 APIs
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=self.client_id)
        except (AttributeError, TypeError):
            self.client = mqtt.Client(client_id=self.client_id)
            
        self._connected = False
        self._callbacks: dict[str, list[Callable[[str, str], None]]] = {}
        
        # Wire up internal callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def connect(self, config: dict[str, Any]) -> bool:
        """Connect to MQTT broker."""
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
            logger.info(f"Connecting to MQTT broker at {broker}:{port}...")
            self.client.connect(broker, port, keepalive=keepalive)
            self.client.loop_start()  # Start background thread for networking
            
            # Wait briefly to confirm connection
            deadline = time.time() + 5.0
            while not self._connected and time.time() < deadline:
                time.sleep(0.1)
                
            if not self._connected:
                logger.error("Timeout waiting for MQTT connection.")
                return False
                
            return True
        except Exception as e:
            logger.error(f"MQTT connection failed: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from broker and stop background thread."""
        logger.info("Disconnecting MQTT...")
        self.client.loop_stop()
        self.client.disconnect()
        self._connected = False

    def is_connected(self) -> bool:
        """Return True if connected to broker."""
        return self._connected

    def publish(self, topic: str, payload: str, qos: int = 1) -> bool:
        """Publish message to MQTT topic."""
        if not self._connected:
            logger.error(f"Cannot publish to {topic}: not connected")
            return False
            
        try:
            info = self.client.publish(topic, payload, qos=qos)
            # info.wait_for_publish() could block, we just assume success if it didn't throw
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
