from __future__ import annotations

import asyncio

import streamlit as st
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
from langchain_community.tools.playwright.utils import create_async_playwright_browser

from config import get_llm
from models.schemas import Flight, Hotel, Activity, TripQuery, TripResults
from scrapers.flights import search_flights
from scrapers.hotels import search_hotels
from scrapers.activities import search_activities


@st.cache_resource
def _get_browser_toolkit() -> PlayWrightBrowserToolkit:
    """Single shared Playwright browser instance cached across Streamlit reruns."""
    async_browser = create_async_playwright_browser(headless=True)
    return PlayWrightBrowserToolkit.from_browser(async_browser=async_browser)


async def run_search(query: TripQuery) -> TripResults:
    """Run all three scrapers concurrently and assemble TripResults."""
    toolkit = _get_browser_toolkit()

    flights: list[Flight] = []
    hotels: list[Hotel] = []
    activities: list[Activity] = []

    results = await asyncio.gather(
        search_flights(query, toolkit),
        search_hotels(query, toolkit),
        search_activities(query, toolkit),
        return_exceptions=True,
    )

    if not isinstance(results[0], BaseException):
        flights = results[0]
    if not isinstance(results[1], BaseException):
        hotels = results[1]
    if not isinstance(results[2], BaseException):
        activities = results[2]

    # Generate spoken summary
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
    llm = get_llm()

    flights_info = (
        f"Cheapest flight: {flights[0].airline} at €{flights[0].price_eur}"
        if flights else "No flights found."
    )
    hotels_info = (
        f"Top hotel: {hotels[0].name} at €{hotels[0].price_per_night_eur}/night"
        if hotels else "No hotels found."
    )
    activities_info = (
        f"Top activity: {activities[0].name}"
        if activities else "No activities found."
    )

    prompt = (
        f"You are a friendly travel assistant summarizing search results for a trip "
        f"from {query.origin} to {query.destination} "
        f"({query.check_in} to {query.check_out}, {query.num_people} person(s)).\n\n"
        f"Results found:\n"
        f"- Flights: {flights_info}\n"
        f"- Hotels: {hotels_info}\n"
        f"- Activities: {activities_info}\n\n"
        f"Write exactly 3 sentences summarizing the best options in a warm, spoken style. "
        f"Be specific with names and prices. Keep it under 80 words total."
    )

    response = llm.invoke(prompt)
    return response.content
