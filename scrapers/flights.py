from __future__ import annotations

import asyncio
from urllib.parse import quote

from langchain_community.agent_toolkits import PlayWrightBrowserToolkit

from config import get_llm
from models.schemas import Flight, FlightResults, TripQuery

_BOT_SIGNALS = ["just a moment", "captcha", "access denied", "verify you are human", "ddos-guard"]


async def search_flights(
    query: TripQuery,
    browser_toolkit: PlayWrightBrowserToolkit,
) -> list[Flight]:
    tools = browser_toolkit.get_tools()
    navigate = next(t for t in tools if t.name == "navigate_browser")
    extract = next(t for t in tools if t.name == "extract_text")

    origin = quote(query.origin)
    destination = quote(query.destination)
    depart = query.check_in.strftime("%Y-%m-%d")
    ret = query.check_out.strftime("%Y-%m-%d")
    url = f"https://www.kayak.com/flights/{origin}-{destination}/{depart}/{ret}"

    await navigate.arun(url)
    await asyncio.sleep(5)
    raw_text: str = await extract.arun("")

    print("\n" + "=" * 60)
    print("[FLIGHTS] first 500 chars:")
    print(raw_text[:500])
    print("=" * 60 + "\n")

    if not raw_text or len(raw_text) < 300 or any(s in raw_text.lower() for s in _BOT_SIGNALS):
        raise Exception("Bot detection triggered on Kayak")

    structuring_llm = get_llm().with_structured_output(FlightResults)
    structured: FlightResults = structuring_llm.invoke(
        f"Extract flight information from the following text and return structured data. "
        f"Convert all prices to EUR (approximate if needed). "
        f"If a price currency is unclear, assume EUR.\n\n{raw_text}"
    )
    return structured.flights
