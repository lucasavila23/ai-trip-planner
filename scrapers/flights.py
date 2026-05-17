from __future__ import annotations

from urllib.parse import quote_plus

from playwright.async_api import Browser

from config import get_llm
from models.schemas import Flight, FlightResults, TripQuery
from scrapers._browser import fetch_page_text, looks_blocked, trim


def _has_flight_content(text: str) -> bool:
    """Reject pages that loaded but contain no actual flight data.

    Google Flights renders results very compactly (~3 000 chars total) so a
    pure length threshold doesn't work — the home/explore page and a real
    results page differ by only a few hundred chars. Instead we look for
    multiple price tokens (every result card carries one) plus a routing
    keyword. The home page typically has ≤2 prices; a results page has 5+.
    """
    if len(text) < 1_500:
        return False
    low = text.lower()
    price_hits = text.count("€") + low.count(" eur") + text.count("$") + text.count("£")
    has_routing = any(kw in low for kw in ("nonstop", "non-stop", " stop", " hr ", "round trip"))
    has_results_marker = ("results returned" in low) or ("results matching" in low)
    return has_routing and (price_hits >= 3 or has_results_marker)


async def search_flights(query: TripQuery, browser: Browser) -> list[Flight]:
    """Scrape flight options for a TripQuery and return structured Flight objects.

    Tries Google Flights first (consistently reliable with city names + EUR
    output) and falls back to Kayak. Returns `[]` rather than raising so the
    supervisor can still assemble a partial TripResults.
    """
    origin = query.origin
    destination = query.destination
    depart = query.check_in.strftime("%Y-%m-%d")
    ret = query.check_out.strftime("%Y-%m-%d")

    google_url = (
        "https://www.google.com/travel/flights?hl=en&curr=EUR&q="
        + quote_plus(
            f"flights from {origin} to {destination} on {depart} returning {ret}"
        )
    )
    kayak_url = (
        f"https://www.kayak.com/flights/{quote_plus(origin)}-{quote_plus(destination)}/"
        f"{depart}/{ret}?sort=bestflight_a"
    )

    raw_text = ""
    for label, url, wait in (
        ("google", google_url, 15.0),
        ("kayak", kayak_url, 10.0),
    ):
        raw_text = await fetch_page_text(
            browser,
            url,
            wait_for_selector='[role="listitem"], [aria-label*="flight" i], [class*="result"]',
            extra_wait=wait,
        )
        valid = (not looks_blocked(raw_text)) and _has_flight_content(raw_text)
        print("\n" + "=" * 60)
        print(f"[FLIGHTS:{label}] {url[:80]}")
        print(f"[FLIGHTS:{label}] len={len(raw_text)} valid={valid}")
        print(f"[FLIGHTS:{label}] first 200: {raw_text[:200]!r}")
        print("=" * 60 + "\n")
        if valid:
            break

    if not _has_flight_content(raw_text):
        print("[FLIGHTS] no usable content from either source")
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
