from __future__ import annotations

from urllib.parse import quote_plus

from playwright.async_api import Browser

from config import get_llm
from models.schemas import Flight, FlightResults, TripQuery
from scrapers._browser import fetch_page_text, looks_blocked, trim


async def search_flights(query: TripQuery, browser: Browser) -> list[Flight]:
    """Scrape flight options for a TripQuery and return structured Flight objects.

    Uses Kayak as the primary source — it accepts city names directly in the
    URL and renders prices server-side. Falls back to Google Flights search if
    the primary is blocked. Returns [] (not exception) on hard failure so the
    supervisor can still assemble a partial TripResults.
    """
    origin = quote_plus(query.origin)
    destination = quote_plus(query.destination)
    depart = query.check_in.strftime("%Y-%m-%d")
    ret = query.check_out.strftime("%Y-%m-%d")

    primary = (
        f"https://www.kayak.com/flights/{origin}-{destination}/{depart}/{ret}"
        f"?sort=bestflight_a"
    )
    fallback = (
        "https://www.google.com/travel/flights?hl=en&curr=EUR&q="
        + quote_plus(
            f"flights from {query.origin} to {query.destination} "
            f"on {depart} returning {ret}"
        )
    )

    raw_text = ""
    for url in (primary, fallback):
        raw_text = await fetch_page_text(
            browser,
            url,
            wait_for_selector='[class*="result"], [aria-label*="flight" i], [role="listitem"]',
            extra_wait=4.0,
        )
        print("\n" + "=" * 60)
        print(f"[FLIGHTS] {url[:70]}")
        print(f"[FLIGHTS] length={len(raw_text)} first 300: {raw_text[:300]!r}")
        print("=" * 60 + "\n")
        if not looks_blocked(raw_text):
            break

    if looks_blocked(raw_text):
        return []

    structuring_llm = get_llm().with_structured_output(FlightResults)
    try:
        structured: FlightResults = structuring_llm.invoke(
            "Extract flight options from the following raw page text and return "
            "them as structured data. Rules:\n"
            "- Convert every price to EUR (1 USD ≈ 0.92 EUR, 1 GBP ≈ 1.17 EUR). "
            "If the currency is ambiguous, assume EUR.\n"
            "- `stops` is an integer: 0 for non-stop, 1 for one stop, etc.\n"
            "- `duration` is a human string like '2h 35m'.\n"
            "- Skip rows that have no price or no airline.\n"
            "- Return at most 10 flights, cheapest first.\n\n"
            f"PAGE TEXT:\n{trim(raw_text)}"
        )
    except Exception as e:
        print(f"[FLIGHTS] structuring failed: {e!r}")
        return []

    return structured.flights[:10]
