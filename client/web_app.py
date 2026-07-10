import os
import json
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import httpx

from client.core.inventory.json_inventory import JsonInventory
from client.business.services.order_service import OrderService
from client.business.services.device_service import DeviceService
from client.business.business_controller import BusinessController
from client.core.mqtt.mqtt_client import MQTTClient

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
mqtt_client = MQTTClient(broker_host="broker.hivemq.com", broker_port=1883)
try:
    mqtt_client.connect()
except Exception as e:
    logger.warning(f"Could not connect to MQTT broker: {e}")

def slot_resolver(product_id: str):
    return inventory.get_slot(product_id)

device_service = DeviceService(
    slot_resolver=slot_resolver,
    mqtt_publish=mqtt_client.publish,
    command_topic=f"vending/machine/{inventory.machine_id}/command"
)
device_service.start()

controller = BusinessController(order_service, device_service, inventory)

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
        
        # Process using BusinessController
        tts_reply = controller.process(data)
        
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
    import uvicorn
    uvicorn.run("client.web_app:app", host="127.0.0.1", port=8000, reload=True)
