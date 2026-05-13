from __future__ import annotations

import asyncio
from urllib.parse import quote

from langchain_community.agent_toolkits import PlayWrightBrowserToolkit

from config import get_llm
from models.schemas import Activity, ActivityResults, TripQuery

_BOT_SIGNALS = ["just a moment", "captcha", "access denied", "verify you are human", "ddos-guard"]


async def search_activities(
    query: TripQuery,
    browser_toolkit: PlayWrightBrowserToolkit,
) -> list[Activity]:
    tools = browser_toolkit.get_tools()
    navigate = next(t for t in tools if t.name == "navigate_browser")
    extract = next(t for t in tools if t.name == "extract_text")

    dest = quote(query.destination)
    url = f"https://www.getyourguide.com/s/?q={dest}"

    await navigate.arun(url)
    await asyncio.sleep(5)
    raw_text: str = await extract.arun("")

    print("\n" + "=" * 60)
    print("[ACTIVITIES] first 500 chars:")
    print(raw_text[:500])
    print("=" * 60 + "\n")

    if not raw_text or len(raw_text) < 300 or any(s in raw_text.lower() for s in _BOT_SIGNALS):
        raise Exception("Bot detection triggered on GetYourGuide")

    structuring_llm = get_llm().with_structured_output(ActivityResults)
    structured: ActivityResults = structuring_llm.invoke(
        f"Extract activity/attraction information from the following text. "
        f"For each activity choose the most fitting category from: "
        f"culture, food, outdoor, nightlife, shopping, other. "
        f"Price and duration are optional — set to null if not mentioned.\n\n{raw_text}"
    )
    return structured.activities
