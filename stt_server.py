"""
STT + NLP WebSocket Server
==========================
- Receives audio from browser via WebSocket
- Transcribes audio using OpenAI Whisper API v1
- Runs NLP (Intent + Entity extraction) on transcribed text
- Returns structured JSON result

Usage:
    python stt_server.py [--api-key KEY] [--port PORT]
    # Set OPENAI_API_KEY env var as fallback
"""

import argparse
import asyncio
import base64
import json
import os
import traceback
from pathlib import Path

import websockets

# ─── Dependencies ──────────────────────────────────────────────────────────────
# pip install websockets openai

try:
    from openai import OpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# ─── NLP Engine ───────────────────────────────────────────────────────────────

PRODUCT_NAMES = {
    'coca': 'Coca Cola',
    'pepsi': 'Pepsi',

    'sting': 'Sting',
    'aquafina': 'Aquafina',
}

NUM_MAP = {
    'một': 1, 'một chai': 1, 'một lon': 1, 'một cái': 1, 'một ly': 1, '1': 1,
    'hai': 2, 'hai chai': 2, 'hai lon': 2, 'hai cái': 2, 'đôi': 2, '2': 2,
    'ba': 3, 'ba chai': 3, 'ba lon': 3, '3': 3,
    'bốn': 4, 'bốn chai': 4, 'tư': 4, '4': 4,
    'năm': 5, 'năm chai': 5, '5': 5,
    'sáu': 6, '6': 6,
    'bảy': 7, 'bảy chai': 7, '7': 7,
    'tám': 8, 'tám chai': 8, '8': 8,
    'chín': 9, '9': 9,
    'mười': 10, '10': 10,
}

INTENT_RULES = [
    {
        'intents': ['buy_product', 'add_product'],
        'keywords': [
            ['cho tôi', 'cho anh', 'cho em', 'cho mình', 'tôi muốn', 'muốn', 'lấy', 'mang', 'bán cho', 'cần', 'đặt', 'order'],
            ['coca', 'pepsi', 'sting', 'aquafina'],
        ],
    },
    {
        'intents': ['add_product'],
        'keywords': [
            ['thêm', 'thêm vào', 'cho thêm', 'cộng thêm', 'lấy thêm', 'gọi thêm'],
        ],
    },
    {
        'intents': ['payment'],
        'keywords': [
            ['thanh toán', 'thanh toan', 'trả tiền', 'tra tien', 'tiền', 'bỏ tiền', 'đưa tiền', 'bao nhiêu', 'tổng cộng', 'hết bao nhiêu'],
        ],
    },
    {
        'intents': ['confirm'],
        'keywords': [
            ['xác nhận', 'xac nhan', 'đồng ý', 'dong y', 'ok', 'oke', 'đúng rồi', 'đúng', 'chốt', 'xong'],
        ],
    },
    {
        'intents': ['change_product'],
        'keywords': [
            ['đổi', 'đổi sang', 'doi', 'doi sang', 'thay đổi', 'thay doi', 'chuyển sang', 'sang'],
            ['coca', 'pepsi', 'sting', 'aquafina', 'khác', 'loại khác'],
        ],
    },
    {
        'intents': ['remove_product'],
        'keywords': [
            ['bỏ', 'bo', 'không lấy', 'giảm', 'bớt', 'hủy', 'loại bỏ', 'xóa'],
            ['coca', 'pepsi', 'sting', 'aquafina', 'lon', 'chai'],
        ],
    },
    {
        'intents': ['cancel'],
        'keywords': [
            ['hủy', 'huy', 'bỏ hết', 'hủy hết', 'xóa hết', 'hết', 'thôi'],
        ],
    },
    {
        'intents': ['show_menu'],
        'keywords': [
            ['xem', 'menu', 'danh sách', 'có gì', 'bán gì', 'cửa hàng', 'xem thử', 'hiện có'],
        ],
    },
    {
        'intents': ['greeting'],
        'keywords': [
            ['xin chào', 'chào', 'hello', 'hi', 'helo', 'chào buổi', 'good morning', 'good afternoon'],
        ],
    },
    {
        'intents': ['help'],
        'keywords': [
            ['giúp', 'giup', 'hướng dẫn', 'cách', 'làm sao', 'chỉ'],
        ],
    },
]


def normalize_number(text: str) -> int:
    """Extract quantity from text."""
    words = text.lower().split()
    for w in words:
        for key, val in NUM_MAP.items():
            if w == key or key in w:
                return val
    return 1


def detect_products(text: str) -> list:
    """Detect product mentions in text."""
    text_lower = text.lower()
    found = []
    for prod_id in PRODUCT_NAMES:
        if prod_id in text_lower:
            found.append(prod_id)
    return found


def classify_intent(text: str):
    """Classify intent using keyword matching."""
    text_lower = text.lower()
    best_intent = 'unknown'
    best_score = 0

    for rule in INTENT_RULES:
        score = 0
        for kw_group in rule['keywords']:
            if any(kw in text_lower for kw in kw_group):
                score += 1
        if score > best_score:
            best_score = score
            best_intent = rule['intents'][0]

    confidence = min(best_score * 0.35, 0.99) if best_intent != 'unknown' else 0.5
    if best_score == 0:
        best_intent = 'unknown'
        confidence = 0.3

    return best_intent, confidence


def extract_entities(text: str, intent: str) -> dict:
    """Extract entities (products, quantity) from text."""
    return {
        'products': detect_products(text),
        'quantity': normalize_number(text),
    }


def nlp_pipeline(text: str) -> dict:
    """Full NLP pipeline. Returns {intent, confidence, products, quantity, text}."""
    intent, confidence = classify_intent(text)
    entities = extract_entities(text, intent)
    return {
        'intent': intent,
        'confidence': confidence,
        'products': entities['products'],
        'quantity': entities['quantity'],
        'text': text,
    }


# ─── Audio helpers ─────────────────────────────────────────────────────────────

def bytes_to_wav(audio_bytes: bytes, sample_rate: int = 16000) -> bytes:
    """Wrap raw PCM int16 bytes into a minimal WAV header."""
    import struct
    wav = bytearray()
    # RIFF header
    wav.extend(b'RIFF')
    wav.extend(struct.pack('<I', 36 + len(audio_bytes)))  # file size - 8
    wav.extend(b'WAVE')
    # fmt chunk
    wav.extend(b'fmt ')
    wav.extend(struct.pack('<I', 16))          # chunk size
    wav.extend(struct.pack('<H', 1))           # PCM format
    wav.extend(struct.pack('<H', 1))           # channels mono
    wav.extend(struct.pack('<I', sample_rate))  # sample rate
    wav.extend(struct.pack('<I', sample_rate * 2))  # byte rate
    wav.extend(struct.pack('<H', 2))           # block align
    wav.extend(struct.pack('<H', 16))          # bits per sample
    # data chunk
    wav.extend(b'data')
    wav.extend(struct.pack('<I', len(audio_bytes)))
    wav.extend(audio_bytes)
    return bytes(wav)


# ─── WebSocket Server ─────────────────────────────────────────────────────────

async def handle_client(websocket, path=None):
    client_id = id(websocket)
    print(f"[{client_id}] Client connected")

    try:
        async for message in websocket:
            if isinstance(message, bytes):
                # Binary: PCM audio data
                try:
                    audio_len = len(message)
                    if audio_len < 3200:  # less than 200ms at 16kHz
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': 'Audio too short',
                        }))
                        continue

                    # Build WAV from raw PCM
                    wav_bytes = bytes_to_wav(message)

                    # Transcribe via OpenAI Whisper API v1
                    import io
                    audio_file = io.BytesIO(wav_bytes)
                    audio_file.name = 'audio.wav'

                    result = openai_client.audio.transcriptions.create(
                        model='whisper-1',
                        file=audio_file,
                        language='vi',
                        response_format='text',
                    )
                    transcribed = result.strip() if result else ''

                    if not transcribed:
                        await websocket.send(json.dumps({
                            'type': 'no_speech',
                            'message': 'Không phát hiện giọng nói',
                        }))
                        continue

                    # Run NLP
                    nlp_result = nlp_pipeline(transcribed)

                    response = {
                        'type': 'result',
                        'transcribed': transcribed,
                        'intent': nlp_result['intent'],
                        'confidence': nlp_result['confidence'],
                        'products': nlp_result['products'],
                        'quantity': nlp_result['quantity'],
                    }
                    await websocket.send(json.dumps(response))
                    print(f"[{client_id}] '{transcribed}' → {nlp_result['intent']} ({nlp_result['confidence']:.2f})")

                except Exception as e:
                    error_msg = traceback.format_exc()
                    print(f"[{client_id}] Error: {e}\n{error_msg}")
                    await websocket.send(json.dumps({
                        'type': 'error',
                        'message': str(e),
                    }))

            elif isinstance(message, str):
                # Text: ping/pong
                try:
                    data = json.loads(message)
                    if data.get('type') == 'ping':
                        await websocket.send(json.dumps({'type': 'pong'}))
                except Exception:
                    pass

    except websockets.exceptions.ConnectionClosed:
        print(f"[{client_id}] Client disconnected")
    except Exception as e:
        print(f"[{client_id}] Unexpected error: {e}")


async def main(args):
    global openai_client

    api_key = args.api_key or os.environ.get('OPENAI_API_KEY', '') or OPENROUTER_API_KEY

    if not api_key:
        raise RuntimeError(
            "No API key found. Pass --api-key or set OPENAI_API_KEY env var."
        )

    if not _OPENAI_AVAILABLE:
        raise RuntimeError("openai package not installed. Run: pip install openai")

    openai_client = OpenAI(
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
    )
    print(f"OpenRouter client ready. Starting server on ws://{args.host}:{args.port}")

    async with websockets.serve(handle_client, args.host, args.port):
        print("STT Server ready. Press Ctrl+C to stop.")
        await asyncio.Future()  # run forever


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='STT + NLP WebSocket Server (OpenAI Whisper API v1)')
    parser.add_argument('--api-key', default='', help='OpenAI API key (or set OPENAI_API_KEY env var)')
    parser.add_argument('--host', default='localhost', help='Server host (default: localhost)')
    parser.add_argument('--port', type=int, default=8765, help='WebSocket port (default: 8765)')
    args = parser.parse_args()

    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        print("\nServer stopped.")
