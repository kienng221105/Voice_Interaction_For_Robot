"""
Mock ESP32 — Giả lập phần mềm vi điều khiển máy bán hàng ESP32.

Module này cung cấp lớp MockESP32 tái tạo lại hành vi của 
firmware ESP32 thực tế (esp.ino) mà không cần phần cứng thật.

Firmware thực tế:
  - Đăng ký (Subscribe) vào MQTT topic ``vending/machine/{id}``
  - Phân tích cú pháp lệnh ``SLOT:X`` từ chuỗi văn bản thuần
  - Điều khiển motor qua relay kết hợp với cơ chế ngắt ISR để phát hiện vòng quay
  - Có thời gian chờ (timeout) 5 giây cho mỗi lần chạy motor
  - KHÔNG phản hồi kết quả (giao tiếp một chiều)

Bản giả lập (Mock) mở rộng thêm:
  - Theo dõi kho hàng (số lượng tồn kho mỗi khe)
  - Trả về phản hồi cấu trúc JSON
  - Giả lập độ trễ motor, kẹt hàng, hết thời gian (timeout), và các lỗi ngẫu nhiên
  - Hỗ trợ cả định dạng lệnh ``SLOT:X`` cũ và định dạng JSON mới

Được thiết kế để chạy như một **tiến trình độc lập** (tách biệt với AI server),
giống hệt như cách mạch ESP32 thực tế là một thiết bị vật lý tách biệt.
"""

from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger("mock_esp32")


# ═══════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════


class DispenseStatus(Enum):
    """Kết quả khả thi của một thao tác xả hàng."""

    SUCCESS = "success"
    OUT_OF_STOCK = "out_of_stock"
    MOTOR_JAM = "motor_jam"
    MOTOR_TIMEOUT = "motor_timeout"
    INVALID_SLOT = "invalid_slot"
    ERROR = "error"


@dataclass
class DispenseResult:
    """Kết quả của một thao tác xả hàng."""

    slot: int
    status: DispenseStatus
    duration_ms: int = 0
    stock_remaining: int = 0
    message: str = ""


@dataclass
class MockESP32Config:
    """Cấu hình cho trình giả lập Mock ESP32.

    Thuộc tính:
        machine_id: Định danh duy nhất cho máy này.
        num_slots: Số lượng khe chứa vật lý (mặc định 4).
        initial_stock: Số lượng tồn kho ban đầu mỗi khe.
        dispense_time_range: (min, max) giây để giả lập thời gian chạy motor.
        failure_rate: Tỷ lệ [0.0, 1.0] lỗi ngẫu nhiên mỗi lần xả hàng.
        jam_slots: Danh sách các số thứ tự khe bị kẹt vĩnh viễn.
        timeout_ms: Thời gian chờ motor tính bằng mili-giây (khớp với TIMEOUT_MS của firmware).
    """

    machine_id: str = "VM001"
    num_slots: int = 4
    initial_stock: dict[int, int] = field(
        default_factory=lambda: {1: 10, 2: 8, 3: 5, 4: 12}
    )
    dispense_time_range: tuple[float, float] = (0.8, 2.0)
    failure_rate: float = 0.0
    jam_slots: list[int] = field(default_factory=list)
    timeout_ms: int = 5000

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MockESP32Config:
        """Tạo cấu hình từ một từ điển (ví dụ: đã phân tích từ YAML)."""
        machine = data.get("machine", {})
        mock = data.get("mock_esp", {})

        initial_stock = mock.get("initial_stock", {1: 10, 2: 8, 3: 5, 4: 12})
        # YAML có thể phân tích khóa là chuỗi; chuẩn hóa thành int
        initial_stock = {int(k): int(v) for k, v in initial_stock.items()}

        time_range = mock.get("dispense_time_range", [0.8, 2.0])

        return cls(
            machine_id=machine.get("id", "VM001"),
            num_slots=mock.get("num_slots", 4),
            initial_stock=initial_stock,
            dispense_time_range=(float(time_range[0]), float(time_range[1])),
            failure_rate=float(mock.get("failure_rate", 0.0)),
            jam_slots=[int(s) for s in mock.get("jam_slots", [])],
            timeout_ms=int(mock.get("timeout_ms", 5000)),
        )


# ═══════════════════════════════════════════════════════════
# Mock ESP32 Core
# ═══════════════════════════════════════════════════════════


class MockESP32:
    """Giả lập phần mềm vi điều khiển ESP32.

    Lớp này **không chứa logic MQTT**. Nó chỉ biết cách:
    - Phân tích payload của lệnh (cũ và JSON)
    - Giả lập hoạt động của motor với độ trễ thực tế
    - Theo dõi tồn kho mỗi khe
    - Trả về kết quả có cấu trúc

    Việc kết nối MQTT được xử lý bên ngoài (xem ``run_mock_esp.py``).
    """

    def __init__(self, config: MockESP32Config) -> None:
        self.config = config
        self.machine_id: str = config.machine_id
        self.num_slots: int = config.num_slots

        # Trạng thái có thể thay đổi
        self.stock: dict[int, int] = dict(config.initial_stock)
        self.jam_slots: list[int] = list(config.jam_slots)

        # Số liệu thống kê
        self._dispense_count: dict[int, int] = {
            i: 0 for i in range(1, config.num_slots + 1)
        }
        self._total_commands: int = 0

        logger.info("=" * 60)
        logger.info("  Mock ESP32 Initialized")
        logger.info(f"  Machine ID : {self.machine_id}")
        logger.info(f"  Slots      : {self.num_slots}")
        logger.info(f"  Failure    : {config.failure_rate * 100:.0f}%")
        logger.info(f"  Jam slots  : {config.jam_slots or 'none'}")
        logger.info("-" * 60)
        for slot in range(1, self.num_slots + 1):
            stock = self.stock.get(slot, 0)
            logger.info(f"  Slot {slot}: stock = {stock}")
        logger.info("=" * 60)

    # ── Phân tích lệnh ─────────────────────────────────────

    def handle_message(self, payload: str) -> list[DispenseResult]:
        """Phân tích tin nhắn đến và thực thi lệnh.

        Hỗ trợ 2 định dạng:

        1. **Cũ (Legacy)** (firmware hiện tại): ``"SLOT:1 SLOT:2"``
        2. **JSON** (giao thức tương lai):
           ``{"command":"dispense","payload":{"items":[{"slot":1,"quantity":1}]}}``

        Tham số:
            payload: Chuỗi tin nhắn thô từ MQTT.

        Trả về:
            Danh sách DispenseResult cho từng sản phẩm được xả.
        """
        self._total_commands += 1
        payload = payload.strip()
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"  COMMAND #{self._total_commands} RECEIVED")
        logger.info(f"  Payload: {payload}")
        logger.info("=" * 60)

        # Thử định dạng JSON trước
        try:
            data = json.loads(payload)
            if isinstance(data, dict) and data.get("command") == "dispense":
                return self._handle_json_command(data)
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

        # Quay lại lệnh SLOT:X cũ
        if "SLOT:" in payload.upper():
            return self._handle_legacy_command(payload)

        logger.warning(f"  Unknown command format: {payload!r}")
        return []

    def _handle_legacy_command(self, payload: str) -> list[DispenseResult]:
        """Phân tích định dạng ``SLOT:X``. Cho phép nhiều khe trong một tin nhắn."""
        results: list[DispenseResult] = []
        upper = payload.upper()

        for i in range(1, self.num_slots + 1):
            tag = f"SLOT:{i}"
            count = upper.count(tag)
            for _ in range(count):
                result = self.dispense(i)
                results.append(result)

        return results

    def _handle_json_command(self, data: dict[str, Any]) -> list[DispenseResult]:
        """Phân tích định dạng lệnh JSON."""
        results: list[DispenseResult] = []
        items = data.get("payload", {}).get("items", [])

        for item in items:
            slot = int(item.get("slot", 0))
            qty = int(item.get("quantity", 1))
            for _ in range(qty):
                result = self.dispense(slot)
                results.append(result)

        return results

    # ── Giả lập Motor ────────────────────────────────────

    def dispense(self, slot: int) -> DispenseResult:
        """Giả lập việc xả một mặt hàng từ *slot*.

        Sao chép logic ``vendOnce(index)`` thực tế:
        1. Xác thực số khe
        2. Kiểm tra tồn kho
        3. Kiểm tra kẹt motor
        4. Tỉ lệ lỗi ngẫu nhiên
        5. Giả lập độ trễ quay motor
        6. Giảm tồn kho khi thành công

        Tham số:
            slot: Số thứ tự khe (bắt đầu từ 1).

        Trả về:
            DispenseResult với trạng thái và siêu dữ liệu.
        """
        logger.info("-" * 40)
        logger.info(f"  [DISPENSE] Slot {slot} — START")

        # 1. Xác thực
        if slot < 1 or slot > self.num_slots:
            logger.error(f"  [DISPENSE] Slot {slot} — INVALID (valid: 1-{self.num_slots})")
            return DispenseResult(
                slot=slot,
                status=DispenseStatus.INVALID_SLOT,
                message=f"Slot {slot} does not exist (valid: 1-{self.num_slots})",
            )

        # 2. Kiểm tra tồn kho
        current_stock = self.stock.get(slot, 0)
        if current_stock <= 0:
            logger.warning(f"  [DISPENSE] Slot {slot} — OUT OF STOCK")
            return DispenseResult(
                slot=slot,
                status=DispenseStatus.OUT_OF_STOCK,
                stock_remaining=0,
                message=f"Slot {slot} is empty",
            )

        # 3. Kẹt motor
        if slot in self.jam_slots:
            delay = random.uniform(2.0, 4.0)
            logger.info(f"  [DISPENSE] Slot {slot} — Motor spinning...")
            time.sleep(delay)
            logger.error(
                f"  [DISPENSE] Slot {slot} — MOTOR JAM "
                f"(timeout after {delay:.1f}s)"
            )
            return DispenseResult(
                slot=slot,
                status=DispenseStatus.MOTOR_JAM,
                duration_ms=int(delay * 1000),
                stock_remaining=current_stock,
                message=f"Motor jam at slot {slot}",
            )

        # 4. Lỗi ngẫu nhiên
        if random.random() < self.config.failure_rate:
            failure = random.choice(
                [DispenseStatus.MOTOR_TIMEOUT, DispenseStatus.ERROR]
            )
            delay = random.uniform(3.0, 5.0)
            logger.info(f"  [DISPENSE] Slot {slot} — Motor spinning...")
            time.sleep(delay)
            logger.error(
                f"  [DISPENSE] Slot {slot} — {failure.value.upper()} "
                f"(random failure after {delay:.1f}s)"
            )
            return DispenseResult(
                slot=slot,
                status=failure,
                duration_ms=int(delay * 1000),
                stock_remaining=current_stock,
                message=f"Random failure: {failure.value}",
            )

        # 5. Xả hàng bình thường — giả lập độ trễ motor
        min_t, max_t = self.config.dispense_time_range
        delay = random.uniform(min_t, max_t)
        logger.info(f"  [DISPENSE] Slot {slot} — Motor spinning... ({delay:.1f}s)")
        time.sleep(delay)

        # 6. Thành công — giảm tồn kho
        self.stock[slot] = current_stock - 1
        self._dispense_count[slot] += 1

        logger.info(f"  [DISPENSE] Slot {slot} — SUCCESS")
        logger.info(f"  [DISPENSE] Slot {slot} — Stock remaining = {self.stock[slot]}")
        logger.info("-" * 40)

        return DispenseResult(
            slot=slot,
            status=DispenseStatus.SUCCESS,
            duration_ms=int(delay * 1000),
            stock_remaining=self.stock[slot],
            message=f"Dispensed 1 item from slot {slot}",
        )

    # ── Truy vấn ─────────────────────────────────────────────

    def get_stock(self, slot: int) -> int:
        """Trả về tồn kho hiện tại cho *slot*."""
        return self.stock.get(slot, 0)

    def get_status(self) -> dict[str, Any]:
        """Trả về trạng thái máy đầy đủ dưới dạng từ điển."""
        return {
            "machine_id": self.machine_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "slots": {
                slot: {
                    "stock": self.stock.get(slot, 0),
                    "jammed": slot in self.jam_slots,
                    "dispense_count": self._dispense_count.get(slot, 0),
                }
                for slot in range(1, self.num_slots + 1)
            },
            "total_commands": self._total_commands,
        }

    # ── Trình trợ giúp quản trị (để kiểm tra / điều khiển thời gian chạy) ───────

    def set_jam(self, slot: int, jammed: bool = True) -> None:
        """Đặt hoặc xóa trạng thái kẹt của một khe."""
        if jammed and slot not in self.jam_slots:
            self.jam_slots.append(slot)
            logger.warning(f"  Slot {slot} marked as JAMMED")
        elif not jammed and slot in self.jam_slots:
            self.jam_slots.remove(slot)
            logger.info(f"  Slot {slot} jam CLEARED")

    def restock(self, slot: int, quantity: int) -> None:
        """Đặt tồn kho cho một khe thành *quantity*."""
        self.stock[slot] = quantity
        logger.info(f"  [RESTOCK] Slot {slot} → stock = {quantity}")

    def build_response(
        self,
        results: list[DispenseResult],
        command_id: str = "",
    ) -> dict[str, Any]:
        """Build a JSON response message from dispense results.

        This is the response the Mock publishes back to the server,
        implementing the bi-directional protocol the real firmware lacks.
        """
        return {
            "version": "1.0",
            "type": "dispense_result",
            "command_id": command_id,
            "machine_id": self.machine_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": [
                {
                    "slot": r.slot,
                    "status": r.status.value,
                    "duration_ms": r.duration_ms,
                    "stock_remaining": r.stock_remaining,
                    "message": r.message,
                }
                for r in results
            ],
        }
