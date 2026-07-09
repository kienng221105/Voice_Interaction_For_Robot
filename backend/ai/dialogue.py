"""
Dialogue Manager Logic.
Determines conversational flow and constructs TTS replies based on Intent.
"""

import logging
from backend.services.session_manager import SessionData
from backend.schemas.chat import Entities

logger = logging.getLogger("dialogue")

class DialogueManager:
    def process(self, intent: str, entities: Entities, session_data: SessionData) -> tuple[str, str]:
        """
        Process the intent given the current session state.
        Returns: (next_dialogue_state, tts_reply)
        """
        # Global Intents (can interrupt any state)
        if intent == "cancel":
            session_data.dialogue_state = "IDLE"
            session_data.context.clear()
            return "IDLE", "Đã hủy giao dịch. Bạn cần gì khác không?"
        
        if intent in ["show_menu", "check_stock", "unknown"]:
            # Keep current state, let Client controller handle the logic for these
            # Backend doesn't know stock, so it returns an empty string. Client will fill it.
            return session_data.dialogue_state, ""

        # State-based Routing
        if session_data.dialogue_state == "IDLE":
            if intent == "buy_product":
                if not entities.products:
                    session_data.dialogue_state = "WAITING_PRODUCT"
                    return "WAITING_PRODUCT", "Bạn muốn mua nước gì?"
                
                prod_names = [f"{p.quantity} {p.product}" for p in entities.products]
                reply = f"Bạn muốn mua {', '.join(prod_names)} đúng không?"
                
                session_data.context["pending_entities"] = entities.model_dump()
                session_data.dialogue_state = "CONFIRMATION"
                return "CONFIRMATION", reply

        elif session_data.dialogue_state == "WAITING_PRODUCT":
            if intent == "buy_product":
                if not entities.products:
                    return "WAITING_PRODUCT", "Bạn muốn mua nước gì?"
                
                prod_names = [f"{p.quantity} {p.product}" for p in entities.products]
                reply = f"Bạn muốn mua {', '.join(prod_names)} đúng không?"
                session_data.context["pending_entities"] = entities.model_dump()
                session_data.dialogue_state = "CONFIRMATION"
                return "CONFIRMATION", reply

        elif session_data.dialogue_state == "CONFIRMATION":
            if intent == "confirm":
                session_data.dialogue_state = "COMPLETE"
                return "COMPLETE", "" # Client will handle the success TTS
            elif intent == "buy_product":
                 # Changed mind
                 prod_names = [f"{p.quantity} {p.product}" for p in entities.products]
                 reply = f"Bạn đổi sang {', '.join(prod_names)} đúng không?"
                 session_data.context["pending_entities"] = entities.model_dump()
                 return "CONFIRMATION", reply

        # Fallback
        session_data.dialogue_state = "IDLE"
        session_data.context.clear()
        return "IDLE", "Xin lỗi, tôi chưa hiểu rõ ý bạn."
