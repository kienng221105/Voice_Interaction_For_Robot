"""
Run Mock ESP32 — Entry point that wires MockESP32 to an MQTT broker.

This script:
  1. Loads config from ``voice_vending/config/config.yaml``
  2. Creates a MockESP32 instance
  3. Connects to the MQTT broker
  4. Subscribes to the command topic
  5. On each message: parses, simulates dispense, publishes response
  6. Runs forever (Ctrl+C to stop)

Usage::

    python run_mock_esp.py
    python run_mock_esp.py --config path/to/config.yaml
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import paho.mqtt.client as mqtt
import yaml

# Ensure package is importable when run from project root
sys.path.insert(0, str(Path(__file__).resolve().parent))

from voice_vending.core.logger import setup_logger
from voice_vending.device.mock_esp32 import MockESP32, MockESP32Config


def load_config(config_path: str) -> dict:
    """Load YAML config file."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Mock ESP32 simulator")
    parser.add_argument(
        "--config",
        default=os.path.join(
            os.path.dirname(__file__),
            "voice_vending",
            "config",
            "config.yaml",
        ),
        help="Path to config.yaml",
    )
    args = parser.parse_args()

    # ── Load config ─────────────────────────────────────────
    config_data = load_config(args.config)
    log_level = getattr(
        logging, config_data.get("logging", {}).get("level", "INFO").upper()
    )
    setup_logger("mock_esp32", level=log_level)
    setup_logger("paho.mqtt", level=logging.WARNING)
    logger = logging.getLogger("mock_esp32")

    # ── Create Mock ESP ─────────────────────────────────────
    esp_config = MockESP32Config.from_dict(config_data)
    esp = MockESP32(esp_config)

    # ── MQTT setup ──────────────────────────────────────────
    mqtt_cfg = config_data.get("mqtt", {})
    broker = mqtt_cfg.get("broker", "broker.hivemq.com")
    port = int(mqtt_cfg.get("port", 1883))
    use_tls = mqtt_cfg.get("use_tls", False)
    username = mqtt_cfg.get("username", "")
    password = mqtt_cfg.get("password", "")

    machine_id = esp.machine_id
    topics = mqtt_cfg.get("topics", {})
    command_topic = topics.get(
        "command", "vending/machine/{machine_id}/command"
    ).format(machine_id=machine_id)
    response_topic = topics.get(
        "response", "vending/machine/{machine_id}/response"
    ).format(machine_id=machine_id)

    # paho-mqtt client (v2 API with VERSION1 callbacks for broad compat)
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=f"mock_esp32_{machine_id}")
    except (AttributeError, TypeError):
        # paho-mqtt v1 fallback
        client = mqtt.Client(client_id=f"mock_esp32_{machine_id}")

    if username:
        client.username_pw_set(username, password)
    if use_tls:
        client.tls_set()

    def on_connect(client: mqtt.Client, userdata: object, flags: dict, rc: int) -> None:
        if rc == 0:
            logger.info(f"Connected to MQTT broker: {broker}:{port}")
            client.subscribe(command_topic, qos=1)
            logger.info(f"Subscribed to: {command_topic}")
            logger.info(f"Will respond on: {response_topic}")
            logger.info("")
            logger.info("Waiting for commands... (Ctrl+C to stop)")
            logger.info("")
        else:
            logger.error(f"MQTT connection failed with code {rc}")

    def on_message(client: mqtt.Client, userdata: object, msg: mqtt.MQTTMessage) -> None:
        payload = msg.payload.decode("utf-8", errors="replace")

        # Extract command_id if JSON
        command_id = ""
        try:
            parsed = json.loads(payload)
            command_id = parsed.get("command_id", "")
        except (json.JSONDecodeError, TypeError):
            pass

        # Process command
        results = esp.handle_message(payload)

        if results:
            # Build and publish response
            response = esp.build_response(results, command_id=command_id)
            response_json = json.dumps(response, ensure_ascii=False)
            client.publish(response_topic, response_json, qos=1)

            # Summary log
            success_count = sum(
                1 for r in results if r.status.value == "success"
            )
            fail_count = len(results) - success_count
            logger.info("")
            logger.info(f"  Response published → {response_topic}")
            logger.info(
                f"  Summary: {success_count} success, {fail_count} failed, "
                f"{len(results)} total"
            )
            logger.info("")

    def on_disconnect(client: mqtt.Client, userdata: object, rc: int) -> None:
        if rc != 0:
            logger.warning(f"Unexpected disconnect (rc={rc}). Will auto-reconnect.")

    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    # ── Connect & run ───────────────────────────────────────
    logger.info(f"Connecting to MQTT broker {broker}:{port}...")
    try:
        client.connect(broker, port, keepalive=60)
    except Exception as e:
        logger.error(f"Cannot connect to MQTT broker: {e}")
        logger.error("Make sure the broker is running and accessible.")
        sys.exit(1)

    try:
        client.loop_forever()
    except KeyboardInterrupt:
        logger.info("")
        logger.info("Shutting down Mock ESP32...")
        status = esp.get_status()
        logger.info(f"Final status: {json.dumps(status, indent=2)}")
        client.disconnect()
        logger.info("Bye!")


if __name__ == "__main__":
    main()
