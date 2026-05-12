from __future__ import annotations

from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
from langchain.agents import create_react_agent, AgentExecutor
from langchain import hub

from config import get_llm
from models.schemas import Activity, ActivityResults, TripQuery


async def search_activities(
    query: TripQuery,
    browser_toolkit: PlayWrightBrowserToolkit,
) -> list[Activity]:
    """Stage 1: browser agent scrapes TripAdvisor. Stage 2: LLM structures results."""

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

        scrape_query = (
            f"Go to https://www.tripadvisor.com/Attractions and search for attractions "
            f"in {query.destination}. "
            f"Extract the top 5 activities or attractions including the name, "
            f"a short description, price if shown, estimated duration if shown, "
            f"and the type of activity (culture, food, outdoor, nightlife, shopping). "
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
        structuring_llm = get_llm().with_structured_output(ActivityResults)
        structured: ActivityResults = structuring_llm.invoke(
            f"Extract activity/attraction information from the following text. "
            f"For each activity choose the most fitting category from: "
            f"culture, food, outdoor, nightlife, shopping, other. "
            f"Price and duration are optional — set to null if not mentioned.\n\n{raw_text}"
        )
        return structured.activities
    except Exception:
        return []
