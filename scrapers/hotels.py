from __future__ import annotations

import asyncio
from urllib.parse import quote

from langchain_community.agent_toolkits import PlayWrightBrowserToolkit

from config import get_llm
from models.schemas import Hotel, HotelResults, TripQuery

_BOT_SIGNALS = ["just a moment", "captcha", "access denied", "verify you are human", "ddos-guard"]


async def search_hotels(
    query: TripQuery,
    browser_toolkit: PlayWrightBrowserToolkit,
) -> list[Hotel]:
    tools = browser_toolkit.get_tools()
    navigate = next(t for t in tools if t.name == "navigate_browser")
    extract = next(t for t in tools if t.name == "extract_text")

    dest = quote(query.destination)
    checkin = query.check_in.strftime("%Y-%m-%d")
    checkout = query.check_out.strftime("%Y-%m-%d")
    url = (
        f"https://www.booking.com/searchresults.html"
        f"?ss={dest}&checkin={checkin}&checkout={checkout}&group_adults={query.num_people}"
    )

    await navigate.arun(url)
    await asyncio.sleep(5)
    raw_text: str = await extract.arun("")

    print("\n" + "=" * 60)
    print("[HOTELS] first 500 chars:")
    print(raw_text[:500])
    print("=" * 60 + "\n")

    if not raw_text or len(raw_text) < 300 or any(s in raw_text.lower() for s in _BOT_SIGNALS):
        raise Exception("Bot detection triggered on Booking.com")

    nights = (query.check_out - query.check_in).days
    structuring_llm = get_llm().with_structured_output(HotelResults)
    structured: HotelResults = structuring_llm.invoke(
        f"Extract hotel information from the following text and return structured data. "
        f"The stay is for {nights} night(s). "
        f"Convert prices to EUR if needed. "
        f"Set free_cancellation to true only if explicitly mentioned. "
        f"Set rating as a float between 0-10 if available, otherwise null.\n\n{raw_text}"
    )
    return structured.hotels
