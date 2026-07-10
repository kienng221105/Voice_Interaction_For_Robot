"""
Mock implementation of the Transport interface for testing.
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
    
    Instead of sending messages over the network, it simply routes published 
    messages directly to any subscribed callbacks in the same Python process.
    Supports basic MQTT wildcard matching (+ and #).
    """

    def __init__(self) -> None:
        self._connected = False
        # topic_pattern -> list of callbacks
        self._subscriptions: dict[str, list[Callable[[str, str], None]]] = {}
        # History of all published messages for assertions in tests
        self.published_messages: list[tuple[str, str]] = []

    def connect(self, config: dict[str, Any]) -> bool:
        """Simulate connection."""
        self._connected = True
        logger.info("Mock Transport connected.")
        return True

    def disconnect(self) -> None:
        """Simulate disconnection."""
        self._connected = False
        logger.info("Mock Transport disconnected.")

    def is_connected(self) -> bool:
        return self._connected

    def publish(self, topic: str, payload: str, qos: int = 1) -> bool:
        """
        Record the published message and route it to matching subscribers.
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
        """Register a callback for a topic pattern."""
        if topic not in self._subscriptions:
            self._subscriptions[topic] = []
        self._subscriptions[topic].append(callback)
        logger.debug(f"Mock Subscribed to: {topic}")
        return True

    # ── Utilities ────────────────────────────────────────────

    def clear_history(self) -> None:
        """Clear published message history (useful between test cases)."""
        self.published_messages.clear()

    @staticmethod
    def _topic_matches(pattern: str, topic: str) -> bool:
        """
        Check if a topic matches an MQTT subscription pattern.
        Supports '+' (single level) and '#' (multi level).
        """
        if pattern == topic:
            return True

        # Convert MQTT pattern to Regex
        # Replace '+' with '[^/]+'
        # Replace '#' with '.*'
        regex_pattern = pattern.replace("+", r"[^/]+")
        regex_pattern = regex_pattern.replace("#", r".*")
        
        # Exact match required from start to end
        regex_pattern = f"^{regex_pattern}$"
        
        try:
            return bool(re.match(regex_pattern, topic))
        except re.error:
            return False
