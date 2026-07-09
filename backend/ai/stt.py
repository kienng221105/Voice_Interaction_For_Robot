"""
Speech-to-Text Module.
Calls Groq/Whisper API to transcribe audio.
"""

import os
import requests
import logging

logger = logging.getLogger("stt")

class STTEngine:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.url = "https://api.groq.com/openai/v1/audio/transcriptions"

    def transcribe(self, wav_bytes: bytes) -> str:
        """Transcribe WAV audio bytes to text using Groq API."""
        if not self.api_key:
            logger.warning("No STT API Key provided. Returning empty transcription.")
            return ""
            
        try:
            resp = requests.post(
                self.url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"file": ("audio.wav", wav_bytes, "audio/wav")},
                data={"model": "whisper-large-v3", "language": "vi"},
                timeout=10,
            )
            
            if resp.status_code == 200:
                text = resp.json().get("text", "").strip()
                
                # Simple anti-hallucination filter
                hallucinations = ["cảm ơn các bạn", "xin chào các bạn", "subtitles by"]
                for h in hallucinations:
                    if h in text.lower():
                        return ""
                return text
            else:
                logger.error(f"STT API Error {resp.status_code}: {resp.text}")
                return ""
                
        except Exception as e:
            logger.error(f"STT Request Error: {e}")
            return ""
