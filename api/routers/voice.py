"""Local voice STT/TTS routes."""

from __future__ import annotations

import base64
import os
import tempfile

from fastapi import APIRouter, File, UploadFile

from api.schemas import SttResponse, TtsRequest, TtsResponse
from auth.deps import CurrentUser
from voice.stt import transcribe_bytes
from voice.tts import ensure_voice_model, synthesize_wav_bytes

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/tts/init")
def tts_init(user: CurrentUser):
    path = ensure_voice_model()
    return {"ok": True, "model_path": str(path)}


@router.post("/tts", response_model=TtsResponse)
def tts_synthesize(body: TtsRequest, user: CurrentUser):
    ensure_voice_model()
    result = synthesize_wav_bytes(body.text)
    return TtsResponse(
        audio_base64=base64.b64encode(result["audio_bytes"]).decode("ascii"),
        mime=result["mime"],
        chars=result["chars"],
        cost_usd=result["cost_usd"],
    )


@router.post("/stt", response_model=SttResponse)
async def stt_transcribe(user: CurrentUser, file: UploadFile = File(...)):
    suffix = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
    data = await file.read()
    result = transcribe_bytes(data, suffix=suffix)
    return SttResponse(
        text=result["text"],
        duration_seconds=result["duration_seconds"],
        model=result["model"],
        cost_usd=result["cost_usd"],
    )
