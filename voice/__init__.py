"""Local voice I/O — faster-whisper STT and Piper TTS ($0, no API keys)."""

from .meta import format_session_cost, voice_cost_usd
from .stt import transcribe_bytes, transcribe_file
from .tts import ensure_voice_model, synthesize_wav_bytes

__all__ = [
    "ensure_voice_model",
    "format_session_cost",
    "synthesize_wav_bytes",
    "transcribe_bytes",
    "transcribe_file",
    "voice_cost_usd",
]
