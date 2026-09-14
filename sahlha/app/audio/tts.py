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
    try:
        from sahlha.app.config import settings
        key = settings.groq_api_key or os.getenv("GROQ_API_KEY", "")
    except Exception:
        key = os.getenv("GROQ_API_KEY", "")
    return bool(key)


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

    client = Groq(api_key=api_key)
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
    api_key = settings.groq_api_key or os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("Groq TTS needs GROQ_API_KEY (and accepted PlayAI model terms).")
    try:
        from groq import Groq  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("Groq TTS needs the 'groq' package (pip install groq).") from exc
    voice = voice or os.getenv("GROQ_TTS_VOICE", settings.groq_tts_voice)
    chunks = split_for_tts(text, settings.groq_tts_max_chars)
    try:
        wavs = [_synthesize_chunk(c, api_key=api_key, model=settings.groq_tts_model, voice=voice)
                for c in chunks]
    except Exception as exc:
        raise RuntimeError(f"Groq TTS request failed: {exc}") from exc
    return stitch_wavs(wavs), voice
