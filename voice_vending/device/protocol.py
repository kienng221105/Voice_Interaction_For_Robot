"""
Bộ dựng Giao thức cho Device Adapter.

Xử lý định dạng payload sao cho khớp với những gì firmware mong đợi.
"""

import json
from datetime import datetime, timezone
from typing import Any


def build_legacy_command(slot: int, quantity: int) -> str:
    """
    Xây dựng lệnh cho firmware ESP32 hiện tại.
    Lặp lại chuỗi 'SLOT:X' ứng với số lượng (quantity) yêu cầu.
    
    Tham số:
        slot: Số khe cứng (ví dụ: 1)
        quantity: Số lượng mặt hàng cần xả
        
    Trả về:
        Ví dụ: "SLOT:1 SLOT:1"
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
    Xây dựng lệnh cho firmware v2 trong tương lai.
    
    Trả về:
        Chuỗi JSON chứa lệnh đã được cấu trúc.
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
