from __future__ import annotations

import asyncio

import streamlit as st
from langchain_community.tools.playwright.utils import create_async_playwright_browser
from playwright.async_api import Browser

from config import get_llm
from models.schemas import Activity, Flight, Hotel, TripQuery, TripResults
from scrapers.activities import search_activities
from scrapers.flights import search_flights
from scrapers.hotels import search_hotels


@st.cache_resource
def _get_browser() -> Browser:
    """Single shared Playwright Chromium instance cached across Streamlit reruns.

    Headless=False because real-display Chrome is harder to fingerprint than
    HeadlessChrome — the stealth init script in scrapers/_browser.py covers
    the rest of the automation tells. Flip to True for server deployments.
    """
    return create_async_playwright_browser(headless=False)


async def run_search(query: TripQuery) -> TripResults:
    """Run all three scrapers concurrently and assemble TripResults.

    Each scraper returns [] on its own failure (block, timeout, structuring
    error), so a single bad site never crashes the whole search.
    """
    browser = _get_browser()

    raw = await asyncio.gather(
        search_flights(query, browser),
        search_hotels(query, browser),
        search_activities(query, browser),
        return_exceptions=True,
    )

    def _coerce(slot, label):
        if isinstance(slot, BaseException):
            print(f"[{label}] crashed: {slot!r}")
            return []
        return slot

    flights: list[Flight] = _coerce(raw[0], "FLIGHTS")
    hotels: list[Hotel] = _coerce(raw[1], "HOTELS")
    activities: list[Activity] = _coerce(raw[2], "ACTIVITIES")

    summary = _generate_summary(query, flights, hotels, activities)

    return TripResults(
        query=query,
        flights=flights,
        hotels=hotels,
        activities=activities,
        summary=summary,
    )


def _generate_summary(
    query: TripQuery,
    flights: list[Flight],
    hotels: list[Hotel],
    activities: list[Activity],
) -> str:
    flights_info = (
        f"Cheapest flight: {flights[0].airline} at €{flights[0].price_eur:.0f}"
        if flights
        else "No flights found."
    )
    hotels_info = (
        f"Top hotel: {hotels[0].name} at €{hotels[0].price_per_night_eur:.0f}/night"
        if hotels
        else "No hotels found."
    )
    activities_info = (
        f"Top activity: {activities[0].name}" if activities else "No activities found."
    )

    prompt = (
        "You are a friendly travel assistant summarising search results for a trip "
        f"from {query.origin} to {query.destination} "
        f"({query.check_in} to {query.check_out}, {query.num_people} person(s)).\n\n"
        "Results:\n"
        f"- Flights: {flights_info}\n"
        f"- Hotels: {hotels_info}\n"
        f"- Activities: {activities_info}\n\n"
        "Write exactly 3 sentences summarising the best options in a warm, spoken "
        "style. Be specific with names and prices. Keep it under 80 words total. "
        "If a category has no results, acknowledge it briefly and move on."
    )

    try:
        response = get_llm().invoke(prompt)
        return response.content
    except Exception as e:
        print(f"[SUMMARY] generation failed: {e!r}")
        return (
            f"Here's what I found for your trip from {query.origin} to "
            f"{query.destination}: {flights_info} {hotels_info} {activities_info}"
        )
