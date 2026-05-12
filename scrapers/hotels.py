from __future__ import annotations

from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
from langchain.agents import create_react_agent, AgentExecutor
from langchain import hub

from config import get_llm
from models.schemas import Hotel, HotelResults, TripQuery


async def search_hotels(
    query: TripQuery,
    browser_toolkit: PlayWrightBrowserToolkit,
) -> list[Hotel]:
    """Stage 1: browser agent scrapes Booking.com. Stage 2: LLM structures results."""

    tools = browser_toolkit.get_tools()
    llm = get_llm()

    # Stage 1 — browser agent extracts raw text
    try:
        prompt = hub.pull("hwchase17/react")
        agent = create_react_agent(llm=llm, tools=tools, prompt=prompt)
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=False,
            handle_parsing_errors=True,
            max_iterations=8,
        )

        check_in_str = query.check_in.strftime("%Y-%m-%d")
        check_out_str = query.check_out.strftime("%Y-%m-%d")
        nights = (query.check_out - query.check_in).days

        scrape_query = (
            f"Go to https://www.booking.com and search for hotels in {query.destination}, "
            f"check-in {check_in_str}, check-out {check_out_str}, "
            f"for {query.num_people} guest(s). "
            f"Extract the top 5 hotel results including hotel name, price per night, "
            f"total price for {nights} night(s), guest rating score, "
            f"and whether free cancellation is available. "
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
    except Exception:
        return []
