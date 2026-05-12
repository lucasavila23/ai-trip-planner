import asyncio

import nest_asyncio
nest_asyncio.apply()

import pandas as pd
import streamlit as st
from streamlit_mic_recorder import mic_recorder

from agents.conversation import ConversationAgent
from agents.supervisor import run_search
from models.schemas import TripQuery, TripResults
from stt import transcribe
from tts import speak_sync

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Voice Trip Planner",
    page_icon="✈️",
    layout="centered",
)

st.title("✈️ Voice Trip Planner")
st.caption("Speak to plan your trip. Hold the button below and describe where you want to go.")

# ── Session state initialisation ─────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages: list[dict] = []

if "trip_query" not in st.session_state:
    st.session_state.trip_query: TripQuery | None = None

if "trip_results" not in st.session_state:
    st.session_state.trip_results: TripResults | None = None

if "conversation_agent" not in st.session_state:
    st.session_state.conversation_agent = ConversationAgent()

if "search_done" not in st.session_state:
    st.session_state.search_done: bool = False


# ── Helper: render chat history ───────────────────────────────────────────────
def render_chat() -> None:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])


# ── Helper: add a message and optionally play TTS ────────────────────────────
def add_assistant_message(text: str, play_audio: bool = True) -> None:
    st.session_state.messages.append({"role": "assistant", "content": text})
    if play_audio:
        try:
            audio_bytes = speak_sync(text)
            st.audio(audio_bytes, format="audio/mp3", autoplay=True)
        except Exception:
            pass  # TTS failure is non-fatal


# ── Initial greeting ──────────────────────────────────────────────────────────
if not st.session_state.messages:
    greeting = (
        "Hi there! I'm your voice travel assistant. "
        "Tell me where you'd like to go and I'll help you plan the perfect trip. "
        "Where are you flying from?"
    )
    add_assistant_message(greeting, play_audio=False)

# ── Section 1: Chat panel ─────────────────────────────────────────────────────
render_chat()

if st.session_state.trip_query is None:
    st.divider()
    st.markdown("**🎤 Hold to speak:**")

    audio_data = mic_recorder(
        start_prompt="🔴 Hold to record",
        stop_prompt="⏹ Release to send",
        just_once=True,
        key="mic",
    )

    if audio_data and audio_data.get("bytes"):
        raw_bytes: bytes = audio_data["bytes"]

        with st.spinner("Transcribing…"):
            user_text = transcribe(raw_bytes)

        if user_text:
            st.session_state.messages.append({"role": "user", "content": user_text})

            with st.spinner("Thinking…"):
                reply, trip_query = st.session_state.conversation_agent.chat(user_text)

            add_assistant_message(reply)

            if trip_query is not None:
                st.session_state.trip_query = trip_query

            st.rerun()

# ── Section 2: Searching indicator + results ──────────────────────────────────
if st.session_state.trip_query is not None and not st.session_state.search_done:
    query = st.session_state.trip_query

    st.info(
        f"🗓 **Trip confirmed!** {query.origin} → {query.destination} | "
        f"{query.check_in} – {query.check_out} | {query.num_people} person(s)"
    )

    with st.spinner("🔍 Searching flights, hotels and activities…"):
        try:
            results: TripResults = asyncio.get_event_loop().run_until_complete(
                run_search(query)
            )
            st.session_state.trip_results = results
            st.session_state.search_done = True
        except Exception as e:
            st.error(f"Search failed: {e}")
            st.session_state.search_done = True

    st.rerun()

# ── Section 3: Results panel ──────────────────────────────────────────────────
if st.session_state.trip_results is not None:
    results: TripResults = st.session_state.trip_results

    st.divider()
    st.subheader("🗺 Your Trip Results")

    # Flights
    with st.expander("✈️ Flights", expanded=True):
        if results.flights:
            df_flights = pd.DataFrame([f.model_dump() for f in results.flights])
            df_flights.columns = [c.replace("_", " ").title() for c in df_flights.columns]
            st.dataframe(df_flights, use_container_width=True)
        else:
            st.info("No flight results found. Try adjusting your dates or origin.")

    # Hotels
    with st.expander("🏨 Hotels", expanded=True):
        if results.hotels:
            df_hotels = pd.DataFrame([h.model_dump() for h in results.hotels])
            df_hotels.columns = [c.replace("_", " ").title() for c in df_hotels.columns]
            st.dataframe(df_hotels, use_container_width=True)
        else:
            st.info("No hotel results found. Try a different destination or dates.")

    # Activities
    with st.expander("🎯 Activities", expanded=True):
        if results.activities:
            df_acts = pd.DataFrame([a.model_dump() for a in results.activities])
            df_acts.columns = [c.replace("_", " ").title() for c in df_acts.columns]
            st.dataframe(df_acts, use_container_width=True)
        else:
            st.info("No activity results found for this destination.")

    # Spoken summary
    if results.summary:
        st.divider()
        st.subheader("📢 Summary")
        st.write(results.summary)
        try:
            summary_audio = speak_sync(results.summary)
            st.audio(summary_audio, format="audio/mp3", autoplay=True)
        except Exception:
            pass

    # Reset button
    st.divider()
    if st.button("🔄 Plan another trip"):
        for key in ("messages", "trip_query", "trip_results", "search_done", "conversation_agent"):
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()
