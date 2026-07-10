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
    Abstract Base Class for network transport.
    
    Provides a common interface for publishing and subscribing to messages,
    regardless of the underlying protocol (MQTT, HTTP, Serial, etc.).
    """

    @abstractmethod
    def connect(self, config: dict[str, Any]) -> bool:
        """
        Establish connection using provided configuration.
        
        Args:
            config: Dictionary containing connection parameters.
        Returns:
            True if connection was successful, False otherwise.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close the connection."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Return True if currently connected."""
        pass

    @abstractmethod
    def publish(self, topic: str, payload: str, qos: int = 1) -> bool:
        """
        Publish a message to a specific topic/endpoint.
        
        Args:
            topic: The destination address or topic.
            payload: The string payload to send.
            qos: Quality of Service (used if applicable, e.g. MQTT).
        Returns:
            True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def subscribe(self, topic: str, callback: Callable[[str, str], None]) -> bool:
        """
        Subscribe to a topic/endpoint to receive messages.
        
        Args:
            topic: The address or topic to listen to.
            callback: Function to call when a message arrives.
                      Signature should be: callback(topic: str, payload: str)
        Returns:
            True if successful.
        """
        pass
