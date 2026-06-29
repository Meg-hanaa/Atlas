"""Text-to-speech via local Piper (piper-tts 1.4.x)."""

from __future__ import annotations

import io
import logging
import os
import subprocess
import sys
import wave
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VOICE_DIR = os.path.join(ROOT, "data", "piper_voices")
DEFAULT_VOICE = os.getenv("ATLAS_PIPER_VOICE", "en_US-lessac-medium")


def voice_model_path(voice_name: str | None = None) -> Path:
    name = voice_name or DEFAULT_VOICE
    return Path(VOICE_DIR) / f"{name}.onnx"


def ensure_voice_model(voice_name: str | None = None) -> Path:
    """Download Piper voice if missing. Uses `python -m piper.download_voices`."""
    path = voice_model_path(voice_name)
    if path.is_file():
        return path
    name = voice_name or DEFAULT_VOICE
    os.makedirs(VOICE_DIR, exist_ok=True)
    logger.info("Downloading Piper voice %s to %s", name, VOICE_DIR)
    subprocess.run(
        [sys.executable, "-m", "piper.download_voices", name, "--data-dir", VOICE_DIR],
        check=True,
        capture_output=True,
        text=True,
    )
    if not path.is_file():
        raise FileNotFoundError(f"Piper voice not found after download: {path}")
    return path


@lru_cache(maxsize=1)
def _piper_voice():
    from piper import PiperVoice

    model_path = ensure_voice_model()
    return PiperVoice.load(str(model_path))


def synthesize_wav_bytes(text: str) -> dict:
    """Synthesize speech to WAV bytes. Returns audio bytes and metadata."""
    if not text.strip():
        raise ValueError("Cannot synthesize empty text")
    voice = _piper_voice()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        voice.synthesize_wav(text.strip(), wav_file)
    audio = buf.getvalue()
    return {
        "audio_bytes": audio,
        "mime": "audio/wav",
        "chars": len(text.strip()),
        "model": f"piper/{DEFAULT_VOICE}",
        "cost_usd": 0.0,
    }
