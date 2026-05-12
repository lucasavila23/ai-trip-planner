import io
import numpy as np
import soundfile as sf
import streamlit as st
from transformers import pipeline


@st.cache_resource
def _load_whisper():
    return pipeline("automatic-speech-recognition", model="openai/whisper-small")


def transcribe(audio_bytes: bytes) -> str:
    """Transcribe raw audio bytes to text using Whisper."""
    whisper = _load_whisper()

    audio_buffer = io.BytesIO(audio_bytes)
    try:
        audio_array, sample_rate = sf.read(audio_buffer)
    except Exception:
        # Fallback: try reading as raw PCM float32 at 16kHz
        audio_array = np.frombuffer(audio_bytes, dtype=np.float32)
        sample_rate = 16000

    if audio_array.ndim > 1:
        audio_array = audio_array.mean(axis=1)

    audio_array = audio_array.astype(np.float32)

    result = whisper({"array": audio_array, "sampling_rate": sample_rate})
    return result["text"].strip()
