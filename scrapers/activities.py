from __future__ import annotations

from urllib.parse import quote_plus

from playwright.async_api import Browser

from config import get_llm
from models.schemas import Activity, ActivityResults, TripQuery
from scrapers._browser import fetch_page_text, looks_blocked, trim


async def search_activities(query: TripQuery, browser: Browser) -> list[Activity]:
    """Scrape attractions/activities for the destination."""
    dest_q = quote_plus(query.destination)

    primary = f"https://www.getyourguide.com/s/?q={dest_q}&currency=EUR"
    fallback = f"https://www.tripadvisor.com/Search?q={dest_q}+things+to+do"

    raw_text = ""
    for url in (primary, fallback):
        raw_text = await fetch_page_text(
            browser,
            url,
            wait_for_selector='[data-test-id*="activity"], article, [class*="card" i]',
            extra_wait=4.0,
        )
        print("\n" + "=" * 60)
        print(f"[ACTIVITIES] {url[:70]}")
        print(f"[ACTIVITIES] length={len(raw_text)} first 300: {raw_text[:300]!r}")
        print("=" * 60 + "\n")
        if not looks_blocked(raw_text):
            break

    if looks_blocked(raw_text):
        return []

    structuring_llm = get_llm().with_structured_output(ActivityResults)
    try:
        structured: ActivityResults = structuring_llm.invoke(
            "Extract activities / attractions from the following page text. "
            "Rules:\n"
            "- `category` MUST be one of: culture, food, outdoor, nightlife, "
            "  shopping, other. Pick the best fit.\n"
            "- `price_eur` and `duration` are optional — set to null if not "
            "  visible.\n"
            "- `description` is a one-sentence summary derived from the page.\n"
            "- Skip rows that are clearly navigation links, not activities.\n"
            "- Return at most 10 activities.\n\n"
            f"PAGE TEXT:\n{trim(raw_text)}"
        )
    except Exception as e:
        print(f"[ACTIVITIES] structuring failed: {e!r}")
        return []

    return structured.activities[:10]
