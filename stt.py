import io
import numpy as np
import streamlit as st
from pydub import AudioSegment
from transformers import pipeline

_TARGET_SR = 16_000


@st.cache_resource
def _load_whisper():
    return pipeline("automatic-speech-recognition", model="openai/whisper-small")


def transcribe(audio_bytes: bytes) -> str:
    """Transcribe raw audio bytes to text using Whisper."""
    whisper = _load_whisper()

    segment = AudioSegment.from_file(io.BytesIO(audio_bytes))
    segment = segment.set_channels(1).set_frame_rate(_TARGET_SR)

    max_val = float(2 ** (8 * segment.sample_width - 1))
    audio_array = np.array(segment.get_array_of_samples(), dtype=np.float32) / max_val

    result = whisper({"array": audio_array, "sampling_rate": _TARGET_SR})
    return result["text"].strip()
