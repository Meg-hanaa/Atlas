"""Cost helpers for local voice — always $0, tracked separately from cascadeflow."""

from __future__ import annotations

VOICE_PROVIDER_LABEL = "local (faster-whisper + piper)"


def voice_cost_usd(*_args, **_kwargs) -> float:
    """Local inference has no metered cost."""
    return 0.0


def format_session_cost(
    llm_cost: float,
    *,
    model_used: str,
    recall_strength: float | None = None,
    voice_used: bool = False,
    stt_seconds: float | None = None,
    tts_chars: int | None = None,
) -> str:
    """Unified session cost line: LLM + local voice breakdown."""
    total = llm_cost + voice_cost_usd()
    parts = [f"model: {model_used}", f"cost: ${total:.6f}"]
    if voice_used:
        detail = VOICE_PROVIDER_LABEL
        extras = []
        if stt_seconds is not None:
            extras.append(f"stt {stt_seconds:.1f}s")
        if tts_chars is not None:
            extras.append(f"tts {tts_chars} chars")
        if extras:
            detail = f"{detail}, {', '.join(extras)}"
        parts.append(f"voice: {detail} ($0)")
    if recall_strength is not None:
        parts.append(f"recall_strength: {recall_strength:.2f}")
    return " · ".join(parts)
