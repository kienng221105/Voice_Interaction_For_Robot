"""
Device Service.
Translates product-level commands into hardware-level MQTT commands.
Manages the command queue for sequential motor execution.
"""

import json
import logging
import queue
import threading
import time
from typing import Callable, Optional
from dataclasses import dataclass

logger = logging.getLogger("device_service")


@dataclass
class DispenseCommand:
    """A single command to dispense a product."""
    product_id: str
    slot: int
    quantity: int
    callback: Optional[Callable] = None


class DeviceService:
    """
    Handles all communication with the physical vending machine (ESP32).
    - Maps product_id -> slot number
    - Queues dispense commands sequentially
    - Publishes MQTT messages
    - Processes ACKs
    """

    def __init__(self, slot_resolver: Callable[[str], Optional[int]],
                 mqtt_publish: Callable[[str, str], None],
                 command_topic: str):
        self._slot_resolver = slot_resolver
        self._mqtt_publish = mqtt_publish
        self._command_topic = command_topic

        self._queue: queue.Queue[Optional[DispenseCommand]] = queue.Queue()
        self._running = False
        self._worker: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the background worker thread."""
        if self._running:
            return
        self._running = True
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()
        logger.info("DeviceService worker started")

    def stop(self) -> None:
        """Stop the background worker thread."""
        self._running = False
        self._queue.put(None)
        if self._worker:
            self._worker.join(timeout=3.0)
        logger.info("DeviceService worker stopped")

    def enqueue_dispense(self, product_id: str, quantity: int,
                         callback: Optional[Callable] = None) -> bool:
        """
        Resolve slot and add a dispense command to the queue.
        Returns False if slot cannot be resolved.
        """
        slot = self._slot_resolver(product_id)
        if slot is None:
            logger.error(f"Cannot resolve slot for '{product_id}'")
            return False

        cmd = DispenseCommand(
            product_id=product_id,
            slot=slot,
            quantity=quantity,
            callback=callback,
        )
        self._queue.put(cmd)
        logger.info(f"Enqueued dispense: {quantity}x '{product_id}' (slot {slot})")
        return True

    def _worker_loop(self) -> None:
        """Process commands one by one."""
        while self._running:
            try:
                cmd = self._queue.get(timeout=1.0)
                if cmd is None:
                    continue
                self._execute_command(cmd)
                self._queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Worker error: {e}")

    def _execute_command(self, cmd: DispenseCommand) -> None:
        """Send MQTT command for each unit sequentially."""
        for i in range(cmd.quantity):
            payload = f"SLOT:{cmd.slot}"
            self._mqtt_publish(self._command_topic, payload)
            logger.info(f"Published: {payload} ({i + 1}/{cmd.quantity})")
            # Small delay between consecutive commands to avoid ESP32 overload
            if i < cmd.quantity - 1:
                time.sleep(0.5)

        if cmd.callback:
            try:
                cmd.callback(cmd.product_id, cmd.quantity)
            except Exception as e:
                logger.error(f"Callback error: {e}")
