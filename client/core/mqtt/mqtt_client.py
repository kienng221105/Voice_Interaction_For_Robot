"""
MQTT Client Wrapper.
Provides a simple publish/subscribe interface for communicating with ESP32.
All broker config is read from constructor parameters (no hardcode).
"""

import logging
import threading
from typing import Callable, Optional

import paho.mqtt.client as mqtt

logger = logging.getLogger("mqtt_client")


class MQTTClient:
    """
    Thin wrapper around paho-mqtt.
    Handles connection, publish, and subscribe with callbacks.
    """

    def __init__(self, broker_host: str, broker_port: int = 1883,
                 username: Optional[str] = None, password: Optional[str] = None):
        self._broker_host = broker_host
        self._broker_port = broker_port
        self._client = mqtt.Client()
        self._connected = False

        if username and password:
            self._client.username_pw_set(username, password)

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        self._subscriptions: dict[str, Callable[[str, str], None]] = {}

    def connect(self) -> None:
        """Connect to the MQTT broker in background."""
        try:
            self._client.connect(self._broker_host, self._broker_port, keepalive=60)
            self._client.loop_start()
            logger.info(f"Connecting to MQTT broker {self._broker_host}:{self._broker_port}...")
        except Exception as e:
            logger.error(f"MQTT connection failed: {e}")

    def disconnect(self) -> None:
        """Disconnect from the broker."""
        self._client.loop_stop()
        self._client.disconnect()
        self._connected = False
        logger.info("MQTT disconnected")

    def publish(self, topic: str, payload: str) -> None:
        """Publish a message to a topic."""
        self._client.publish(topic, payload)
        logger.debug(f"Published to {topic}: {payload}")

    def subscribe(self, topic: str, callback: Callable[[str, str], None]) -> None:
        """Subscribe to a topic with a callback."""
        self._subscriptions[topic] = callback
        if self._connected:
            self._client.subscribe(topic)
        logger.info(f"Subscribed to {topic}")

    def _on_connect(self, client, userdata, flags, rc) -> None:
        """Called when broker connection is established."""
        if rc == 0:
            self._connected = True
            logger.info("MQTT connected successfully")
            # Re-subscribe to all topics on reconnect
            for topic in self._subscriptions:
                self._client.subscribe(topic)
        else:
            logger.error(f"MQTT connection failed with code {rc}")

    def _on_disconnect(self, client, userdata, rc) -> None:
        """Called when broker connection is lost."""
        self._connected = False
        if rc != 0:
            logger.warning(f"MQTT unexpected disconnect (rc={rc})")

    def _on_message(self, client, userdata, msg) -> None:
        """Route incoming messages to registered callbacks."""
        topic = msg.topic
        payload = msg.payload.decode("utf-8", errors="replace")
        callback = self._subscriptions.get(topic)
        if callback:
            try:
                callback(topic, payload)
            except Exception as e:
                logger.error(f"Callback error for {topic}: {e}")

    @property
    def is_connected(self) -> bool:
        return self._connected
