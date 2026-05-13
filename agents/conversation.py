from __future__ import annotations

from typing import Optional
from pydantic import BaseModel

from config import get_llm
from models.schemas import TripQuery


SYSTEM_PROMPT = """You are a friendly and knowledgeable travel assistant helping the user plan a trip.

Your job is to collect: origin city, destination, travel dates, 
number of travellers, and optional budget. But you do not need to 
collect these in a rigid order.

IMPORTANT RULES:
- If the user describes what they want (weather, culture, budget, 
  activities, region) but has not named a destination, suggest 2-3 
  specific cities that match their description. Give one sentence 
  on why each fits. Then ask them to pick one.
- If the user asks for options or comparisons, provide them. 
  Do not just repeat "please tell me your destination."
- Only ask for one missing piece of information at a time.
- Once the user has picked a destination, continue collecting 
  the remaining details naturally.
- When you have origin, destination, dates, and number of 
  travellers confirmed, summarise everything back and ask 
  for final confirmation.
- Only set confirmed=True after the user explicitly says yes 
  to the summary.
"""


class _ConversationOutput(BaseModel):
    reply: str
    trip_query: Optional[TripQuery] = None


class ConversationAgent:
    def __init__(self) -> None:
        self._messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        self._llm = get_llm()
        self._structured_llm = self._llm.with_structured_output(_ConversationOutput)

    def chat(self, user_text: str) -> tuple[str, Optional[TripQuery]]:
        """
        Send a user message, get back (reply_text, TripQuery | None).
        TripQuery is returned only when confirmed=True.
        """
        self._messages.append({"role": "user", "content": user_text})

        output: _ConversationOutput = self._structured_llm.invoke(self._messages)

        reply = output.reply
        trip_query = output.trip_query if (output.trip_query and output.trip_query.confirmed) else None

        self._messages.append({"role": "assistant", "content": reply})

        return reply, trip_query

    def reset(self) -> None:
        self._messages = [{"role": "system", "content": SYSTEM_PROMPT}]
