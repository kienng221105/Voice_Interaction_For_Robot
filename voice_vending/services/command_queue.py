"""
Dịch vụ Hàng đợi Lệnh.

Đảm bảo rằng các lệnh xả hàng được thực thi theo tuần tự và xử lý
logic ACK/Timeout (Phản hồi/Hết thời gian) giữa AI và phần cứng.
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
    """Đại diện cho một yêu cầu xả hàng được xếp hàng."""
    job_id: str
    product_id: str
    quantity: int
    callback: Optional[callable] = None  # Được gọi khi công việc hoàn thành


class CommandQueue:
    """
    Quản lý việc thực thi tuần tự các lệnh xả hàng.
    
    1. AI đưa một sản phẩm vào hàng đợi để xả.
    2. Hàng đợi giữ chỗ (reserve) số lượng trong InventoryManager.
    3. Luồng (worker thread) nhận công việc, gửi đến DeviceAdapter.
    4. Luồng chờ ACK (hoặc giả lập độ trễ nếu là firmware cũ).
    5. Khi hoàn thành, chốt (commit) hoặc nhả (release) tồn kho dựa trên mức độ thành công.
    """

    def __init__(self, adapter: DeviceAdapter, inventory: InventoryManager) -> None:
        self.adapter = adapter
        self.inventory = inventory
        
        self._queue: queue.Queue[DispenseJob] = queue.Queue()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        
        # Dictionary để lưu trữ sự kiện cho các ACK đến (ánh xạ theo command_id)
        self._pending_acks: dict[str, dict[str, Any]] = {}
        self._ack_events: dict[str, threading.Event] = {}
        
        # Đăng ký topic phản hồi nếu dùng giao thức JSON
        if self.adapter.protocol_format == "json":
            self.adapter.transport.subscribe(
                self.adapter.response_topic, 
                self._on_device_response
            )

    def start(self) -> None:
        """Bắt đầu luồng công việc (worker thread) chạy ngầm."""
        if self._running:
            return
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        logger.info("Command Queue started.")

    def stop(self) -> None:
        """Dừng luồng công việc (worker thread)."""
        self._running = False
        if self._worker_thread:
            # Gửi một công việc rỗng None để đánh thức queue.get()
            self._queue.put(None)  # type: ignore
            # Đánh thức luồng worker đang đợi
            self._worker_thread.join(timeout=2.0)
        logger.info("Command Queue stopped.")

    def enqueue(self, product_id: str, quantity: int = 1, callback: Optional[callable] = None) -> bool:
        """
        Thêm một công việc xả hàng vào hàng đợi.
        Trả về True nếu được đưa vào hàng đợi thành công (đã giữ chỗ tồn kho), False nếu hết hàng.
        """
        # 1. Giữ chỗ tồn kho trước để tránh điều kiện đua (race conditions)
        try:
            self.inventory.reserve(product_id, quantity)
        except OutOfStockError as e:
            logger.warning(f"Failed to enqueue {quantity}x '{product_id}': {e}")
            return False
            
        # 2. Thêm vào hàng đợi
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
        """Luồng chạy ngầm xử lý các công việc một cách tuần tự."""
        while self._running:
            try:
                job = self._queue.get(timeout=1.0)
                if job is None:
                    continue  # Tín hiệu dừng
                    
                self._process_job(job)
                self._queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in CommandQueue worker loop: {e}")

    def _process_job(self, job: DispenseJob) -> None:
        """Thực thi một công việc và xử lý logic tồn kho dựa trên kết quả."""
        logger.info(f"Processing job {job.job_id}...")
        
        # 1. Gửi lệnh qua Adapter
        success_sent = self.adapter.dispense_product(
            job.product_id, 
            quantity=job.quantity, 
            command_id=job.job_id
        )
        
        if not success_sent:
            # Thất bại ngay từ lúc gửi (ví dụ: slot không hợp lệ, mất kết nối transport)
            logger.error(f"Job {job.job_id}: Failed to send command.")
            self.inventory.release(job.product_id, job.quantity)
            self._invoke_callback(job, success_qty=0, fail_qty=job.quantity)
            return

        # 2. Chờ thực thi (ACK hoặc giả lập độ trễ)
        success_qty = 0
        fail_qty = 0
        
        if self.adapter.protocol_format == "json":
            success_qty, fail_qty = self._wait_for_json_ack(job)
        else:
            # Phần cứng thực tế với firmware v1 (cũ) -> Ngủ và giả định thành công
            success_qty, fail_qty = self._simulate_legacy_execution(job)
            
        if success_qty > 0:
            self.inventory.confirm_dispense(job.product_id, success_qty)
        if fail_qty > 0:
            self.inventory.release(job.product_id, fail_qty)
            
        self._invoke_callback(job, success_qty, fail_qty)
        logger.info(f"Job {job.job_id} finished. Success: {success_qty}, Failed: {fail_qty}")

    def _simulate_legacy_execution(self, job: DispenseJob) -> tuple[int, int]:
        """
        Vì firmware cũ không gửi ACK (phản hồi), chúng ta ước tính thời gian 
        rớt hàng và giả định một cách mù quáng là thành công.
        """
        # Giả định 2.5 giây cho mỗi sản phẩm
        estimated_duration = job.quantity * 2.5
        logger.info(f"Job {job.job_id}: Legacy mode. Sleeping for {estimated_duration:.1f}s...")
        time.sleep(estimated_duration)
        
        # Giả định tất cả thành công
        return job.quantity, 0

    def _wait_for_json_ack(self, job: DispenseJob) -> tuple[int, int]:
        """
        Đợi phản hồi trên MQTT cho một command_id cụ thể.
        """
        event = threading.Event()
        self._ack_events[job.job_id] = event
        
        # Chờ đợi lên đến (timeout_per_item * quantity + 5s buffer)
        timeout = job.quantity * 6.0 + 5.0
        
        logger.info(f"Job {job.job_id}: Waiting for JSON ACK (timeout={timeout}s)...")
        event_set = event.wait(timeout)
        
        # Dọn dẹp sự kiện
        self._ack_events.pop(job.job_id, None)
        response_data = self._pending_acks.pop(job.job_id, None)
        
        if not event_set or not response_data:
            logger.error(f"Job {job.job_id}: TIMEOUT waiting for ACK.")
            # Phần cứng có thể bị treo, nhả tất cả ra
            return 0, job.quantity
            
        # Phân tích kết quả phản hồi
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
        """Callback cho phản hồi đến từ thiết bị."""
        try:
            data = json.loads(payload)
            cmd_id = data.get("command_id")
            
            if cmd_id and cmd_id in self._ack_events:
                self._pending_acks[cmd_id] = data
                self._ack_events[cmd_id].set()
                
        except (json.JSONDecodeError, AttributeError):
            pass

    def _invoke_callback(self, job: DispenseJob, success_qty: int, fail_qty: int) -> None:
        """Kích hoạt callback nếu được cung cấp."""
        if job.callback:
            try:
                job.callback(job.product_id, success_qty, fail_qty)
            except Exception as e:
                logger.error(f"Callback error for job {job.job_id}: {e}")
