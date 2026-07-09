"""
WebSocket Router for Audio Streaming.
"""

import json
import logging
import struct
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.schemas.chat import ChatResponse

logger = logging.getLogger("voice_ws")
router = APIRouter()

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

@router.websocket("/ws/audio/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    Handle incoming WebSocket connections.
    Receive audio bytes, process STT -> NLU -> Dialogue, and return JSON.
    """
    await websocket.accept()
    logger.info(f"WebSocket connected for session: {session_id}")
    
    app_state = websocket.app.state
    audio_buffer = bytearray()
    
    try:
        while True:
            message = await websocket.receive()
            
            if "bytes" in message:
                # Accumulate raw PCM data
                audio_buffer.extend(message["bytes"])
                
            elif "text" in message:
                text_msg = message["text"]
                try:
                    data = json.loads(text_msg)
                    if data.get("type") == "audio_end":
                        if len(audio_buffer) < 3200:
                            await websocket.send_json({"error": "Audio too short"})
                            audio_buffer.clear()
                            continue
                            
                        # 1. Convert PCM to WAV
                        wav_bytes = bytes_to_wav(bytes(audio_buffer))
                        audio_buffer.clear()
                        
                        # 2. STT Processing
                        transcribed = app_state.stt_engine.transcribe(wav_bytes)
                        if not transcribed:
                            await websocket.send_json({"error": "No speech detected"})
                            continue
                            
                        logger.info(f"[{session_id}] Transcribed: {transcribed}")
                        
                        # 3. NLP & Dialogue Logic
                        session = app_state.session_manager.get_session(session_id)
                        intent, entities, confidence = app_state.nlu_engine.extract(transcribed)
                        next_state, reply = app_state.dialogue_manager.process(intent, entities, session)
                        app_state.session_manager.save_session(session_id, session)
                        
                        # 4. Construct response
                        resp = ChatResponse(
                            session_id=session_id,
                            reply=reply,
                            intent=intent,
                            entities=entities,
                            dialogue_state=next_state,
                            confidence=confidence
                        )
                        
                        await websocket.send_text(resp.model_dump_json())
                        
                except Exception as e:
                    logger.error(f"Error parsing text message: {e}")
                    await websocket.send_json({"error": str(e)})

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session: {session_id}")
    except Exception as e:
        logger.error(f"Unexpected WS Error: {e}")
