"""
Command Queue Service.

Ensures that dispensing commands are executed sequentially and handles
the ACK/Timeout logic between AI and hardware.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from voice_vending.device.adapter import DeviceAdapter
from voice_vending.services.inventory_manager import InventoryManager, OutOfStockError

logger = logging.getLogger("command_queue")


@dataclass
class DispenseJob:
    """Represents a queued request to dispense a product."""
    job_id: str
    product_id: str
    quantity: int
    callback: Optional[callable] = None  # Called when job finishes


class CommandQueue:
    """
    Manages the sequential execution of dispense commands.
    
    1. AI queues a product to dispense.
    2. Queue reserves stock in InventoryManager.
    3. Worker thread takes job, sends to DeviceAdapter.
    4. Worker waits for ACK (or simulates delay if Legacy firmware).
    5. On finish, commits or releases stock based on success rate.
    """

    def __init__(self, adapter: DeviceAdapter, inventory: InventoryManager) -> None:
        self.adapter = adapter
        self.inventory = inventory
        
        self._queue: queue.Queue[DispenseJob] = queue.Queue()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        
        # Dictionary to store events for incoming ACKs (mapped by command_id)
        self._pending_acks: dict[str, dict[str, Any]] = {}
        self._ack_events: dict[str, threading.Event] = {}
        
        # Subscribe to response topic if using JSON protocol
        if self.adapter.protocol_format == "json":
            self.adapter.transport.subscribe(
                self.adapter.response_topic, 
                self._on_device_response
            )

    def start(self) -> None:
        """Start the background worker thread."""
        if self._running:
            return
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        logger.info("Command Queue started.")

    def stop(self) -> None:
        """Stop the background worker thread."""
        self._running = False
        if self._worker_thread:
            # Push a dummy None job to wake up queue.get()
            self._queue.put(None)  # type: ignore
            self._worker_thread.join(timeout=2.0)
        logger.info("Command Queue stopped.")

    def enqueue(self, product_id: str, quantity: int = 1, callback: Optional[callable] = None) -> bool:
        """
        Add a dispense job to the queue.
        Returns True if successfully queued (stock reserved), False if out of stock.
        """
        # 1. Reserve stock first to prevent race conditions
        try:
            self.inventory.reserve(product_id, quantity)
        except OutOfStockError as e:
            logger.warning(f"Failed to enqueue {quantity}x '{product_id}': {e}")
            return False
            
        # 2. Add to queue
        job = DispenseJob(
            job_id=f"cmd_{uuid.uuid4().hex[:8]}",
            product_id=product_id,
            quantity=quantity,
            callback=callback
        )
        self._queue.put(job)
        logger.info(f"Enqueued job {job.job_id} for {quantity}x '{product_id}'")
        return True

    def _worker_loop(self) -> None:
        """Background thread processing jobs sequentially."""
        while self._running:
            try:
                job = self._queue.get(timeout=1.0)
                if job is None:
                    continue  # Stop signal
                    
                self._process_job(job)
                self._queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in CommandQueue worker loop: {e}")

    def _process_job(self, job: DispenseJob) -> None:
        """Execute a single job and handle inventory logic based on outcome."""
        logger.info(f"Processing job {job.job_id}...")
        
        # 1. Send command via Adapter
        success_sent = self.adapter.dispense_product(
            job.product_id, 
            quantity=job.quantity, 
            command_id=job.job_id
        )
        
        if not success_sent:
            # Failed to even send (e.g. invalid slot, transport down)
            logger.error(f"Job {job.job_id}: Failed to send command.")
            self.inventory.release(job.product_id, job.quantity)
            self._invoke_callback(job, success_qty=0, fail_qty=job.quantity)
            return

        # 2. Wait for execution (ACK or simulated delay)
        success_qty = 0
        fail_qty = 0
        
        if self.adapter.protocol_format == "json":
            # Real hardware with v2 firmware -> Wait for JSON ACK
            success_qty, fail_qty = self._wait_for_json_ack(job)
        else:
            # Real hardware with v1 (legacy) firmware -> Sleep and assume success
            success_qty, fail_qty = self._simulate_legacy_execution(job)
            
        # 3. Update Inventory based on actual hardware outcome
        if success_qty > 0:
            self.inventory.confirm_dispense(job.product_id, success_qty)
        if fail_qty > 0:
            self.inventory.release(job.product_id, fail_qty)
            
        self._invoke_callback(job, success_qty, fail_qty)
        logger.info(f"Job {job.job_id} finished. Success: {success_qty}, Failed: {fail_qty}")

    def _simulate_legacy_execution(self, job: DispenseJob) -> tuple[int, int]:
        """
        Since legacy firmware does not send ACKs, we estimate the time 
        it takes to drop the items and blindly assume success.
        """
        # Assume 2.5 seconds per item
        estimated_duration = job.quantity * 2.5
        logger.info(f"Job {job.job_id}: Legacy mode. Sleeping for {estimated_duration:.1f}s...")
        time.sleep(estimated_duration)
        
        # Assume all succeeded
        return job.quantity, 0

    def _wait_for_json_ack(self, job: DispenseJob) -> tuple[int, int]:
        """
        Wait for a response on MQTT for a specific command_id.
        """
        event = threading.Event()
        self._ack_events[job.job_id] = event
        
        # Wait up to (timeout_per_item * quantity + 5s buffer)
        timeout = job.quantity * 6.0 + 5.0
        
        logger.info(f"Job {job.job_id}: Waiting for JSON ACK (timeout={timeout}s)...")
        event_set = event.wait(timeout)
        
        # Cleanup event
        self._ack_events.pop(job.job_id, None)
        response_data = self._pending_acks.pop(job.job_id, None)
        
        if not event_set or not response_data:
            logger.error(f"Job {job.job_id}: TIMEOUT waiting for ACK.")
            # Hardware might be hung, release everything
            return 0, job.quantity
            
        # Parse response results
        success_qty = 0
        results = response_data.get("results", [])
        
        for r in results:
            if r.get("status") == "success":
                success_qty += 1
                
        fail_qty = job.quantity - success_qty
        # Prevent negative fails just in case hardware goes crazy
        fail_qty = max(0, fail_qty) 
        
        return success_qty, fail_qty

    def _on_device_response(self, topic: str, payload: str) -> None:
        """Callback for incoming MQTT responses."""
        try:
            data = json.loads(payload)
            cmd_id = data.get("command_id")
            
            if cmd_id and cmd_id in self._ack_events:
                self._pending_acks[cmd_id] = data
                self._ack_events[cmd_id].set()
                
        except (json.JSONDecodeError, AttributeError):
            pass

    def _invoke_callback(self, job: DispenseJob, success_qty: int, fail_qty: int) -> None:
        if job.callback:
            try:
                job.callback(job.product_id, success_qty, fail_qty)
            except Exception as e:
                logger.error(f"Callback error for job {job.job_id}: {e}")
