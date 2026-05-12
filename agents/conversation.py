from __future__ import annotations

from typing import Optional
from pydantic import BaseModel

from config import get_llm
from models.schemas import TripQuery


SYSTEM_PROMPT = """You are a friendly travel assistant. Your only job is to collect
the following details from the user to plan their trip:
1. Origin city (where they are flying from)
2. Destination city or country
3. Check-in / departure date
4. Check-out / return date
5. Number of travellers
6. Optional: budget in EUR

Ask one question at a time. Be warm and concise. Once you have all required details
(origin, destination, check-in, check-out, num_people), confirm them back to the user
in a single clear summary message and ask if everything looks correct.

Only set confirmed=True in the structured response when the user explicitly agrees
(e.g., "yes", "that's correct", "looks good", "confirm", "perfect").
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
