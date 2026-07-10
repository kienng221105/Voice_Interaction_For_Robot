"""
Full Pipeline STT + NLP Server
=============================
- Receives audio from browser via WebSocket
- Transcribes audio using OpenRouter Whisper API v1
- Extracts intent + entities using Ollama (local Qwen 2.5 1.5B)
- Returns structured JSON result

Dependencies:
    pip install websockets openai requests

Usage:
    python nlp_server.py [--port PORT]
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')
import argparse
import asyncio
import io
import json
import struct
import time
import traceback

import requests
import websockets
from openai import OpenAI

# ─── Config ────────────────────────────────────────────────────────────────────

import os
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# Ollama base_url phải có /v1 để OpenAI-compat client hoạt động đúng
OLLAMA_BASE_URL = "http://localhost:11434/v1"
# Student model fine-tuned từ Qwen2.5-7B teacher, quantize Q8_0 (1.6GB)
OLLAMA_MODEL = "vending-student"

SYSTEM_PROMPT = """You are a Vietnamese Vending Machine NLU assistant.
Extract intent and entities from Vietnamese text. Output ONLY a raw JSON object.

Output format:
{"intent": "<intent>", "items": [{"product": "<product>", "quantity": <int>}]}

Intents: buy_product, add_product, remove_product, change_product, payment, cancel, confirm, show_menu, greeting, help, unknown
Canonical products: coca, pepsi, sting, aquafina (normalize all aliases, e.g. "bep si"→pepsi, "aqua"→aquafina)
Empty items [] for intents with no product (cancel, payment, show_menu, greeting, help, confirm, unknown).

DO NOT output markdown or explanation. Output ONLY the JSON."""

VALID_INTENTS = {
    "greeting", "show_menu", "buy_product", "add_product",
    "change_product", "payment", "cancel", "confirm",
    "remove_product", "help", "unknown",
}
VALID_PRODUCTS = {"coca", "pepsi", "sting", "aquafina"}

# ─── Clients ──────────────────────────────────────────────────────────────────

# Khởi tạo Ollama client một lần duy nhất với /v1 base_url đúng chuẩn
ollama_client = OpenAI(api_key="ollama", base_url=OLLAMA_BASE_URL)
print("Connecting to Ollama...")
try:
    ollama_client.chat.completions.create(model=OLLAMA_MODEL, messages=[{"role": "user", "content": "hi"}], max_tokens=5)
    print(f"Ollama ready with model: {OLLAMA_MODEL}")
except Exception as e:
    print(f"Ollama warning: {e}")

# ─── Helpers ───────────────────────────────────────────────────────────────────

def bytes_to_wav(audio_bytes: bytes, sample_rate: int = 16000) -> bytes:
    """Wrap raw PCM int16 mono bytes into a WAV file."""
    wav = bytearray()
    wav.extend(b'RIFF')
    wav.extend(struct.pack('<I', 36 + len(audio_bytes)))
    wav.extend(b'WAVE')
    wav.extend(b'fmt ')
    wav.extend(struct.pack('<I', 16))
    wav.extend(struct.pack('<H', 1))
    wav.extend(struct.pack('<H', 1))
    wav.extend(struct.pack('<I', sample_rate))
    wav.extend(struct.pack('<I', sample_rate * 2))
    wav.extend(struct.pack('<H', 2))
    wav.extend(struct.pack('<H', 16))
    wav.extend(b'data')
    wav.extend(struct.pack('<I', len(audio_bytes)))
    wav.extend(audio_bytes)
    return bytes(wav)


def extract_json(text: str) -> dict:
    """Parse JSON from LLM output, stripping markdown code blocks."""
    text = text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1].strip()
    try:
        return json.loads(text)
    except Exception:
        return {"intent": "unknown", "items": []}


def nlp_pipeline(text: str) -> dict:
    """Call Ollama to extract intent + entities."""
    t0 = time.time()
    response = ollama_client.chat.completions.create(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f'Text: "{text}"'},
        ],
        temperature=0.0,
        max_tokens=150,
    )
    raw = response.choices[0].message.content.strip()
    latency = time.time() - t0

    result = extract_json(raw)

    intent = result.get("intent", "unknown")
    if intent not in VALID_INTENTS:
        intent = "unknown"

    items = []
    for item in result.get("items", []):
        product = item.get("product", "").lower().strip()
        if product not in VALID_PRODUCTS:
            continue
        quantity = item.get("quantity")
        try:
            quantity = max(1, int(quantity))
        except (TypeError, ValueError):
            quantity = 1
        items.append({"product": product, "quantity": quantity})

    # ── Post-processing: rule-based override for critical misclassifications ──
    # Web Speech API đôi khi trả text không dấu → model có thể bị nhầm intent.
    # Safety net này chỉ override khi keyword rõ ràng.
    text_lower = text.lower()
    REMOVE_TRIGGERS = [
        "bỏ bớt", "bo bot", "giảm", "bớt", "xóa", "xoa", "trừ", "tru",
        "không lấy", "khong lay", "bỏ đi", "bo di", "bỏ ra", "bo ra",
        "bỏ bớt", "không muốn", "không cần",
    ]
    CANCEL_TRIGGERS = [
        "hủy hết", "huy het", "bỏ hết", "bo het", "xóa hết", "xoa het",
        "thôi không mua", "thoi khong mua", "không mua nữa", "khong mua nua",
        "hủy đơn", "huy don",
    ]
    ADD_TRIGGERS = ["thêm vào", "them vao", "cho thêm", "cho them", "gọi thêm"]

    if intent in ("buy_product", "unknown"):
        if any(t in text_lower for t in CANCEL_TRIGGERS):
            intent = "cancel"
            items = []
        elif any(t in text_lower for t in REMOVE_TRIGGERS) and items:
            intent = "remove_product"
    if intent in ("buy_product",) and any(t in text_lower for t in ADD_TRIGGERS):
        intent = "add_product"

    return {
        "intent": intent,
        "items": items,
        "raw_model_output": raw,
        "latency_s": round(latency, 3),
    }


import base64

def stt_pipeline(audio_bytes: bytes) -> str:
    """Transcribe audio using Groq Whisper API (fastest) or OpenRouter fallback."""
    wav_bytes = bytes_to_wav(audio_bytes)
    
    text = ""

    # 1. Ưu tiên dùng Groq API trực tiếp (Siêu nhanh, ~0.2s)
    if GROQ_API_KEY:
        resp = requests.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
            },
            files={
                "file": ("audio.wav", io.BytesIO(wav_bytes), "audio/wav"),
            },
            data={
                "model": "whisper-large-v3",
                "language": "vi",
            },
            timeout=30,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Groq Whisper error {resp.status_code}: {resp.text}")
        text = resp.json().get("text", "").strip()
    else:
        # 2. Fallback về OpenRouter nếu không có key Groq
        base64_audio = base64.b64encode(wav_bytes).decode("utf-8")
        payload = {
            "model": "openai/whisper-large-v3",
            "input_audio": {
                "data": base64_audio,
                "format": "wav"
            },
            "language": "vi",
            "provider": {
                "order": ["Groq"]
            }
        }

        resp = requests.post(
            f"{OPENROUTER_BASE_URL}/audio/transcriptions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=30,
        )

        if resp.status_code != 200:
            raise RuntimeError(f"OpenRouter Whisper error {resp.status_code}: {resp.text}")

        result = resp.json()
        text = result.get("text", "").strip() if result else ""

    # 3. Bộ lọc chống ảo giác (Anti-Hallucination Filter)
    # Whisper V3 thường ảo giác ra các cụm từ này khi thu âm trúng khoảng lặng (Silence)
    hallucinations = [
        "hẹn gặp lại các bạn trong những video tiếp theo",
        "cảm ơn các bạn đã theo dõi",
        "cảm ơn các bạn",
        "chào các bạn",
        "xin chào các bạn",
        "subtitles by",
        "vietsub",
        "hẹn gặp lại",
        "subscribe",
        "đăng ký kênh",
        "những video hấp dẫn",
        "la la school",
        "bỏ lỡ những video",
        "chúc các bạn",
    ]
    
    text_lower = text.lower()
    for h in hallucinations:
        if h in text_lower:
            print(f"[STT Filter] Đã chặn ảo giác của Whisper: '{text}'")
            return ""
            
    return text


# ─── WebSocket Server ─────────────────────────────────────────────────────────

async def handle_client(websocket):
    client_id = id(websocket)
    print(f"[{client_id}] Connected")
    
    audio_buffer = bytearray()

    try:
        async for message in websocket:
            if isinstance(message, str):
                try:
                    data = json.loads(message)
                    if data.get("type") == "ping":
                        await websocket.send(json.dumps({"type": "pong"}))
                    elif data.get("type") == "audio_end":
                        # Client stopped speaking, process the accumulated buffer
                        if len(audio_buffer) < 3200:
                            await websocket.send(json.dumps({
                                "type": "error",
                                "message": "Audio too short",
                            }))
                            audio_buffer.clear()
                            continue

                        audio_data = bytes(audio_buffer)
                        audio_buffer.clear()

                        try:
                            # 1. Speech-to-Text
                            t0 = time.time()
                            transcribed = stt_pipeline(audio_data)
                            stt_time = time.time() - t0

                            if not transcribed:
                                await websocket.send(json.dumps({
                                    "type": "no_speech",
                                    "message": "Không phát hiện giọng nói",
                                }))
                                continue

                            # 2. NLP
                            nlp_result = nlp_pipeline(transcribed)

                            response = {
                                "type": "result",
                                "transcribed": transcribed,
                                "intent": nlp_result["intent"],
                                "items": nlp_result["items"],
                                "raw_model_output": nlp_result["raw_model_output"],
                                "latency_s": nlp_result["latency_s"],
                            }
                            await websocket.send(json.dumps(response))

                            print(f"[{client_id}] STT({stt_time:.2f}s)='{transcribed}' → intent={nlp_result['intent']}, "
                                  f"items={nlp_result['items']}, nlp_latency={nlp_result['latency_s']}s")

                        except Exception as e:
                            err = traceback.format_exc()
                            print(f"[{client_id}] Error: {e}\n{err}")
                            await websocket.send(json.dumps({
                                "type": "error",
                                "message": f"Lỗi STT/NLP: {e}",
                            }))
                            
                    elif data.get("type") == "nlp_request":
                        # Text input directly (if any)
                        text = data.get("text", "").strip()
                        if not text:
                            continue
                        try:
                            nlp_result = nlp_pipeline(text)
                            response = {
                                "type": "result",
                                "transcribed": text,
                                "intent": nlp_result["intent"],
                                "items": nlp_result["items"],
                                "raw_model_output": nlp_result["raw_model_output"],
                                "latency_s": nlp_result["latency_s"],
                            }
                            await websocket.send(json.dumps(response))
                        except Exception as e:
                            await websocket.send(json.dumps({"type": "error", "message": str(e)}))
                except Exception:
                    pass
                continue

            # Accumulate raw PCM audio bytes sent continuously from microphone
            if isinstance(message, bytes):
                audio_buffer.extend(message)
                continue

            try:
                transcribed = stt_pipeline(message)

                if not transcribed:
                    await websocket.send(json.dumps({
                        "type": "no_speech",
                        "message": "Không phát hiện giọng nói",
                    }))
                    continue

                nlp_result = nlp_pipeline(transcribed)

                response = {
                    "type": "result",
                    "transcribed": transcribed,
                    "intent": nlp_result["intent"],
                    "items": nlp_result["items"],
                    "raw_model_output": nlp_result["raw_model_output"],
                    "latency_s": nlp_result["latency_s"],
                }
                await websocket.send(json.dumps(response))

                print(f"[{client_id}] STT='{transcribed}' → intent={nlp_result['intent']}, "
                      f"items={nlp_result['items']}, nlp_latency={nlp_result['latency_s']}s")

            except Exception as e:
                err = traceback.format_exc()
                print(f"[{client_id}] Error: {e}\n{err}")
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": f"Lỗi server: {e}",
                }))

    except websockets.exceptions.ConnectionClosed:
        print(f"[{client_id}] Disconnected")
    except Exception as e:
        print(f"[{client_id}] Unexpected: {e}")


async def main(args):
    print(f"Starting server on ws://{args.host}:{args.port}")
    async with websockets.serve(handle_client, args.host, args.port):
        print("Server ready. Press Ctrl+C to stop.")
        await asyncio.Future()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Full Pipeline STT + NLP Server")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        print("\nServer stopped.")
