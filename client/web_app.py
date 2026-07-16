import os
import json
import logging
import time
from pathlib import Path
import socket

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import httpx
import uvicorn

from client.core.inventory.json_inventory import JsonInventory
from client.business.services.order_service import OrderService
from client.business.services.device_service import DeviceService
from client.business.business_controller import BusinessController
from client.core.mqtt.mqtt_client import MQTTClient

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

HOST_IP = get_local_ip()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("web_app")

# Initialize core dependencies
ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "voice_vending" / "config"
INVENTORY_FILE = CONFIG_DIR / "inventory.json"

inventory = JsonInventory(str(INVENTORY_FILE))
order_service = OrderService(inventory)

# MQTT config
mqtt_client = MQTTClient(
    broker_host="broker.hivemq.com",
    broker_port=1883,
    username="",
    password=""
)
try:
    mqtt_client.connect()
except Exception as e:
    logger.warning(f"Could not connect to MQTT broker: {e}")

def slot_resolver(product_id: str):
    return inventory.get_slot(product_id)

device_service = DeviceService(
    slot_resolver=slot_resolver,
    mqtt_publish=mqtt_client.publish,
    command_topic="vending/machine/VM001/command"
)
device_service.start()

controller = BusinessController(order_service, device_service, inventory)

# ==========================================
# PAYMENT STATE & payOS CONFIG
# ==========================================
PAYOS_CLIENT_ID = "3bb6f539-8a8f-4f5f-84d5-e7991a10b6cc"
PAYOS_API_KEY = "69a695b8-bfbb-4335-a312-5e9eabcaf0ba"
PAYOS_CHECKSUM_KEY = "af5c31b415e49ea0f41de3e943885bd1d241bc7cb8f63fb2471cbe6deb086302"

pending_payment = {
    "active": False,
    "amount": 0,
    "order_ref": "",
    "confirmed": False,
    "created_at": 0,
}

def verify_payos_signature(data: dict, signature: str) -> bool:
    """Verify payOS webhook signature using HMAC-SHA256."""
    import hashlib, hmac
    # Sort data keys and build query string
    sorted_keys = sorted(data.keys())
    data_str = "&".join(f"{k}={data[k]}" for k in sorted_keys)
    computed = hmac.new(
        PAYOS_CHECKSUM_KEY.encode(),
        data_str.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed, signature)

def get_inventory_dict():
    return {
        p.product_id: {
            "id": p.product_id,
            "display_name": p.display_name,
            "price": p.price,
            "stock": p.stock,
            "enabled": p.enabled
        } for p in inventory.get_all_available()
    }

app = FastAPI(title="Voice Vending Machine - Local App")

# Serve static files
STATIC_DIR = Path(__file__).resolve().parent / "web" / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return "<h1>Error: index.html not found</h1>"
    with open(index_file, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/state")
async def get_state():
    """Returns the current inventory and cart state."""
    return {
        "inventory": get_inventory_dict(),
        "cart": {item.product_id: item.quantity for item in order_service.get_cart_items()}
    }

@app.post("/api/execute")
async def execute_command(request: Request):
    """
    Receives JSON from the frontend (which came from Cloud AI Backend),
    processes it through the BusinessController, and returns the TTS reply
    and the new state.
    """
    try:
        data = await request.json()
        logger.info(f"Received from UI: {data}")
        
        intent = data.get("intent", "")
        
        # Publish confirm TTS immediately BEFORE processing the order
        # so that the audio plays BEFORE the motor starts spinning.
        if intent == "confirm":
            mqtt_client.publish("vending/machine/VM001/command", f"PLAY:http://{HOST_IP}:8000/static/vend.mp3")
            # Clear payment state after confirming
            pending_payment["active"] = False
            pending_payment["confirmed"] = False
            
        # Process using BusinessController (this triggers SLOT:X for motors)
        tts_reply = controller.process(data)
        
        # Publish other predefined TTS URLs to the ESP32
        if intent == "payment":
            mqtt_client.publish("vending/machine/VM001/command", f"PLAY:http://{HOST_IP}:8000/static/qr.mp3")
            # Set up pending payment and call payOS API
            cart_items = order_service.get_cart_items()
            total = sum(
                inventory.get_product(item.product_id).price * item.quantity
                for item in cart_items
                if inventory.get_product(item.product_id)
            )
            order_code = int(time.time() * 1000) % 9007199254740991 # Safe 53-bit int
            
            # Call payOS API
            import hashlib, hmac
            desc = "VendingMachine"
            cancel_url = "http://localhost:8000/"
            return_url = "http://localhost:8000/"
            
            sig_data = f"amount={total}&cancelUrl={cancel_url}&description={desc}&orderCode={order_code}&returnUrl={return_url}"
            signature = hmac.new(PAYOS_CHECKSUM_KEY.encode(), sig_data.encode(), hashlib.sha256).hexdigest()
            
            payload = {
                "orderCode": order_code,
                "amount": total,
                "description": desc,
                "cancelUrl": cancel_url,
                "returnUrl": return_url,
                "signature": signature,
                "items": [{"name": "Nuoc uong", "quantity": 1, "price": total}]
            }
            
            qr_code_str = ""
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        "https://api-merchant.payos.vn/v2/payment-requests",
                        json=payload,
                        headers={
                            "x-client-id": PAYOS_CLIENT_ID,
                            "x-api-key": PAYOS_API_KEY
                        },
                        timeout=10.0
                    )
                    resp_data = resp.json()
                    if resp_data.get("code") == "00":
                        qr_code_str = resp_data["data"]["qrCode"]
                        logger.info(f"Tạo link payOS thành công! orderCode: {order_code}")
                    else:
                        logger.error(f"PayOS API Error: {resp_data}")
            except Exception as e:
                logger.error(f"Failed to call PayOS API: {e}")
            
            pending_payment["active"] = True
            pending_payment["amount"] = total
            pending_payment["order_ref"] = str(order_code)
            pending_payment["qr_code_str"] = qr_code_str
            pending_payment["confirmed"] = False
            pending_payment["created_at"] = time.time()
            logger.info(f"[PAYMENT] Chờ thanh toán: {total}đ, mã: {order_code}")
        elif intent in ["buy_product", "add_product"]:
            if "hết hàng" in tts_reply:
                mqtt_client.publish("vending/machine/VM001/command", f"PLAY:http://{HOST_IP}:8000/static/out.mp3")
            else:
                mqtt_client.publish("vending/machine/VM001/command", f"PLAY:http://{HOST_IP}:8000/static/cart.mp3")
        elif intent == "remove_product":
            if "Không tìm thấy" in tts_reply:
                mqtt_client.publish("vending/machine/VM001/command", f"PLAY:http://{HOST_IP}:8000/static/not_found.mp3")
            else:
                mqtt_client.publish("vending/machine/VM001/command", f"PLAY:http://{HOST_IP}:8000/static/remove.mp3")
        elif intent in ["view_menu", "ask_menu", "menu", "check_menu"]:
            mqtt_client.publish("vending/machine/VM001/command", f"PLAY:http://{HOST_IP}:8000/static/menu.mp3")
        else:
            if "menu" in intent.lower():
                mqtt_client.publish("vending/machine/VM001/command", f"PLAY:http://{HOST_IP}:8000/static/menu.mp3")
        
        return JSONResponse({
            "status": "success",
            "reply": tts_reply,
            "state": {
                "inventory": get_inventory_dict(),
                "cart": {item.product_id: item.quantity for item in order_service.get_cart_items()}
            }
        })
    except Exception as e:
        logger.error(f"Error processing command: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

# ==========================================
# PAYMENT WEBHOOK (payOS)
# ==========================================
@app.post("/api/payment_webhook")
async def payment_webhook(request: Request):
    """
    Receives payment notifications from payOS.
    Format: {"code":"00","desc":"success","success":true,"data":{...},"signature":"..."}
    """
    try:
        body = await request.json()
        logger.info(f"[WEBHOOK] Received: {json.dumps(body, ensure_ascii=False)}")
        
        # Check if payment was successful
        if body.get("code") != "00" or not body.get("success"):
            logger.info("[WEBHOOK] Payment not successful, ignoring.")
            return JSONResponse({"success": True})
        
        data = body.get("data", {})
        signature = body.get("signature", "")
        
        # Verify signature
        if signature and not verify_payos_signature(data, signature):
            logger.warning("[WEBHOOK] Invalid signature, rejecting.")
            return JSONResponse({"success": False, "message": "Invalid signature"}, status_code=401)
        
        if not pending_payment["active"]:
            logger.info("[WEBHOOK] No pending payment, ignoring.")
            return JSONResponse({"success": True})
        
        expected_amount = pending_payment["amount"]
        amount = data.get("amount", 0)
        desc = str(data.get("description", ""))
        order_code = data.get("orderCode", "")
        
        # Match by amount (primary) or order reference in description
        amount_match = amount >= expected_amount and expected_amount > 0
        ref_match = pending_payment["order_ref"] and pending_payment["order_ref"] in desc
        
        if amount_match or ref_match:
            pending_payment["confirmed"] = True
            logger.info(f"[WEBHOOK] ✅ Thanh toán thành công! {amount}đ - {desc} (orderCode: {order_code})")
            return JSONResponse({"success": True, "matched": True})
        
        logger.info(f"[WEBHOOK] Giao dịch không khớp (expected {expected_amount}đ, got {amount}đ).")
        return JSONResponse({"success": True, "matched": False})
    except Exception as e:
        logger.error(f"[WEBHOOK] Error: {e}")
        return JSONResponse({"success": False}, status_code=500)

@app.get("/api/payment_status")
async def payment_status():
    """
    Frontend polls this endpoint every 2s while QR modal is open.
    Returns whether the payment has been confirmed by the webhook.
    """
    # Auto-expire after 5 minutes
    if pending_payment["active"] and time.time() - pending_payment["created_at"] > 300:
        pending_payment["active"] = False
        pending_payment["confirmed"] = False
        
    return JSONResponse({
        "active": pending_payment["active"],
        "confirmed": pending_payment["confirmed"],
        "amount": pending_payment["amount"],
        "order_ref": pending_payment["order_ref"],
        "qr_code_str": pending_payment.get("qr_code_str", "")
    })

@app.post("/api/chat")
async def chat_proxy(request: Request):
    """
    Proxies text chat requests to Cloud Run to bypass CORS issues.
    """
    try:
        data = await request.json()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://voice-vending-backend-968863294243.asia-southeast1.run.app/api/chat",
                json=data,
                timeout=30.0
            )
            return JSONResponse(resp.json(), status_code=resp.status_code)
    except Exception as e:
        logger.error(f"Error proxying chat command: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

if __name__ == "__main__":
    uvicorn.run("client.web_app:app", host="0.0.0.0", port=8000, reload=True)

