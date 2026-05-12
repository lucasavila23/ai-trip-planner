from __future__ import annotations

from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
from langchain.agents import create_react_agent
from langchain import hub

from config import get_llm
from models.schemas import Flight, FlightResults, TripQuery


async def search_flights(
    query: TripQuery,
    browser_toolkit: PlayWrightBrowserToolkit,
) -> list[Flight]:
    """Stage 1: browser agent scrapes Google Flights. Stage 2: LLM structures results."""

    tools = browser_toolkit.get_tools()
    llm = get_llm()

    # Stage 1 — browser agent extracts raw text
    try:
        prompt = hub.pull("hwchase17/react")
        agent = create_react_agent(llm=llm, tools=tools, prompt=prompt)

        from langchain.agents import AgentExecutor
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=False,
            handle_parsing_errors=True,
            max_iterations=8,
        )

        check_in_str = query.check_in.strftime("%Y-%m-%d")
        check_out_str = query.check_out.strftime("%Y-%m-%d")

        scrape_query = (
            f"Go to https://www.google.com/travel/flights and search for flights "
            f"from {query.origin} to {query.destination}, "
            f"departing {check_in_str} and returning {check_out_str}, "
            f"for {query.num_people} passenger(s). "
            f"Extract the top 5 flight results including airline name, departure time, "
            f"arrival time, flight duration, number of stops, and price in EUR. "
            f"Return the raw text of what you find."
        )

        result = await agent_executor.ainvoke({"input": scrape_query})
        raw_text: str = result.get("output", "")
    except Exception as e:
        raw_text = f"Scraping failed: {e}"

    if not raw_text or "failed" in raw_text.lower():
        return []

    # Stage 2 — structure with Pydantic
    try:
        structuring_llm = get_llm().with_structured_output(FlightResults)
        structured: FlightResults = structuring_llm.invoke(
            f"Extract flight information from the following text and return structured data. "
            f"Convert all prices to EUR (approximate if needed). "
            f"If a price currency is unclear, assume EUR.\n\n{raw_text}"
        )
        return structured.flights
    except Exception:
        return []
