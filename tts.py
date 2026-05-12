import asyncio
import io

import edge_tts

VOICE = "en-US-JennyNeural"


async def speak(text: str) -> bytes:
    """Generate TTS audio bytes from text using edge-tts."""
    communicate = edge_tts.Communicate(text, VOICE)
    audio_buffer = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_buffer.write(chunk["data"])
    audio_buffer.seek(0)
    return audio_buffer.read()


def speak_sync(text: str) -> bytes:
    """Synchronous wrapper around speak()."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(speak(text))
        else:
            return loop.run_until_complete(speak(text))
    except RuntimeError:
        return asyncio.run(speak(text))
