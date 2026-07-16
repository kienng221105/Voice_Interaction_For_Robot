"""
Bộ chuyển đổi Thiết bị (Device Adapter).

Biên dịch các lệnh AI cấp cao thành các giao thức đặc thù của phần cứng.
Kết hợp InventoryManager (để xác định khe chứa) và Transport (để gửi đi).
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
    Cầu nối giữa Tầng Ứng dụng (Application) và Tầng Hạ tầng (Infrastructure).
    
    Nhận yêu cầu mua "sản phẩm", dịch thành "khe chứa" (slots),
    sau đó xuất bản (publish) chúng thông qua Transport.
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
        
        # Xác định định dạng giao thức (mặc định là legacy cho firmware hiện tại)
        self.protocol_format = config.get("protocol_format", "legacy")
        
        # Tải cấu hình topic
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
        Xuất một sản phẩm cụ thể.
        
        Quy trình:
        1. Truy vấn Kho (Inventory) để tìm khe chứa (slot).
        2. Định dạng chuỗi lệnh dựa trên giao thức đã cấu hình.
        3. Xuất bản lên Transport.
        
        Lưu ý: Việc trừ kho thực tế (confirm_dispense) sẽ chỉ diễn ra
        khi phần cứng phản hồi thành công (được xử lý bởi CommandQueue sau đó).
        """
        logger.info(f"Adapter asked to dispense {quantity}x '{product_id}'")
        
        # 1. Xác định khe chứa
        slot = self.inventory.find_slot(product_id)
        if slot is None:
            logger.error(f"Cannot dispense '{product_id}': No valid slot found.")
            return False
            
        # 2. Xây dựng Payload
        if self.protocol_format == "json":
            payload = build_json_command(
                machine_id=self.machine_id,
                command_id=command_id,
                slot=slot,
                quantity=quantity
            )
        else:
            # Dự phòng cho firmware thực tế hiện tại
            payload = build_legacy_command(slot, quantity)
            
        if not payload:
            logger.error("Generated empty payload.")
            return False

        # 3. Xuất bản (Publish)
        logger.debug(f"Adapter generated payload: {payload}")
        logger.info(f"Publishing command to {self.command_topic}")
        
        success = self.transport.publish(self.command_topic, payload, qos=1)
        if not success:
            logger.error("Transport failed to publish message.")
            return False
            
        return True
