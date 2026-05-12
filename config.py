import os

from langchain_google_genai import ChatGoogleGenerativeAI

GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
LLM_MODEL: str = "gemini-2.5-flash"


def get_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=LLM_MODEL,
        google_api_key=GEMINI_API_KEY,
        temperature=0.2,
    )
