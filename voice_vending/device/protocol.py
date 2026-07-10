"""
Protocol builders for Device Adapter.

Handles formatting of payloads to match firmware expectations.
"""

import json
from datetime import datetime, timezone
from typing import Any


def build_legacy_command(slot: int, quantity: int) -> str:
    """
    Build command for current ESP32 firmware.
    Repeats 'SLOT:X' for the given quantity.
    
    Args:
        slot: The hardware slot number (e.g. 1)
        quantity: Number of items to dispense
        
    Returns:
        e.g. "SLOT:1 SLOT:1"
    """
    if quantity <= 0:
        return ""
    tags = [f"SLOT:{slot}"] * quantity
    return " ".join(tags)


def build_json_command(
    machine_id: str, 
    command_id: str, 
    slot: int, 
    quantity: int
) -> str:
    """
    Build command for future v2 firmware.
    
    Returns:
        JSON string containing structured command.
    """
    payload = {
        "version": "1.0",
        "command": "dispense",
        "command_id": command_id,
        "machine_id": machine_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "items": [
                {
                    "slot": slot,
                    "quantity": quantity
                }
            ]
        }
    }
    return json.dumps(payload, ensure_ascii=False)
