"""
Device Adapter.

Translates high-level AI commands into hardware-specific protocols.
Combines InventoryManager (to resolve slots) and Transport (to send).
"""

from __future__ import annotations

import logging
from typing import Any

from voice_vending.device.protocol import build_legacy_command, build_json_command
from voice_vending.device.transport.base import Transport
from voice_vending.services.inventory_manager import InventoryManager

logger = logging.getLogger("device_adapter")


class AdapterError(Exception):
    pass


class DeviceAdapter:
    """
    Bridges the Application Layer and Infrastructure Layer.
    
    Takes requests for "products" and translates them into "slots",
    then publishes them over the Transport.
    """

    def __init__(
        self,
        transport: Transport,
        inventory: InventoryManager,
        config: dict[str, Any],
    ) -> None:
        self.transport = transport
        self.inventory = inventory
        self.config = config
        
        # Determine protocol format (default to legacy for current firmware)
        self.protocol_format = config.get("protocol_format", "legacy")
        
        # Load topic configuration
        mqtt_cfg = config.get("mqtt", {})
        self.machine_id = self.inventory.machine_id
        
        topics = mqtt_cfg.get("topics", {})
        self.command_topic = topics.get(
            "command", "vending/machine/{machine_id}/command"
        ).format(machine_id=self.machine_id)
        
        self.response_topic = topics.get(
            "response", "vending/machine/{machine_id}/response"
        ).format(machine_id=self.machine_id)

    def dispense_product(self, product_id: str, quantity: int = 1, command_id: str = "") -> bool:
        """
        Dispense a specific product.
        
        Workflow:
        1. Query Inventory for slot.
        2. Format command string based on configured protocol.
        3. Publish to Transport.
        
        Note: Actual stock deduction (confirm_dispense) should happen 
        when the hardware responds with success (handled by CommandQueue later).
        """
        logger.info(f"Adapter asked to dispense {quantity}x '{product_id}'")
        
        # 1. Resolve slot
        slot = self.inventory.find_slot(product_id)
        if slot is None:
            logger.error(f"Cannot dispense '{product_id}': No valid slot found.")
            return False
            
        # 2. Build Payload
        if self.protocol_format == "json":
            payload = build_json_command(
                machine_id=self.machine_id,
                command_id=command_id,
                slot=slot,
                quantity=quantity
            )
        else:
            # Fallback to current real firmware
            payload = build_legacy_command(slot, quantity)
            
        if not payload:
            logger.error("Generated empty payload.")
            return False

        # 3. Publish
        logger.debug(f"Adapter generated payload: {payload}")
        logger.info(f"Publishing command to {self.command_topic}")
        
        success = self.transport.publish(self.command_topic, payload, qos=1)
        if not success:
            logger.error("Transport failed to publish message.")
            return False
            
        return True
