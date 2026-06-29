"""Tests for local voice helpers (mocked inference)."""

from unittest.mock import MagicMock, patch

from voice.meta import format_session_cost, voice_cost_usd
from voice.tts import synthesize_wav_bytes


def test_voice_cost_is_zero():
    assert voice_cost_usd() == 0.0


def test_format_session_cost_includes_voice_breakdown():
    line = format_session_cost(
        0.000012,
        model_used="qwen/qwen3-32b",
        voice_used=True,
        stt_seconds=3.5,
        tts_chars=120,
    )
    assert "cost: $0.000012" in line
    assert "voice: local" in line
    assert "$0" in line
    assert "stt 3.5s" in line
    assert "tts 120 chars" in line


@patch("voice.tts._piper_voice")
def test_synthesize_wav_bytes(mock_voice_fn):
    mock_voice = MagicMock()

    def _write(text, wav_file):
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22050)
        wav_file.writeframes(b"\x00\x00" * 100)

    mock_voice.synthesize_wav.side_effect = _write
    mock_voice_fn.return_value = mock_voice

    result = synthesize_wav_bytes("Hello Atlas")
    assert result["cost_usd"] == 0.0
    assert result["mime"] == "audio/wav"
    assert len(result["audio_bytes"]) > 44
    assert result["chars"] == 11


@patch("voice.stt._whisper_model")
def test_transcribe_file(mock_model_fn):
    from voice.stt import transcribe_file

    segment = MagicMock()
    segment.text = "  gradient descent  "
    info = MagicMock()
    info.duration = 2.5
    mock_model_fn.return_value.transcribe.return_value = ([segment], info)

    result = transcribe_file("/tmp/fake.wav")
    assert result["text"] == "gradient descent"
    assert result["cost_usd"] == 0.0
    assert result["duration_seconds"] == 2.5
