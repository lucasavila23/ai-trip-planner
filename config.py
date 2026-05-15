import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

# Load variables from a local .env file (gitignored) so the key persists
# across terminal sessions. A real `export GEMINI_API_KEY=…` still wins.
load_dotenv()

GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
LLM_MODEL: str = "gemini-2.5-flash"


def get_llm() -> ChatGoogleGenerativeAI:
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Put it in a .env file in the project "
            "root (GEMINI_API_KEY=your-key) or export it in your shell."
        )
    return ChatGoogleGenerativeAI(
        model=LLM_MODEL,
        google_api_key=GEMINI_API_KEY,
        temperature=0.2,
    )
