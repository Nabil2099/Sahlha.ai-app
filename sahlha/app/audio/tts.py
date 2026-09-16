"""Groq text-to-speech provider (Orpheus English voices).

Interface: `synthesize(text, voice=None) -> bytes` (single WAV).
Long text is split sentence-aware and stitched. Swappable behind this module.
"""
from __future__ import annotations

import io
import os
import re
import wave


def tts_available() -> bool:
    from sahlha.app.config import settings
    return bool(settings.groq_api_key.strip() or (settings.openrouter_api_key.strip() and settings.openrouter_tts_model))


def split_for_tts(text: str, max_chars: int = 900) -> list[str]:
    """Sentence-aware splitter (pure — unit tested)."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    chunks, current = [], ""
    for s in sentences:
        if len(s) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            for i in range(0, len(s), max_chars):  # hard-split overlong sentence
                chunks.append(s[i:i + max_chars])
        elif len(current) + len(s) + 1 <= max_chars:
            current = f"{current} {s}".strip()
        else:
            chunks.append(current)
            current = s
    if current:
        chunks.append(current)
    return chunks or [text[:max_chars]]


def stitch_wavs(wavs: list[bytes]) -> bytes:
    """Concatenate WAV blobs with identical params into one WAV (pure — unit tested)."""
    if len(wavs) == 1:
        return wavs[0]
    readers = [wave.open(io.BytesIO(w), "rb") for w in wavs]
    params = readers[0].getparams()
    for r in readers[1:]:
        if (r.getnchannels(), r.getsampwidth(), r.getframerate()) != \
           (params.nchannels, params.sampwidth, params.framerate):
            raise ValueError("TTS chunks have mismatched audio params; cannot stitch")
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(params.nchannels)
        w.setsampwidth(params.sampwidth)
        w.setframerate(params.framerate)
        for r in readers:
            w.writeframes(r.readframes(r.getnframes()))
    return out.getvalue()


def _synthesize_chunk(text: str, *, api_key: str, model: str, voice: str) -> bytes:
    from groq import Groq

    from sahlha.app.config import settings
    client = Groq(api_key=api_key, max_retries=0, timeout=settings.provider_timeout_seconds)
    resp = client.audio.speech.create(model=model, voice=voice, input=text,
                                      response_format="wav")
    data = resp.read()
    if not data:
        raise RuntimeError("Groq TTS returned empty audio")
    return data


def synthesize(text: str, voice: str | None = None) -> tuple[bytes, str]:
    """Returns (wav_bytes, voice_used). Raises RuntimeError when unusable."""
    from sahlha.app.config import settings

    text = (text or "").strip()
    if not text:
        raise ValueError("Nothing to synthesize: empty text")
    primary_voice = (voice or settings.groq_tts_voice).strip()
    chunks = split_for_tts(text, settings.groq_tts_max_chars)
    from sahlha.app.agent.providers import retryable_provider_error
    if settings.groq_api_key.strip():
        try:
            wavs = [_synthesize_chunk(c, api_key=settings.groq_api_key.strip(),
                    model=settings.groq_tts_model, voice=primary_voice) for c in chunks]
            result = stitch_wavs(wavs)
            if not valid_wav(result):
                raise RuntimeError("Invalid provider audio")
            return result, primary_voice
        except Exception as exc:
            if not retryable_provider_error(exc):
                raise RuntimeError("Audio is unavailable: primary speech configuration or response error") from exc
    if settings.openrouter_api_key.strip() and settings.openrouter_tts_model:
        try:
            # Regenerate the entire recording with one provider/voice, never mix formats.
            backup_voice = settings.openrouter_tts_voice
            result = stitch_wavs([_openrouter_chunk(c, backup_voice) for c in chunks])
            if not valid_wav(result):
                raise RuntimeError("Invalid backup audio")
            return result, backup_voice
        except Exception as exc:
            raise RuntimeError("Audio is unavailable right now.") from exc
    raise RuntimeError("Audio requires GROQ_API_KEY or configured OpenRouter speech")


def valid_wav(data: bytes) -> bool:
    try:
        with wave.open(io.BytesIO(data), "rb") as stream:
            return stream.getnframes() > 0 and bool(stream.readframes(1))
    except (EOFError, wave.Error, OSError):
        return False


def _openrouter_chunk(text: str, voice: str) -> bytes:
    from openai import OpenAI
    from sahlha.app.config import settings
    with OpenAI(api_key=settings.openrouter_api_key.strip(), base_url=settings.openrouter_base_url,
                max_retries=0, timeout=settings.provider_timeout_seconds) as client:
        response = client.audio.speech.create(model=settings.openrouter_tts_model, voice=voice,
                    input=text, response_format=settings.openrouter_tts_format)
        data = response.read()
    if settings.openrouter_tts_format == "pcm":
        if not data or len(data) % 2:
            raise RuntimeError("Invalid PCM response")
        out = io.BytesIO()
        with wave.open(out, "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(settings.openrouter_tts_sample_rate)
            stream.writeframes(data)
        return out.getvalue()
    if settings.openrouter_tts_format == "mp3":
        # Optional system ffmpeg converts compressed output to the existing WAV contract.
        import shutil
        import subprocess
        executable = shutil.which("ffmpeg")
        if not executable:
            raise RuntimeError("MP3 speech needs ffmpeg or configure PCM speech")
        result = subprocess.run([executable, "-v", "error", "-i", "pipe:0", "-f", "wav", "-ac", "1",
                                 "-ar", str(settings.openrouter_tts_sample_rate), "pipe:1"],
                                input=data, capture_output=True, timeout=settings.provider_timeout_seconds, check=True)
        return result.stdout
    raise ValueError("Unsupported OpenRouter speech format")
