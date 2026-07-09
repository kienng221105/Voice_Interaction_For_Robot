"""
Natural Language Understanding Module.
Extracts Intent and Entities using llama-cpp-python (GGUF).
"""

import os
import json
import logging
import re
from typing import Tuple, Dict, Any
from backend.schemas.chat import Entities, EntityProduct

logger = logging.getLogger("nlu")

class NLUEngine:
    def __init__(self, model_path: str):
        self.model_path = model_path
        self.llm = None
        
        if os.path.exists(model_path):
            try:
                from llama_cpp import Llama
                logger.info(f"Loading GGUF model from {model_path}...")
                # Reduce n_ctx to save RAM, we only process short sentences
                self.llm = Llama(model_path=model_path, n_ctx=256, verbose=False)
                logger.info("Model loaded successfully.")
            except ImportError:
                logger.warning("llama-cpp-python not installed. Using fallback NLU.")
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
        else:
            logger.warning(f"GGUF model not found at {model_path}. Using fallback rule-based NLU for MVP.")

    def extract(self, text: str) -> Tuple[str, Entities, float]:
        """
        Analyze text to extract Intent and Entities.
        Returns: (intent, entities, confidence_score)
        """
        text_lower = text.lower()
        if self.llm is None:
            return self._fallback_extract(text_lower)
        
        # Real LLM inference here
        system_prompt = (
            "You are a Vending Machine NLU assistant. Extract intent and entities from Vietnamese text. "
            "Output ONLY JSON. Intents: buy_product, cancel, confirm, check_stock. "
            "Products: coca, pepsi, sting, aquafina.\n"
            "Format: {\"intent\": \"...\", \"items\": [{\"product\": \"...\", \"quantity\": 1}]}\n"
        )
        prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{text}<|im_end|>\n<|im_start|>assistant\n"
        
        try:
            output = self.llm(prompt, max_tokens=100, temperature=0.0, stop=["<|im_end|>"])
            raw_text = output['choices'][0]['text'].strip()
            
            # Basic JSON extraction
            match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                intent = data.get("intent", "unknown")
                items = data.get("items", [])
                
                entities = Entities()
                for item in items:
                    prod = item.get("product")
                    qty = item.get("quantity", 1)
                    if prod:
                        entities.products.append(EntityProduct(product=prod, quantity=qty))
                        
                return intent, entities, 0.95
                
            return self._fallback_extract(text_lower)
            
        except Exception as e:
            logger.error(f"LLM Error: {e}")
            return self._fallback_extract(text_lower)

    def _fallback_extract(self, text: str) -> Tuple[str, Entities, float]:
        """Simple keyword matching fallback."""
        if "hủy" in text or "thôi" in text or "không mua" in text:
            return "cancel", Entities(), 0.9
        if "còn" in text or "kiểm tra" in text:
            return "check_stock", Entities(), 0.9
        if "có" in text or "ok" in text or "đúng" in text or "ừ" in text:
            return "confirm", Entities(), 0.9
        
        # Assume buy
        entities = Entities()
        for p in ["coca", "pepsi", "sting", "aqua", "aquafina"]:
            if p in text:
                match = re.search(r'(\d+)', text)
                qty = int(match.group(1)) if match else 1
                
                # Normalize names
                if p == "aqua": p = "aquafina"
                if p == "bò húc": p = "redbull" # Assuming mapped name
                
                entities.products.append(EntityProduct(product=p, quantity=qty))
        
        if entities.products:
            return "buy_product", entities, 0.8
            
        return "unknown", Entities(), 0.5
