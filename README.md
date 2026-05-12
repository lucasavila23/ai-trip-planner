# Voice Trip Planner

A voice-powered trip planning prototype built with Streamlit, Whisper, Gemini, and LangChain agents.

## What it does

1. **Listen** – speak into your microphone to describe your trip
2. **Converse** – a Gemini-powered assistant asks follow-up questions to collect origin, destination, dates, number of travellers, and optional budget
3. **Search** – three browser agents scrape Google Flights, Booking.com, and TripAdvisor in parallel
4. **Summarise** – results are displayed in the UI and read back to you via text-to-speech

## Tech stack

| Component | Technology |
|-----------|-----------|
| LLM | Gemini 2.5 Flash (`langchain-google-genai`) |
| Speech-to-Text | Whisper Small (HuggingFace, local) |
| Text-to-Speech | edge-tts `en-US-JennyNeural` (local) |
| Web scraping | Playwright + LangChain browser toolkit |
| Structured outputs | Pydantic + `with_structured_output` |
| UI | Streamlit + `streamlit-mic-recorder` |

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Playwright browsers

```bash
playwright install
```

### 3. Set your Gemini API key

```bash
export GEMINI_API_KEY="your-key-here"
```

Get a free key at <https://aistudio.google.com/app/apikey>.

### 4. Run the app

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`.

## Project structure

```
trip_planner/
├── app.py                  # Streamlit UI
├── config.py               # Gemini LLM factory (single source of model name)
├── stt.py                  # Whisper transcription
├── tts.py                  # edge-tts text-to-speech
├── models/
│   └── schemas.py          # Pydantic data models
├── agents/
│   ├── conversation.py     # Multi-turn trip-detail collection agent
│   └── supervisor.py       # Orchestrates parallel scraping + summary
├── scrapers/
│   ├── flights.py          # Google Flights browser agent
│   ├── hotels.py           # Booking.com browser agent
│   └── activities.py       # TripAdvisor browser agent
└── requirements.txt
```

## Notes

- Whisper and the Playwright browser are cached with `@st.cache_resource` so they load only once per session.
- All three scrapers share a single browser instance created in `supervisor.py`.
- If any individual scraper fails the others continue; an empty list is shown with a friendly message.
- The model name (`gemini-2.5-flash`) is defined in exactly one place: `config.py`.
