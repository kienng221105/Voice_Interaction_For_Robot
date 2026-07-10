"""
Mock ESP32 — Simulates ESP32 vending machine firmware.

This module provides a MockESP32 class that replicates the behavior of the
real ESP32 firmware (esp.ino) without requiring actual hardware.

The real firmware:
  - Subscribes to MQTT topic ``vending/machine/{id}``
  - Parses ``SLOT:X`` commands from plain-text payloads
  - Drives motors via relay with ISR-based cycle detection
  - Has 5-second timeout per motor operation
  - Does NOT publish responses (one-way communication)

The mock extends this by:
  - Tracking inventory (stock per slot)
  - Publishing structured JSON responses
  - Simulating motor delays, jams, timeouts, and random failures
  - Supporting both legacy ``SLOT:X`` and new JSON command formats

Designed to run as a **standalone process** (separate from the AI server),
just like the real ESP32 is a separate physical device.
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
    """Possible outcomes of a dispense operation."""

    SUCCESS = "success"
    OUT_OF_STOCK = "out_of_stock"
    MOTOR_JAM = "motor_jam"
    MOTOR_TIMEOUT = "motor_timeout"
    INVALID_SLOT = "invalid_slot"
    ERROR = "error"


@dataclass
class DispenseResult:
    """Result of a single dispense operation."""

    slot: int
    status: DispenseStatus
    duration_ms: int = 0
    stock_remaining: int = 0
    message: str = ""


@dataclass
class MockESP32Config:
    """Configuration for the Mock ESP32 simulator.

    Attributes:
        machine_id: Unique identifier for this machine.
        num_slots: Number of physical slots (default 4).
        initial_stock: Starting stock per slot.
        dispense_time_range: (min, max) seconds for motor simulation.
        failure_rate: Probability [0.0, 1.0] of random failure per dispense.
        jam_slots: List of slot numbers that are permanently jammed.
        timeout_ms: Motor timeout in milliseconds (matches firmware TIMEOUT_MS).
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
        """Create config from a dictionary (e.g. parsed YAML)."""
        machine = data.get("machine", {})
        mock = data.get("mock_esp", {})

        initial_stock = mock.get("initial_stock", {1: 10, 2: 8, 3: 5, 4: 12})
        # YAML may parse keys as strings; normalise to int
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
    """Simulates ESP32 vending machine firmware.

    This class contains **no MQTT logic**.  It only knows how to:
    - Parse command payloads (legacy and JSON)
    - Simulate motor operation with realistic delays
    - Track stock per slot
    - Return structured results

    MQTT wiring is handled externally (see ``run_mock_esp.py``).
    """

    def __init__(self, config: MockESP32Config) -> None:
        self.config = config
        self.machine_id: str = config.machine_id
        self.num_slots: int = config.num_slots

        # Mutable state
        self.stock: dict[int, int] = dict(config.initial_stock)
        self.jam_slots: list[int] = list(config.jam_slots)

        # Statistics
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

    # ── Command Parsing ─────────────────────────────────────

    def handle_message(self, payload: str) -> list[DispenseResult]:
        """Parse an incoming message and execute commands.

        Supports two formats:

        1. **Legacy** (current firmware): ``"SLOT:1 SLOT:2"``
        2. **JSON** (future protocol):
           ``{"command":"dispense","payload":{"items":[{"slot":1,"quantity":1}]}}``

        Args:
            payload: Raw message string from MQTT.

        Returns:
            List of DispenseResult for each dispensed item.
        """
        self._total_commands += 1
        payload = payload.strip()
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"  COMMAND #{self._total_commands} RECEIVED")
        logger.info(f"  Payload: {payload}")
        logger.info("=" * 60)

        # Try JSON first
        try:
            data = json.loads(payload)
            if isinstance(data, dict) and data.get("command") == "dispense":
                return self._handle_json_command(data)
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

        # Fall back to legacy SLOT:X
        if "SLOT:" in payload.upper():
            return self._handle_legacy_command(payload)

        logger.warning(f"  Unknown command format: {payload!r}")
        return []

    def _handle_legacy_command(self, payload: str) -> list[DispenseResult]:
        """Parse ``SLOT:X`` format.  Multiple slots allowed in one message."""
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
        """Parse JSON command format."""
        results: list[DispenseResult] = []
        items = data.get("payload", {}).get("items", [])

        for item in items:
            slot = int(item.get("slot", 0))
            qty = int(item.get("quantity", 1))
            for _ in range(qty):
                result = self.dispense(slot)
                results.append(result)

        return results

    # ── Motor Simulation ────────────────────────────────────

    def dispense(self, slot: int) -> DispenseResult:
        """Simulate dispensing one item from *slot*.

        Mirrors the real ``vendOnce(index)`` logic:
        1. Validate slot number
        2. Check stock
        3. Check for motor jam
        4. Random failure chance
        5. Simulate motor spin delay
        6. Decrement stock on success

        Args:
            slot: 1-based slot number.

        Returns:
            DispenseResult with status and metadata.
        """
        logger.info("-" * 40)
        logger.info(f"  [DISPENSE] Slot {slot} — START")

        # 1. Validate
        if slot < 1 or slot > self.num_slots:
            logger.error(f"  [DISPENSE] Slot {slot} — INVALID (valid: 1-{self.num_slots})")
            return DispenseResult(
                slot=slot,
                status=DispenseStatus.INVALID_SLOT,
                message=f"Slot {slot} does not exist (valid: 1-{self.num_slots})",
            )

        # 2. Check stock
        current_stock = self.stock.get(slot, 0)
        if current_stock <= 0:
            logger.warning(f"  [DISPENSE] Slot {slot} — OUT OF STOCK")
            return DispenseResult(
                slot=slot,
                status=DispenseStatus.OUT_OF_STOCK,
                stock_remaining=0,
                message=f"Slot {slot} is empty",
            )

        # 3. Motor jam
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

        # 4. Random failure
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

        # 5. Normal dispense — simulate motor delay
        min_t, max_t = self.config.dispense_time_range
        delay = random.uniform(min_t, max_t)
        logger.info(f"  [DISPENSE] Slot {slot} — Motor spinning... ({delay:.1f}s)")
        time.sleep(delay)

        # 6. Success — decrement stock
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

    # ── Queries ─────────────────────────────────────────────

    def get_stock(self, slot: int) -> int:
        """Return current stock for *slot*."""
        return self.stock.get(slot, 0)

    def get_status(self) -> dict[str, Any]:
        """Return full machine status as a dictionary."""
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

    # ── Admin helpers (for testing / runtime control) ───────

    def set_jam(self, slot: int, jammed: bool = True) -> None:
        """Set or clear jam state for a slot."""
        if jammed and slot not in self.jam_slots:
            self.jam_slots.append(slot)
            logger.warning(f"  Slot {slot} marked as JAMMED")
        elif not jammed and slot in self.jam_slots:
            self.jam_slots.remove(slot)
            logger.info(f"  Slot {slot} jam CLEARED")

    def restock(self, slot: int, quantity: int) -> None:
        """Set stock for a slot to *quantity*."""
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
