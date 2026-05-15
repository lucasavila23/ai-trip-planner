from __future__ import annotations

from urllib.parse import quote_plus

from playwright.async_api import Browser

from config import get_llm
from models.schemas import Hotel, HotelResults, TripQuery
from scrapers._browser import fetch_page_text, looks_blocked, trim


async def search_hotels(query: TripQuery, browser: Browser) -> list[Hotel]:
    """Scrape Booking.com for hotels matching the TripQuery."""
    dest = quote_plus(query.destination)
    checkin = query.check_in.strftime("%Y-%m-%d")
    checkout = query.check_out.strftime("%Y-%m-%d")
    nights = max((query.check_out - query.check_in).days, 1)

    primary = (
        "https://www.booking.com/searchresults.html"
        f"?ss={dest}"
        f"&checkin={checkin}&checkout={checkout}"
        f"&group_adults={query.num_people}"
        "&selected_currency=EUR"
        "&order=popularity"
    )

    raw_text = await fetch_page_text(
        browser,
        primary,
        wait_for_selector='[data-testid="property-card"], [data-testid="title"]',
        extra_wait=4.5,
    )
    print("\n" + "=" * 60)
    print(f"[HOTELS] length={len(raw_text)} first 300: {raw_text[:300]!r}")
    print("=" * 60 + "\n")

    if looks_blocked(raw_text):
        return []

    structuring_llm = get_llm().with_structured_output(HotelResults)
    try:
        structured: HotelResults = structuring_llm.invoke(
            "Extract hotel listings from the following Booking.com page text. "
            f"The stay is {nights} night(s) for {query.num_people} guest(s). "
            "Rules:\n"
            "- Prices are already in EUR on this page; do not re-convert.\n"
            "- `price_per_night_eur` = total price / nights (compute if only "
            "  total is shown).\n"
            "- `total_price_eur` = the displayed total for the whole stay.\n"
            "- `rating` is a float 0-10 if visible, otherwise null.\n"
            "- `free_cancellation` true only if the card explicitly says so.\n"
            "- Skip rows with no price.\n"
            "- Return at most 10 hotels, sorted by Booking's order.\n\n"
            f"PAGE TEXT:\n{trim(raw_text)}"
        )
    except Exception as e:
        print(f"[HOTELS] structuring failed: {e!r}")
        return []

    return structured.hotels[:10]
