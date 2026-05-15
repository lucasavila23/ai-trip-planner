# Voice Trip Planner

A voice-powered trip planning prototype built for the IE University AI/ML course final project. The user speaks naturally to describe a trip; the app transcribes the audio, holds a multi-turn conversation to collect all necessary details, then scrapes real-time flights, hotels, and activities in parallel, and reads the results back aloud.

---

## Demo flow

```
User speaks → Whisper transcribes → Gemini converses →
  (confirmed) → 3 Playwright scrapers run concurrently →
    Pydantic structures each result → Gemini writes summary →
      UI renders tables + plays TTS audio
```

---

## Quick start

### 1. Clone and enter the project

```bash
git clone https://github.com/lucasavila23/ai-trip-planner.git
cd ai-trip-planner
```

### 2. Create and activate the virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate      # macOS / Linux
# .venv\Scripts\activate       # Windows
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Install the Playwright browser

```bash
playwright install chromium
```

### 5. Set your Gemini API key

```bash
export GEMINI_API_KEY="your-key-here"
```

Get a free key at <https://aistudio.google.com/app/apikey>. The free tier is enough to run the app.

### 6. Run

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`.

---

## Project structure

```
trip_planner/
│
├── app.py                   # Streamlit entry point — UI logic and state
├── config.py                # LLM factory (single source of model name + API key)
│
├── stt.py                   # Speech-to-Text: Whisper Small via HuggingFace pipeline
├── tts.py                   # Text-to-Speech: edge-tts with Jenny Neural voice
│
├── models/
│   └── schemas.py           # All Pydantic models shared across the codebase
│
├── agents/
│   ├── conversation.py      # Stateful multi-turn ConversationAgent (collects trip details)
│   └── supervisor.py        # Orchestrates parallel scraping + generates spoken summary
│
├── scrapers/
│   ├── _browser.py          # Shared stealth Playwright helper (UA, headers, anti-bot init script)
│   ├── flights.py           # Two-stage scraper: stealth fetch → Gemini structure → FlightResults
│   ├── hotels.py            # Two-stage scraper: stealth fetch → Gemini structure → HotelResults
│   └── activities.py        # Two-stage scraper: stealth fetch → Gemini structure → ActivityResults
│
├── requirements.txt         # Direct dependencies (unpinned)
├── requirements.lock.txt    # Exact pinned versions from the working venv
└── README.md
```

---

## Architecture

### Overview diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Streamlit UI (app.py)                   │
│                                                                  │
│  [mic_recorder] ──► stt.transcribe() ──► ConversationAgent      │
│                                               │                  │
│                                    (TripQuery confirmed?)        │
│                                               │ yes              │
│                                    supervisor.run_search()       │
│                                    ┌──────────┴──────────┐      │
│                            search_flights  search_hotels  search_activities
│                                    └──────────┬──────────┘      │
│                                         TripResults              │
│                                               │                  │
│                               st.dataframe ◄──┘                  │
│                               tts.speak_sync() → st.audio()     │
└─────────────────────────────────────────────────────────────────┘
```

### Layer 1 — Data models (`models/schemas.py`)

All data contracts live in a single file. Every scraper, agent, and UI component imports from here — nothing defines its own schema inline.

| Model | Purpose |
|---|---|
| `TripQuery` | Collected trip intent: origin, destination, dates, people, budget, confirmed flag |
| `Flight` | Single flight option |
| `FlightResults` | Wrapper list used with `with_structured_output` |
| `Hotel` | Single hotel option with cancellation info |
| `HotelResults` | Wrapper list |
| `Activity` | Attraction with a fixed Literal category enum |
| `ActivityResults` | Wrapper list |
| `TripResults` | Final assembled result: query + all three lists + summary text |

### Layer 2 — STT / TTS (`stt.py`, `tts.py`)

**Speech-to-Text** runs Whisper Small entirely locally. The HuggingFace pipeline is wrapped in `@st.cache_resource` so it loads once and stays hot across Streamlit reruns. Raw audio bytes from the mic recorder are read with `soundfile`, averaged to mono, cast to `float32`, and fed to Whisper.

**Text-to-Speech** uses `edge-tts` (Microsoft's free neural TTS, no API key). The async `speak()` coroutine is wrapped in `speak_sync()` which handles the `nest_asyncio` + running event loop edge case that Streamlit creates. Returns raw MP3 bytes that Streamlit plays directly with `st.audio(autoplay=True)`.

### Layer 3 — Conversation agent (`agents/conversation.py`)

`ConversationAgent` keeps a `messages` list and appends every turn (user + assistant). Each call invokes the LLM with `with_structured_output(_ConversationOutput)`, a small wrapper schema that holds:

- `reply: str` — the text to show the user
- `trip_query: Optional[TripQuery]` — only populated once the LLM has all details and `confirmed=True`

The system prompt instructs the model to ask one question at a time and only set `confirmed=True` when the user explicitly agrees to a summary. This avoids premature confirmation from partial answers.

### Layer 4 — Scrapers (`scrapers/`)

Each scraper follows the **two-stage pattern** from the course cheatsheet (S26.3):

**Stage 1 — Stealth Playwright fetch (raw text)**

A shared `scrapers/_browser.py` helper opens a fresh `BrowserContext` per scrape with anti-bot countermeasures: a real desktop user-agent, `Accept-Language` / `Sec-Ch-Ua` headers, and an init script that masks `navigator.webdriver`, fakes `navigator.plugins`, and shims `window.chrome`. The page is loaded with `wait_until=domcontentloaded`, then waits for a result selector, then for `networkidle`, then scrolls to trigger lazy-loaded cards before returning `inner_text("body")`. The result is trimmed (head + tail, 20k chars max) before being sent to the LLM.

If the rendered text matches a known bot-wall signal (`captcha`, `verify you are human`, `unusual traffic`, …) or is shorter than 300 chars, the scraper switches to a fallback URL (where one is defined) and on second failure returns `[]`.

**Stage 2 — Structured output (typed objects)**

The raw text is passed to `get_llm().with_structured_output(XxxResults)`, which guarantees a validated Pydantic object. Stage 2 is wrapped in try/except and returns `[]` if the LLM call fails, so a single bad page never crashes the whole search.

| Scraper | Primary target | Fallback | Pydantic schema |
|---|---|---|---|
| `flights.py` | kayak.com | google.com/travel/flights | `FlightResults` |
| `hotels.py` | booking.com | — | `HotelResults` |
| `activities.py` | getyourguide.com | tripadvisor.com | `ActivityResults` |

### Layer 5 — Supervisor (`agents/supervisor.py`)

`run_search()` fires all three scrapers concurrently with `asyncio.gather(..., return_exceptions=True)`. Individual failures are caught per-result — a `BaseException` instance means that scraper crashed, and its slot becomes an empty list. The rest continue normally. Scrapers also already handle their own soft failures (blocked, structuring error) by returning `[]` directly.

After gathering, a final Gemini call generates a 3-sentence spoken summary highlighting the best option from each category. If the summary call itself fails, a deterministic fallback string is used so the UI always has something to render and read aloud.

The Playwright browser is created once via `@st.cache_resource` in `supervisor.py` and passed to each scraper call. All three scrapers share the same browser process but open their own isolated `BrowserContext` per scrape, so cookies and stealth state don't bleed across sites.

### Layer 6 — UI (`app.py`)

Three logical sections driven by `st.session_state`:

| State | Section shown |
|---|---|
| No `trip_query` | Chat panel + mic recorder |
| `trip_query` set, not yet searched | Spinner while `run_search` executes |
| `trip_results` set | Three expanders with dataframes + summary audio |

`nest_asyncio.apply()` is called at the very top of `app.py` (before any imports that touch asyncio) because Streamlit runs its own event loop and `asyncio.gather` would otherwise deadlock.

---

## Technology choices and rationale

### LLM — Gemini 2.5 Flash

Chosen for its long context window (1M tokens), which is important for scraper output that can be verbose, and its structured output support via LangChain's `with_structured_output`. Flash tier is fast enough for interactive use and free via AI Studio. The model name is defined in exactly one place (`config.py`) so swapping to a different model requires a single edit.

### STT — Whisper Small (local)

Running Whisper locally avoids latency from a round-trip API call and eliminates the need for a second API key. The "small" checkpoint (244M parameters) fits easily in CPU RAM and transcribes a short voice clip in under 2 seconds on modern hardware. `@st.cache_resource` ensures the model loads once per session.

### TTS — edge-tts (local)

Microsoft's `edge-tts` library streams neural TTS audio without an API key by calling the same endpoint the Edge browser uses. `en-US-JennyNeural` is a natural-sounding conversational voice. Audio bytes are returned directly to Streamlit's `st.audio` component, which supports `autoplay=True` for a hands-free experience.

### Web scraping — Playwright (direct) with stealth context

Structured scraping APIs (e.g. dedicated flight APIs) either require paid keys or have strict rate limits. Playwright gives a real browser that handles JavaScript rendering, cookie banners, and dynamic content. We use Playwright's async API directly rather than the LangChain `PlayWrightBrowserToolkit` — the toolkit adds a ReAct loop on top of `page.goto` + `page.inner_text`, which is overhead without benefit when the URL is deterministic.

A single shared `Browser` instance (cached in `supervisor.py` via `@st.cache_resource`) is reused across all three scrapers; each scrape opens its own `BrowserContext` with a randomised desktop user-agent, locale, and a `navigator.webdriver`-masking init script. This keeps the three sites isolated from each other while still amortising the browser launch cost.

### Structured outputs — Pydantic `with_structured_output`

Using `llm.with_structured_output(Schema)` guarantees that every field has the correct Python type (e.g. `price_eur: float`, not a string like `"€199"`). The LLM is also given conversion instructions ("convert to EUR if needed") in the stage-2 prompt, so currency mismatches are handled at the structuring step rather than in post-processing code.

### Orchestration — `asyncio.gather` (no agent framework for parallelism)

The three scrapers are independent and have no shared state, making `asyncio.gather` the right tool: simpler, more transparent, and faster than a LangGraph workflow for this use case. A full multi-agent framework would add indirection without benefit here.

### UI — Streamlit

Streamlit's session state model maps naturally to the app's three phases (conversation → loading → results). `streamlit-mic-recorder` provides a push-to-talk button that works directly in the browser without requiring OS-level microphone permissions setup.

---

## Environment details

- **Python**: 3.12
- **Virtual env**: `.venv/` (standard `venv`, not conda)
- **Pinned versions**: `requirements.lock.txt` (generated from the working install)
- **Playwright browser**: Chromium (headless)

---

## Common issues

| Issue | Fix |
|---|---|
| `GEMINI_API_KEY not set` | `export GEMINI_API_KEY="..."` before running |
| `playwright install` not run | Run `playwright install chromium` inside the venv |
| Mic not working in browser | Allow microphone access when the browser prompts |
| `soundfile` read error on audio | Some browser mic encodings need `ffmpeg`; install with `brew install ffmpeg` |
| Scraper returns empty list | The target site may have changed layout — the LLM still extracts what it can |
| Streamlit rerun clears spinner | This is expected; state is preserved in `st.session_state` |
